"""Canonical backend services for participant mapping and participants files.

This module owns backend-only logic for:
- participants_mapping.json normalization/persistence
- dataset-derived participants.tsv/json creation
- safe preview/apply merge workflows for enriching an existing participants.tsv
"""

from __future__ import annotations

import json
import csv
import io
import re
import shutil
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, cast

import pandas as pd

from src.participants_converter import ParticipantsConverter


def _import_read_tabular_file():
    try:
        from src.converters.file_reader import read_tabular_file
    except ImportError:
        from converters.file_reader import read_tabular_file
    return read_tabular_file


_read_tabular_file = _import_read_tabular_file()

ParticipantLogCallback = Callable[[str, str], None]

_PARTICIPANT_ID_PATTERN = re.compile(r"(sub-[A-Za-z0-9]+)")
_MISSING_TOKENS = {"", "n/a", "na", "nan", "none"}
_SESSION_RESOLUTION_ACTIONS = {
    "pick_session",
    "pick_latest_session",
    "split_sessions",
}


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
            raise ValueError(
                "Invalid library path: target must be an existing directory"
            )
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


def describe_participants_workflow(project_root: Path) -> dict[str, object]:
    """Describe which participant-management workflows are valid for a project."""
    resolved_root = project_root.expanduser().resolve()
    participants_tsv = resolved_root / "participants.tsv"
    participants_json = resolved_root / "participants.json"

    has_participants_tsv = participants_tsv.exists() and participants_tsv.is_file()
    has_participants_json = participants_json.exists() and participants_json.is_file()

    if has_participants_tsv:
        return {
            "state": "case_selection_required",
            "available_cases": ["1", "2", "3"],
            "requires_case_selection": True,
            "default_case": None,
            "show_case_guide": True,
            "mode_options": ["file", "existing"],
            "file_actions": ["replace", "merge"],
            "metadata_without_tsv": False,
        }

    return {
        "state": "import_required",
        "available_cases": ["1"],
        "requires_case_selection": False,
        "default_case": "1",
        "show_case_guide": False,
        "mode_options": ["file"],
        "file_actions": ["replace"],
        "metadata_without_tsv": has_participants_json,
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
    participants = list(cast(list[str], dataset_summary["participants"]))
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
    participants = list(cast(list[str], dataset_summary["participants"]))
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


def sync_participants_tsv_with_subject_dirs(
    project_root: Path,
    *,
    log_callback: ParticipantLogCallback | None = None,
) -> dict[str, object]:
    """Ensure participants.tsv contains all top-level sub-* directories.

    The sync is intentionally additive/safe:
    - Normalize existing participant IDs to canonical ``sub-<label>``
    - Merge duplicate IDs created by normalization (keep first non-missing values)
    - Append missing subject IDs as rows with ``n/a`` defaults
    - Preserve rows with invalid/empty participant_id verbatim (no destructive drop)
    """
    resolved_root = project_root.expanduser().resolve()
    participants_tsv = resolved_root / "participants.tsv"

    try:
        subject_ids = sorted(
            child.name
            for child in resolved_root.iterdir()
            if child.is_dir() and child.name.startswith("sub-")
        )
    except Exception as exc:
        raise ValueError(f"Failed to inspect dataset subjects: {exc}") from exc

    if not subject_ids:
        return {
            "status": "skipped",
            "reason": "no_subject_directories",
            "participants_tsv": str(participants_tsv),
            "subject_count": 0,
            "added_count": 0,
            "normalized_count": 0,
            "duplicates_merged": 0,
        }

    if not participants_tsv.exists() or not participants_tsv.is_file():
        return {
            "status": "skipped",
            "reason": "participants_tsv_missing",
            "participants_tsv": str(participants_tsv),
            "subject_count": len(subject_ids),
            "added_count": 0,
            "normalized_count": 0,
            "duplicates_merged": 0,
        }

    try:
        with participants_tsv.open("r", encoding="utf-8", newline="") as handle:
            reader = csv.DictReader(handle, delimiter="\t")
            header = [str(column) for column in (reader.fieldnames or [])]
            rows = [
                {
                    str(column): value
                    for column, value in dict(raw_row or {}).items()
                }
                for raw_row in reader
            ]
    except Exception as exc:
        raise ValueError(f"Failed to read participants.tsv: {exc}") from exc

    if "participant_id" not in header:
        return {
            "status": "skipped",
            "reason": "participant_id_column_missing",
            "participants_tsv": str(participants_tsv),
            "subject_count": len(subject_ids),
            "added_count": 0,
            "normalized_count": 0,
            "duplicates_merged": 0,
        }

    row_by_participant_id: dict[str, dict[str, Any]] = {}
    untouched_rows: list[dict[str, Any]] = []
    normalized_count = 0
    duplicates_merged = 0

    for raw_row in rows:
        row = {column: raw_row.get(column) for column in header}
        raw_participant_id = row.get("participant_id")
        normalized_participant_id = ParticipantsConverter._normalize_participant_id(
            raw_participant_id
        )

        if normalized_participant_id is None:
            untouched_rows.append(row)
            continue

        original_text = str(raw_participant_id or "").strip()
        if original_text != normalized_participant_id:
            normalized_count += 1

        row["participant_id"] = normalized_participant_id
        existing_row = row_by_participant_id.get(normalized_participant_id)
        if existing_row is None:
            row_by_participant_id[normalized_participant_id] = row
            continue

        duplicates_merged += 1
        for column in header:
            if column == "participant_id":
                continue
            existing_value = existing_row.get(column)
            incoming_value = row.get(column)
            if _is_missing_participant_value(
                existing_value
            ) and not _is_missing_participant_value(incoming_value):
                existing_row[column] = incoming_value

    missing_subject_ids = [
        participant_id
        for participant_id in subject_ids
        if participant_id not in row_by_participant_id
    ]
    for participant_id in missing_subject_ids:
        new_row = {column: "n/a" for column in header}
        new_row["participant_id"] = participant_id
        row_by_participant_id[participant_id] = new_row

    if not (missing_subject_ids or normalized_count or duplicates_merged):
        return {
            "status": "unchanged",
            "participants_tsv": str(participants_tsv),
            "subject_count": len(subject_ids),
            "participant_count": len(row_by_participant_id),
            "added_count": 0,
            "normalized_count": 0,
            "duplicates_merged": 0,
        }

    ordered_rows = untouched_rows + [
        row_by_participant_id[participant_id]
        for participant_id in sorted(row_by_participant_id.keys())
    ]

    try:
        with participants_tsv.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(
                handle,
                fieldnames=header,
                delimiter="\t",
                lineterminator="\n",
            )
            writer.writeheader()
            for row in ordered_rows:
                payload: dict[str, str] = {}
                for column in header:
                    value = row.get(column)
                    if column == "participant_id":
                        payload[column] = str(value or "").strip()
                    else:
                        payload[column] = "" if value is None else str(value)
                writer.writerow(payload)
    except Exception as exc:
        raise ValueError(f"Failed to write participants.tsv: {exc}") from exc

    if log_callback:
        details: list[str] = []
        if missing_subject_ids:
            details.append(f"added {len(missing_subject_ids)} missing participant row(s)")
        if normalized_count:
            details.append(f"normalized {normalized_count} participant_id value(s)")
        if duplicates_merged:
            details.append(f"merged {duplicates_merged} duplicate row(s)")
        if details:
            log_callback("INFO", "Synced participants.tsv: " + ", ".join(details))

    return {
        "status": "updated",
        "participants_tsv": str(participants_tsv),
        "subject_count": len(subject_ids),
        "participant_count": len(row_by_participant_id),
        "added_count": len(missing_subject_ids),
        "added_ids": missing_subject_ids,
        "normalized_count": normalized_count,
        "duplicates_merged": duplicates_merged,
    }


def _is_missing_participant_value(value: Any) -> bool:
    if value is None:
        return True
    try:
        if pd.isna(value):
            return True
    except Exception:
        pass
    return str(value).strip().lower() in _MISSING_TOKENS


def _participant_value_text(value: Any, *, default: str = "n/a") -> str:
    if _is_missing_participant_value(value):
        return default
    return str(value).strip()


def _parse_participant_numeric_value(value: Any) -> float | None:
    if _is_missing_participant_value(value):
        return None

    text = str(value).strip()
    if not text:
        return None

    normalized_text = text.replace(",", ".")
    try:
        return float(normalized_text)
    except Exception:
        return None


def _participant_values_numeric_equivalent(
    existing_value: Any,
    incoming_value: Any,
) -> bool:
    existing_numeric = _parse_participant_numeric_value(existing_value)
    incoming_numeric = _parse_participant_numeric_value(incoming_value)
    if existing_numeric is None or incoming_numeric is None:
        return False
    return abs(existing_numeric - incoming_numeric) < 1e-12


def _normalized_participant_text(value: Any) -> str:
    return str(value).strip().lower()


def _normalize_session_resolution_decision_entry(raw_entry: Any) -> dict[str, str]:
    action = ""
    session = ""

    if isinstance(raw_entry, str):
        action = str(raw_entry).strip().lower()
    elif isinstance(raw_entry, dict):
        action = str(raw_entry.get("action") or "").strip().lower()
        session = str(raw_entry.get("session") or "").strip()

    if action not in _SESSION_RESOLUTION_ACTIONS:
        action = ""

    return {
        "action": action,
        "session": session,
    }


def _resolve_source_column_for_standard_variable(
    mapping: dict[str, Any],
    standard_variable: str,
) -> str:
    mappings = mapping.get("mappings") if isinstance(mapping, dict) else None
    if not isinstance(mappings, dict):
        return ""

    target_standard = str(standard_variable or "").strip()
    for spec in mappings.values():
        if not isinstance(spec, dict):
            continue
        spec_standard = str(spec.get("standard_variable") or "").strip()
        if spec_standard != target_standard:
            continue
        source_column = str(spec.get("source_column") or "").strip()
        if source_column:
            return source_column

    return ""


def _normalize_session_value(value: Any) -> str:
    if _is_missing_participant_value(value):
        return ""

    text = str(value).strip()
    if not text:
        return ""

    numeric_value = _parse_participant_numeric_value(text)
    if numeric_value is not None and abs(numeric_value - round(numeric_value)) < 1e-12:
        return str(int(round(numeric_value)))

    return text


def _sanitize_session_token(value: str) -> str:
    token = re.sub(r"[^A-Za-z0-9]+", "-", str(value or "").strip())
    token = re.sub(r"-+", "-", token).strip("-")
    if not token:
        token = "unknown"
    return token.lower()


def _find_session_column_name(columns: list[str], preferred: str = "") -> str:
    if not columns:
        return ""

    by_lower = {str(column).strip().lower(): str(column) for column in columns}
    preferred_clean = str(preferred or "").strip()
    if preferred_clean and preferred_clean.lower() in by_lower:
        return by_lower[preferred_clean.lower()]

    canonical_order = [
        "session",
        "ses",
        "session_id",
        "sessionid",
        "visit",
        "timepoint",
        "wave",
        "run",
    ]
    for name in canonical_order:
        if name in by_lower:
            return by_lower[name]

    for column in columns:
        lowered = str(column).strip().lower()
        if any(token in lowered for token in ("session", "ses", "visit", "timepoint", "wave", "run")):
            return str(column)

    return ""


def _sorted_session_values(values: set[str]) -> list[str]:
    def sort_key(raw: str) -> tuple[int, float | str]:
        numeric = _parse_participant_numeric_value(raw)
        if numeric is not None:
            return (0, numeric)
        return (1, str(raw))

    return sorted((str(value).strip() for value in values if str(value).strip()), key=sort_key)


def _unique_column_name(base: str, existing_columns: list[str]) -> str:
    candidate = str(base or "").strip() or "column"
    used = set(existing_columns)
    if candidate not in used:
        return candidate

    index = 2
    next_candidate = f"{candidate}_{index}"
    while next_candidate in used:
        index += 1
        next_candidate = f"{candidate}_{index}"
    return next_candidate


_HARMONIZATION_ACTIONS = {"keep_existing", "use_incoming", "keep_both"}


def _next_available_participant_column_name(
    base_column: str,
    *,
    existing_columns: list[str],
) -> str:
    base = str(base_column or "").strip() or "variable"
    candidate = f"{base}_incoming"
    index = 2
    used = {str(column).strip() for column in existing_columns}
    while candidate in used:
        candidate = f"{base}_incoming_{index}"
        index += 1
    return candidate


def _normalize_harmonization_decision_entry(
    raw_entry: Any,
) -> tuple[str, str | None]:
    action = "keep_existing"
    new_column: str | None = None

    if isinstance(raw_entry, str):
        action = str(raw_entry).strip().lower()
    elif isinstance(raw_entry, dict):
        action = str(raw_entry.get("action") or "").strip().lower()
        new_column_text = str(raw_entry.get("new_column") or "").strip()
        if new_column_text:
            new_column = new_column_text

    if action not in _HARMONIZATION_ACTIONS:
        action = "keep_existing"

    return action, new_column


def _canonical_display_text(
    text_value: str,
    fallback_map: dict[str, str],
) -> str:
    normalized = _normalized_participant_text(text_value)
    return str(fallback_map.get(normalized) or text_value).strip()


def _infer_low_cardinality_code_equivalence_maps(
    existing_rows_by_id: dict[str, dict[str, Any]],
    incoming_rows_by_id: dict[str, dict[str, Any]],
    *,
    matched_ids: list[str],
    shared_columns: list[str],
    max_unique_values: int = 12,
    min_unique_values: int = 2,
) -> dict[str, dict[str, Any]]:
    """Infer safe incoming->existing code maps for categorical low-cardinality fields.

    This supports merge cases where two sources encode the same field using
    different but consistent codings (e.g., F/M vs 1/2).
    """
    inferred_maps: dict[str, dict[str, Any]] = {}

    for column in shared_columns:
        existing_to_incoming: dict[str, set[str]] = {}
        incoming_to_existing: dict[str, set[str]] = {}
        existing_display: dict[str, str] = {}
        incoming_display: dict[str, str] = {}
        pair_count = 0

        for participant_id in matched_ids:
            existing_row = existing_rows_by_id.get(participant_id) or {}
            incoming_row = incoming_rows_by_id.get(participant_id) or {}

            existing_value = existing_row.get(column)
            incoming_value = incoming_row.get(column)
            if _is_missing_participant_value(
                existing_value
            ) or _is_missing_participant_value(incoming_value):
                continue

            if _participant_values_numeric_equivalent(existing_value, incoming_value):
                continue

            existing_text = _normalized_participant_text(existing_value)
            incoming_text = _normalized_participant_text(incoming_value)
            if not existing_text or not incoming_text or existing_text == incoming_text:
                continue

            pair_count += 1
            existing_to_incoming.setdefault(existing_text, set()).add(incoming_text)
            incoming_to_existing.setdefault(incoming_text, set()).add(existing_text)
            existing_display.setdefault(existing_text, str(existing_value).strip())
            incoming_display.setdefault(incoming_text, str(incoming_value).strip())

        if not existing_to_incoming:
            continue

        if (
            len(existing_to_incoming) < min_unique_values
            or len(incoming_to_existing) < min_unique_values
        ):
            continue

        if (
            len(existing_to_incoming) > max_unique_values
            or len(incoming_to_existing) > max_unique_values
        ):
            continue

        if any(len(values) != 1 for values in existing_to_incoming.values()):
            continue
        if any(len(values) != 1 for values in incoming_to_existing.values()):
            continue

        if len(existing_to_incoming) != len(incoming_to_existing):
            continue

        incoming_to_existing_map = {
            incoming_code: next(iter(existing_codes))
            for incoming_code, existing_codes in incoming_to_existing.items()
        }
        existing_to_incoming_map = {
            existing_code: next(iter(incoming_codes))
            for existing_code, incoming_codes in existing_to_incoming.items()
        }

        inferred_maps[column] = {
            "incoming_to_existing": incoming_to_existing_map,
            "existing_to_incoming": existing_to_incoming_map,
            "incoming_display": incoming_display,
            "existing_display": existing_display,
            "pair_count": pair_count,
        }

    return inferred_maps


def _collect_preview_column_values(
    df: pd.DataFrame | None, *, max_values: int = 50
) -> dict[str, list[str]]:
    if df is None or df.empty:
        return {}

    column_values: dict[str, list[str]] = {}
    limit = max(int(max_values or 50), 1)

    for column in df.columns:
        unique_values: list[str] = []
        seen_values: set[str] = set()

        for raw_value in df[column].tolist():
            if _is_missing_participant_value(raw_value):
                continue

            text_value = str(raw_value).strip()
            if not text_value or text_value in seen_values:
                continue

            seen_values.add(text_value)
            unique_values.append(text_value)
            if len(unique_values) >= limit:
                break

        column_values[str(column)] = unique_values

    return column_values


def _load_existing_participants_table(project_root: Path) -> pd.DataFrame:
    participants_tsv = project_root / "participants.tsv"
    if not participants_tsv.exists():
        raise ValueError(
            "participants.tsv not found at project root. Use participants convert to create it first."
        )

    try:
        existing_df = pd.read_csv(participants_tsv, sep="\t", dtype=str)
    except Exception as exc:
        raise ValueError(f"Failed to read existing participants.tsv: {exc}") from exc

    if "participant_id" not in existing_df.columns:
        raise ValueError(
            "Existing participants.tsv must contain a participant_id column"
        )

    validated_rows: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    for index, row in enumerate(existing_df.to_dict(orient="records"), start=2):
        participant_id = str(row.get("participant_id") or "").strip()
        normalized = ParticipantsConverter._normalize_participant_id(participant_id)
        if not participant_id or normalized is None:
            raise ValueError(
                "Existing participants.tsv contains an invalid participant_id "
                f"at row {index}: {participant_id or '<empty>'}"
            )
        if normalized != participant_id:
            raise ValueError(
                "Existing participants.tsv must already use canonical participant_id values. "
                f"Found '{participant_id}' at row {index}; expected '{normalized}'."
            )
        if participant_id in seen_ids:
            raise ValueError(
                f"Existing participants.tsv contains duplicate participant_id '{participant_id}'"
            )
        seen_ids.add(participant_id)
        normalized_row = {str(col): row.get(col) for col in existing_df.columns}
        normalized_row["participant_id"] = participant_id
        validated_rows.append(normalized_row)

    return pd.DataFrame(
        validated_rows, columns=[str(col) for col in existing_df.columns]
    )


def _load_existing_participants_schema(project_root: Path) -> dict[str, Any]:
    participants_json = project_root / "participants.json"
    if not participants_json.exists():
        return {}

    try:
        payload = json.loads(participants_json.read_text(encoding="utf-8"))
    except Exception as exc:
        raise ValueError(f"Failed to read existing participants.json: {exc}") from exc

    if not isinstance(payload, dict):
        raise ValueError("Existing participants.json must contain a JSON object")
    return payload


def _build_participants_merge_input(
    project_root: Path,
    source_file: str | Path,
    mapping: dict[str, Any],
    *,
    separator: str | None = None,
    sheet: str | int = 0,
    session_resolution_decisions: dict[str, Any] | None = None,
    log_callback: ParticipantLogCallback | None = None,
) -> tuple[pd.DataFrame, list[str], dict[str, Any]]:
    source_path = Path(source_file).expanduser().resolve()
    if not source_path.exists():
        raise ValueError(f"Input file not found: {source_path}")

    with tempfile.TemporaryDirectory(prefix="prism_participants_merge_") as tmp_dir:
        converter = ParticipantsConverter(project_root, log_callback=log_callback)
        success, output_df, messages = converter.convert_participant_data(
            source_path,
            mapping,
            output_file=Path(tmp_dir) / "participants.tsv",
            separator=separator or "auto",
            sheet=sheet,
        )

    if not success or output_df is None:
        message = "; ".join(str(item) for item in messages if str(item).strip())
        raise ValueError(message or "Failed to build participant merge input")

    def _selected_source_id_column() -> str:
        mapping_entries = mapping.get("mappings") if isinstance(mapping, dict) else None
        if not isinstance(mapping_entries, dict):
            return "participant_id"

        for spec in mapping_entries.values():
            if not isinstance(spec, dict):
                continue
            standard_variable = str(spec.get("standard_variable") or "").strip()
            if standard_variable != "participant_id":
                continue
            source_column = str(spec.get("source_column") or "").strip()
            if source_column:
                return source_column
        return "participant_id"

    def _repeated_row_conflict_columns(message_items: list[str]) -> list[str]:
        prefix = "Multiple rows per participant had differing values;"
        for item in message_items:
            text = str(item or "").strip()
            if prefix not in text:
                continue
            if "for:" not in text:
                return []
            columns_text = text.split("for:", 1)[1].strip()
            if not columns_text:
                return []
            return [
                column.strip()
                for column in columns_text.split(",")
                if column.strip()
            ]
        return []

    def _repeated_row_conflict_error_text(
        source_id_column: str,
        conflict_columns: list[str],
    ) -> str:
        conflict_columns_text = (
            f" Conflicting selected columns: {', '.join(conflict_columns)}."
            if conflict_columns
            else ""
        )
        return (
            "Selected input data has non-unique values for the selected ID column "
            f"'{source_id_column}' (normalized to participant_id)."
            f"{conflict_columns_text} "
            "Ensure each participant has one consistent value per selected merge column before merging. "
            "Tip: If this started after using Add More Columns, remove the listed conflicting column(s) "
            "or make repeated source rows consistent for those columns."
        )

    has_repeated_row_conflicts = any(
        "Multiple rows per participant had differing values" in str(message)
        for message in messages
    )

    session_resolution_payload: dict[str, Any] = {
        "session_column": "",
        "candidates": [],
        "decisions": {},
        "unresolved_columns": [],
        "intra_session_conflicts": [],
    }

    if has_repeated_row_conflicts:
        source_id_column = _selected_source_id_column()
        conflict_columns = _repeated_row_conflict_columns(messages)

        if not conflict_columns:
            raise ValueError(
                _repeated_row_conflict_error_text(source_id_column, conflict_columns)
            )

        file_ext = source_path.suffix.lower()
        kind_map = {
            ".xlsx": "xlsx",
            ".xls": "xlsx",
            ".csv": "csv",
            ".tsv": "tsv",
            ".txt": "tsv",
            ".sav": "sav",
            ".rds": "rds",
            ".rdata": "rdata",
            ".rda": "rdata",
        }
        kind = kind_map.get(file_ext, "csv")
        separator_value = None if (separator or "auto") == "auto" else separator
        try:
            source_result = _read_tabular_file(
                source_path,
                kind=kind,
                separator=separator_value,
                sheet=sheet,
            )
        except Exception:
            raise ValueError(
                _repeated_row_conflict_error_text(source_id_column, conflict_columns)
            )

        source_df = source_result.df.copy()
        source_columns = [str(column) for column in source_df.columns]
        if source_id_column not in source_columns:
            raise ValueError(
                _repeated_row_conflict_error_text(source_id_column, conflict_columns)
            )

        preferred_session_column = ""
        if isinstance(session_resolution_decisions, dict):
            for raw_decision in session_resolution_decisions.values():
                if not isinstance(raw_decision, dict):
                    continue
                preferred_session_column = str(
                    raw_decision.get("session_column") or ""
                ).strip()
                if preferred_session_column:
                    break

        session_column = _find_session_column_name(
            source_columns,
            preferred=preferred_session_column,
        )
        if not session_column:
            raise ValueError(
                _repeated_row_conflict_error_text(source_id_column, conflict_columns)
            )

        source_df["_participant_id"] = source_df[source_id_column].map(
            ParticipantsConverter._normalize_participant_id
        )
        source_df["_session_value"] = source_df[session_column].map(
            _normalize_session_value
        )

        available_sessions = _sorted_session_values(
            {
                str(value).strip()
                for value in source_df["_session_value"].tolist()
                if str(value).strip()
            }
        )
        if not available_sessions:
            raise ValueError(
                _repeated_row_conflict_error_text(source_id_column, conflict_columns)
            )

        decisions_payload = (
            session_resolution_decisions
            if isinstance(session_resolution_decisions, dict)
            else {}
        )
        normalized_decisions: dict[str, dict[str, str]] = {}
        unresolved_columns: list[str] = []
        intra_session_conflicts: list[dict[str, Any]] = []
        candidates: list[dict[str, Any]] = []
        output_columns = [str(column) for column in output_df.columns]

        for standard_column in conflict_columns:
            source_column = _resolve_source_column_for_standard_variable(
                mapping,
                standard_column,
            )
            if not source_column and standard_column in source_columns:
                source_column = standard_column

            decision_entry = _normalize_session_resolution_decision_entry(
                decisions_payload.get(standard_column)
            )
            normalized_decisions[standard_column] = {
                "action": decision_entry["action"],
                "session": _normalize_session_value(decision_entry["session"]),
            }

            candidate: dict[str, Any] = {
                "column": standard_column,
                "source_column": source_column,
                "session_column": session_column,
                "available_actions": [
                    "pick_session",
                    "pick_latest_session",
                    "split_sessions",
                ],
                "available_sessions": available_sessions,
                "selected_action": decision_entry["action"],
                "selected_session": _normalize_session_value(decision_entry["session"]),
                "generated_columns": [],
            }

            if not source_column or source_column not in source_columns:
                unresolved_columns.append(standard_column)
                candidates.append(candidate)
                continue

            value_sets: dict[str, dict[str, set[str]]] = {}
            for row in source_df.to_dict(orient="records"):
                participant_id = str(row.get("_participant_id") or "").strip()
                session_value = str(row.get("_session_value") or "").strip()
                raw_value = row.get(source_column)
                if not participant_id or not session_value or _is_missing_participant_value(raw_value):
                    continue

                text_value = str(raw_value).strip()
                if not text_value:
                    continue

                value_sets.setdefault(participant_id, {}).setdefault(
                    session_value, set()
                ).add(text_value)

            value_by_pid_session: dict[str, dict[str, str]] = {}
            for participant_id, sessions_map in value_sets.items():
                for session_value, values_set in sessions_map.items():
                    if len(values_set) > 1:
                        intra_session_conflicts.append(
                            {
                                "column": standard_column,
                                "participant_id": participant_id,
                                "session": session_value,
                                "values": sorted(values_set),
                            }
                        )
                    value_by_pid_session.setdefault(participant_id, {})[
                        session_value
                    ] = sorted(values_set)[0]

            action = decision_entry["action"]
            selected_session = _normalize_session_value(decision_entry["session"])
            if action == "pick_session":
                if not selected_session or selected_session not in available_sessions:
                    unresolved_columns.append(standard_column)
                    candidates.append(candidate)
                    continue

                candidate["selected_action"] = "pick_session"
                candidate["selected_session"] = selected_session

                output_df[standard_column] = output_df["participant_id"].map(
                    lambda pid: value_by_pid_session.get(
                        str(pid or "").strip(), {}
                    ).get(selected_session, "n/a")
                )
                candidates.append(candidate)
                continue

            if action == "pick_latest_session":
                latest_session = available_sessions[-1] if available_sessions else ""
                if not latest_session:
                    unresolved_columns.append(standard_column)
                    candidates.append(candidate)
                    continue

                candidate["selected_action"] = "pick_latest_session"
                candidate["selected_session"] = latest_session
                normalized_decisions[standard_column]["session"] = latest_session

                output_df[standard_column] = output_df["participant_id"].map(
                    lambda pid: value_by_pid_session.get(
                        str(pid or "").strip(), {}
                    ).get(latest_session, "n/a")
                )
                candidates.append(candidate)
                continue

            if action == "split_sessions":
                generated_columns: list[str] = []
                for session_value in available_sessions:
                    base_column_name = (
                        f"{standard_column}@ses-{_sanitize_session_token(session_value)}"
                    )
                    resolved_column_name = _unique_column_name(
                        base_column_name,
                        output_columns + generated_columns,
                    )
                    generated_columns.append(resolved_column_name)
                    output_df[resolved_column_name] = output_df["participant_id"].map(
                        lambda pid, _session=session_value: value_by_pid_session.get(
                            str(pid or "").strip(), {}
                        ).get(_session, "n/a")
                    )

                if standard_column in output_df.columns:
                    output_df = output_df.drop(columns=[standard_column])
                output_columns = [
                    column for column in output_columns if column != standard_column
                ] + generated_columns

                candidate["selected_action"] = "split_sessions"
                candidate["generated_columns"] = generated_columns
                candidates.append(candidate)
                continue

            unresolved_columns.append(standard_column)
            candidates.append(candidate)

        blocking_columns = {item.get("column") for item in intra_session_conflicts}
        unresolved_columns.extend(
            sorted(
                str(column)
                for column in blocking_columns
                if str(column or "").strip()
            )
        )

        # Preserve stable column order with participant_id first.
        ordered_columns = [
            "participant_id",
            *[
                column
                for column in output_df.columns
                if str(column) != "participant_id"
            ],
        ]
        output_df = output_df.loc[:, [col for col in ordered_columns if col in output_df.columns]]

        session_resolution_payload = {
            "session_column": session_column,
            "candidates": candidates,
            "decisions": normalized_decisions,
            "unresolved_columns": sorted(set(unresolved_columns)),
            "intra_session_conflicts": intra_session_conflicts,
        }

    if output_df.empty:
        raise ValueError("Converted participant merge input is empty")

    return output_df, messages, session_resolution_payload


def _build_merged_participants_schema(
    existing_schema: dict[str, Any],
    *,
    merged_columns: list[str],
    neurobagel_schema: dict | None = None,
    log_callback: ParticipantLogCallback | None = None,
) -> tuple[dict[str, Any], list[str], int]:
    merged_schema: dict[str, Any] = dict(existing_schema)
    schema_fields_added: list[str] = []

    neurobagel_merged = 0
    if neurobagel_schema:
        merged_schema, neurobagel_merged = merge_neurobagel_schema_for_columns(
            merged_schema,
            neurobagel_schema,
            merged_columns,
            log_callback=log_callback,
        )

    if "participant_id" not in merged_schema:
        merged_schema["participant_id"] = {}
        schema_fields_added.append("participant_id")

    for column in merged_columns:
        if column in merged_schema:
            field_schema = merged_schema.get(column)
            if not isinstance(field_schema, dict):
                merged_schema[column] = {}
                field_schema = merged_schema[column]
            if "Description" not in field_schema:
                field_schema["Description"] = (
                    "Unique participant identifier"
                    if column == "participant_id"
                    else f"Participant {column}"
                )
            continue

        merged_schema[column] = {}
        schema_fields_added.append(column)
        merged_schema[column]["Description"] = (
            "Unique participant identifier"
            if column == "participant_id"
            else f"Participant {column}"
        )

    participant_id_schema = merged_schema.get("participant_id")
    if (
        isinstance(participant_id_schema, dict)
        and "Description" not in participant_id_schema
    ):
        participant_id_schema["Description"] = "Unique participant identifier"

    return merged_schema, schema_fields_added, neurobagel_merged


def _create_backup(path: Path) -> str | None:
    if not path.exists():
        return None
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    backup_path = path.with_name(f"{path.name}.bak-{timestamp}")
    shutil.copy2(path, backup_path)
    return str(backup_path)


def _plan_participants_merge(
    project_root: Path,
    source_file: str | Path,
    mapping: dict[str, Any],
    *,
    separator: str | None = None,
    sheet: str | int = 0,
    preview_limit: int = 20,
    neurobagel_schema: dict | None = None,
    harmonization_decisions: dict[str, Any] | None = None,
    session_resolution_decisions: dict[str, Any] | None = None,
    log_callback: ParticipantLogCallback | None = None,
    include_all_conflicts: bool = False,
) -> tuple[dict[str, Any], pd.DataFrame, dict[str, Any]]:
    resolved_root = project_root.expanduser().resolve()
    source_path = Path(source_file).expanduser().resolve()
    existing_df = _load_existing_participants_table(resolved_root)
    existing_schema = _load_existing_participants_schema(resolved_root)
    incoming_df, messages, session_resolution_payload = _build_participants_merge_input(
        resolved_root,
        source_path,
        mapping,
        separator=separator,
        sheet=sheet,
        session_resolution_decisions=session_resolution_decisions,
        log_callback=log_callback,
    )

    existing_columns = [str(col) for col in existing_df.columns]
    incoming_columns = [str(col) for col in incoming_df.columns]
    full_columns = existing_columns + [
        column for column in incoming_columns if column not in existing_columns
    ]
    new_columns = [
        column
        for column in incoming_columns
        if column != "participant_id" and column not in existing_columns
    ]
    shared_columns = [
        column
        for column in incoming_columns
        if column != "participant_id" and column in existing_columns
    ]

    existing_rows = existing_df.to_dict(orient="records")
    incoming_rows = incoming_df.to_dict(orient="records")
    existing_ids = [str(row["participant_id"]).strip() for row in existing_rows]
    incoming_ids = [str(row["participant_id"]).strip() for row in incoming_rows]
    existing_id_set = set(existing_ids)
    incoming_id_set = set(incoming_ids)

    matched_ids = sorted(existing_id_set & incoming_id_set)
    new_participant_ids = sorted(incoming_id_set - existing_id_set)
    existing_only_ids = sorted(existing_id_set - incoming_id_set)

    existing_rows_by_id = {
        str(row.get("participant_id") or "").strip(): row for row in existing_rows
    }
    incoming_rows_by_id = {
        str(row.get("participant_id") or "").strip(): row for row in incoming_rows
    }
    inferred_code_maps = _infer_low_cardinality_code_equivalence_maps(
        existing_rows_by_id,
        incoming_rows_by_id,
        matched_ids=matched_ids,
        shared_columns=shared_columns,
    )

    user_harmonization_decisions = (
        harmonization_decisions if isinstance(harmonization_decisions, dict) else {}
    )
    applied_harmonization_decisions: dict[str, dict[str, str]] = {}
    harmonization_candidates: list[dict[str, Any]] = []
    keep_both_target_columns: dict[str, str] = {}
    harmonize_to_existing_columns: set[str] = set()
    harmonize_to_incoming_columns: set[str] = set()

    for column in sorted(inferred_code_maps):
        map_data = inferred_code_maps.get(column) or {}
        incoming_to_existing_map = map_data.get("incoming_to_existing")
        existing_to_incoming_map = map_data.get("existing_to_incoming")
        incoming_display = map_data.get("incoming_display")
        existing_display = map_data.get("existing_display")

        if not isinstance(incoming_to_existing_map, dict) or not isinstance(
            existing_to_incoming_map, dict
        ):
            continue
        if not isinstance(incoming_display, dict):
            incoming_display = {}
        if not isinstance(existing_display, dict):
            existing_display = {}

        action, requested_new_column = _normalize_harmonization_decision_entry(
            user_harmonization_decisions.get(column)
        )

        resolved_new_column = ""
        if action == "keep_both":
            candidate = str(requested_new_column or "").strip()
            if not candidate or candidate == column or candidate in full_columns:
                candidate = _next_available_participant_column_name(
                    column,
                    existing_columns=full_columns,
                )
            resolved_new_column = candidate
            keep_both_target_columns[column] = resolved_new_column
            if resolved_new_column not in full_columns:
                full_columns.append(resolved_new_column)
            if resolved_new_column not in new_columns:
                new_columns.append(resolved_new_column)

        if action == "use_incoming":
            harmonize_to_incoming_columns.add(column)
        else:
            harmonize_to_existing_columns.add(column)

        applied_harmonization_decisions[column] = {
            "action": action,
            "new_column": resolved_new_column,
        }

        mapping_pairs: list[dict[str, str]] = []
        for incoming_code, existing_code in sorted(incoming_to_existing_map.items()):
            incoming_label = str(incoming_display.get(incoming_code, incoming_code))
            existing_label = str(existing_display.get(existing_code, existing_code))
            mapping_pairs.append(
                {
                    "incoming_value": _canonical_display_text(
                        incoming_label,
                        incoming_display,
                    ),
                    "existing_value": _canonical_display_text(
                        existing_label,
                        existing_display,
                    ),
                }
            )

        harmonization_candidates.append(
            {
                "column": column,
                "available_actions": ["keep_existing", "use_incoming", "keep_both"],
                "selected_action": action,
                "selected_new_column": resolved_new_column,
                "default_new_column": _next_available_participant_column_name(
                    column,
                    existing_columns=full_columns,
                ),
                "matched_pair_count": int(map_data.get("pair_count") or 0),
                "mapping_pairs": mapping_pairs,
            }
        )

    merged_by_id: dict[str, dict[str, Any]] = {}
    for row in existing_rows:
        participant_id = str(row["participant_id"]).strip()
        merged_by_id[participant_id] = {
            str(column): row.get(column) for column in full_columns
        }
        merged_by_id[participant_id]["participant_id"] = participant_id

    fill_actions: list[dict[str, str]] = []
    conflicts: list[dict[str, str]] = []
    fillable_value_count = 0
    conflict_count = 0
    auto_resolved_equivalent_count = 0

    for row in incoming_rows:
        participant_id = str(row["participant_id"]).strip()
        incoming_values = {str(column): row.get(column) for column in incoming_columns}

        if participant_id not in merged_by_id:
            new_row = {column: "n/a" for column in full_columns}
            new_row["participant_id"] = participant_id
            for column in incoming_columns:
                if column == "participant_id":
                    continue
                incoming_text = _participant_value_text(incoming_values.get(column))
                new_row[column] = incoming_text
                keep_both_column = keep_both_target_columns.get(column)
                if keep_both_column:
                    new_row[keep_both_column] = incoming_text
            merged_by_id[participant_id] = new_row
            continue

        merged_row = merged_by_id[participant_id]
        for column in incoming_columns:
            if column == "participant_id":
                continue

            incoming_value = incoming_values.get(column)
            existing_value = merged_row.get(column)
            keep_both_column = keep_both_target_columns.get(column)

            if column not in existing_columns:
                merged_row[column] = _participant_value_text(incoming_value)
                continue

            if keep_both_column and not _is_missing_participant_value(incoming_value):
                merged_row[keep_both_column] = _participant_value_text(incoming_value)

            if _is_missing_participant_value(
                existing_value
            ) and not _is_missing_participant_value(incoming_value):
                next_value = _participant_value_text(incoming_value)
                merged_row[column] = next_value
                fillable_value_count += 1
                if len(fill_actions) < preview_limit:
                    fill_actions.append(
                        {
                            "participant_id": participant_id,
                            "column": column,
                            "existing_value": _participant_value_text(existing_value),
                            "incoming_value": next_value,
                        }
                    )
                continue

            if _is_missing_participant_value(
                existing_value
            ) or _is_missing_participant_value(incoming_value):
                continue

            existing_text = str(existing_value).strip()
            incoming_text = str(incoming_value).strip()
            if existing_text != incoming_text:
                if _participant_values_numeric_equivalent(existing_text, incoming_text):
                    auto_resolved_equivalent_count += 1
                    continue

                map_data = inferred_code_maps.get(column) or {}
                incoming_to_existing_map = map_data.get("incoming_to_existing")
                if not isinstance(incoming_to_existing_map, dict):
                    incoming_to_existing_map = {}

                mapped_existing_text = incoming_to_existing_map.get(
                    _normalized_participant_text(incoming_text)
                )
                if mapped_existing_text and mapped_existing_text == _normalized_participant_text(
                    existing_text
                ):
                    auto_resolved_equivalent_count += 1
                    decision = (applied_harmonization_decisions.get(column) or {}).get(
                        "action", "keep_existing"
                    )
                    if decision == "use_incoming":
                        merged_row[column] = incoming_text
                    continue

                conflict_count += 1
                if include_all_conflicts or len(conflicts) < preview_limit:
                    conflicts.append(
                        {
                            "participant_id": participant_id,
                            "column": column,
                            "existing_value": existing_text,
                            "incoming_value": incoming_text,
                        }
                    )

    for column in harmonize_to_existing_columns:
        map_data = inferred_code_maps.get(column) or {}
        incoming_to_existing_map = map_data.get("incoming_to_existing")
        existing_display = map_data.get("existing_display")
        if not isinstance(incoming_to_existing_map, dict) or not isinstance(
            existing_display, dict
        ):
            continue

        for row in merged_by_id.values():
            current_value = row.get(column)
            if _is_missing_participant_value(current_value):
                continue

            current_text = str(current_value).strip()
            normalized = _normalized_participant_text(current_text)
            target_code = incoming_to_existing_map.get(normalized, normalized)
            if target_code in existing_display:
                row[column] = str(existing_display[target_code]).strip()

    for column in harmonize_to_incoming_columns:
        map_data = inferred_code_maps.get(column) or {}
        existing_to_incoming_map = map_data.get("existing_to_incoming")
        incoming_display = map_data.get("incoming_display")
        if not isinstance(existing_to_incoming_map, dict) or not isinstance(
            incoming_display, dict
        ):
            continue

        for row in merged_by_id.values():
            current_value = row.get(column)
            if _is_missing_participant_value(current_value):
                continue

            current_text = str(current_value).strip()
            normalized = _normalized_participant_text(current_text)
            target_code = existing_to_incoming_map.get(normalized, normalized)
            if target_code in incoming_display:
                row[column] = str(incoming_display[target_code]).strip()

    for source_column, incoming_column in keep_both_target_columns.items():
        map_data = inferred_code_maps.get(source_column) or {}
        incoming_display = map_data.get("incoming_display")
        if not isinstance(incoming_display, dict):
            incoming_display = {}

        for row in merged_by_id.values():
            current_value = row.get(incoming_column)
            if _is_missing_participant_value(current_value):
                continue

            current_text = str(current_value).strip()
            normalized = _normalized_participant_text(current_text)
            if normalized in incoming_display:
                row[incoming_column] = str(incoming_display[normalized]).strip()

    merged_rows: list[dict[str, Any]] = []
    for participant_id in existing_ids:
        row = merged_by_id[participant_id]
        for column in new_columns:
            if column not in row or _is_missing_participant_value(row.get(column)):
                row[column] = "n/a"
        merged_rows.append({column: row.get(column) for column in full_columns})

    for participant_id in new_participant_ids:
        row = merged_by_id[participant_id]
        merged_rows.append({column: row.get(column) for column in full_columns})

    merged_df = pd.DataFrame(merged_rows, columns=full_columns)
    merged_df = merged_df.where(pd.notna(merged_df), None)

    merged_schema, schema_fields_added, neurobagel_merged = (
        _build_merged_participants_schema(
            existing_schema,
            merged_columns=full_columns,
            neurobagel_schema=neurobagel_schema,
            log_callback=log_callback,
        )
    )

    preview_df = merged_df.head(max(int(preview_limit or 20), 1)).astype(object)
    preview_df = preview_df.where(preview_df.notna(), None)

    session_resolution_required = bool(
        (session_resolution_payload.get("unresolved_columns") or [])
        or (session_resolution_payload.get("intra_session_conflicts") or [])
    )

    payload: dict[str, Any] = {
        "status": "success",
        "project_root": str(resolved_root),
        "input": str(source_path),
        "participants_tsv": str(resolved_root / "participants.tsv"),
        "participants_json": str(resolved_root / "participants.json"),
        "columns": full_columns,
        "existing_participant_count": len(existing_ids),
        "incoming_participant_count": len(incoming_ids),
        "merged_participant_count": len(merged_df),
        "matched_participant_count": len(matched_ids),
        "new_participant_count": len(new_participant_ids),
        "existing_only_participant_count": len(existing_only_ids),
        "new_columns": new_columns,
        "shared_columns": shared_columns,
        "fillable_value_count": fillable_value_count,
        "auto_resolved_equivalent_count": auto_resolved_equivalent_count,
        "conflict_count": conflict_count,
        "can_apply": conflict_count == 0 and not session_resolution_required,
        "requires_conflict_resolution": conflict_count > 0,
        "session_resolution_required": session_resolution_required,
        "session_resolution_column": session_resolution_payload.get("session_column") or "",
        "session_resolution_candidates": session_resolution_payload.get("candidates") or [],
        "session_resolution_decisions": session_resolution_payload.get("decisions") or {},
        "session_resolution_unresolved_columns": session_resolution_payload.get("unresolved_columns") or [],
        "session_resolution_blockers": session_resolution_payload.get("intra_session_conflicts") or [],
        "matched_participants": matched_ids[:preview_limit],
        "new_participants": new_participant_ids[:preview_limit],
        "existing_only_participants": existing_only_ids[:preview_limit],
        "fill_actions": fill_actions,
        "conflicts": conflicts,
        "preview_rows": preview_df.to_dict(orient="records"),
        "column_values": _collect_preview_column_values(merged_df),
        "messages": messages,
        "schema_fields_added": schema_fields_added,
        "neurobagel_fields_merged": neurobagel_merged,
        "harmonization_candidates": harmonization_candidates,
        "harmonization_decisions": applied_harmonization_decisions,
    }
    return payload, merged_df, merged_schema


def preview_participants_merge(
    project_root: Path,
    source_file: str | Path,
    mapping: dict[str, Any],
    *,
    separator: str | None = None,
    sheet: str | int = 0,
    preview_limit: int = 20,
    neurobagel_schema: dict | None = None,
    harmonization_decisions: dict[str, Any] | None = None,
    session_resolution_decisions: dict[str, Any] | None = None,
    log_callback: ParticipantLogCallback | None = None,
) -> dict[str, Any]:
    """Preview a safe merge from a source table into an existing participants.tsv."""
    payload, _merged_df, _merged_schema = _plan_participants_merge(
        project_root,
        source_file,
        mapping,
        separator=separator,
        sheet=sheet,
        preview_limit=preview_limit,
        neurobagel_schema=neurobagel_schema,
        harmonization_decisions=harmonization_decisions,
        session_resolution_decisions=session_resolution_decisions,
        log_callback=log_callback,
    )
    payload["action"] = "preview"
    return payload


def apply_participants_merge(
    project_root: Path,
    source_file: str | Path,
    mapping: dict[str, Any],
    *,
    separator: str | None = None,
    sheet: str | int = 0,
    preview_limit: int = 20,
    neurobagel_schema: dict | None = None,
    harmonization_decisions: dict[str, Any] | None = None,
    session_resolution_decisions: dict[str, Any] | None = None,
    log_callback: ParticipantLogCallback | None = None,
    create_backups: bool = True,
) -> dict[str, Any]:
    """Apply a conflict-free merge into participants.tsv and participants.json."""
    payload, merged_df, merged_schema = _plan_participants_merge(
        project_root,
        source_file,
        mapping,
        separator=separator,
        sheet=sheet,
        preview_limit=preview_limit,
        neurobagel_schema=neurobagel_schema,
        harmonization_decisions=harmonization_decisions,
        session_resolution_decisions=session_resolution_decisions,
        log_callback=log_callback,
    )

    if not bool(payload.get("can_apply")):
        raise ValueError(
            "Merge preview is not apply-ready. Resolve conflicts and session-resolution blockers before applying."
        )

    resolved_root = project_root.expanduser().resolve()
    participants_tsv = resolved_root / "participants.tsv"
    participants_json = resolved_root / "participants.json"

    backup_files: list[str] = []
    if create_backups:
        for file_path in (participants_tsv, participants_json):
            backup_path = _create_backup(file_path)
            if backup_path:
                backup_files.append(backup_path)

    merged_df.to_csv(participants_tsv, sep="\t", index=False)
    participants_json.write_text(
        json.dumps(merged_schema, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    payload.update(
        {
            "action": "apply",
            "files_written": [str(participants_tsv), str(participants_json)],
            "backup_files": backup_files,
        }
    )
    return payload


def export_participants_merge_conflicts_csv(
    project_root: Path,
    source_file: str | Path,
    mapping: dict[str, Any],
    *,
    separator: str | None = None,
    sheet: str | int = 0,
    preview_limit: int = 20,
    neurobagel_schema: dict | None = None,
    harmonization_decisions: dict[str, Any] | None = None,
    session_resolution_decisions: dict[str, Any] | None = None,
    log_callback: ParticipantLogCallback | None = None,
) -> str:
    """Return a CSV report with every blocking merge conflict."""
    payload, _merged_df, _merged_schema = _plan_participants_merge(
        project_root,
        source_file,
        mapping,
        separator=separator,
        sheet=sheet,
        preview_limit=preview_limit,
        neurobagel_schema=neurobagel_schema,
        harmonization_decisions=harmonization_decisions,
        session_resolution_decisions=session_resolution_decisions,
        log_callback=log_callback,
        include_all_conflicts=True,
    )

    output = io.StringIO(newline="")
    fieldnames = [
        "participant_id",
        "column",
        "existing_value",
        "incoming_value",
        "recommended_action",
    ]
    writer = csv.DictWriter(output, fieldnames=fieldnames)
    writer.writeheader()

    for conflict in cast(list[dict[str, Any]], payload.get("conflicts", [])):
        writer.writerow(
            {
                "participant_id": str(conflict.get("participant_id") or "").strip(),
                "column": str(conflict.get("column") or "").strip(),
                "existing_value": str(conflict.get("existing_value") or "").strip(),
                "incoming_value": str(conflict.get("incoming_value") or "").strip(),
                "recommended_action": (
                    "Review manually and update either the existing participants.tsv "
                    "or the incoming source file before re-running merge"
                ),
            }
        )

    return output.getvalue()


__all__ = [
    "ParticipantLogCallback",
    "apply_participants_merge",
    "collect_dataset_participants",
    "convert_dataset_participants",
    "describe_participants_workflow",
    "export_participants_merge_conflicts_csv",
    "merge_neurobagel_schema_for_columns",
    "normalize_participant_mapping",
    "preview_dataset_participants",
    "preview_participants_merge",
    "resolve_participant_mapping_target",
    "save_participant_mapping",
]
