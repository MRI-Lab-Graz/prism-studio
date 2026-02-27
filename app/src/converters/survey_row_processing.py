"""Row-level survey processing helpers extracted from survey converter."""

from __future__ import annotations


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
    non_item_toplevel_keys,
    missing_token: str,
    validate_item_fn,
) -> tuple[dict[str, str], int]:
    """Process a single task's data for one subject/session."""
    all_items = [k for k in schema.keys() if k not in non_item_toplevel_keys]
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
    non_item_toplevel_keys,
    missing_token: str,
    validate_item_fn,
) -> tuple[dict[str, str], int]:
    """Process a single task/run's data for one subject/session."""
    all_items = [k for k in schema.keys() if k not in non_item_toplevel_keys]
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


def _validate_survey_item_value(
    *,
    item_id: str,
    val,
    item_schema: dict | None,
    sub_id: str,
    task: str,
    strict_levels: bool,
    items_using_tolerance: dict[str, set[str]],
    normalize_fn,
    is_missing_fn,
    find_matching_level_key_fn,
    missing_token: str,
):
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
