"""Shared helper utilities for survey conversion internals.

This module contains pure helper logic for template structure comparisons and
BIDS survey filename/run mapping.
"""

from __future__ import annotations


_NON_ITEM_TOPLEVEL_KEYS = {
    "Technical",
    "Study",
    "Metadata",
    "Normative",
    "Scoring",
    # Template metadata (not survey response columns)
    "I18n",
    "LimeSurvey",
    "_aliases",
    "_reverse_aliases",
    "_prismmeta",
}


# Keys that are considered "styling" or metadata, not structural
_STYLING_KEYS = {
    "Description",
    "Levels",
    "MinValue",
    "MaxValue",
    "Units",
    "HelpText",
    "Aliases",
    "AliasOf",
    "Derivative",
    "TermURL",
}


def _extract_template_structure(template: dict) -> set[str]:
    """Extract the structural signature of a template (item keys only)."""
    return {
        k
        for k in template.keys()
        if k not in _NON_ITEM_TOPLEVEL_KEYS and isinstance(template.get(k), dict)
    }


def _compare_template_structures(
    template_a: dict, template_b: dict
) -> tuple[bool, set[str], set[str]]:
    """Compare two templates structurally."""
    struct_a = _extract_template_structure(template_a)
    struct_b = _extract_template_structure(template_b)

    only_in_a = struct_a - struct_b
    only_in_b = struct_b - struct_a

    return (len(only_in_a) == 0 and len(only_in_b) == 0), only_in_a, only_in_b


def _build_bids_survey_filename(
    sub_id: str, ses_id: str, task: str, run: int | None = None, extension: str = "tsv"
) -> str:
    """Build a BIDS-compliant survey filename."""
    parts = [sub_id, ses_id, f"task-{task}"]
    if run is not None:
        parts.append(f"run-{run:02d}")
    parts.append("survey")  # Add suffix without extension
    return "_".join(parts) + f".{extension}"


def _determine_task_runs(
    tasks_with_data: set[str], task_occurrences: dict[str, int]
) -> dict[str, int | None]:
    """Determine which tasks need run numbers based on occurrence count."""
    task_runs: dict[str, int | None] = {}
    for task in tasks_with_data:
        count = task_occurrences.get(task, 1)
        if count > 1:
            task_runs[task] = count
        else:
            task_runs[task] = None
    return task_runs
