"""Survey data processing: value normalization, column classification, and row validation.

This module consolidates logic for:
1. Normalizing survey item values (integers, strings, missing values).
2. Classifying and grouping columns (LimeSurvey system columns, run suffixes).
3. Processing and validating individual data rows against schemas.
"""

from __future__ import annotations

import re
from typing import Any


# -----------------------------------------------------------------------------
# Value Normalization
# -----------------------------------------------------------------------------


def _normalize_item_value(val: Any, *, missing_token: str) -> str:
    """Normalize a survey item value to a string representation."""
    # Local import to avoid hard dependency at module level if pandas is missing
    # (though usually pandas is required for the DF operations calling this)
    try:
        from pandas import isna
    except ImportError:
        def isna(x): return x is None

    if isna(val) or (isinstance(val, str) and str(val).strip() == ""):
        return missing_token
    if isinstance(val, bool):
        return str(val).lower()
    if isinstance(val, int):
        return str(int(val))
    if isinstance(val, float):
        if val.is_integer():
            return str(int(val))
        return str(val)
    return str(val)


# -----------------------------------------------------------------------------
# Column Classification & Run Parsing
# -----------------------------------------------------------------------------

# Patterns to detect run suffix in column names.
_RUN_SUFFIX_PATTERNS = [
    re.compile(r"^(.+)_run-?(\d+)$", re.IGNORECASE),  # BIDS: SWLS01_run-02
    re.compile(r"^(.+?)run(\d+)$", re.IGNORECASE),    # LimeSurvey: SWLS01run02
]

# LimeSurvey system columns - these are platform metadata
LIMESURVEY_SYSTEM_COLUMNS = {
    # Core system fields
    "id", "submitdate", "startdate", "datestamp", "lastpage", "startlanguage",
    "seed", "token", "ipaddr", "refurl",
    # Timing fields
    "interviewtime",
    # Other common fields
    "optout", "emailstatus", "attribute_1", "attribute_2", "attribute_3",
}

# Pattern for LimeSurvey group timing columns: groupTime123, grouptime456
_LS_TIMING_PATTERN = re.compile(r"^grouptime\d+$", re.IGNORECASE)


def _is_limesurvey_system_column(column_name: str) -> bool:
    """Check if a column is a LimeSurvey system/metadata column."""
    col_lower = column_name.strip().lower()

    if col_lower in LIMESURVEY_SYSTEM_COLUMNS:
        return True

    if _LS_TIMING_PATTERN.match(col_lower):
        return True

    if col_lower.startswith("duration_"):
        return True

    return False


def _extract_limesurvey_columns(df_columns: list[str]) -> tuple[list[str], list[str]]:
    """Separate LimeSurvey system columns from questionnaire columns."""
    ls_cols = []
    other_cols = []

    for col in df_columns:
        if _is_limesurvey_system_column(col):
            ls_cols.append(col)
        else:
            other_cols.append(col)

    return ls_cols, other_cols


def _parse_run_from_column(column_name: str) -> tuple[str, int | None]:
    """Parse run information from a column name."""
    stripped = column_name.strip()
    for pattern in _RUN_SUFFIX_PATTERNS:
        m = pattern.match(stripped)
        if m:
            base_name = m.group(1)
            run_num = int(m.group(2))
            return base_name, run_num
    return column_name, None


def _group_columns_by_run(columns: list[str]) -> dict[str, dict[int | None, list[str]]]:
    """Group columns by their base name and run number.
    
    Returns:
        Dict mapping base_name -> {run_number: [columns]}
    """
    grouped: dict[str, dict[int | None, list[str]]] = {}
    for col in columns:
        base_name, run_num = _parse_run_from_column(col)
        if base_name not in grouped:
            grouped[base_name] = {}
        if run_num not in grouped[base_name]:
            grouped[base_name][run_num] = []
        grouped[base_name][run_num].append(col)
    return grouped


# -----------------------------------------------------------------------------
# Row Processing & Validation
# -----------------------------------------------------------------------------


def _validate_survey_item_value(
    *,
    item_id: str,
    val: Any,
    item_schema: dict | None,
    sub_id: str,
    task: str,
    strict_levels: bool,
    items_using_tolerance: dict[str, set[str]],
    normalize_fn,
    is_missing_fn,
    find_matching_level_key_fn,
    missing_token: str,
) -> None:
    """Internal validation for a single survey item value."""
    if is_missing_fn(val) or not isinstance(item_schema, dict):
        return

    levels = item_schema.get("Levels")
    if not isinstance(levels, dict) or not levels:
        return

    v_str = normalize_fn(val)
    if v_str == missing_token:
        return

    if v_str in levels:
        return

    matched_key = find_matching_level_key_fn(v_str, levels)
    if matched_key is not None:
        return

    try:
        def _to_float(x):
            try:
                return float(str(x).strip())
            except (ValueError, TypeError, AttributeError):
                return None

        v_num = _to_float(v_str)
        min_v = _to_float(item_schema.get("MinValue"))
        max_v = _to_float(item_schema.get("MaxValue"))

        if v_num is not None and min_v is not None and max_v is not None:
            if min_v <= v_num <= max_v:
                return

        if not strict_levels:
            l_nums = [n for n in [_to_float(k) for k in levels.keys()] if n is not None]
            if len(l_nums) >= 2 and v_num is not None:
                if min(l_nums) <= v_num <= max(l_nums):
                    items_using_tolerance.setdefault(task, set()).add(item_id)
                    return
    except (ValueError, TypeError, AttributeError):
        pass

    allowed = ", ".join(sorted(levels.keys()))
    raise ValueError(
        f"Invalid value '{val}' for '{item_id}' (Sub: {sub_id}, Task: {task}). Expected: {allowed}"
    )


def _process_survey_row(
    *,
    row,
    df_cols,
    task: str,
    schema: dict,
    sub_id: str,
    strict_levels: bool,
    items_using_tolerance: dict[str, set[str]],
    is_missing_fn,
    normalize_val_fn,
    non_item_keys,
    missing_token: str,
    validate_item_fn,
) -> tuple[dict[str, str], int]:
    """Process a single task's data for one subject/session."""
    all_items = [k for k in schema.keys() if k not in non_item_keys]
    expected = [k for k in all_items if k not in schema.get("_aliases", {})]

    out: dict[str, str] = {}
    missing_count = 0

    for item_id in expected:
        candidates = [item_id] + schema.get("_reverse_aliases", {}).get(item_id, [])
        found_val = None
        found_col = None

        for cand in candidates:
            if cand in df_cols and not is_missing_fn(row[cand]):
                found_val = row[cand]
                found_col = cand
                break

        if found_col:
            validate_item_fn(
                item_id=item_id,
                val=found_val,
                item_schema=schema.get(item_id),
                sub_id=sub_id,
                task=task,
                strict_levels=strict_levels,
                items_using_tolerance=items_using_tolerance,
                normalize_fn=normalize_val_fn,
                is_missing_fn=is_missing_fn,
            )
            norm = normalize_val_fn(found_val)
            if norm == missing_token:
                missing_count += 1
            out[item_id] = norm
        else:
            out[item_id] = missing_token
            missing_count += 1

    return out, missing_count


def _process_survey_row_with_run(
    *,
    row,
    df_cols,
    task: str,
    run: int | None,
    schema: dict,
    run_col_mapping: dict[str, str],
    sub_id: str,
    strict_levels: bool,
    items_using_tolerance: dict[str, set[str]],
    is_missing_fn,
    normalize_val_fn,
    non_item_keys,
    missing_token: str,
    validate_item_fn,
) -> tuple[dict[str, str], int]:
    """Process a single task/run's data for one subject/session."""
    all_items = [k for k in schema.keys() if k not in non_item_keys]
    expected = [k for k in all_items if k not in schema.get("_aliases", {})]

    out: dict[str, str] = {}
    missing_count = 0

    for item_id in expected:
        candidates = [item_id] + schema.get("_reverse_aliases", {}).get(item_id, [])
        found_val = None
        found_col = None

        for cand in candidates:
            if cand in run_col_mapping:
                actual_col = run_col_mapping[cand]
                if actual_col in df_cols and not is_missing_fn(row[actual_col]):
                    found_val = row[actual_col]
                    found_col = actual_col
                    break
            elif cand in df_cols and not is_missing_fn(row[cand]):
                found_val = row[cand]
                found_col = cand
                break

        if found_col:
            validate_item_fn(
                item_id=item_id,
                val=found_val,
                item_schema=schema.get(item_id),
                sub_id=sub_id,
                task=task,
                strict_levels=strict_levels,
                items_using_tolerance=items_using_tolerance,
                normalize_fn=normalize_val_fn,
                is_missing_fn=is_missing_fn,
            )
            norm = normalize_val_fn(found_val)
            if norm == missing_token:
                missing_count += 1
            out[item_id] = norm
        else:
            out[item_id] = missing_token
            missing_count += 1

    return out, missing_count
