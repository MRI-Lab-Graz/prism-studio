"""Session and duplicate-ID handling helpers for survey conversion."""

from __future__ import annotations


def _detect_sessions(*, df, res_ses_col: str | None) -> list[str]:
    """Detect session values from the selected session column."""
    detected_sessions: list[str] = []
    if res_ses_col:
        detected_sessions = sorted(
            [
                str(v).strip()
                for v in df[res_ses_col].dropna().unique()
                if str(v).strip()
            ]
        )
        print(f"[PRISM INFO] Sessions detected in {res_ses_col}: {detected_sessions}")
    else:
        print(
            f"[PRISM DEBUG] No session column detected (res_ses_col is None). Available columns: {list(df.columns)[:20]}"
        )
    return detected_sessions


def _filter_rows_by_selected_session(
    *,
    df,
    res_ses_col: str | None,
    session: str | None,
    duplicate_handling: str,
    detected_sessions: list[str],
):
    """Filter rows according to selected session policy."""
    rows_before_filter = len(df)
    if res_ses_col and session and session != "all":
        session_normalized = str(session).strip()
        df_filtered = df[df[res_ses_col].astype(str).str.strip() == session_normalized]
        if len(df_filtered) == 0:
            raise ValueError(
                f"No rows found with session '{session}' in column '{res_ses_col}'. "
                f"Available values: {', '.join(detected_sessions if detected_sessions else ['none'])}"
            )
        df = df_filtered
        print(
            f"[PRISM INFO] Filtered {rows_before_filter} rows → {len(df)} rows for session '{session}'"
        )
    elif (
        res_ses_col
        and not session
        and detected_sessions
        and duplicate_handling == "error"
    ):
        first_session = detected_sessions[0]
        df_filtered = df[df[res_ses_col].astype(str).str.strip() == first_session]
        if len(df_filtered) > 0:
            df = df_filtered
            print(
                f"[PRISM INFO] Auto-filtering to first session '{first_session}' for preview ({rows_before_filter} rows → {len(df)} rows)"
            )
    elif session == "all" and res_ses_col:
        print(f"[PRISM INFO] Processing all sessions from '{res_ses_col}'")

    return df


def _handle_duplicate_ids(
    *,
    df,
    res_id_col: str,
    duplicate_handling: str,
    normalize_sub_fn,
) -> tuple[object, str | None, list[str]]:
    """Handle duplicate participant IDs according to duplicate_handling policy."""
    warnings: list[str] = []
    res_ses_col_override: str | None = None

    normalized_ids = df[res_id_col].astype(str).map(normalize_sub_fn)
    if normalized_ids.duplicated().any():
        dup_ids = sorted(set(normalized_ids[normalized_ids.duplicated()]))
        dup_count = len(dup_ids)

        if duplicate_handling == "error":
            raise ValueError(
                f"Duplicate participant_id values after normalization: {', '.join(dup_ids[:5])}"
            )
        elif duplicate_handling == "keep_first":
            df = df[~normalized_ids.duplicated(keep="first")].copy()
            warnings.append(
                f"Duplicate IDs found ({dup_count} duplicates). Kept first occurrence for: {', '.join(dup_ids[:5])}"
            )
        elif duplicate_handling == "keep_last":
            df = df[~normalized_ids.duplicated(keep="last")].copy()
            warnings.append(
                f"Duplicate IDs found ({dup_count} duplicates). Kept last occurrence for: {', '.join(dup_ids[:5])}"
            )
        elif duplicate_handling == "sessions":
            df = df.copy()
            df["_dup_session_num"] = df.groupby(normalized_ids.values).cumcount() + 1
            res_ses_col_override = "_dup_session_num"
            warnings.append(
                f"Duplicate IDs found ({dup_count} duplicates). Created multiple sessions for: {', '.join(dup_ids[:5])}"
            )

    return df, res_ses_col_override, warnings
