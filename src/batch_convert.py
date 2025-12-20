"""Batch conversion utilities for physiological and eyetracking data.

This module provides utilities for batch converting raw data files from a flat folder
structure into PRISM/BIDS-style datasets. The input files must follow the naming convention:

    sub-<id>_ses-<id>_task-<id>.<ext>

Example:
    sub-003_ses-1_task-rest.raw     → physio data
    sub-003_ses-1_task-find.edf     → eyetracking data

Supported formats:
- Physio: .raw, .vpd (Varioport devices) → converted to .edf + .json
- Eyetracking: .edf (SR Research EyeLink) → copied + .json sidecar generated
"""

from __future__ import annotations

import json
import re
import shutil
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal, Callable

# Pattern for BIDS-like filenames: sub-XXX_ses-YYY_task-ZZZ[_extra].<ext>
BIDS_FILENAME_PATTERN = re.compile(
    r"^(?P<sub>sub-[a-zA-Z0-9]+)"
    r"(?:_(?P<ses>ses-[a-zA-Z0-9]+))?"
    r"_(?P<task>task-[a-zA-Z0-9]+)"
    r"(?P<extra>(?:_[a-zA-Z0-9]+-[a-zA-Z0-9]+)*)"
    r"\.(?P<ext>raw|vpd|edf)$",
    re.IGNORECASE,
)

# Modality detection by extension
PHYSIO_EXTENSIONS = {".raw", ".vpd"}
EYETRACKING_EXTENSIONS = {".edf"}


@dataclass
class ConvertedFile:
    """Result of converting a single file."""

    source_path: Path
    output_files: list[Path]
    modality: Literal["physio", "eyetracking"]
    subject: str
    session: str | None
    task: str
    success: bool
    error: str | None = None


@dataclass
class BatchConvertResult:
    """Result of batch conversion."""

    source_folder: Path
    output_folder: Path
    converted: list[ConvertedFile] = field(default_factory=list)
    skipped: list[tuple[Path, str]] = field(default_factory=list)  # (path, reason)

    @property
    def success_count(self) -> int:
        return sum(1 for f in self.converted if f.success)

    @property
    def error_count(self) -> int:
        return sum(1 for f in self.converted if not f.success)


def parse_bids_filename(filename: str) -> dict | None:
    """Parse a BIDS-like filename into its components.

    Args:
        filename: The filename to parse (e.g., "sub-003_ses-1_task-rest.raw")

    Returns:
        Dictionary with keys: sub, ses, task, extra, ext, or None if invalid
    """
    match = BIDS_FILENAME_PATTERN.match(filename)
    if not match:
        return None

    return {
        "sub": match.group("sub"),
        "ses": match.group("ses"),
        "task": match.group("task"),
        "extra": match.group("extra") or "",
        "ext": match.group("ext").lower(),
    }


def detect_modality(ext: str) -> Literal["physio", "eyetracking"] | None:
    """Detect the modality based on file extension."""
    ext_lower = ext.lower() if not ext.startswith(".") else ext.lower()
    if not ext_lower.startswith("."):
        ext_lower = f".{ext_lower}"

    if ext_lower in PHYSIO_EXTENSIONS:
        return "physio"
    elif ext_lower in EYETRACKING_EXTENSIONS:
        return "eyetracking"
    return None


def _create_physio_sidecar(
    source_path: Path,
    output_json: Path,
    *,
    task_name: str,
    sampling_rate: float | None = None,
    recording_label: str = "ecg",
) -> None:
    """Create a PRISM-compliant JSON sidecar for physio data."""
    sidecar = {
        "Technical": {
            "SamplingRate": sampling_rate or "unknown",
            "RecordingDuration": "unknown",
            "SourceFormat": source_path.suffix.lower().lstrip("."),
        },
        "Study": {
            "TaskName": task_name.replace("task-", ""),
        },
        "Metadata": {
            "SourceFile": source_path.name,
            "ConvertedFrom": "Varioport",
        },
        "Columns": {
            "time": {"Description": "Time in seconds", "Units": "s"},
        },
    }

    with open(output_json, "w", encoding="utf-8") as f:
        json.dump(sidecar, f, indent=2, ensure_ascii=False)


def _create_eyetracking_sidecar(
    source_path: Path,
    output_json: Path,
    *,
    task_name: str,
) -> None:
    """Create a PRISM-compliant JSON sidecar for eyetracking data."""
    sidecar = {
        "Technical": {
            "SamplingRate": "unknown",  # Would need to read EDF header
            "Manufacturer": "SR Research",
            "DeviceSerialNumber": "unknown",
            "EyeTrackingMethod": "video-based",
            "RecordedEye": "unknown",
        },
        "Study": {
            "TaskName": task_name.replace("task-", ""),
        },
        "Metadata": {
            "SourceFile": source_path.name,
        },
        "ScreenDistance": "unknown",
        "ScreenSize": "unknown",
    }

    with open(output_json, "w", encoding="utf-8") as f:
        json.dump(sidecar, f, indent=2, ensure_ascii=False)


def convert_physio_file(
    source_path: Path,
    output_dir: Path,
    *,
    parsed: dict,
    base_freq: float | None = None,
) -> ConvertedFile:
    """Convert a single physio file (Varioport .raw/.vpd) to PRISM format.

    This uses the existing convert_varioport function if available, otherwise
    just copies the file and creates a sidecar.
    """
    sub = parsed["sub"]
    ses = parsed["ses"]
    task = parsed["task"]
    ext = parsed["ext"]

    # Build output path: output_dir/sub-XXX/[ses-YYY/]physio/
    if ses:
        out_folder = output_dir / sub / ses / "physio"
    else:
        out_folder = output_dir / sub / "physio"
    out_folder.mkdir(parents=True, exist_ok=True)

    # Recording label based on source format
    rec_label = "vpd" if ext == "vpd" else "raw"

    # Build BIDS filename
    parts = [sub]
    if ses:
        parts.append(ses)
    parts.append(task)
    parts.append(f"recording-{rec_label}")
    parts.append("physio")
    base_name = "_".join(parts)

    output_files = []

    try:
        # Try to use the Varioport converter
        try:
            from helpers.physio.convert_varioport import convert_varioport

            out_edf = out_folder / f"{base_name}.edf"
            out_json = out_folder / f"{base_name}.json"

            convert_varioport(
                str(source_path),
                str(out_edf),
                str(out_json),
                task_name=task.replace("task-", ""),
                base_freq=base_freq,
            )

            if out_edf.exists():
                output_files.append(out_edf)
            if out_json.exists():
                output_files.append(out_json)

        except ImportError:
            # Fallback: just copy file and create minimal sidecar
            out_data = out_folder / f"{base_name}.{ext}"
            out_json = out_folder / f"{base_name}.json"

            shutil.copy2(source_path, out_data)
            _create_physio_sidecar(
                source_path,
                out_json,
                task_name=task,
                sampling_rate=base_freq,
            )

            output_files.extend([out_data, out_json])

        return ConvertedFile(
            source_path=source_path,
            output_files=output_files,
            modality="physio",
            subject=sub,
            session=ses,
            task=task,
            success=True,
        )

    except Exception as e:
        return ConvertedFile(
            source_path=source_path,
            output_files=[],
            modality="physio",
            subject=sub,
            session=ses,
            task=task,
            success=False,
            error=str(e),
        )


def convert_eyetracking_file(
    source_path: Path,
    output_dir: Path,
    *,
    parsed: dict,
) -> ConvertedFile:
    """Convert a single eyetracking file (.edf) to PRISM format.

    For EyeLink .edf files, we copy the file (it's already a standard format)
    and create a JSON sidecar with metadata.
    """
    sub = parsed["sub"]
    ses = parsed["ses"]
    task = parsed["task"]

    # Build output path: output_dir/sub-XXX/[ses-YYY/]eyetracking/
    if ses:
        out_folder = output_dir / sub / ses / "eyetracking"
    else:
        out_folder = output_dir / sub / "eyetracking"
    out_folder.mkdir(parents=True, exist_ok=True)

    # Build BIDS filename
    parts = [sub]
    if ses:
        parts.append(ses)
    parts.append(task)
    parts.append("eyetrack")
    base_name = "_".join(parts)

    out_edf = out_folder / f"{base_name}.edf"
    out_json = out_folder / f"{base_name}.json"

    output_files = []

    try:
        # Copy the EDF file
        shutil.copy2(source_path, out_edf)
        output_files.append(out_edf)

        # Create sidecar
        _create_eyetracking_sidecar(source_path, out_json, task_name=task)
        output_files.append(out_json)

        # TODO: In future, we could parse the EDF header to extract:
        # - Sampling rate
        # - Recorded eye (left/right/both)
        # - Recording duration
        # - Screen settings

        return ConvertedFile(
            source_path=source_path,
            output_files=output_files,
            modality="eyetracking",
            subject=sub,
            session=ses,
            task=task,
            success=True,
        )

    except Exception as e:
        return ConvertedFile(
            source_path=source_path,
            output_files=[],
            modality="eyetracking",
            subject=sub,
            session=ses,
            task=task,
            success=False,
            error=str(e),
        )


def batch_convert_folder(
    source_folder: Path | str,
    output_folder: Path | str,
    *,
    physio_sampling_rate: float | None = None,
    modality_filter: Literal["all", "physio", "eyetracking"] = "all",
    log_callback: Callable | None = None,
) -> BatchConvertResult:
    """Batch convert all supported files from a flat folder structure.

    Args:
        source_folder: Path to folder containing raw data files
        output_folder: Path to output PRISM dataset folder
        physio_sampling_rate: Optional sampling rate override for physio files
        modality_filter: Which modalities to process ("all", "physio", or "eyetracking")
        log_callback: Optional callback for logging messages: log_callback(message, level)
                      where level is "info", "success", "warning", or "error"

    Returns:
        BatchConvertResult with details of all conversions
    """

    def log(msg: str, level: str = "info"):
        if log_callback:
            log_callback(msg, level)

    source_folder = Path(source_folder)
    output_folder = Path(output_folder)

    result = BatchConvertResult(
        source_folder=source_folder,
        output_folder=output_folder,
    )

    log(f"📂 Scanning source folder: {source_folder.name}", "info")

    # Find all supported files
    all_extensions = set()
    if modality_filter in ("all", "physio"):
        all_extensions.update(PHYSIO_EXTENSIONS)
    if modality_filter in ("all", "eyetracking"):
        all_extensions.update(EYETRACKING_EXTENSIONS)

    # Collect files first to get total count
    files_to_process = []
    for file_path in sorted(source_folder.iterdir()):
        if not file_path.is_file():
            continue
        ext = file_path.suffix.lower()
        if ext in all_extensions:
            files_to_process.append(file_path)

    log(f"📋 Found {len(files_to_process)} files to process", "info")

    for idx, file_path in enumerate(files_to_process, 1):
        ext = file_path.suffix.lower()

        # Parse filename
        parsed = parse_bids_filename(file_path.name)
        if not parsed:
            msg = f"Invalid filename pattern. Expected: sub-XXX_ses-YYY_task-ZZZ.{ext}"
            result.skipped.append((file_path, msg))
            log(
                f"⏭️  [{idx}/{len(files_to_process)}] Skipped: {file_path.name} - {msg}",
                "warning",
            )
            continue

        # Detect modality and convert
        modality = detect_modality(ext)
        log(
            f"🔄 [{idx}/{len(files_to_process)}] Converting: {file_path.name} ({modality})",
            "info",
        )

        if modality == "physio":
            converted = convert_physio_file(
                file_path,
                output_folder,
                parsed=parsed,
                base_freq=physio_sampling_rate,
            )
        elif modality == "eyetracking":
            converted = convert_eyetracking_file(
                file_path,
                output_folder,
                parsed=parsed,
            )
        else:
            msg = f"Unknown modality for extension: {ext}"
            result.skipped.append((file_path, msg))
            log(
                f"⏭️  [{idx}/{len(files_to_process)}] Skipped: {file_path.name} - {msg}",
                "warning",
            )
            continue

        result.converted.append(converted)

        if converted.success:
            log(
                f"✅ [{idx}/{len(files_to_process)}] Success: {file_path.name} → {converted.modality}/",
                "success",
            )
        else:
            log(
                f"❌ [{idx}/{len(files_to_process)}] Error: {file_path.name} - {converted.error}",
                "error",
            )

    # Summary
    log("", "info")
    log("📊 Conversion complete:", "info")
    log(f"   ✅ Successful: {result.success_count}", "success")
    if result.error_count > 0:
        log(f"   ❌ Errors: {result.error_count}", "error")
    if result.skipped:
        log(f"   ⏭️  Skipped: {len(result.skipped)}", "warning")

    return result


def create_dataset_description(
    output_folder: Path,
    *,
    name: str = "Converted Dataset",
    description: str = "Dataset converted from raw physio/eyetracking files",
) -> Path:
    """Create a dataset_description.json file for the output dataset."""
    desc = {
        "Name": name,
        "BIDSVersion": "1.9.0",
        "DatasetType": "raw",
        "Description": description,
        "GeneratedBy": [
            {
                "Name": "prism batch converter",
                "Version": "1.0.0",
            }
        ],
    }

    output_path = output_folder / "dataset_description.json"
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(desc, f, indent=2, ensure_ascii=False)

    return output_path


# CLI interface
if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="Batch convert physio/eyetracking data from flat folder to PRISM format"
    )
    parser.add_argument(
        "source",
        type=Path,
        help="Source folder containing raw files (flat structure)",
    )
    parser.add_argument(
        "output",
        type=Path,
        help="Output folder for PRISM dataset",
    )
    parser.add_argument(
        "--sampling-rate",
        type=float,
        help="Override sampling rate for physio files",
    )
    parser.add_argument(
        "--modality",
        choices=["all", "physio", "eyetracking"],
        default="all",
        help="Which modalities to convert (default: all)",
    )
    parser.add_argument(
        "--dataset-name",
        default="Converted Dataset",
        help="Name for dataset_description.json",
    )

    args = parser.parse_args()

    print(f"Converting files from: {args.source}")
    print(f"Output folder: {args.output}")
    print()

    # Create output folder
    args.output.mkdir(parents=True, exist_ok=True)

    # Run conversion
    result = batch_convert_folder(
        args.source,
        args.output,
        physio_sampling_rate=args.sampling_rate,
        modality_filter=args.modality,
    )

    # Create dataset description
    create_dataset_description(args.output, name=args.dataset_name)

    # Print summary
    print(f"✅ Successfully converted: {result.success_count} files")
    if result.error_count > 0:
        print(f"❌ Errors: {result.error_count} files")
    if result.skipped:
        print(f"⏭️  Skipped: {len(result.skipped)} files")
        for path, reason in result.skipped:
            print(f"   - {path.name}: {reason}")

    print()
    for conv in result.converted:
        status = "✅" if conv.success else "❌"
        print(f"{status} {conv.source_path.name} → {conv.modality}/")
        if conv.error:
            print(f"   Error: {conv.error}")
