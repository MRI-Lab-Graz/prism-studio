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

ParticipantLogCallback = Callable[[str, str], None]

_PARTICIPANT_ID_PATTERN = re.compile(r"(sub-[A-Za-z0-9]+)")
_MISSING_TOKENS = {"", "n/a", "na", "nan", "none"}


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
    log_callback: ParticipantLogCallback | None = None,
) -> tuple[pd.DataFrame, list[str]]:
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

    if any(
        "Multiple rows per participant had differing values" in str(message)
        for message in messages
    ):
        raise ValueError(
            "Source participant table contains conflicting repeated participant rows. "
            "Resolve those conflicts before merging."
        )

    if output_df.empty:
        raise ValueError("Converted participant merge input is empty")

    return output_df, messages


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
    log_callback: ParticipantLogCallback | None = None,
    include_all_conflicts: bool = False,
) -> tuple[dict[str, Any], pd.DataFrame, dict[str, Any]]:
    resolved_root = project_root.expanduser().resolve()
    source_path = Path(source_file).expanduser().resolve()
    existing_df = _load_existing_participants_table(resolved_root)
    existing_schema = _load_existing_participants_schema(resolved_root)
    incoming_df, messages = _build_participants_merge_input(
        resolved_root,
        source_path,
        mapping,
        separator=separator,
        sheet=sheet,
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

    merged_by_id: dict[str, dict[str, Any]] = {}
    for row in existing_rows:
        participant_id = str(row["participant_id"]).strip()
        merged_by_id[participant_id] = {
            str(column): row.get(column) for column in full_columns
        }
        merged_by_id[participant_id]["participant_id"] = participant_id

    matched_ids = sorted(existing_id_set & incoming_id_set)
    new_participant_ids = sorted(incoming_id_set - existing_id_set)
    existing_only_ids = sorted(existing_id_set - incoming_id_set)

    fill_actions: list[dict[str, str]] = []
    conflicts: list[dict[str, str]] = []
    fillable_value_count = 0
    conflict_count = 0

    for row in incoming_rows:
        participant_id = str(row["participant_id"]).strip()
        incoming_values = {str(column): row.get(column) for column in incoming_columns}

        if participant_id not in merged_by_id:
            new_row = {column: "n/a" for column in full_columns}
            new_row["participant_id"] = participant_id
            for column in incoming_columns:
                if column == "participant_id":
                    continue
                new_row[column] = _participant_value_text(incoming_values.get(column))
            merged_by_id[participant_id] = new_row
            continue

        merged_row = merged_by_id[participant_id]
        for column in incoming_columns:
            if column == "participant_id":
                continue

            incoming_value = incoming_values.get(column)
            existing_value = merged_row.get(column)

            if column not in existing_columns:
                merged_row[column] = _participant_value_text(incoming_value)
                continue

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
        "conflict_count": conflict_count,
        "can_apply": conflict_count == 0,
        "requires_conflict_resolution": conflict_count > 0,
        "matched_participants": matched_ids[:preview_limit],
        "new_participants": new_participant_ids[:preview_limit],
        "existing_only_participants": existing_only_ids[:preview_limit],
        "fill_actions": fill_actions,
        "conflicts": conflicts,
        "preview_rows": preview_df.to_dict(orient="records"),
        "messages": messages,
        "schema_fields_added": schema_fields_added,
        "neurobagel_fields_merged": neurobagel_merged,
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
        log_callback=log_callback,
    )

    if int(payload.get("conflict_count") or 0) > 0:
        raise ValueError(
            "Merge preview contains conflicting values. Resolve them before applying."
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
