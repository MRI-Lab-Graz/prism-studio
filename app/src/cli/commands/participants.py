"""Participants-related prism_tools command handlers."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import cast

import pandas as pd

from src.converters.file_reader import read_tabular_file
from src.converters.id_detection import detect_id_column, has_prismmeta_columns
from src.participants_backend import (
    convert_dataset_participants,
    merge_neurobagel_schema_for_columns,
    preview_dataset_participants,
    save_participant_mapping,
)
from src.participants_converter import ParticipantsConverter
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
    source_fmt = "lsa" if suffix == ".lsa" else "xlsx"
    explicit_id = str(explicit or "").strip() or None
    return detect_id_column(
        list(df.columns),
        source_fmt,
        explicit_id_column=explicit_id,
        has_prismmeta=has_prismmeta_columns(list(df.columns)),
    )


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
    detected = _auto_detect_id_column(df, input_path.suffix.lower(), None)
    columns = [str(c) for c in df.columns]

    payload = {
        "id_found": bool(detected),
        "id_column": detected,
        "columns": columns,
    }
    if bool(getattr(args, "json", False)):
        print(json.dumps(payload, ensure_ascii=False))
    else:
        print(f"Detected ID column: {detected or '<none>'}")
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
            print(f"Project: {project_text}")
            print(f"Participants: {payload['total_participants']}")
            print(
                "Sample: "
                + ", ".join(str(item) for item in payload.get("participants", []))
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
        print("Error: Could not auto-detect ID column.")
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
            for entry in payload.get("log", []):
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

    converter = ParticipantsConverter(project_root)
    mapping = None
    for candidate in participants_mapping_candidates(project_root):
        if candidate.exists() and candidate.is_file():
            mapping = converter.load_mapping_from_file(candidate)
            if mapping:
                break

    if not mapping:
        separator_option = normalize_separator_option(getattr(args, "separator", None))
        df = _load_participant_table(
            input_path,
            sheet=_parse_sheet(getattr(args, "sheet", 0)),
            separator_option=separator_option,
        )
        id_column = _auto_detect_id_column(
            df,
            input_path.suffix.lower(),
            getattr(args, "id_column", None),
        )
        if not id_column:
            print("Error: Could not auto-detect ID column and no mapping was found.")
            sys.exit(2)

        mapping = {
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

        for col in ["age", "sex", "gender", "education", "handedness", "group"]:
            if col in {str(c).lower(): str(c) for c in df.columns}:
                src = {str(c).lower(): str(c) for c in df.columns}[col]
                mapping["mappings"][col] = {
                    "source_column": src,
                    "standard_variable": col,
                    "type": "string",
                }

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
                f"Saved {Path(result['mapping_file']).name}. "
                "This mapping is applied when you run Extract & Convert."
            ),
        },
    )
    if bool(getattr(args, "json", False)):
        _emit_json(payload)
    else:
        print(payload["message"])
        print(f"Wrote: {payload['file_path']}")
