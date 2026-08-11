from __future__ import annotations

import re
from dataclasses import dataclass
from typing import cast

from .survey_core import _NON_ITEM_TOPLEVEL_KEYS
from .survey_processing import _parse_run_from_column


@dataclass
class ColumnMapping:
    """Mapping information for a single column."""

    task: str
    run: int | None  # None if single occurrence, 1/2/3... if multiple runs
    base_item: str  # Item name without run suffix (for template lookup)


_NEAR_MATCH_SEPARATOR_RE = re.compile(r"[-_\s]+")
_NEAR_MATCH_NON_ALNUM_RE = re.compile(r"[^a-zA-Z0-9]+")
_NEAR_MATCH_DIGITS_RE = re.compile(r"\d+")


def _normalize_near_match_item_code(value: str) -> str:
    """Normalize item code for conservative near-match checks.

    This intentionally only tolerates minimal formatting differences:
    separators (``-``, ``_``, whitespace) and numeric zero-padding.
    """
    text = str(value or "").strip()
    if not text:
        return ""

    compact = _NEAR_MATCH_SEPARATOR_RE.sub("", text)
    compact = _NEAR_MATCH_NON_ALNUM_RE.sub("", compact).lower()
    if not compact:
        return ""

    def _normalize_digits(match: re.Match[str]) -> str:
        raw = match.group(0)
        stripped = raw.lstrip("0")
        return stripped or "0"

    return _NEAR_MATCH_DIGITS_RE.sub(_normalize_digits, compact)


def _collect_primary_template_items(template_payload: dict) -> set[str]:
    """Return canonical template item keys used for response matching."""
    items: set[str] = set()
    for key, value in template_payload.items():
        if key in _NON_ITEM_TOPLEVEL_KEYS or not isinstance(value, dict):
            continue
        if value.get("AliasOf"):
            continue

        items.add(key)

        nested_items = value.get("Items")
        if isinstance(nested_items, dict):
            for nested_key, nested_value in nested_items.items():
                if not isinstance(nested_value, dict):
                    continue
                if nested_value.get("AliasOf"):
                    continue
                items.add(nested_key)

    return items


def _match_columns_to_templates(
    *,
    df,
    item_to_task: dict[str, str],
    participant_columns_lower: set[str],
    id_col: str,
    ses_col: str | None,
    run_col: str | None,
) -> tuple[dict[str, ColumnMapping], list[str], dict[str, set[int | None]]]:
    """Exact-match each non-id/session/run column against item_to_task,
    tolerating a PRISM run suffix ({item}_run-{NN})."""
    lower_to_col = {str(c).strip().lower(): str(c).strip() for c in df.columns}

    participant_fallbacks = {
        "age",
        "sex",
        "gender",
        "education",
        "handedness",
        "completion_date",
    }
    participant_columns_present = {
        lower_to_col[c]
        for c in (participant_columns_lower | participant_fallbacks)
        if c in lower_to_col
    }

    cols = [
        c for c in df.columns if c not in {id_col} and c != ses_col and c != run_col
    ]
    col_to_mapping: dict[str, ColumnMapping] = {}
    unknown_cols: list[str] = []
    task_run_tracker: dict[str, set[int | None]] = {}

    for c in cols:
        col_lower = str(c).strip().lower()

        if c in participant_columns_present or col_lower in participant_columns_present:
            continue
        if col_lower in participant_columns_lower:
            continue

        base_name, run_num = _parse_run_from_column(c)

        matched_task = None
        matched_base = c
        if c in item_to_task:
            matched_task = item_to_task[c]
            matched_base = c
        elif base_name in item_to_task:
            matched_task = item_to_task[base_name]
            matched_base = base_name

        if matched_task:
            col_to_mapping[c] = ColumnMapping(
                task=matched_task, run=run_num, base_item=matched_base
            )
            if matched_task not in task_run_tracker:
                task_run_tracker[matched_task] = set()
            task_run_tracker[matched_task].add(run_num)
        else:
            unknown_cols.append(c)

    return col_to_mapping, unknown_cols, task_run_tracker


def _find_near_match_candidates(
    *,
    filtered_unknown: list[str],
    templates: dict[str, dict] | None,
    selected_tasks: set[str] | None,
    col_to_mapping: dict[str, ColumnMapping],
) -> tuple[list[dict[str, object]], list[str]]:
    """Find unmapped columns that near-match a template item (tolerating
    separator/casing/zero-padding differences), conservatively: only
    approved when applying every candidate for a task would produce a full
    1:1 item-count match against that task's remaining unmapped items, or
    the candidates carry explicit run context."""
    near_match_candidates: list[dict[str, object]] = []
    warnings: list[str] = []

    if not (filtered_unknown and templates):
        return near_match_candidates, warnings

    scoped_tasks = set(selected_tasks) if selected_tasks else set(templates.keys())

    task_primary_items: dict[str, set[str]] = {}
    task_alias_lookup: dict[str, dict[str, str]] = {}
    normalized_item_lookup: dict[str, set[tuple[str, str]]] = {}

    for task, template_data in templates.items():
        if task not in scoped_tasks:
            continue
        template_json = (
            template_data.get("json") if isinstance(template_data, dict) else None
        )
        if not isinstance(template_json, dict):
            continue

        primary_items = _collect_primary_template_items(template_json)
        if not primary_items:
            continue
        task_primary_items[task] = primary_items

        aliases = template_json.get("_aliases")
        alias_lookup: dict[str, str] = {}
        if isinstance(aliases, dict):
            for alias, canonical in aliases.items():
                if not isinstance(alias, str) or not isinstance(canonical, str):
                    continue
                if canonical in primary_items:
                    alias_lookup[alias] = canonical
        task_alias_lookup[task] = alias_lookup

        for item_key in primary_items:
            normalized = _normalize_near_match_item_code(item_key)
            if not normalized:
                continue
            normalized_item_lookup.setdefault(normalized, set()).add((task, item_key))

    exact_mapped_by_task: dict[str, set[str]] = {}
    for mapping in col_to_mapping.values():
        if mapping.task not in task_primary_items:
            continue
        canonical = task_alias_lookup.get(mapping.task, {}).get(
            mapping.base_item, mapping.base_item
        )
        exact_mapped_by_task.setdefault(mapping.task, set()).add(canonical)

    task_candidates: dict[str, list[dict[str, object]]] = {}
    for source_column in filtered_unknown:
        base_name, run_num = _parse_run_from_column(source_column)
        normalized_base = _normalize_near_match_item_code(base_name)
        if not normalized_base:
            continue

        target_candidates = normalized_item_lookup.get(normalized_base) or set()
        if len(target_candidates) != 1:
            continue

        task, target_item = next(iter(target_candidates))
        task_candidates.setdefault(task, []).append(
            {
                "source_column": source_column,
                "source_base_item": base_name,
                "target_item": target_item,
                "task": task,
                "run": run_num,
            }
        )

    approved_candidates: list[dict[str, object]] = []
    for task, candidates in task_candidates.items():
        if task not in task_primary_items:
            continue
        primary_items = task_primary_items[task]
        if not primary_items:
            continue

        has_explicit_run_context = any(
            candidate.get("run") is not None for candidate in candidates
        )
        proposed_items = {
            str(candidate.get("target_item", ""))
            for candidate in candidates
            if candidate.get("target_item")
        }

        if not has_explicit_run_context:
            exact_items = exact_mapped_by_task.get(task, set())
            missing_items = primary_items - exact_items
            if proposed_items != missing_items or len(candidates) != len(
                missing_items
            ):
                warnings.append(
                    f"Near-match candidates for task '{task}' were ignored because "
                    "they do not produce a full one-to-one item count match."
                )
                continue

        seen_targets: set[tuple[str, object]] = set()
        has_duplicate_targets = False
        for candidate in candidates:
            target_item = str(candidate.get("target_item", "")).strip()
            target_run = candidate.get("run")
            key = (target_item, target_run)
            if key in seen_targets:
                has_duplicate_targets = True
                break
            seen_targets.add(key)

        if has_duplicate_targets:
            warnings.append(
                f"Near-match candidates for task '{task}' were ignored due to duplicate target mappings."
            )
            continue

        approved_candidates.extend(candidates)

    near_match_candidates = sorted(
        approved_candidates,
        key=lambda candidate: (
            str(candidate.get("task", "")),
            str(candidate.get("source_column", "")),
        ),
    )

    return near_match_candidates, warnings


def _apply_approved_near_matches(
    *,
    near_match_candidates: list[dict[str, object]],
    allow_near_item_match: bool,
    near_match_tasks: set[str] | None,
    col_to_mapping: dict[str, ColumnMapping],
    task_run_tracker: dict[str, set[int | None]],
    filtered_unknown: list[str],
) -> tuple[list[str], bool, list[str]]:
    """Apply near-match candidates the caller has confirmed (allow_near_item_match),
    optionally restricted to near_match_tasks. Mutates col_to_mapping and
    task_run_tracker in place. Returns the updated filtered_unknown list,
    whether anything was applied, and any warnings."""
    near_match_task_filter: set[str] | None = None
    if near_match_tasks is not None:
        near_match_task_filter = {
            str(task).strip().lower() for task in near_match_tasks if str(task).strip()
        }

    near_match_applied = False
    warnings: list[str] = []

    if near_match_candidates and allow_near_item_match:
        candidates_to_apply = near_match_candidates
        if near_match_task_filter is not None:
            candidates_to_apply = [
                candidate
                for candidate in near_match_candidates
                if str(candidate.get("task", "")).strip().lower()
                in near_match_task_filter
            ]

        applied_columns: list[str] = []
        for candidate in candidates_to_apply:
            source_column = str(candidate.get("source_column", "")).strip()
            target_item = str(candidate.get("target_item", "")).strip()
            task = str(candidate.get("task", "")).strip()
            run_value = candidate.get("run")

            if not source_column or not target_item or not task:
                continue
            if source_column in col_to_mapping:
                continue

            col_to_mapping[source_column] = ColumnMapping(
                task=task,
                run=cast(int | None, run_value),
                base_item=target_item,
            )
            task_run_tracker.setdefault(task, set()).add(cast(int | None, run_value))
            applied_columns.append(source_column)

        if applied_columns:
            near_match_applied = True
            applied_set = set(applied_columns)
            filtered_unknown = [
                col for col in filtered_unknown if col not in applied_set
            ]
            shown = ", ".join(
                f"{candidate['source_column']}->{candidate['target_item']}"
                for candidate in candidates_to_apply[:8]
            )
            more = (
                ""
                if len(candidates_to_apply) <= 8
                else f" (+{len(candidates_to_apply) - 8} more)"
            )
            warnings.append(
                f"Applied near item matches after confirmation ({len(applied_columns)}): {shown}{more}"
            )
        skipped_candidate_count = len(near_match_candidates) - len(candidates_to_apply)
        if skipped_candidate_count > 0:
            warnings.append(
                f"Skipped {skipped_candidate_count} near-match candidate(s) for unselected survey tasks."
            )
        if not candidates_to_apply and near_match_task_filter is not None:
            warnings.append(
                "Near item matches were enabled, but none matched the selected survey tasks."
            )
    elif near_match_candidates:
        shown = ", ".join(
            f"{candidate['source_column']}->{candidate['target_item']}"
            for candidate in near_match_candidates[:8]
        )
        more = (
            ""
            if len(near_match_candidates) <= 8
            else f" (+{len(near_match_candidates) - 8} more)"
        )
        warnings.append(
            f"Near item matches available after confirmation ({len(near_match_candidates)}): {shown}{more}"
        )

    return filtered_unknown, near_match_applied, warnings


def _map_survey_columns(
    *,
    df,
    item_to_task: dict[str, str],
    participant_columns_lower: set[str],
    id_col: str,
    ses_col: str | None,
    run_col: str | None = None,
    unknown_mode: str,
    templates: dict[str, dict] | None = None,
    selected_tasks: set[str] | None = None,
    allow_near_item_match: bool = False,
    near_match_tasks: set[str] | None = None,
) -> tuple[
    dict[str, ColumnMapping],
    list[str],
    list[str],
    dict[str, int | None],
    list[dict[str, object]],
    bool,
]:
    """Determine which columns map to which surveys and identify unmapped columns.

    Now also detects run information from PRISM naming convention:
    {QUESTIONNAIRE}_{ITEM}_run-{NN}

    Returns:
        col_to_mapping: Dict mapping column name to ColumnMapping(task, run, base_item)
        unknown_cols: List of unmapped column names
        warnings: List of warning messages
        task_runs: Dict mapping task name to max run number (None if single occurrence)
        near_match_candidates: Safe near-match candidates requiring explicit confirmation
        near_match_applied: Whether near matches were actually applied
    """
    col_to_mapping, unknown_cols, task_run_tracker = _match_columns_to_templates(
        df=df,
        item_to_task=item_to_task,
        participant_columns_lower=participant_columns_lower,
        id_col=id_col,
        ses_col=ses_col,
        run_col=run_col,
    )

    warnings: list[str] = []
    bookkeeping = {
        "id",
        "submitdate",
        "lastpage",
        "startlanguage",
        "seed",
        "startdate",
        "datestamp",
        "token",
        "refurl",
        "ipaddr",
        "googleid",
        "session_id",
        "participant_id",
        "attribute_1",
        "attribute_2",
        "attribute_3",
    }
    # Also filter out LimeSurvey "Other" text columns (other, other_1, other_2, ...),
    # PRISM metadata questions, and menstrual cycle columns with LS-mangled names
    _other_pattern = re.compile(r"^other(_\d+)?$", re.IGNORECASE)
    _prismmeta_pattern = re.compile(r"^prismmeta", re.IGNORECASE)
    filtered_unknown = [
        c
        for c in unknown_cols
        if str(c).lower() not in bookkeeping
        and not _other_pattern.match(str(c).strip())
        and not _prismmeta_pattern.match(str(c).strip())
    ]

    near_match_candidates, near_match_find_warnings = _find_near_match_candidates(
        filtered_unknown=filtered_unknown,
        templates=templates,
        selected_tasks=selected_tasks,
        col_to_mapping=col_to_mapping,
    )
    warnings.extend(near_match_find_warnings)

    filtered_unknown, near_match_applied, near_match_apply_warnings = (
        _apply_approved_near_matches(
            near_match_candidates=near_match_candidates,
            allow_near_item_match=allow_near_item_match,
            near_match_tasks=near_match_tasks,
            col_to_mapping=col_to_mapping,
            task_run_tracker=task_run_tracker,
            filtered_unknown=filtered_unknown,
        )
    )
    warnings.extend(near_match_apply_warnings)

    # Determine final run assignments per task
    # If a task has only items with run=None, no runs needed
    # If a task has items with run numbers, all items for that task get run numbers
    task_runs: dict[str, int | None] = {}
    for task, runs in task_run_tracker.items():
        run_numbers = [run_number for run_number in runs if run_number is not None]
        if run_numbers:
            task_runs[task] = max(run_numbers)
        else:
            task_runs[task] = None

    if filtered_unknown:
        if unknown_mode == "error":
            raise ValueError("Unmapped columns: " + ", ".join(filtered_unknown))
        if unknown_mode == "warn":
            shown = ", ".join(filtered_unknown[:10])
            more = (
                ""
                if len(filtered_unknown) <= 10
                else f" (+{len(filtered_unknown) - 10} more)"
            )
            warnings.append(
                f"Unmapped columns (not in any survey template): {shown}{more}"
            )

    return (
        col_to_mapping,
        filtered_unknown,
        warnings,
        task_runs,
        near_match_candidates,
        near_match_applied,
    )
