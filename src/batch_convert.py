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
from typing import Callable

# Pattern for BIDS-like filenames: sub-XXX_ses-YYY_task-ZZZ[_extra].<ext>
BIDS_FILENAME_PATTERN = re.compile(
    r"^(?P<sub>sub-[a-zA-Z0-9]+)"
    r"(?:_(?P<ses>ses-[a-zA-Z0-9]+))?"
    r"_(?P<task>task-[a-zA-Z0-9]+)"
    r"(?P<extra>(?:_[a-zA-Z0-9]+(?:-[a-zA-Z0-9]+)?)*)"
    r"\.(?P<ext>[a-zA-Z0-9]+(?:\.gz)?)$",
    re.IGNORECASE,
)

# Modality detection by extension
PHYSIO_EXTENSIONS = {".raw", ".vpd", ".edf"}
EYETRACKING_EXTENSIONS = {".edf"}
GENERIC_EXTENSIONS = {
    ".tsv",
    ".tsv.gz",
    ".csv",
    ".txt",
    ".json",
    ".nii",
    ".nii.gz",
    ".pdf",
    ".png",
    ".jpg",
    ".jpeg",
}


@dataclass
class ConvertedFile:
    """Result of converting a single file."""

    source_path: Path
    output_files: list[Path]
    modality: str
    subject: str
    session: str | None
    task: str
    success: bool
    error: str | None = None


@dataclass
class FileConflict:
    """A file conflict when output already exists."""

    output_path: Path
    source_path: Path | None = None
    reason: str = "File already exists"  # "identical" or "different"


@dataclass
class BatchConvertResult:
    """Result of batch conversion."""

    source_folder: Path
    output_folder: Path
    converted: list[ConvertedFile] = field(default_factory=list)
    skipped: list[tuple[Path, str]] = field(default_factory=list)  # (path, reason)
    conflicts: list[FileConflict] = field(default_factory=list)  # File conflicts
    existing_files: int = 0  # Count of files that already exist (for dry-run reporting)
    new_files: int = 0  # Count of files that would be created (for dry-run reporting)

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


def detect_modality(ext: str) -> str | None:
    """Detect the modality based on file extension."""
    ext_lower = ext.lower() if not ext.startswith(".") else ext.lower()
    if not ext_lower.startswith("."):
        ext_lower = f".{ext_lower}"

    if ext_lower in PHYSIO_EXTENSIONS:
        return "physio"
    elif ext_lower in EYETRACKING_EXTENSIONS:
        return "eyetracking"
    elif ext_lower in GENERIC_EXTENSIONS:
        return "generic"
    return None


def _files_identical(path1: Path, path2: Path) -> bool:
    """Check if two files have identical content (for binary and text files)."""
    try:
        if not path1.exists() or not path2.exists():
            return False
        # For large files, compare size first
        if path1.stat().st_size != path2.stat().st_size:
            return False
        # For small files, compare content
        if path1.stat().st_size < 1_000_000:  # < 1 MB
            return path1.read_bytes() == path2.read_bytes()
        # For larger files, just trust size comparison
        return True
    except Exception:
        return False


def safe_write_file(
    source_path: Path,
    dest_path: Path,
    *,
    allow_overwrite: bool = True,
) -> tuple[bool, str | None]:
    """Safely write a file, checking for conflicts.

    Args:
        source_path: Path to source file to copy
        dest_path: Path to destination
        allow_overwrite: If False, skip if file exists

    Returns:
        (success: bool, conflict_reason: str | None)
        - (True, None): File written successfully
        - (False, None): Source file not found
        - (False, "identical"): File exists with same content (skipped)
        - (False, "different"): File exists with different content (conflict)
    """
    if not source_path.exists():
        return False, None

    if dest_path.exists():
        # Check if content is identical
        if _files_identical(source_path, dest_path):
            return False, "identical"
        # Content differs
        if not allow_overwrite:
            return False, "different"

    try:
        dest_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source_path, dest_path)
        return True, None
    except Exception as e:
        return False, f"error: {e}"


def _create_physio_sidecar(
    source_path: Path,
    output_json: Path,
    *,
    task_name: str,
    sampling_rate: float | None = None,
    recording_label: str = "ecg",
    extra_meta: dict | None = None,
) -> None:
    """Create a PRISM-compliant JSON sidecar for physio data."""
    extra_meta = extra_meta or {}
    sidecar = {
        "Technical": {
            "SamplingRate": sampling_rate
            or extra_meta.get("SamplingFrequency")
            or "unknown",
            "RecordingDuration": extra_meta.get("RecordingDuration") or "unknown",
            "SourceFormat": source_path.suffix.lower().lstrip("."),
        },
        "Study": {
            "TaskName": task_name.replace("task-", ""),
        },
        "Metadata": {
            "SourceFile": source_path.name,
            "ConvertedFrom": (
                "Varioport" if source_path.suffix.lower() in (".raw", ".vpd") else "EDF"
            ),
        },
        "Columns": {
            "time": {"Description": "Time in seconds", "Units": "s"},
        },
    }

    if "Channels" in extra_meta:
        for ch in extra_meta["Channels"]:
            sidecar["Columns"][ch] = {"Description": f"Channel {ch}"}

    with open(output_json, "w", encoding="utf-8") as f:
        json.dump(sidecar, f, indent=2, ensure_ascii=False)


def _create_eyetracking_sidecar(
    source_path: Path,
    output_json: Path,
    *,
    task_name: str,
    extra_meta: dict | None = None,
) -> None:
    """Create a PRISM-compliant JSON sidecar for eyetracking data."""
    extra_meta = extra_meta or {}
    sidecar = {
        "Technical": {
            "SamplingRate": extra_meta.get("SamplingFrequency") or "unknown",
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


def _extract_edf_metadata(edf_path: Path) -> dict:
    """Extract metadata from an EDF file using pyedflib."""
    try:
        import pyedflib
        from collections import Counter

        f = pyedflib.EdfReader(str(edf_path))

        # Get basic info
        n_channels = f.signals_in_file
        duration = f.file_duration
        start_datetime = f.getStartdatetime()

        # Get channel info
        channels = []
        sampling_rates = []
        for i in range(n_channels):
            channels.append(f.getLabel(i))
            sampling_rates.append(f.getSampleFrequency(i))

        f.close()

        # Use the most common sampling rate as the default
        common_sr = (
            Counter(sampling_rates).most_common(1)[0][0] if sampling_rates else 0
        )

        return {
            "SamplingFrequency": common_sr,
            "RecordingDuration": duration,
            "StartTime": (
                start_datetime.strftime("%H:%M:%S") if start_datetime else None
            ),
            "Channels": channels,
            "AllSamplingRates": sampling_rates,
        }
    except Exception as e:
        print(f"Warning: Could not extract EDF metadata from {edf_path}: {e}")
        return {}


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
        # Try to use the Varioport converter for .raw/.vpd
        if ext in (".raw", ".vpd"):
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
        else:
            # For .edf or other formats already in physio-compatible format
            out_data = out_folder / f"{base_name}.{ext}"
            out_json = out_folder / f"{base_name}.json"

            shutil.copy2(source_path, out_data)

            # Extract metadata if it's an EDF file
            edf_meta = {}
            if ext == "edf":
                edf_meta = _extract_edf_metadata(source_path)

            _create_physio_sidecar(
                source_path,
                out_json,
                task_name=task,
                sampling_rate=base_freq,
                extra_meta=edf_meta,
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
        edf_meta = _extract_edf_metadata(source_path)
        _create_eyetracking_sidecar(
            source_path, out_json, task_name=task, extra_meta=edf_meta
        )
        output_files.append(out_json)

        # Try to enrich sidecar with EDF header info if pyedflib is available
        try:
            import pyedflib

            with pyedflib.EdfReader(str(source_path)) as f:
                with open(out_json, "r", encoding="utf-8") as jf:
                    sidecar = json.load(jf)

                if "Technical" not in sidecar:
                    sidecar["Technical"] = {}

                # Extract sampling rate (from first signal)
                if f.signals_in_file > 0:
                    sidecar["Technical"]["SamplingFrequency"] = f.getSampleFrequency(0)

                # Extract duration
                sidecar["Technical"]["Duration"] = f.getFileDuration()

                with open(out_json, "w", encoding="utf-8") as jf:
                    json.dump(sidecar, jf, indent=2)
        except (ImportError, Exception):
            pass

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


def convert_generic_file(
    source_path: Path,
    output_dir: Path,
    *,
    parsed: dict,
    target_modality: str = "extra",
) -> ConvertedFile:
    """Organize a generic file into PRISM structure by copying it.

    Args:
        source_path: Path to source file
        output_dir: Path to output dataset root
        parsed: Parsed BIDS components
        target_modality: Modality folder name (e.g., 'survey', 'anat', 'func')
    """
    sub = parsed["sub"]
    ses = parsed["ses"]
    task = parsed["task"]
    ext = parsed["ext"]
    extra = parsed["extra"]

    # Build output path: output_dir/sub-XXX/[ses-YYY/]modality/
    if ses:
        out_folder = output_dir / sub / ses / target_modality
    else:
        out_folder = output_dir / sub / target_modality
    out_folder.mkdir(parents=True, exist_ok=True)

    # Build BIDS filename
    parts = [sub]
    if ses:
        parts.append(ses)
    parts.append(task)
    if extra:
        parts.append(extra.lstrip("_"))

    # Add suffix based on modality if not already in extra
    suffix_map = {
        "survey": "survey",
        "biometrics": "biometrics",
        "physio": "physio",
        "eyetracking": "eyetrack",
        "anat": "T1w",
        "func": "bold",
    }

    suffix = suffix_map.get(target_modality, target_modality)

    # Check if suffix is already present in the parts
    suffix_already_present = False
    for p in parts:
        if p == suffix or p.endswith(f"_{suffix}") or p.endswith(f"-{suffix}"):
            suffix_already_present = True
            break

    if not suffix_already_present:
        parts.append(suffix)

    base_name = "_".join(parts)
    out_data = out_folder / f"{base_name}.{ext}"

    try:
        shutil.copy2(source_path, out_data)

        # Create a minimal sidecar if it's a data file (not already a json)
        output_files = [out_data]
        if ext != "json":
            out_json = out_folder / f"{base_name}.json"
            sidecar = {
                "Metadata": {
                    "SourceFile": source_path.name,
                    "OrganizedBy": "prism batch organizer",
                }
            }
            with open(out_json, "w", encoding="utf-8") as f:
                json.dump(sidecar, f, indent=2)
            output_files.append(out_json)

        return ConvertedFile(
            source_path=source_path,
            output_files=output_files,
            modality=target_modality,
            subject=sub,
            session=ses,
            task=task,
            success=True,
        )
    except Exception as e:
        return ConvertedFile(
            source_path=source_path,
            output_files=[],
            modality=target_modality,
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
    modality_filter: str = "all",
    log_callback: Callable | None = None,
    dry_run: bool = False,
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
    if dry_run:
        log("🧪 DRY RUN MODE - No files will be written", "info")

    # Find all supported files
    all_extensions = set()
    if modality_filter in ("all", "physio"):
        all_extensions.update(PHYSIO_EXTENSIONS)
    if modality_filter in ("all", "eyetracking"):
        all_extensions.update(EYETRACKING_EXTENSIONS)
    if modality_filter not in ("all", "physio", "eyetracking"):
        # If a specific modality is requested that isn't physio/eyetracking,
        # we assume it's a generic copy operation
        all_extensions.update(GENERIC_EXTENSIONS)
        all_extensions.update(PHYSIO_EXTENSIONS)
        all_extensions.update(EYETRACKING_EXTENSIONS)

    # Collect files first to get total count
    files_to_process = []
    for file_path in sorted(source_folder.iterdir()):
        if not file_path.is_file():
            continue
        ext = file_path.suffix.lower()
        # Handle .nii.gz
        if file_path.name.lower().endswith(".nii.gz"):
            ext = ".nii.gz"

        if modality_filter == "all":
            if (
                ext in PHYSIO_EXTENSIONS
                or ext in EYETRACKING_EXTENSIONS
                or ext in GENERIC_EXTENSIONS
            ):
                files_to_process.append(file_path)
        elif ext in all_extensions:
            files_to_process.append(file_path)

    log(f"📋 Found {len(files_to_process)} files to process", "info")

    for idx, file_path in enumerate(files_to_process, 1):
        ext = file_path.suffix.lower()
        if file_path.name.lower().endswith(".nii.gz"):
            ext = ".nii.gz"

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

        # Override modality if filter is specific and not 'all'
        if modality_filter not in ("all", "physio", "eyetracking"):
            modality = "generic"
            target_modality = modality_filter
        else:
            target_modality = modality

        log(
            f"🔄 [{idx}/{len(files_to_process)}] Processing: {file_path.name} ({target_modality})",
            "info",
        )

        if target_modality == "physio":
            converted = convert_physio_file(
                file_path,
                output_folder,
                parsed=parsed,
                base_freq=physio_sampling_rate,
            )
        elif target_modality == "eyetracking":
            converted = convert_eyetracking_file(
                file_path,
                output_folder,
                parsed=parsed,
            )
        elif modality == "generic" or modality_filter not in (
            "all",
            "physio",
            "eyetracking",
        ):
            converted = convert_generic_file(
                file_path,
                output_folder,
                parsed=parsed,
                target_modality=(
                    target_modality if target_modality != "generic" else "extra"
                ),
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
            # Track file existence for dry-run reporting
            if dry_run and converted.output_files:
                files_exist = sum(1 for f in converted.output_files if f.exists())
                result.existing_files += files_exist
                result.new_files += len(converted.output_files) - files_exist

            if dry_run:
                # In dry run, show what would be created
                if converted.output_files:
                    output_paths = ", ".join([f.name for f in converted.output_files])
                    log(
                        f"✅ [{idx}/{len(files_to_process)}] Would create: {file_path.name} → {converted.modality}/ ({output_paths})",
                        "success",
                    )
                else:
                    log(
                        f"✅ [{idx}/{len(files_to_process)}] Would process: {file_path.name} → {converted.modality}/",
                        "success",
                    )
            else:
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
    if dry_run:
        log("🧪 DRY RUN SUMMARY:", "info")
        log(f"   ✅ Would organize: {result.success_count} files", "success")
        log(f"   📄 New files: {result.new_files}", "info")
        log(
            f"   📋 Existing files (will be overwritten): {result.existing_files}",
            "warning",
        )
    else:
        log("📊 Conversion complete:", "info")
        log(f"   ✅ Successful: {result.success_count}", "success")
    if result.error_count > 0:
        log(f"   ❌ Errors: {result.error_count}", "error")
    if result.skipped:
        log(f"   ⏭️  Skipped: {len(result.skipped)}", "warning")
    if result.conflicts:
        log(f"   ⚠️  Conflicts: {len(result.conflicts)}", "warning")
    if dry_run:
        log("💡 Run 'Copy to Project' when you're ready to execute.", "info")

    return result


def create_dataset_description(
    output_folder: Path,
    *,
    name: str = "Converted Dataset",
    description: str = "Dataset converted from raw physio/eyetracking files",
) -> Path:
    """Create a dataset_description.json file for the output dataset following BIDS v1.10.1."""
    desc = {
        "Name": name,
        "BIDSVersion": "1.10.1",
        "DatasetType": "raw",
        "Description": description,
        "Authors": ["PRISM Batch Converter"],
        "GeneratedBy": [
            {
                "Name": "PRISM Batch Converter",
                "Version": "1.1.1",
                "Description": "Automated conversion from raw physiological/eyetracking files to BIDS/PRISM structure.",
            }
        ],
        "HEDVersion": "8.2.0",
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
