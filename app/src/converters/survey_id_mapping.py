"""Subject ID mapping helpers for survey conversion."""

from __future__ import annotations

from pathlib import Path


def _apply_subject_id_mapping(
    *,
    df,
    res_id_col: str,
    id_map: dict[str, str] | None,
    id_map_file,
    suggest_id_matches_fn,
    missing_id_mapping_error_cls,
):
    """Apply optional subject ID mapping and return updated dataframe/ID column."""
    warnings: list[str] = []
    if not id_map:
        return df, res_id_col, warnings

    df = df.copy()

    all_cols_lower = {str(c).strip().lower(): str(c) for c in df.columns}
    preferred_order = [
        res_id_col,
        "participant_id",
        "code",
        "token",
        "id",
        "subject",
        "sub_id",
        "participant",
    ]
    candidate_cols: list[str] = []
    seen = set()
    for name in preferred_order:
        if not name:
            continue
        if name in df.columns and name not in seen:
            candidate_cols.append(name)
            seen.add(name)
            continue
        lower = str(name).strip().lower()
        if lower in all_cols_lower:
            actual = all_cols_lower[lower]
            if actual not in seen:
                candidate_cols.append(actual)
                seen.add(actual)

    id_map_lower = {str(k).strip().lower(): v for k, v in id_map.items()}

    def _score_column(col: str) -> tuple[int, float]:
        col_values = df[col].astype(str).str.strip()
        unique_vals = set(col_values.unique())
        matches = len([v for v in unique_vals if str(v).strip().lower() in id_map_lower])
        total = len(unique_vals) if unique_vals else 1
        ratio = matches / total if total else 0.0
        return matches, ratio

    print(f"[PRISM DEBUG] ID map keys sample: {list(id_map_lower.keys())[:5]} ...")
    print(f"[PRISM DEBUG] Dataframe columns: {list(df.columns)}")
    print(f"[PRISM DEBUG] Candidate ID columns: {candidate_cols}")

    best_col = res_id_col
    best_matches, best_ratio = _score_column(res_id_col)
    print(f"[PRISM DEBUG] Score {res_id_col}: matches={best_matches}, ratio={best_ratio:.3f}")
    for c in candidate_cols:
        matches, ratio = _score_column(c)
        print(f"[PRISM DEBUG] Score {c}: matches={matches}, ratio={ratio:.3f}")
        if (matches > best_matches) or (matches == best_matches and ratio > best_ratio):
            best_col = c
            best_matches, best_ratio = matches, ratio

    if best_matches == 0 and "code" in candidate_cols:
        best_col = "code"
        print("[PRISM DEBUG] No matches; falling back to 'code' column")

    if best_col != res_id_col:
        warnings.append(
            f"Selected id_column '{best_col}' based on ID map overlap ({best_matches} matches)."
        )
        res_id_col = best_col

    print(
        f"[PRISM DEBUG] Selected ID column: {res_id_col}; unique sample: {df[res_id_col].astype(str).unique()[:10]}"
    )

    df[res_id_col] = df[res_id_col].astype(str).str.strip()
    ids_in_data = set(df[res_id_col].unique())
    missing = sorted([i for i in ids_in_data if str(i).strip().lower() not in id_map_lower])
    if missing:
        sample = ", ".join(missing[:20])
        more = "" if len(missing) <= 20 else f" (+{len(missing) - 20} more)"
        map_keys = list(id_map.keys())
        suggestions = suggest_id_matches_fn(missing, map_keys)
        raise missing_id_mapping_error_cls(
            missing,
            suggestions,
            f"ID mapping incomplete: {len(missing)} IDs from data are missing in the mapping: {sample}{more}.",
        )

    df[res_id_col] = df[res_id_col].map(
        lambda x: id_map_lower.get(str(x).strip().lower(), id_map.get(str(x).strip(), x))
    )
    warnings.append(
        f"Applied subject ID mapping from {Path(id_map_file).name} ({len(id_map)} entries)."
    )

    return df, res_id_col, warnings
