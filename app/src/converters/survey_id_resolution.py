"""ID/session column resolution helpers for survey conversion."""

from __future__ import annotations


def _resolve_id_and_session_cols(
    df,
    id_column: str | None,
    session_column: str | None,
    participants_template: dict | None = None,
    source_format: str = "xlsx",
    has_prismmeta: bool = False,
) -> tuple[str, str | None]:
    """Determine participant ID and session columns from dataframe."""
    from .id_detection import detect_id_column, IdColumnNotDetectedError

    resolved_id = detect_id_column(
        df_columns=list(df.columns),
        source_format=source_format,
        explicit_id_column=id_column,
        has_prismmeta=has_prismmeta,
    )
    if not resolved_id:
        raise IdColumnNotDetectedError(list(df.columns), source_format)

    def _find_col(candidates: set[str]) -> str | None:
        lower_map = {str(c).strip().lower(): str(c).strip() for c in df.columns}
        for c in candidates:
            if c in lower_map:
                return lower_map[c]
        return None

    resolved_ses: str | None
    if session_column:
        if session_column not in df.columns:
            raise ValueError(
                f"session_column '{session_column}' not found in input columns"
            )
        resolved_ses = session_column
    else:
        resolved_ses = _find_col({"session", "ses", "visit", "timepoint"})

    return str(resolved_id), resolved_ses
