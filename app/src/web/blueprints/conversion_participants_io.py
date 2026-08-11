import re
import shutil
import tempfile
from pathlib import Path

from flask import Response, jsonify, request
from werkzeug.utils import secure_filename

from src.converters.file_reader import infer_tabular_kind, read_tabular_file

from .conversion_utils import (
    expected_delimiter_for_suffix as _shared_expected_delimiter_for_suffix,
)
from .conversion_utils import normalize_separator_option as _shared_normalize_separator

_SUPPORTED_PARTICIPANTS_UPLOAD_SUFFIXES = {
    ".xlsx",
    ".csv",
    ".tsv",
    ".sav",
    ".rds",
    ".rdata",
    ".rda",
    ".lsa",
}
_SUPPORTED_PARTICIPANTS_UPLOAD_MESSAGE = (
    "Supported formats: .xlsx, .csv, .tsv, .sav, .rds, .rdata, .rda, .lsa"
)


def _save_participants_upload_to_temp(
    *,
    uploaded_file,
    temp_prefix: str,
) -> dict[str, object]:
    source_file_path = (
        (request.form.get("source_file_path") or "").strip()
        or (request.args.get("source_file_path") or "").strip()
    )

    source_path: Path | None = None
    if uploaded_file and uploaded_file.filename:
        filename = secure_filename(uploaded_file.filename)
    elif source_file_path:
        source_path = Path(source_file_path).expanduser().resolve()
        if not source_path.exists() or not source_path.is_file():
            raise ValueError(f"File not found: {source_file_path}")
        filename = secure_filename(source_path.name)
    else:
        raise ValueError("Missing input file")

    suffix = Path(filename).suffix.lower()
    if suffix not in _SUPPORTED_PARTICIPANTS_UPLOAD_SUFFIXES:
        raise ValueError(_SUPPORTED_PARTICIPANTS_UPLOAD_MESSAGE)

    tmp_dir = tempfile.mkdtemp(prefix=temp_prefix)
    input_path = Path(tmp_dir) / filename
    if source_path is not None:
        shutil.copy2(source_path, input_path)
    else:
        uploaded_file.save(str(input_path))

    return {
        "tmp_dir": tmp_dir,
        "input_path": input_path,
        "filename": filename,
        "suffix": suffix,
    }


def _normalize_separator_option(value: str | None) -> str:
    return _shared_normalize_separator(value)


def _expected_delimiter_for_suffix(suffix: str, separator_option: str) -> str | None:
    return _shared_expected_delimiter_for_suffix(suffix, separator_option)


def _read_participants_input_table(
    *,
    input_path: Path,
    suffix: str,
    sheet_arg: str | int,
    separator_option: str,
):
    if suffix == ".lsa":
        from src.converters.survey import _read_lsa_as_dataframe

        return _read_lsa_as_dataframe(input_path)

    kind = infer_tabular_kind(input_path)
    if kind in {"xlsx", "csv", "tsv", "sav", "rds", "rdata"}:
        result = read_tabular_file(
            input_path,
            kind=kind,
            sheet=sheet_arg,
            separator=_expected_delimiter_for_suffix(suffix, separator_option),
        )
        return result.df

    raise ValueError(_SUPPORTED_PARTICIPANTS_UPLOAD_MESSAGE)


def _get_excel_sheet_metadata(input_path: Path) -> dict[str, object]:
    metadata: dict[str, object] = {
        "sheet_names": [],
        "non_empty_sheet_names": [],
        "non_empty_sheet_indexes": [],
    }

    try:
        import pandas as pd

        with pd.ExcelFile(input_path) as workbook:
            sheet_names = [str(name) for name in workbook.sheet_names]
            non_empty_sheet_names: list[str] = []
            non_empty_sheet_indexes: list[int] = []

            for index, sheet_name in enumerate(sheet_names):
                try:
                    sheet_df = workbook.parse(sheet_name=sheet_name, dtype=str)
                except Exception:
                    continue

                if sheet_df is not None and not sheet_df.empty:
                    non_empty_sheet_names.append(sheet_name)
                    non_empty_sheet_indexes.append(index)

        metadata["sheet_names"] = sheet_names
        metadata["non_empty_sheet_names"] = non_empty_sheet_names
        metadata["non_empty_sheet_indexes"] = non_empty_sheet_indexes
    except Exception:
        return metadata

    return metadata


def _resolve_participants_sheet_arg(
    *,
    input_path: Path,
    suffix: str,
    sheet_value: str | None,
    sheet_metadata: dict[str, object] | None = None,
) -> str | int:
    sheet_text = str(sheet_value or "").strip()
    if sheet_text:
        try:
            return int(sheet_text) if sheet_text.isdigit() else sheet_text
        except (ValueError, TypeError):
            return 0

    if suffix == ".xlsx":
        metadata = (
            sheet_metadata
            if isinstance(sheet_metadata, dict)
            else _get_excel_sheet_metadata(input_path)
        )
        non_empty_sheet_indexes = metadata.get("non_empty_sheet_indexes")
        if (
            isinstance(non_empty_sheet_indexes, list)
            and len(non_empty_sheet_indexes) > 0
        ):
            first_non_empty = non_empty_sheet_indexes[0]
            if isinstance(first_non_empty, int):
                return first_non_empty

    return 0


_TIME_STYLE_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("clock", re.compile(r"^\d{1,2}:\d{2}(?::\d{2})?$")),
    ("hours", re.compile(r"^\d+(?:\.\d+)?\s*h(?:ours?)?$", re.IGNORECASE)),
    (
        "minutes",
        re.compile(r"^\d+(?:\.\d+)?\s*m(?:in(?:ute)?s?)?$", re.IGNORECASE),
    ),
    ("seconds", re.compile(r"^\d+(?:\.\d+)?\s*s(?:ec(?:ond)?s?)?$", re.IGNORECASE)),
    ("numeric", re.compile(r"^\d+(?:\.\d+)?$")),
)


def _classify_time_style(value: str) -> str | None:
    text = str(value or "").strip()
    if not text:
        return None

    for style_name, pattern in _TIME_STYLE_PATTERNS:
        if pattern.match(text):
            return style_name

    return None


def _detect_mixed_time_style_columns(
    df, max_examples: int = 4, max_scanned_values: int = 250
) -> list[dict[str, object]]:
    """Find columns that mix multiple time-like formats, e.g. HH:MM and 2h."""
    issues: list[dict[str, object]] = []

    for col in df.columns:
        col_values = [
            str(v).strip()
            for v in df[col].dropna().astype(str).head(max_scanned_values)
            if str(v).strip()
        ]
        if len(col_values) < 2:
            continue

        style_set: set[str] = set()
        example_values: list[str] = []

        for value in col_values:
            style = _classify_time_style(value)
            if not style:
                continue
            style_set.add(style)
            if value not in example_values:
                example_values.append(value)

        if len(style_set) < 2:
            continue

        has_clock_like = "clock" in style_set
        has_unit_or_numeric = any(
            style in style_set for style in {"hours", "minutes", "seconds", "numeric"}
        )
        if not (has_clock_like and has_unit_or_numeric):
            continue

        issues.append(
            {
                "column": str(col),
                "detected_formats": sorted(style_set),
                "examples": example_values[:max_examples],
            }
        )

    return issues


def _format_mixed_time_style_message(
    mixed_columns: list[dict[str, object]],
) -> str:
    if not mixed_columns:
        return ""

    details: list[str] = []
    for issue in mixed_columns:
        column = str(issue.get("column") or "")
        examples_raw = issue.get("examples") or []
        examples = list(examples_raw) if isinstance(examples_raw, (list, tuple)) else []
        examples_text = ", ".join(f"'{str(v)}'" for v in examples[:4])
        if examples_text:
            details.append(f"{column} ({examples_text})")
        else:
            details.append(column)

    joined = "; ".join(details)
    return (
        "Detected mixed time formats in participant data: "
        f"{joined}. Please fix this manually in the source file before import. "
        "PRISM does not auto-convert mixed formats. Use exactly one format per "
        "affected column (recommended: all HH:MM or all numeric minutes) and "
        "avoid ranges/ambiguous values (for example '4-6h' or '10 30')."
    )


def _diagnose_preview_error(
    exc: Exception,
    df,
    input_path: "Path | None",
    suffix: "str | None",
    sheet_arg,
    separator_option: "str | None",
    preview_stage: "str | None",
) -> "tuple[Response, int]":
    """Build the error response for a failed /api/participants-preview request.

    Tries to detect mixed time-format columns (using df if already loaded,
    else by re-reading input_path) to give a more actionable error than the
    raw exception message.
    """
    diagnostic_columns: list[dict[str, object]] = []

    if df is not None:
        try:
            diagnostic_columns = _detect_mixed_time_style_columns(df)
        except Exception:
            diagnostic_columns = []

    if (
        not diagnostic_columns
        and input_path is not None
        and suffix in {".xlsx", ".csv", ".tsv", ".lsa"}
    ):
        try:
            diagnostic_df = _read_participants_input_table(
                input_path=input_path,
                suffix=suffix,
                sheet_arg=sheet_arg,
                separator_option=separator_option,
            )
            if diagnostic_df is not None:
                diagnostic_columns = _detect_mixed_time_style_columns(diagnostic_df)
        except Exception:
            diagnostic_columns = []

    if diagnostic_columns:
        mixed_time_message = _format_mixed_time_style_message(diagnostic_columns)
        return (
            jsonify(
                {
                    "error": mixed_time_message,
                    "error_code": "mixed_time_formats",
                    "problem_columns": diagnostic_columns,
                }
            ),
            400,
        )

    error_text = str(exc) or "Preview failed"
    error_type = exc.__class__.__name__
    stage_text = preview_stage or "unknown stage"

    if error_text.strip().lower() == "the string did not match the expected pattern.":
        error_text = (
            "Preview failed due to an invalid value pattern in the uploaded data "
            f"(stage: {stage_text}). Please check columns with timing/duration values "
            "for mixed formats and ambiguous tokens, then retry."
        )

    return (
        jsonify(
            {
                "error": error_text,
                "error_type": error_type,
                "error_stage": stage_text,
            }
        ),
        500,
    )
