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
SCREENING_GROUP = "screening-only"


def is_screening_only(row: dict) -> bool:
    """Prescreened rows (``group`` = screening-only) skip eligibility and tailored checks."""
    return (row.get("group") or "").strip().lower() == SCREENING_GROUP


def _load_json(path: Path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def _num(value) -> str:
    return str(int(value)) if float(value).is_integer() else str(value)


def _range_text(crit: dict) -> str:
    lo, hi = crit.get("min"), crit.get("max")
    if lo is not None and hi is not None:
        text = f"{_num(lo)}-{_num(hi)}"
    elif lo is not None:
        text = f"at least {_num(lo)}"
    else:
        text = f"at most {_num(hi)}"
    return f"{text} {crit['unit']}" if crit.get("unit") else text


def _level_labels(spec) -> dict[str, set[str]]:
    """Code -> labels from a participants.json column.

    Both ``Levels`` (free text, whatever the lab wrote) and
    ``Annotations.Levels[code].Label`` (the NeuroBagel label) count, so a
    criterion written with NeuroBagel labels still matches German or
    abbreviated value labels.
    """
    if not isinstance(spec, dict):
        return {}
    sources = []
    if isinstance(spec.get("Levels"), dict):
        sources.append(spec["Levels"])
    annotations = spec.get("Annotations")
    if isinstance(annotations, dict) and isinstance(annotations.get("Levels"), dict):
        sources.append(annotations["Levels"])
    labels: dict[str, set[str]] = {}
    for source in sources:
        for code, value in source.items():
            if isinstance(value, dict):
                value = value.get("Label") or value.get("Description")
            if value:
                labels.setdefault(str(code), set()).add(str(value))
    return labels


def _numeric_violation(raw: str, crit: dict) -> bool:
    try:
        value = float(raw.replace(",", "."))
    except ValueError:
        return False  # the data-type checks report non-numeric values
    if value != value:  # "nan" parses as a float but is no measurement
        return False
    lo, hi = crit.get("min"), crit.get("max")
    inside = (lo is None or value >= lo) and (hi is None or value <= hi)
    return inside if crit.get("mode") == "exclude" else not inside


def _is_number(value) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _usable(crit) -> bool:
    """Shape the checks rely on; anything else is reported, never evaluated."""
    if not isinstance(crit, dict):
        return False
    if not (isinstance(crit.get("id"), str) and crit["id"]):
        return False
    if crit.get("mode") not in ("include", "exclude"):
        return False
    if crit.get("type") == "numeric":
        bounds = [crit[k] for k in ("min", "max") if k in crit]
        return bool(bounds) and all(_is_number(b) for b in bounds)
    if crit.get("type") == "categorical":
        values = crit.get("values")
        return isinstance(values, list) and bool(values) and all(isinstance(v, str) for v in values)
    return False


def usable_criteria(entries) -> list[dict]:
    """The entries of an ``Eligibility.Criteria`` value the checks can use."""
    return [c for c in entries if _usable(c)] if isinstance(entries, list) else []


def _read_criteria(root_dir: str) -> tuple[list[dict], list[tuple[str, str | None]]]:
    """(usable criteria, (description, id) per rejected entry) from project.json."""
    project = _load_json(Path(root_dir) / "project.json")
    eligibility = project.get("Eligibility") if isinstance(project, dict) else None
    entries = eligibility.get("Criteria") if isinstance(eligibility, dict) else None
    if not isinstance(entries, list):
        return [], []
    usable = usable_criteria(entries)
    rejected = []
    for n, c in enumerate(entries, 1):
        if _usable(c):
            continue
        crit_id = c.get("id") if isinstance(c, dict) and isinstance(c.get("id"), str) else None
        rejected.append((f"#{n}" + (f" ('{crit_id}')" if crit_id else ""), crit_id))
    return usable, rejected


def load_criteria(root_dir: str) -> list:
    """The project's usable ``Eligibility.Criteria``, ``[]`` when there are none."""
    return _read_criteria(root_dir)[0]


def check_eligibility(root_dir: str) -> list[tuple[str, str, str]]:
    root = Path(root_dir)
    criteria, rejected = _read_criteria(root_dir)
    sidecar = _load_json(root / "participants.json")
    if not (criteria or rejected) or not isinstance(sidecar, dict):
        return []

    by_id: dict[str, dict] = {}
    duplicates: set[str] = set()
    for crit in criteria:
        if crit["id"] in by_id:
            duplicates.add(crit["id"])
        else:
            by_id[crit["id"]] = crit

    links = {
        col: spec[LINK_KEY]
        for col, spec in sidecar.items()
        if isinstance(spec, dict) and isinstance(spec.get(LINK_KEY), str) and spec[LINK_KEY]
    }
    linked = set(links.values())
    unlinked = [
        ("WARNING", f"PRISM603 Eligibility criterion '{crit_id}' is not linked to a participants column, so it is not checked; link it in the participant annotation step (Eligibility criterion).", str(root / "participants.json"))
        for crit_id in by_id
        if crit_id not in linked
    ]
    if not links:
        return unlinked

    tsv = root / "participants.tsv"
    try:
        with tsv.open(encoding="utf-8-sig", newline="") as handle:
            reader = csv.DictReader(handle, delimiter="\t")
            columns = reader.fieldnames or []
            rows = list(reader)
    except (OSError, ValueError):
        return []  # unreadable or non-UTF-8 files are reported elsewhere

    config: list[tuple[str, str, str]] = [
        ("WARNING", f"PRISM603 Eligibility criterion {desc} in project.json is malformed (needs an id, type numeric or categorical, mode include or exclude, and a numeric min/max or a list of values); it is ignored.", str(root / "project.json"))
        for desc, _ in rejected
    ]
    found: list[tuple[str, str, str]] = []
    reported: set[str] = set()  # duplicate ids already warned about
    for col, crit_id in links.items():
        crit = by_id.get(crit_id)
        if crit is None and crit_id in {rid for _, rid in rejected}:
            continue  # already reported as malformed
        if crit is None:
            config.append(("WARNING", f"PRISM603 Column '{col}' is linked to eligibility criterion '{crit_id}', which is not in project.json.", str(root / "participants.json")))
            continue
        if crit_id in duplicates and crit_id not in reported:
            reported.add(crit_id)
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
            known = set().union(*labels.values())
            if not wanted & known:
                config.append(("WARNING", f"PRISM603 Eligibility criterion '{crit_id}' cannot be checked: none of its values ({', '.join(sorted(wanted))}) is a value label of column '{col}' ({', '.join(sorted(known))}).", str(root / "participants.json")))
                continue
            expected = f"values {', '.join(sorted(wanted))}"

            def violates(raw, labels=labels, wanted=wanted, crit=crit):
                hit = bool(labels.get(raw, set()) & wanted)
                return hit if crit.get("mode") == "exclude" else not hit
        else:  # numeric: _usable guarantees a known type
            lo, hi = crit.get("min"), crit.get("max")
            if lo is not None and hi is not None and lo > hi:
                config.append(("WARNING", f"PRISM603 Eligibility criterion '{crit_id}' has min {_num(lo)} greater than max {_num(hi)}; it is skipped.", str(root / "project.json")))
                continue
            if _level_labels(sidecar.get(col)):
                config.append(("WARNING", f"PRISM603 Eligibility criterion '{crit_id}' is numeric but column '{col}' has value labels (Levels), so its values are codes; link a categorical criterion instead.", str(root / "participants.json")))
                continue
            expected = f"range {_range_text(crit)}"

            def violates(raw, crit=crit):
                return _numeric_violation(raw, crit)

        values = ((row.get(col) or "").strip() for row in rows if not is_screening_only(row))
        count = sum(1 for raw in values if raw.lower() not in _MISSING and violates(raw))
        if count:  # one line per criterion: a count, never a list of participants
            found.append(("WARNING", f"PRISM602 {count} participant(s) with {col} {where} the {kind} {expected} (criterion: {label})", str(tsv)))

    return config + unlinked + found
