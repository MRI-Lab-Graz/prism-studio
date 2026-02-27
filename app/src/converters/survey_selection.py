"""Survey selection parsing helpers for conversion workflows."""

from __future__ import annotations


def _resolve_selected_tasks(
    *,
    survey_filter: str | None,
    templates: dict,
) -> set[str] | None:
    """Parse and validate survey filter into selected normalized task names."""
    selected_tasks: set[str] | None = None
    if survey_filter:
        parts = [p.strip() for p in str(survey_filter).replace(";", ",").split(",")]
        parts = [p for p in parts if p]
        selected = {p.lower().replace("survey-", "") for p in parts}
        unknown_surveys = sorted([t for t in selected if t not in templates])
        if unknown_surveys:
            raise ValueError(
                "Unknown surveys: "
                + ", ".join(unknown_surveys)
                + ". Available: "
                + ", ".join(sorted(templates.keys()))
            )
        selected_tasks = selected

    return selected_tasks
