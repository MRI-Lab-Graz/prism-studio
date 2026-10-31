"""What is in a survey data file before converting it: its columns, the likely ID column, and the sessions and
runs it holds. One implementation for Studio's ID/session/run column pickers and `prism_tools survey detect-columns`."""

from __future__ import annotations

from pathlib import Path

PRISM_ID_COLUMNS = ("participant_id", "participantid", "prism_participant_id", "prismparticipantid")


def _distinct_values(df, column: str) -> list[str]:
    return sorted(str(v).strip() for v in df[column].dropna().unique() if str(v).strip())


def detect_columns(
    path: Path,
    *,
    separator: str | None = None,
    session_column_override: str = "",
    run_column_override: str = "",
) -> dict:
    """Columns of a .lsa/.xlsx/.csv/.tsv file with the suggested ID column and detected sessions and runs.
    A manually chosen session/run column (not matching the auto-detect names) still gets its values read.
    Raises ValueError with a readable message when the file cannot be read."""
    from src.converters.file_reader import expected_delimiter_for_suffix, normalize_separator_option, read_tabular_file
    from src.converters.id_detection import detect_id_column, has_prismmeta_columns

    suffix = path.suffix.lower()
    if suffix == ".lsa":
        from src.converters.limesurvey import parse_lsa_responses

        try:
            df, _, _ = parse_lsa_responses(str(path))
        except Exception as exc:
            raise ValueError(f"Failed to read .lsa: {exc}") from exc
    elif suffix in (".xlsx", ".csv", ".tsv"):
        df = read_tabular_file(
            path,
            kind="xlsx" if suffix == ".xlsx" else suffix.lstrip("."),
            separator=expected_delimiter_for_suffix(suffix, normalize_separator_option(separator)),
        ).df
    else:
        return {"columns": [], "suggested_id_column": None}

    columns = list(df.columns)
    has_prismmeta = has_prismmeta_columns(columns)
    result = {
        "columns": columns,
        "suggested_id_column": detect_id_column(
            columns, "lsa" if suffix == ".lsa" else "xlsx", has_prismmeta=has_prismmeta
        ),
        "is_prism_data": has_prismmeta or any(c.lower() in PRISM_ID_COLUMNS for c in columns),
        "session_column": None,
        "detected_sessions": [],
        "run_column": None,
        "detected_runs": [],
    }
    lower_to_col = {str(c).strip().lower(): str(c).strip() for c in columns}
    for kind, names, override in (
        ("session", ("session", "ses", "visit", "timepoint"), session_column_override),
        ("run", ("run", "run_id", "run_number", "run_nr"), run_column_override),
    ):
        found = next((lower_to_col[n] for n in names if n in lower_to_col), None)
        result[f"{kind}_column"] = found
        values_column = override if override in df.columns else found
        if values_column and values_column in df.columns:
            result[f"detected_{kind}s"] = _distinct_values(df, values_column)
    return result
