"""Preregistration draft: project.json -> Markdown in AsPredicted question order.

A draft only. Registering (time stamp, frozen copy) happens at a registry.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

EMPTY = "_Not filled in yet._"

DATA_STATUS_LABELS = {
    "not-collected": "No data collected yet",
    "collected-not-accessed": "Data collected, not yet looked at",
    "accessed": "Data collected and accessed",
}

HEADER = (
    "# Preregistration draft\n\n"
    "_This is a draft generated from project.json, not a registration. "
    "Register it at a registry (e.g. OSF, AsPredicted) to get a time-stamped, frozen version._\n"
)


def _text(value: Any) -> str:
    if isinstance(value, list):
        return "\n".join(f"- {t}" for t in (_text(v) for v in value) if t)
    if isinstance(value, (str, int)) and not isinstance(value, bool):
        return str(value).strip()
    return ""


def _labelled(*pairs: tuple[str, Any]) -> str:
    """'Label: value' lines for the filled values; multi-line values go on their own lines."""
    lines = []
    for label, value in pairs:
        text = _text(value)
        if text:
            lines.append(
                f"**{label}:** {text}" if "\n" not in text else f"**{label}:**\n{text}"
            )
    return "\n\n".join(lines)


def _groups(conditions: dict) -> str:
    groups = conditions.get("Groups")
    if not isinstance(groups, list):
        return ""
    lines = []
    for group in groups:
        if not isinstance(group, dict):
            continue
        label = _text(group.get("label")) or _text(group.get("id"))
        description = _text(group.get("description"))
        if label:
            lines.append(f"- {label}: {description}" if description else f"- {label}")
    return "\n".join(lines)


def _section(project: dict, key: str) -> dict:
    value = project.get(key)
    return value if isinstance(value, dict) else {}


def draft_markdown(project: dict) -> str:
    prereg = _section(project, "Preregistration")
    design = _section(project, "StudyDesign")
    eligibility = _section(project, "Eligibility")
    procedure = _section(project, "Procedure")
    status = _text(prereg.get("DataStatus"))

    answers = [
        (
            "1. Have any data been collected for this study already?",
            DATA_STATUS_LABELS.get(status, status),
        ),
        (
            "2. What is the main question or hypothesis being tested?",
            _text(prereg.get("Hypotheses")),
        ),
        (
            "3. Describe the key dependent variable(s) and how they will be measured.",
            _text(prereg.get("PrimaryOutcomes")),
        ),
        (
            "4. How many and which conditions will participants be assigned to?",
            _labelled(
                ("Conditions", _groups(_section(project, "Conditions"))),
                ("Design", design.get("Type")),
                ("Randomization", design.get("Randomization")),
                ("Blinding", design.get("Blinding")),
                ("Control condition", design.get("ControlCondition")),
            ),
        ),
        (
            "5. Specify exactly which analyses you will conduct.",
            _labelled(
                ("Analyses", prereg.get("AnalysisPlan")),
                ("Inference criteria", prereg.get("InferenceCriteria")),
            ),
        ),
        (
            "6. Describe how outliers will be defined and handled, and your rules for excluding observations.",
            _labelled(
                ("Exclusion criteria", eligibility.get("ExclusionCriteria")),
                ("Quality control", procedure.get("QualityControl")),
                ("Missing data", procedure.get("MissingDataHandling")),
            ),
        ),
        (
            "7. How many observations will be collected, or what will determine sample size?",
            _labelled(
                ("Target sample size", eligibility.get("TargetSampleSize")),
                ("Power analysis", eligibility.get("PowerAnalysis")),
                ("Inclusion criteria", eligibility.get("InclusionCriteria")),
            ),
        ),
        (
            "8. Anything else you would like to preregister?",
            _labelled(
                ("Secondary outcomes", prereg.get("SecondaryOutcomes")),
                ("Exploratory analyses", prereg.get("ExploratoryAnalyses")),
            ),
        ),
    ]
    body = "\n\n".join(
        f"## {question}\n\n{answer or EMPTY}" for question, answer in answers
    )
    return f"{HEADER}\n{body}\n"


def load_draft(project_path: str | Path) -> str:
    """Draft for a project root or a project.json path; FileNotFoundError without project.json."""
    path = Path(project_path)
    if path.is_dir():
        path = path / "project.json"
    if not path.is_file():
        raise FileNotFoundError(f"No project.json at {path}")
    return draft_markdown(json.loads(path.read_text(encoding="utf-8")))
