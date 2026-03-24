"""Participants-related prism_tools command handlers."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd

from src.converters.id_detection import detect_id_column, has_prismmeta_columns
from src.participants_converter import ParticipantsConverter
from src.participants_paths import participants_mapping_candidates
from src.web.blueprints.conversion_participants_helpers import (
    _collect_default_participant_columns,
)
from src.web.blueprints.conversion_utils import (
    expected_delimiter_for_suffix,
    normalize_separator_option,
    read_tabular_dataframe_robust,
)


def _resolve_project_root(project_arg: str | None) -> Path:
    project_text = str(project_arg or "").strip()
    if not project_text:
        return Path.cwd()

    project_path = Path(project_text).expanduser().resolve()
    if project_path.is_file():
        return project_path.parent
    return project_path


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
    if suffix == ".xlsx":
        return pd.read_excel(input_path, sheet_name=sheet, dtype=str)
    if suffix in {".csv", ".tsv"}:
        return read_tabular_dataframe_robust(
            input_path,
            expected_delimiter=expected_delimiter_for_suffix(suffix, separator_option),
            dtype=str,
        )
    if suffix == ".lsa":
        from src.converters.survey import _read_lsa_as_dataframe

        return _read_lsa_as_dataframe(input_path)
    raise ValueError("Supported formats: .xlsx, .csv, .tsv, .lsa")


def _auto_detect_id_column(df: pd.DataFrame, suffix: str, explicit: str | None) -> str | None:
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

    payload = {
        "id_found": bool(detected),
        "id_column": detected,
        "columns": [str(c) for c in df.columns],
    }
    if bool(getattr(args, "json", False)):
        print(json.dumps(payload, ensure_ascii=False))
    else:
        print(f"Detected ID column: {detected or '<none>'}")
        print("Columns:", ", ".join(payload["columns"]))


def cmd_participants_preview(args) -> None:
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
        print(json.dumps(payload, ensure_ascii=False))
    else:
        print(f"Project: {project_root}")
        print(f"Input:   {input_path}")
        print(f"ID col:  {id_column}")
        print(f"Rows:    {len(df)}")
        print(f"Columns: {', '.join(output_columns)}")


def cmd_participants_convert(args) -> None:
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

    payload = {
        "success": bool(success),
        "project_root": str(project_root),
        "output": str(output_path),
        "rows": int(len(df_out)) if df_out is not None else 0,
        "messages": messages,
    }
    if bool(getattr(args, "json", False)):
        print(json.dumps(payload, ensure_ascii=False))
    else:
        for message in messages:
            print(message)
        if success:
            print(f"Wrote: {output_path}")

    if not success:
        sys.exit(1)
