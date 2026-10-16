"""Eligibility criteria from project.json, checked against participants.tsv.

Criteria are entered once in the project metadata (``Eligibility.Criteria``).
A participants.json column opts in with ``"EligibilityCriterion": "<id>"``; the
limits are never copied there. Every finding is a WARNING: collected data is
checked while a study is still running.
"""

from __future__ import annotations

import csv
import json
from pathlib import Path

LINK_KEY = "EligibilityCriterion"
_MISSING = {"", "n/a", "na"}


def _load_json(path: Path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def _num(value) -> str:
    return f"{value:g}"


def _range_text(crit: dict) -> str:
    lo, hi = crit.get("min"), crit.get("max")
    if lo is not None and hi is not None:
        text = f"{_num(lo)}-{_num(hi)}"
    elif lo is not None:
        text = f"at least {_num(lo)}"
    else:
        text = f"at most {_num(hi)}"
    return f"{text} {crit['unit']}" if crit.get("unit") else text


def _level_labels(spec) -> dict[str, str]:
    """Code -> label from a participants.json column (Levels, else Annotations.Levels)."""
    if not isinstance(spec, dict):
        return {}
    levels = spec.get("Levels")
    if isinstance(levels, dict) and levels:
        pairs = levels.items()
    else:
        annotations = spec.get("Annotations")
        annotated = annotations.get("Levels") if isinstance(annotations, dict) else None
        pairs = annotated.items() if isinstance(annotated, dict) else ()
    labels = {}
    for code, value in pairs:
        if isinstance(value, dict):
            value = value.get("Label") or value.get("Description")
        if value:
            labels[str(code)] = str(value)
    return labels


def _numeric_violation(raw: str, crit: dict) -> bool:
    try:
        value = float(raw.replace(",", "."))
    except ValueError:
        return False  # the data-type checks report non-numeric values
    lo, hi = crit.get("min"), crit.get("max")
    inside = (lo is None or value >= lo) and (hi is None or value <= hi)
    return inside if crit.get("mode") == "exclude" else not inside


def load_criteria(root_dir: str) -> list:
    """The project's ``Eligibility.Criteria`` list, ``[]`` when there is none."""
    project = _load_json(Path(root_dir) / "project.json")
    eligibility = project.get("Eligibility") if isinstance(project, dict) else None
    criteria = eligibility.get("Criteria") if isinstance(eligibility, dict) else None
    return criteria if isinstance(criteria, list) else []


def check_eligibility(root_dir: str) -> list[tuple[str, str, str]]:
    root = Path(root_dir)
    criteria = load_criteria(root_dir)
    sidecar = _load_json(root / "participants.json")
    if not criteria or not isinstance(sidecar, dict):
        return []

    by_id: dict[str, dict] = {}
    duplicates: set[str] = set()
    for crit in criteria:
        if isinstance(crit, dict) and crit.get("id"):
            if crit["id"] in by_id:
                duplicates.add(crit["id"])
            else:
                by_id[crit["id"]] = crit

    links = {
        col: spec[LINK_KEY]
        for col, spec in sidecar.items()
        if isinstance(spec, dict) and spec.get(LINK_KEY)
    }
    if not links:
        return []

    tsv = root / "participants.tsv"
    try:
        with tsv.open(encoding="utf-8-sig", newline="") as handle:
            reader = csv.DictReader(handle, delimiter="\t")
            columns = reader.fieldnames or []
            rows = list(reader)
    except OSError:
        return []  # unreadable files are reported elsewhere

    config: list[tuple[str, str, str]] = []
    found: list[tuple[str, str, str]] = []
    for col, crit_id in links.items():
        crit = by_id.get(crit_id)
        if crit is None:
            config.append(("WARNING", f"PRISM603 Column '{col}' is linked to eligibility criterion '{crit_id}', which is not in project.json.", str(root / "participants.json")))
            continue
        if crit_id in duplicates:
            config.append(("WARNING", f"PRISM603 Eligibility criterion id '{crit_id}' is defined more than once in project.json; the first one is used.", str(root / "project.json")))
        if col not in columns:
            config.append(("WARNING", f"PRISM603 Eligibility criterion '{crit_id}' is linked to column '{col}', which is not in participants.tsv.", str(tsv)))
            continue
        kind = "exclusion" if crit.get("mode") == "exclude" else "inclusion"
        where = "inside" if crit.get("mode") == "exclude" else "outside"
        label = crit.get("label") or crit_id
        if crit.get("type") == "categorical":
            labels = _level_labels(sidecar.get(col))
            if not labels:
                config.append(("WARNING", f"PRISM603 Eligibility criterion '{crit_id}' cannot be checked: column '{col}' has no Levels (value labels) in participants.json.", str(root / "participants.json")))
                continue
            wanted = {str(v) for v in crit.get("values") or []}
            expected = f"values {', '.join(sorted(wanted))}"

            def violates(raw, labels=labels, wanted=wanted, crit=crit):
                hit = labels.get(raw) in wanted
                return hit if crit.get("mode") == "exclude" else not hit

            def shown(raw, labels=labels):
                return f"{raw} ({labels[raw]})" if raw in labels else raw
        elif crit.get("type") == "numeric":
            lo, hi = crit.get("min"), crit.get("max")
            if lo is not None and hi is not None and lo > hi:
                config.append(("WARNING", f"PRISM603 Eligibility criterion '{crit_id}' has min {_num(lo)} greater than max {_num(hi)}; it is skipped.", str(root / "project.json")))
                continue
            expected = f"range {_range_text(crit)}"

            def violates(raw, crit=crit):
                return _numeric_violation(raw, crit)

            def shown(raw):
                return raw
        else:
            continue
        for row in rows:
            raw = (row.get(col) or "").strip()
            if raw.lower() in _MISSING or not violates(raw):
                continue
            found.append(("WARNING", f"PRISM602 {row.get('participant_id', '?')}: {col} {shown(raw)} is {where} the {kind} {expected} (criterion: {label})", str(tsv)))

    if found:
        config.append(("WARNING", f"PRISM602 {len(found)} participant(s) outside eligibility criteria.", str(tsv)))
    return config + found
