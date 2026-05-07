"""Survey data processing: value normalization, column classification, and row validation.

This module consolidates logic for:
1. Normalizing survey item values (integers, strings, missing values).
2. Classifying and grouping columns (LimeSurvey system columns, run suffixes).
3. Processing and validating individual data rows against schemas.
"""

from __future__ import annotations

import re
from typing import Any


class SurveyValueOutOfBoundsError(ValueError):
    """Structured error for survey values that do not fit template levels/range."""

    def __init__(
        self,
        *,
        task: str,
        item_id: str,
        sub_id: str,
        raw_value: Any,
        expected_levels: list[str],
        suggested_offsets: list[float | int] | None = None,
        configured_offset: float | None = None,
        message: str,
    ) -> None:
        super().__init__(message)
        self.task = task
        self.item_id = item_id
        self.sub_id = sub_id
        self.raw_value = raw_value
        self.expected_levels = expected_levels
        self.suggested_offsets = suggested_offsets or []
        self.configured_offset = configured_offset


def _resolve_task_value_offset(
    task: str,
    task_value_offsets: dict[str, float] | None,
) -> float | None:
    if not isinstance(task_value_offsets, dict) or not task_value_offsets:
        return None

    task_key = str(task or "").strip().lower()
    if task_key in task_value_offsets:
        return float(task_value_offsets[task_key])
    if "*" in task_value_offsets:
        return float(task_value_offsets["*"])
    return None


def _coerce_numeric_offset_value(value: float) -> float | int:
    rounded = round(value)
    if abs(float(value) - float(rounded)) < 1e-9:
        return int(rounded)
    return float(value)


def _coerce_offset_suggestion(value: float) -> float | int:
    rounded = round(value)
    if abs(float(value) - float(rounded)) < 1e-9:
        return int(rounded)
    return float(round(value, 6))


def _suggest_offsets_for_invalid_value(
    *,
    value_num: float | None,
    levels: dict,
    item_schema: dict,
) -> list[float | int]:
    if value_num is None:
        return []

    def _to_float(x):
        try:
            return float(str(x).strip())
        except (ValueError, TypeError, AttributeError):
            return None

    suggestions: list[float | int] = []

    raw_allowed_values = item_schema.get("AllowedValues")
    if isinstance(raw_allowed_values, list) and raw_allowed_values:
        numeric_allowed_values = sorted(
            n for n in (_to_float(entry) for entry in raw_allowed_values) if n is not None
        )
        if numeric_allowed_values:
            min_distance = min(
                abs(allowed_value - value_num)
                for allowed_value in numeric_allowed_values
            )
            for allowed_value in numeric_allowed_values:
                if abs(abs(allowed_value - value_num) - min_distance) > 1e-9:
                    continue
                suggestions.append(
                    _coerce_offset_suggestion(allowed_value - value_num)
                )

    if not suggestions:
        numeric_levels = sorted(
            n for n in (_to_float(key) for key in levels.keys()) if n is not None
        )
        if len(numeric_levels) >= 2:
            min_level = numeric_levels[0]
            max_level = numeric_levels[-1]
            if value_num < min_level:
                suggestions.append(_coerce_offset_suggestion(min_level - value_num))
            elif value_num > max_level:
                suggestions.append(_coerce_offset_suggestion(max_level - value_num))

    if not suggestions:
        min_v = _to_float(item_schema.get("MinValue"))
        max_v = _to_float(item_schema.get("MaxValue"))
        if min_v is not None and max_v is not None:
            if value_num < min_v:
                suggestions.append(_coerce_offset_suggestion(min_v - value_num))
            elif value_num > max_v:
                suggestions.append(_coerce_offset_suggestion(max_v - value_num))

    deduped: list[float | int] = []
    seen = set()
    for suggestion in suggestions:
        key = f"{float(suggestion):.6f}"
        if key in seen:
            continue
        seen.add(key)
        deduped.append(suggestion)
    return deduped

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

        def isna(x):
            return x is None

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
    re.compile(r"^(.+?)run(\d+)$", re.IGNORECASE),  # LimeSurvey: SWLS01run02
]

# LimeSurvey system columns - platform metadata fields present in response tables.
# These are consistent across LS 3.x, 5.x, and 6.x. Optional columns (startdate,
# datestamp, ipaddr, refurl) only appear when enabled in survey settings.
# Reference: SurveyDynamic.php getDefaultColumns() + Notifications & Data panel.
LIMESURVEY_SYSTEM_COLUMNS = {
    # Core default columns (always present in response table)
    "id",  # Response ID (auto-increment)
    "submitdate",  # Submission timestamp (NULL if incomplete)
    "lastpage",  # Last page viewed by respondent
    "startlanguage",  # Language selected at survey start
    "completed",  # Completion status flag (LS internal)
    "seed",  # Randomization seed for question/answer order
    "token",  # Participant access token (if token-based)
    # Optional columns (enabled via Notifications & Data panel)
    "startdate",  # Timestamp when survey was started
    "datestamp",  # Timestamp of last respondent action
    "ipaddr",  # IP address (if Save IP Address enabled)
    "refurl",  # Referrer URL (if Save Referrer URL enabled)
    # Timing fields
    "interviewtime",  # Total time spent on survey in seconds
    # Participant table fields (when token management is active)
    "optout",  # Participant opt-out status
    "emailstatus",  # Email delivery status
    # Custom participant attributes (LS 5.x+)
    "attribute_1",
    "attribute_2",
    "attribute_3",
}

# Patterns for dynamic timing columns in the survey_SID_timings table.
# LimeSurvey stores per-group and per-question timing data:
#   - groupTimeNNN / grouptimeNNN  (time on question group, in seconds)
#   - questionTimeNNN              (time on individual question, in seconds, LS 5+)
#   - interviewtime                (total survey time, also in LIMESURVEY_SYSTEM_COLUMNS)
_LS_TIMING_PATTERN = re.compile(r"^(grouptime|questiontime)\d+$", re.IGNORECASE)


def _is_limesurvey_system_column(column_name: str) -> bool:
    """Check if a column is a LimeSurvey system/metadata column.

    Handles:
    - Fixed system columns (id, submitdate, seed, token, etc.)
    - Dynamic timing columns (grouptime123, questiontime456)
    - Duration columns (duration_*)
    - Custom attribute columns (attribute_N beyond 1-3)
    """
    col_lower = column_name.strip().lower()

    if col_lower in LIMESURVEY_SYSTEM_COLUMNS:
        return True

    if _LS_TIMING_PATTERN.match(col_lower):
        return True

    if col_lower.startswith("duration_"):
        return True

    # Additional participant attributes beyond 1-3 (attribute_4, attribute_5, etc.)
    if re.match(r"^attribute_\d+$", col_lower):
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
    task_value_offsets: dict[str, float] | None = None,
    offset_application_counts: dict[str, int] | None = None,
) -> Any:
    """Internal validation for a single survey item value."""
    if is_missing_fn(val) or not isinstance(item_schema, dict):
        return val

    levels = item_schema.get("Levels")
    if not isinstance(levels, dict) or not levels:
        return val

    def _to_float(x):
        try:
            return float(str(x).strip())
        except (ValueError, TypeError, AttributeError):
            return None

    task_offset = _resolve_task_value_offset(task, task_value_offsets)
    validated_value = val
    value_num = _to_float(val)
    if task_offset is not None and value_num is not None:
        validated_value = _coerce_numeric_offset_value(float(value_num) + float(task_offset))
        if offset_application_counts is not None:
            offset_application_counts[task] = offset_application_counts.get(task, 0) + 1

    v_str = normalize_fn(validated_value)
    if v_str == missing_token:
        return validated_value

    # Keep converter-time checks aligned with validator behavior: when
    # AllowedValues is present, it is the authoritative allowlist.
    normalized_allowed_values: list[str] = []
    raw_allowed_values = item_schema.get("AllowedValues")
    if isinstance(raw_allowed_values, list) and raw_allowed_values:
        seen_allowed_values: set[str] = set()
        for raw_allowed in raw_allowed_values:
            normalized_allowed = normalize_fn(raw_allowed)
            if normalized_allowed == missing_token:
                continue
            if normalized_allowed in seen_allowed_values:
                continue
            seen_allowed_values.add(normalized_allowed)
            normalized_allowed_values.append(normalized_allowed)

    if normalized_allowed_values:
        if v_str in normalized_allowed_values:
            return validated_value
        v_num_for_allowed = _to_float(v_str)
        if (
            v_num_for_allowed is not None
            and float(v_num_for_allowed).is_integer()
            and str(int(v_num_for_allowed)) in normalized_allowed_values
        ):
            return validated_value

        expected_levels = sorted(str(x) for x in normalized_allowed_values)
        suggested_offsets = (
            []
            if task_offset is not None
            else _suggest_offsets_for_invalid_value(
                value_num=_to_float(val),
                levels=levels,
                item_schema=item_schema,
            )
        )

        msg = (
            f"Invalid value '{val}' for '{item_id}' (Sub: {sub_id}, Task: {task}). "
            f"Expected: {', '.join(expected_levels)}"
        )
        if task_offset is not None:
            msg += (
                f". The configured offset {float(task_offset):+g} did not resolve this value."
            )
        elif suggested_offsets:
            msg += ". Suggested task offset(s): " + ", ".join(
                f"{float(offset):+g}" for offset in suggested_offsets
            )

        raise SurveyValueOutOfBoundsError(
            task=task,
            item_id=item_id,
            sub_id=sub_id,
            raw_value=val,
            expected_levels=expected_levels,
            suggested_offsets=suggested_offsets,
            configured_offset=task_offset,
            message=msg,
        )

    if v_str in levels:
        return validated_value

    matched_key = find_matching_level_key_fn(v_str, levels)
    if matched_key is not None:
        return validated_value

    try:
        v_num = _to_float(v_str)
        min_v = _to_float(item_schema.get("MinValue"))
        max_v = _to_float(item_schema.get("MaxValue"))

        if v_num is not None and min_v is not None and max_v is not None:
            if min_v <= v_num <= max_v:
                return validated_value

        if not strict_levels:
            l_nums = [n for n in [_to_float(k) for k in levels.keys()] if n is not None]
            if len(l_nums) >= 2 and v_num is not None:
                if min(l_nums) <= v_num <= max(l_nums):
                    items_using_tolerance.setdefault(task, set()).add(item_id)
                    return validated_value
    except (ValueError, TypeError, AttributeError):
        pass

    expected_levels = sorted(str(k) for k in levels.keys())
    allowed = ", ".join(expected_levels)
    suggested_offsets = (
        []
        if task_offset is not None
        else _suggest_offsets_for_invalid_value(
            value_num=_to_float(val),
            levels=levels,
            item_schema=item_schema,
        )
    )

    msg = (
        f"Invalid value '{val}' for '{item_id}' (Sub: {sub_id}, Task: {task}). "
        f"Expected: {allowed}"
    )
    if task_offset is not None:
        msg += (
            f". The configured offset {float(task_offset):+g} did not resolve this value."
        )
    elif suggested_offsets:
        msg += ". Suggested task offset(s): " + ", ".join(
            f"{float(offset):+g}" for offset in suggested_offsets
        )

    raise SurveyValueOutOfBoundsError(
        task=task,
        item_id=item_id,
        sub_id=sub_id,
        raw_value=val,
        expected_levels=expected_levels,
        suggested_offsets=suggested_offsets,
        configured_offset=task_offset,
        message=msg,
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
    task_value_offsets: dict[str, float] | None = None,
    offset_application_counts: dict[str, int] | None = None,
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
            validated_value = validate_item_fn(
                item_id=item_id,
                val=found_val,
                item_schema=schema.get(item_id),
                sub_id=sub_id,
                task=task,
                strict_levels=strict_levels,
                items_using_tolerance=items_using_tolerance,
                normalize_fn=normalize_val_fn,
                is_missing_fn=is_missing_fn,
                task_value_offsets=task_value_offsets,
                offset_application_counts=offset_application_counts,
            )
            norm = normalize_val_fn(validated_value)
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
    task_value_offsets: dict[str, float] | None = None,
    offset_application_counts: dict[str, int] | None = None,
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
            validated_value = validate_item_fn(
                item_id=item_id,
                val=found_val,
                item_schema=schema.get(item_id),
                sub_id=sub_id,
                task=task,
                strict_levels=strict_levels,
                items_using_tolerance=items_using_tolerance,
                normalize_fn=normalize_val_fn,
                is_missing_fn=is_missing_fn,
                task_value_offsets=task_value_offsets,
                offset_application_counts=offset_application_counts,
            )
            norm = normalize_val_fn(validated_value)
            if norm == missing_token:
                missing_count += 1
            out[item_id] = norm
        else:
            out[item_id] = missing_token
            missing_count += 1

    return out, missing_count
