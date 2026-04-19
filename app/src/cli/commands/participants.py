"""Participants-related prism_tools command handlers."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import cast

import pandas as pd

from src.converters.file_reader import read_tabular_file
from src.participants_backend import (
    apply_participants_merge,
    convert_dataset_participants,
    export_participants_merge_conflicts_csv,
    merge_neurobagel_schema_for_columns,
    preview_dataset_participants,
    preview_participants_merge,
    save_participant_mapping,
)
from src.participants_converter import ParticipantsConverter
from src.participants_id_selection import resolve_participants_id_selection
from src.participants_paths import participants_mapping_candidates
from src.web.blueprints.conversion_participants_helpers import (
    _collect_default_participant_columns,
)
from src.web.blueprints.conversion_utils import (
    expected_delimiter_for_suffix,
    normalize_separator_option,
)


def _resolve_project_root(project_arg: str | None) -> Path:
    project_text = str(project_arg or "").strip()
    if not project_text:
        return Path.cwd()

    project_path = Path(project_text).expanduser().resolve()
    if project_path.is_file():
        return project_path.parent
    return project_path


def _emit_json(payload: dict[str, object]) -> None:
    print(json.dumps(payload, ensure_ascii=False))


def _parse_neurobagel_schema(raw_value: str | None) -> dict:
    value = str(raw_value or "").strip()
    if not value:
        return {}
    try:
        payload = json.loads(value)
    except json.JSONDecodeError as exc:
        raise ValueError("Invalid JSON provided for --neurobagel-schema") from exc
    if not isinstance(payload, dict):
        raise ValueError("--neurobagel-schema must decode to a JSON object")
    return payload


def _parse_sheet(value: str | int | None):
    sheet = str(value if value is not None else "0").strip() or "0"
    return int(sheet) if sheet.isdigit() else sheet


def _load_participant_table(
    input_path: Path,
    *,
    sheet,
    separator_option: str,
) -> pd.DataFrame:
    suffix = input_path.suffix.lower()
    if suffix in {".xlsx", ".csv", ".tsv"}:
        kind = "xlsx" if suffix == ".xlsx" else suffix.lstrip(".")
        result = read_tabular_file(
            input_path,
            kind=kind,
            sheet=sheet,
            separator=expected_delimiter_for_suffix(suffix, separator_option),
        )
        return result.df
    if suffix == ".lsa":
        from src.converters.survey import _read_lsa_as_dataframe

        return _read_lsa_as_dataframe(input_path)
    raise ValueError("Supported formats: .xlsx, .csv, .tsv, .lsa")


def _auto_detect_id_column(
    df: pd.DataFrame, suffix: str, explicit: str | None
) -> str | None:
    id_resolution = resolve_participants_id_selection(
        list(df.columns),
        suffix,
        explicit_id_column=explicit,
    )
    resolved = str(id_resolution.get("resolved_id_column") or "").strip()
    if resolved:
        return resolved

    explicit_id = str(explicit or "").strip()
    if not explicit_id and bool(id_resolution.get("id_selection_required")):
        return None

    suggested = str(id_resolution.get("suggested_id_column") or "").strip()
    return suggested or None


def _build_auto_participant_mapping(df: pd.DataFrame, id_column: str) -> dict[str, object]:
    lowered_columns = {str(c).lower(): str(c) for c in df.columns}
    mapping: dict[str, object] = {
        "version": "1.0",
        "description": "Auto-generated participants mapping",
        "mappings": {
            "participant_id": {
                "source_column": id_column,
                "standard_variable": "participant_id",
                "type": "string",
            }
        },
    }

    mappings = cast(dict[str, dict[str, str]], mapping["mappings"])
    for col in ["age", "sex", "gender", "education", "handedness", "group"]:
        if col not in lowered_columns:
            continue
        source_column = lowered_columns[col]
        mappings[col] = {
            "source_column": source_column,
            "standard_variable": col,
            "type": "string",
        }

    return mapping


def _load_saved_participant_mapping(project_root: Path) -> dict | None:
    converter = ParticipantsConverter(project_root)
    for candidate in participants_mapping_candidates(project_root):
        if not (candidate.exists() and candidate.is_file()):
            continue
        mapping = converter.load_mapping_from_file(candidate)
        if mapping:
            return mapping
    return None


def _resolve_participant_mapping(
    project_root: Path,
    input_path: Path,
    *,
    sheet,
    separator_option: str,
    explicit_id_column: str | None,
) -> dict[str, object]:
    mapping = _load_saved_participant_mapping(project_root)
    if mapping:
        return mapping

    df = _load_participant_table(
        input_path,
        sheet=sheet,
        separator_option=separator_option,
    )
    id_column = _auto_detect_id_column(
        df,
        input_path.suffix.lower(),
        explicit_id_column,
    )
    if not id_column:
        raise ValueError(
            "Could not determine ID column and no mapping was found. Use --id-column to select it explicitly."
        )
    return _build_auto_participant_mapping(df, id_column)


def cmd_participants_detect_id(args) -> None:
    input_path = Path(args.input).expanduser().resolve()
    if not input_path.exists():
        print(f"Error: input file not found: {input_path}")
        sys.exit(1)

    separator_option = normalize_separator_option(getattr(args, "separator", None))
    df = _load_participant_table(
        input_path,
        sheet=_parse_sheet(getattr(args, "sheet", 0)),
        separator_option=separator_option,
    )
    columns = [str(c) for c in df.columns]
    id_resolution = resolve_participants_id_selection(columns, input_path.suffix.lower())
    detected = (
        str(id_resolution.get("resolved_id_column") or "").strip()
        or str(id_resolution.get("suggested_id_column") or "").strip()
        or None
    )

    payload = {
        "id_found": bool(detected),
        "id_column": detected,
        "source_id_column": id_resolution.get("source_id_column"),
        "suggested_id_column": id_resolution.get("suggested_id_column"),
        "participant_id_column": id_resolution.get("participant_id_column"),
        "participant_id_found": bool(id_resolution.get("participant_id_found")),
        "id_selection_required": bool(id_resolution.get("id_selection_required")),
        "columns": columns,
    }
    if bool(getattr(args, "json", False)):
        print(json.dumps(payload, ensure_ascii=False))
    else:
        print(f"Detected ID column: {detected or '<none>'}")
        if payload["id_selection_required"]:
            print("Manual ID selection required (use --id-column).")
        print("Columns:", ", ".join(columns))


def cmd_participants_preview(args) -> None:
    mode = str(getattr(args, "mode", "file") or "file").strip().lower() or "file"
    if mode == "dataset":
        project_text = str(getattr(args, "project", "") or "").strip()
        if not project_text:
            print("Error: --project is required for dataset preview mode.")
            sys.exit(2)

        try:
            payload = preview_dataset_participants(
                _resolve_project_root(project_text),
                extract_from_survey=bool(getattr(args, "extract_from_survey", True)),
                extract_from_biometrics=bool(
                    getattr(args, "extract_from_biometrics", True)
                ),
            )
        except ValueError as exc:
            if bool(getattr(args, "json", False)):
                _emit_json({"error": str(exc)})
            else:
                print(f"Error: {exc}")
            sys.exit(2)

        if bool(getattr(args, "json", False)):
            _emit_json(payload)
        else:
            sample_items = payload.get("participants")
            sample_participants = sample_items if isinstance(sample_items, list) else []
            print(f"Project: {project_text}")
            print(f"Participants: {payload['total_participants']}")
            print(
                "Sample: "
                + ", ".join(str(item) for item in sample_participants)
            )
        return

    if not getattr(args, "input", None):
        print("Error: --input is required for file preview mode.")
        sys.exit(2)

    input_path = Path(args.input).expanduser().resolve()
    if not input_path.exists():
        print(f"Error: input file not found: {input_path}")
        sys.exit(1)

    project_root = _resolve_project_root(getattr(args, "project", None))
    separator_option = normalize_separator_option(getattr(args, "separator", None))
    sheet = _parse_sheet(getattr(args, "sheet", 0))
    df = _load_participant_table(
        input_path,
        sheet=sheet,
        separator_option=separator_option,
    )

    id_column = _auto_detect_id_column(
        df,
        input_path.suffix.lower(),
        getattr(args, "id_column", None),
    )
    if not id_column:
        print("Error: Could not determine ID column. Use --id-column to select it explicitly.")
        sys.exit(2)

    output_columns = _collect_default_participant_columns(df, id_column)

    converter = ParticipantsConverter(project_root)
    mapping = None
    for candidate in participants_mapping_candidates(project_root):
        if candidate.exists() and candidate.is_file():
            mapping = converter.load_mapping_from_file(candidate)
            if mapping:
                break

    additional_columns: list[str] = []
    if isinstance(mapping, dict) and isinstance(mapping.get("mappings"), dict):
        for map_spec in mapping["mappings"].values():
            if not isinstance(map_spec, dict):
                continue
            source_col = str(map_spec.get("source_column") or "").strip()
            if source_col and source_col in df.columns:
                additional_columns.append(source_col)

    for col in additional_columns:
        if col not in output_columns:
            output_columns.append(col)

    preview_limit = int(getattr(args, "preview_limit", 20) or 20)
    preview_df = df[output_columns].head(preview_limit).astype(object)
    preview_df = preview_df.where(preview_df.notna(), None)

    payload = {
        "status": "success",
        "project_root": str(project_root),
        "input": str(input_path),
        "id_column": id_column,
        "columns": [str(c) for c in output_columns],
        "participant_count": len(df),
        "preview_rows": preview_df.to_dict(orient="records"),
    }
    if bool(getattr(args, "json", False)):
        _emit_json(payload)
    else:
        print(f"Project: {project_root}")
        print(f"Input:   {input_path}")
        print(f"ID col:  {id_column}")
        print(f"Rows:    {len(df)}")
        print(f"Columns: {', '.join(output_columns)}")


def cmd_participants_convert(args) -> None:
    mode = str(getattr(args, "mode", "file") or "file").strip().lower() or "file"
    if mode == "dataset":
        project_text = str(getattr(args, "project", "") or "").strip()
        if not project_text:
            payload = cast(
                dict[str, object],
                {
                    "error": "--project is required for dataset convert mode.",
                    "log": [],
                },
            )
            if bool(getattr(args, "json", False)):
                _emit_json(payload)
            else:
                print(f"Error: {payload['error']}")
            sys.exit(2)

        project_root = _resolve_project_root(project_text)
        project_root.mkdir(parents=True, exist_ok=True)
        participants_tsv = project_root / "participants.tsv"
        participants_json = project_root / "participants.json"
        existing_files = []
        if participants_tsv.exists():
            existing_files.append(str(participants_tsv))
        if participants_json.exists():
            existing_files.append(str(participants_json))
        if existing_files and not bool(getattr(args, "force", False)):
            payload = cast(
                dict[str, object],
                {
                    "error": "Participant files already exist. Use --force to overwrite them.",
                    "existing_files": existing_files,
                    "log": [],
                },
            )
            if bool(getattr(args, "json", False)):
                _emit_json(payload)
            else:
                print(f"Error: {payload['error']}")
            sys.exit(2)

        log_entries: list[dict[str, str]] = []

        def log_msg(level: str, message: str) -> None:
            log_entries.append({"level": level, "message": message})

        try:
            log_msg("INFO", "Extracting participant data from dataset...")
            payload = convert_dataset_participants(
                project_root,
                neurobagel_schema=_parse_neurobagel_schema(
                    getattr(args, "neurobagel_schema", None)
                ),
                extract_from_survey=bool(getattr(args, "extract_from_survey", True)),
                extract_from_biometrics=bool(
                    getattr(args, "extract_from_biometrics", True)
                ),
                log_callback=log_msg,
            )
            payload["log"] = log_entries
        except ValueError as exc:
            payload = cast(dict[str, object], {"error": str(exc), "log": log_entries})
            if bool(getattr(args, "json", False)):
                _emit_json(payload)
            else:
                print(f"Error: {exc}")
            sys.exit(2)

        if bool(getattr(args, "json", False)):
            _emit_json(cast(dict[str, object], payload))
        else:
            log_items = payload.get("log")
            log_entries = log_items if isinstance(log_items, list) else []
            for entry in log_entries:
                if not isinstance(entry, dict):
                    continue
                message = str(entry.get("message") or "").strip()
                if message:
                    print(message)
        return

    if not getattr(args, "input", None):
        print("Error: --input is required for file convert mode.")
        sys.exit(2)

    input_path = Path(args.input).expanduser().resolve()
    if not input_path.exists():
        print(f"Error: input file not found: {input_path}")
        sys.exit(1)

    project_root = _resolve_project_root(getattr(args, "project", None))
    project_root.mkdir(parents=True, exist_ok=True)
    output_path = project_root / "participants.tsv"

    separator_option = normalize_separator_option(getattr(args, "separator", None))
    try:
        mapping = _resolve_participant_mapping(
            project_root,
            input_path,
            sheet=_parse_sheet(getattr(args, "sheet", 0)),
            separator_option=separator_option,
            explicit_id_column=getattr(args, "id_column", None),
        )
    except ValueError as exc:
        print(f"Error: {exc}")
        sys.exit(2)

    converter = ParticipantsConverter(project_root)

    if output_path.exists() and not bool(getattr(args, "force", False)):
        print(
            f"Error: {output_path} already exists. Use --force to overwrite.",
        )
        sys.exit(2)

    success, df_out, messages = converter.convert_participant_data(
        input_path,
        mapping,
        output_file=output_path,
    )

    neurobagel_schema = _parse_neurobagel_schema(
        getattr(args, "neurobagel_schema", None)
    )
    participants_json_path = project_root / "participants.json"
    if success and df_out is not None:
        participants_json_data = {
            col: {"Description": f"Participant {col}"} for col in df_out.columns
        }
        if neurobagel_schema:
            participants_json_data, _ = merge_neurobagel_schema_for_columns(
                participants_json_data,
                neurobagel_schema,
                list(df_out.columns),
            )
        participants_json_path.write_text(
            json.dumps(participants_json_data, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

    payload = cast(
        dict[str, object],
        {
            "success": bool(success),
            "project_root": str(project_root),
            "output": str(output_path),
            "metadata_output": str(participants_json_path) if success else None,
            "rows": int(len(df_out)) if df_out is not None else 0,
            "messages": messages,
        },
    )
    if bool(getattr(args, "json", False)):
        _emit_json(payload)
    else:
        for message in messages:
            print(message)
        if success:
            print(f"Wrote: {output_path}")
            print(f"Wrote: {participants_json_path}")

    if not success:
        sys.exit(1)


def cmd_participants_merge(args) -> None:
    if not getattr(args, "input", None):
        print("Error: --input is required.")
        sys.exit(2)

    project_text = str(getattr(args, "project", "") or "").strip()
    if not project_text:
        print("Error: --project is required.")
        sys.exit(2)

    input_path = Path(args.input).expanduser().resolve()
    if not input_path.exists():
        print(f"Error: input file not found: {input_path}")
        sys.exit(1)

    project_root = _resolve_project_root(project_text)
    separator_option = normalize_separator_option(getattr(args, "separator", None))
    sheet = _parse_sheet(getattr(args, "sheet", 0))
    preview_limit = int(getattr(args, "preview_limit", 20) or 20)
    separator = expected_delimiter_for_suffix(input_path.suffix.lower(), separator_option)
    export_conflicts_csv = bool(getattr(args, "conflicts_csv", False))

    if export_conflicts_csv and bool(getattr(args, "apply", False)):
        print("Error: --conflicts-csv cannot be combined with --apply.")
        sys.exit(2)

    if export_conflicts_csv and bool(getattr(args, "json", False)):
        print("Error: --conflicts-csv cannot be combined with --json.")
        sys.exit(2)

    try:
        mapping = _resolve_participant_mapping(
            project_root,
            input_path,
            sheet=sheet,
            separator_option=separator_option,
            explicit_id_column=getattr(args, "id_column", None),
        )
    except ValueError as exc:
        payload = cast(dict[str, object], {"error": str(exc), "log": []})
        if bool(getattr(args, "json", False)):
            _emit_json(payload)
        else:
            print(f"Error: {payload['error']}")
        sys.exit(2)

    neurobagel_schema = _parse_neurobagel_schema(
        getattr(args, "neurobagel_schema", None)
    )

    if export_conflicts_csv:
        try:
            csv_text = export_participants_merge_conflicts_csv(
                project_root,
                input_path,
                mapping,
                separator=separator,
                sheet=sheet,
                preview_limit=preview_limit,
                neurobagel_schema=neurobagel_schema,
            )
        except ValueError as exc:
            print(f"Error: {exc}")
            sys.exit(2)

        sys.stdout.write(csv_text)
        return

    try:
        preview_payload = preview_participants_merge(
            project_root,
            input_path,
            mapping,
            separator=separator,
            sheet=sheet,
            preview_limit=preview_limit,
            neurobagel_schema=neurobagel_schema,
        )
    except ValueError as exc:
        payload = cast(dict[str, object], {"error": str(exc), "log": []})
        if bool(getattr(args, "json", False)):
            _emit_json(payload)
        else:
            print(f"Error: {payload['error']}")
        sys.exit(2)

    if not bool(getattr(args, "apply", False)):
        if bool(getattr(args, "json", False)):
            _emit_json(preview_payload)
        else:
            print(f"Project: {project_root}")
            print(f"Input:   {input_path}")
            print(
                "Matched participants: "
                + str(preview_payload.get("matched_participant_count", 0))
            )
            print(
                "New participants:     "
                + str(preview_payload.get("new_participant_count", 0))
            )
            print(
                "Existing-only:        "
                + str(preview_payload.get("existing_only_participant_count", 0))
            )
            print(
                "Fillable values:      "
                + str(preview_payload.get("fillable_value_count", 0))
            )
            print("Conflicts:            " + str(preview_payload.get("conflict_count", 0)))
            new_columns = preview_payload.get("new_columns", [])
            if new_columns:
                print("New columns:          " + ", ".join(str(col) for col in new_columns))
            for conflict in cast(list[dict[str, object]], preview_payload.get("conflicts", [])):
                print(
                    "Conflict: "
                    + f"{conflict.get('participant_id')} {conflict.get('column')} "
                    + f"existing={conflict.get('existing_value')} incoming={conflict.get('incoming_value')}"
                )
        return

    if not bool(preview_payload.get("can_apply")):
        error_payload = dict(preview_payload)
        error_payload["error"] = (
            "Merge preview contains conflicting values. Resolve them before applying."
        )
        if bool(getattr(args, "json", False)):
            _emit_json(cast(dict[str, object], error_payload))
        else:
            print(f"Error: {error_payload['error']}")
            for conflict in cast(list[dict[str, object]], error_payload.get("conflicts", [])):
                print(
                    "Conflict: "
                    + f"{conflict.get('participant_id')} {conflict.get('column')} "
                    + f"existing={conflict.get('existing_value')} incoming={conflict.get('incoming_value')}"
                )
        sys.exit(2)

    try:
        apply_payload = apply_participants_merge(
            project_root,
            input_path,
            mapping,
            separator=separator,
            sheet=sheet,
            preview_limit=preview_limit,
            neurobagel_schema=neurobagel_schema,
        )
    except ValueError as exc:
        payload = cast(dict[str, object], {"error": str(exc), "log": []})
        if bool(getattr(args, "json", False)):
            _emit_json(payload)
        else:
            print(f"Error: {payload['error']}")
        sys.exit(2)

    if bool(getattr(args, "json", False)):
        _emit_json(apply_payload)
    else:
        print(f"Project: {project_root}")
        print(f"Input:   {input_path}")
        print("Merged participants.tsv successfully.")
        print(
            "Participants: "
            + str(apply_payload.get("merged_participant_count", 0))
            + " total"
        )
        backup_files = cast(list[str], apply_payload.get("backup_files", []))
        for backup_file in backup_files:
            print(f"Backup: {backup_file}")


def cmd_participants_save_mapping(args) -> None:
    mapping_text = str(getattr(args, "mapping_json", "") or "").strip()
    if not mapping_text:
        payload = cast(
            dict[str, object], {"error": "--mapping-json is required.", "log": []}
        )
        if bool(getattr(args, "json", False)):
            _emit_json(payload)
        else:
            print(f"Error: {payload['error']}")
        sys.exit(2)

    try:
        mapping = json.loads(mapping_text)
    except json.JSONDecodeError as exc:
        payload = cast(
            dict[str, object],
            {
                "error": f"Invalid JSON provided for --mapping-json: {exc}",
                "log": [],
            },
        )
        if bool(getattr(args, "json", False)):
            _emit_json(payload)
        else:
            print(f"Error: {payload['error']}")
        sys.exit(2)

    if not isinstance(mapping, dict):
        payload = cast(
            dict[str, object],
            {"error": "--mapping-json must decode to a JSON object.", "log": []},
        )
        if bool(getattr(args, "json", False)):
            _emit_json(payload)
        else:
            print(f"Error: {payload['error']}")
        sys.exit(2)

    project_text = str(getattr(args, "project", "") or "").strip()
    library_text = str(getattr(args, "library_path", "") or "").strip()

    try:
        result = save_participant_mapping(
            mapping,
            project_root=_resolve_project_root(project_text) if project_text else None,
            library_path=library_text or None,
        )
    except ValueError as exc:
        payload = cast(dict[str, object], {"error": str(exc), "log": []})
        if bool(getattr(args, "json", False)):
            _emit_json(payload)
        else:
            print(f"Error: {payload['error']}")
        sys.exit(2)

    payload = cast(
        dict[str, object],
        {
            "status": "success",
            "file_path": str(result["mapping_file"]),
            "library_source": str(result["library_source"]),
            "message": (
                f"Saved {Path(cast(str | Path, result['mapping_file'])).name}. "
                "This mapping is applied when you run Extract & Convert."
            ),
        },
    )
    if bool(getattr(args, "json", False)):
        _emit_json(payload)
    else:
        print(payload["message"])
        print(f"Wrote: {payload['file_path']}")
