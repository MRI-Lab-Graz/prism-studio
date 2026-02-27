"""Helpers for preparing mapping-derived conversion results."""

from __future__ import annotations


def _resolve_tasks_with_warnings(
    *,
    col_to_mapping: dict,
    selected_tasks: set[str] | None,
    template_warnings_by_task: dict[str, list[str]],
) -> tuple[set[str], list[str]]:
    """Resolve tasks included in conversion and collect relevant warnings."""
    tasks_with_data = {m.task for m in col_to_mapping.values()}
    if selected_tasks is not None:
        tasks_with_data = tasks_with_data.intersection(selected_tasks)
    if not tasks_with_data:
        raise ValueError("No survey item columns matched the selected templates.")

    warnings: list[str] = []
    for task_name in sorted(tasks_with_data):
        warnings.extend(template_warnings_by_task.get(task_name, []))

    return tasks_with_data, warnings


def _build_col_to_task_and_task_runs(
    *,
    col_to_mapping: dict,
) -> tuple[dict[str, str], dict[tuple[str, int | None], list[str]]]:
    """Build compatibility col->task map and grouped task/run columns."""
    col_to_task = {col: m.task for col, m in col_to_mapping.items()}

    task_run_columns: dict[tuple[str, int | None], list[str]] = {}
    for col, mapping in col_to_mapping.items():
        key = (mapping.task, mapping.run)
        if key not in task_run_columns:
            task_run_columns[key] = []
        task_run_columns[key].append(col)

    return col_to_task, task_run_columns


def _build_template_matches_payload(*, lsa_analysis: dict | None) -> dict | None:
    """Build template match payload for API responses."""
    template_matches: dict | None = None
    if lsa_analysis:
        template_matches = {}
        for group_name, group_info in lsa_analysis["groups"].items():
            match = group_info.get("match")
            template_matches[group_name] = match.to_dict() if match else None
    return template_matches
