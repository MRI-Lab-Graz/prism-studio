"""Backend services for participant mapping and dataset-derived outputs."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Callable

import pandas as pd

ParticipantLogCallback = Callable[[str, str], None]

_PARTICIPANT_ID_PATTERN = re.compile(r"(sub-[A-Za-z0-9]+)")


def normalize_participant_mapping(mapping: object) -> dict:
    """Normalize web-style flat mappings into the structured mapping schema."""
    if not mapping:
        raise ValueError("Missing mapping data")
    if not isinstance(mapping, dict):
        raise ValueError("Mapping data must be a JSON object")
    if "mappings" in mapping:
        return mapping

    mappings_block: dict[str, dict[str, str]] = {}
    for source_column, standard_variable in mapping.items():
        src = str(source_column).strip()
        if not src:
            continue

        std_raw = str(standard_variable).strip() or src
        std = re.sub(r"[^a-zA-Z0-9_]+", "_", std_raw).strip("_").lower()
        if not std:
            std = re.sub(r"[^a-zA-Z0-9_]+", "_", src).strip("_").lower()
        if not std:
            continue

        mappings_block[std] = {
            "source_column": src,
            "standard_variable": std,
            "type": "string",
        }

    return {
        "version": "1.0",
        "description": "Additional variables mapping created from PRISM web UI",
        "mappings": mappings_block,
    }


def resolve_participant_mapping_target(
    *,
    project_root: Path | None,
    library_path: str | Path | None,
) -> tuple[Path, str]:
    """Resolve the directory that should receive participants_mapping.json."""
    if project_root is not None:
        target_lib_path = project_root.resolve() / "code" / "library"
        target_lib_path.mkdir(parents=True, exist_ok=True)
        return target_lib_path, "project"

    if library_path:
        try:
            target_lib_path = Path(str(library_path)).expanduser().resolve()
        except Exception as exc:
            raise ValueError(f"Invalid library path: {exc}") from exc
        if not target_lib_path.exists() or not target_lib_path.is_dir():
            raise ValueError("Invalid library path: target must be an existing directory")
        return target_lib_path, "provided"

    raise ValueError(
        "No valid library path found. Please ensure project is loaded or select a library path."
    )


def save_participant_mapping(
    mapping: object,
    *,
    project_root: Path | None = None,
    library_path: str | Path | None = None,
) -> dict[str, object]:
    """Persist participants_mapping.json to the best available library location."""
    normalized_mapping = normalize_participant_mapping(mapping)
    target_lib_path, library_source = resolve_participant_mapping_target(
        project_root=project_root,
        library_path=library_path,
    )

    mapping_file = target_lib_path / "participants_mapping.json"
    mapping_file.write_text(
        json.dumps(normalized_mapping, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    return {
        "mapping_file": mapping_file,
        "library_source": library_source,
        "normalized_mapping": normalized_mapping,
    }


def merge_neurobagel_schema_for_columns(
    base_schema: dict,
    neurobagel_schema: dict,
    allowed_columns: list[str],
    log_callback: ParticipantLogCallback | None = None,
) -> tuple[dict, int]:
    """Merge NeuroBagel schema into participants metadata for known TSV columns."""
    if not isinstance(base_schema, dict):
        base_schema = {}
    if not isinstance(neurobagel_schema, dict):
        return base_schema, 0

    allowed = {str(col) for col in allowed_columns}
    merged_count = 0

    for col, schema_def in neurobagel_schema.items():
        if col not in allowed:
            if log_callback:
                log_callback(
                    "INFO",
                    f"Skipped annotation-only field '{col}' (not present in participants.tsv)",
                )
            continue

        if col not in base_schema:
            base_schema[col] = {}

        if isinstance(schema_def, dict) and "Annotations" in schema_def:
            if "Annotations" not in base_schema[col]:
                base_schema[col]["Annotations"] = {}
            annotations = schema_def["Annotations"]
            if isinstance(annotations, dict):
                base_schema[col]["Annotations"].update(annotations)

        if isinstance(schema_def, dict):
            for key, value in schema_def.items():
                if key == "Annotations":
                    continue
                if key not in base_schema[col]:
                    base_schema[col][key] = value

        merged_count += 1

    return base_schema, merged_count


def collect_dataset_participants(
    project_root: Path,
    *,
    extract_from_survey: bool = True,
    extract_from_biometrics: bool = True,
    log_callback: ParticipantLogCallback | None = None,
) -> dict[str, object]:
    """Collect participant IDs from survey and biometrics files within a dataset."""
    resolved_root = project_root.expanduser().resolve()
    participants: set[str] = set()

    survey_files: list[Path] = []
    if extract_from_survey:
        survey_files = list(resolved_root.rglob("**/survey/*_survey.tsv"))
        if log_callback:
            log_callback("INFO", f"Found {len(survey_files)} survey files")
        for file_path in survey_files:
            match = _PARTICIPANT_ID_PATTERN.search(file_path.name)
            if match:
                participants.add(match.group(1))

    biometrics_files: list[Path] = []
    if extract_from_biometrics:
        biometrics_files = list(resolved_root.rglob("**/biometrics/*_biometrics.tsv"))
        if log_callback:
            log_callback("INFO", f"Found {len(biometrics_files)} biometrics files")
        for file_path in biometrics_files:
            match = _PARTICIPANT_ID_PATTERN.search(file_path.name)
            if match:
                participants.add(match.group(1))

    return {
        "participants": sorted(participants),
        "survey_file_count": len(survey_files),
        "biometrics_file_count": len(biometrics_files),
    }


def preview_dataset_participants(
    project_root: Path,
    *,
    extract_from_survey: bool = True,
    extract_from_biometrics: bool = True,
) -> dict[str, object]:
    """Return a preview payload for dataset-derived participants extraction."""
    dataset_summary = collect_dataset_participants(
        project_root,
        extract_from_survey=extract_from_survey,
        extract_from_biometrics=extract_from_biometrics,
    )
    participants = list(dataset_summary["participants"])
    if not participants:
        raise ValueError("No participant data found in dataset")

    return {
        "status": "success",
        "participant_count": len(participants),
        "participants": participants[:20],
        "total_participants": len(participants),
    }


def convert_dataset_participants(
    project_root: Path,
    *,
    neurobagel_schema: dict | None = None,
    extract_from_survey: bool = True,
    extract_from_biometrics: bool = True,
    log_callback: ParticipantLogCallback | None = None,
) -> dict[str, object]:
    """Create participants.tsv and participants.json from dataset-derived IDs."""
    resolved_root = project_root.expanduser().resolve()
    dataset_summary = collect_dataset_participants(
        resolved_root,
        extract_from_survey=extract_from_survey,
        extract_from_biometrics=extract_from_biometrics,
        log_callback=log_callback,
    )
    participants = list(dataset_summary["participants"])
    if not participants:
        raise ValueError("No participant data found in dataset")

    if log_callback:
        log_callback("INFO", f"Found {len(participants)} unique participants")

    participants_tsv = resolved_root / "participants.tsv"
    participants_json = resolved_root / "participants.json"

    df = pd.DataFrame({"participant_id": participants})
    df.to_csv(participants_tsv, sep="\t", index=False)

    participants_json_data = {
        "participant_id": {"Description": "Unique participant identifier"}
    }

    if neurobagel_schema:
        participants_json_data, merged_count = merge_neurobagel_schema_for_columns(
            participants_json_data,
            neurobagel_schema,
            list(df.columns),
            log_callback=log_callback,
        )
        if log_callback:
            log_callback(
                "INFO",
                f"Merged NeuroBagel annotations for {merged_count} participants.tsv column(s)",
            )

    participants_json.write_text(
        json.dumps(participants_json_data, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    if log_callback:
        log_callback(
            "INFO",
            f"✓ Created {participants_tsv.name} with {len(participants)} participants",
        )
        log_callback("INFO", f"✓ Created {participants_json.name}")

    return {
        "status": "success",
        "participant_count": len(participants),
        "files_created": [str(participants_tsv), str(participants_json)],
    }