"""Helpers for unmatched LSA group normalization and aggregation."""

from __future__ import annotations


def _collect_unmatched_lsa_group(
    *,
    group_name: str,
    group_info: dict,
    unmatched_groups: list[dict],
    non_item_toplevel_keys,
    sanitize_task_name_fn,
) -> None:
    """Normalize/merge one unmatched LSA group into unmatched_groups."""
    from .template_matcher import _normalize_item_codes, _strip_run_from_group_name
    from .template_matcher import _strip_run_suffix

    task_key = sanitize_task_name_fn(group_name).lower()
    if not task_key:
        task_key = group_name.lower().replace(" ", "")

    base_key = _strip_run_from_group_name(task_key)
    if not base_key:
        base_key = task_key

    raw_codes = group_info["item_codes"]
    base_codes, _ = _normalize_item_codes(
        raw_codes if isinstance(raw_codes, set) else set(raw_codes)
    )
    base_prism = {}
    for k, v in group_info["prism_json"].items():
        if k in non_item_toplevel_keys or not isinstance(v, dict):
            base_prism[k] = v
        else:
            stripped, _ = _strip_run_suffix(k)
            if stripped not in base_prism:
                base_prism[stripped] = v

    existing = next((g for g in unmatched_groups if g["task_key"] == base_key), None)
    if existing is None:
        unmatched_groups.append(
            {
                "group_name": group_name,
                "task_key": base_key,
                "item_codes": base_codes,
                "prism_json": base_prism,
            }
        )
    else:
        existing["item_codes"] = existing["item_codes"] | base_codes
