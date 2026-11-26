"""Coded participants columns need value labels (Levels) in participants.json.

A column is only *guessed* to be coded (few distinct integer-like values and no
``Unit``), so an unlabeled one is a warning. A column that declares ``Levels``
has said it is categorical, so a value without a label is a certain error.
"""

from __future__ import annotations

import csv
import json
from pathlib import Path

MAX_CODES = 10  # more distinct values than this: not a code list
_MISSING = {"", "n/a", "na"}

# Codes Studio once wrote that mean something else, or are not in the vocabulary
# (checked 2026-11-26: NCI Thesaurus; SNOMED CT International via tx.fhir.org).
_ABSENT = "not in the current SNOMED CT International Edition"
WRONG_TERM_CODES = {
    "ncit:C17781": "it is GTP-Binding Protein RAD, not an education level",
    "ncit:C17782": "it is CDKN1A Gene, not an education level",
    "ncit:C17783": "it is Cyclin-Dependent Kinase Inhibitor 1, not an education level",
    "ncit:C17784": "it is Cyclin-Dependent Kinase 4 Inhibitor B, not an education level",
    "ncit:C17785": "it is Cyclin-Dependent Kinase 5, not an education level",
    "ncit:C20432": "it is Betacellulin, not an education level",
    "ncit:C41185": "it is Concentration, not a study group",
    "snomed:14421000": _ABSENT,
    "snomed:14647231000119105": _ABSENT,
    "snomed:16022009": _ABSENT,
    "snomed:20863000": _ABSENT,
    "snomed:224530016": _ABSENT,
    "snomed:447964000": _ABSENT,
    "snomed:78791000": _ABSENT,
    "snomed:87622008": _ABSENT,
    "snomed:408856003": "it is retired in SNOMED CT",
}


def _term_codes(value) -> set[str]:
    """Every string anywhere inside a sidecar entry."""
    if isinstance(value, dict):
        value = list(value.values())
    if isinstance(value, list):
        return set().union(*map(_term_codes, value))
    return {value} if isinstance(value, str) else set()


def _wrong_code_issues(sidecar, path: Path) -> list[tuple[str, str, str]]:
    if not isinstance(sidecar, dict):
        return []
    return [
        (
            "WARNING",
            f"participants.json column '{column}' uses the term code {code}: "
            f"{WRONG_TERM_CODES[code]}. Remove the TermURL or replace it with a "
            "code you have checked.",
            str(path),
        )
        for column, spec in sidecar.items()
        for code in sorted(_term_codes(spec) & WRONG_TERM_CODES.keys())
    ]


def _is_integer_like(value: str) -> bool:
    try:
        return float(value).is_integer()
    except ValueError:
        return True  # text such as "M"/"F" can be a code too


def add_missing_levels(schema: dict, df) -> None:
    """Add every data value a column's ``Levels`` lacks, labelled with the code itself.

    Codes can be any string (``-oth-``, ``AO02``), whatever tool produced them; a
    real label can be filled in later. Columns without ``Levels`` are left alone.
    """
    for column, spec in schema.items():
        levels = spec.get("Levels") if isinstance(spec, dict) else None
        if not isinstance(levels, dict) or column not in df.columns:
            continue
        values = {str(v).strip() for v in df[column].dropna()} - _MISSING
        for code in sorted(values - set(levels)):
            levels[code] = code


def _label(level) -> str:
    """A level's label; BIDS allows a string or an object."""
    if isinstance(level, dict):
        level = level.get("Label") or level.get("Description") or ""
    return str(level).strip().casefold()


def swapped_codes(levels: dict, annotations) -> list[str]:
    """Codes whose annotation label is the Levels label of a *different* code.

    Not reported: other wording (translations, standard term names), and a code
    that shares its term with the code of that label (many codes, one term).
    """
    annotated = annotations.get("Levels") if isinstance(annotations, dict) else None
    if not isinstance(annotated, dict):
        return []
    labels = {code: _label(level) for code, level in levels.items()}
    terms = {code: _label(term) for code, term in annotated.items()}
    return sorted(
        code
        for code, term in terms.items()
        if term
        and term != labels.get(code)
        and any(
            label == term and terms.get(other) != term
            for other, label in labels.items()
        )
    )


def check_participants_levels(root_dir: str) -> list[tuple[str, str, str]]:
    root = Path(root_dir)
    tsv, sidecar_path = root / "participants.tsv", root / "participants.json"
    if not tsv.is_file():
        return []
    try:
        sidecar = (
            json.loads(sidecar_path.read_text(encoding="utf-8"))
            if sidecar_path.is_file()
            else {}
        )
        with tsv.open(encoding="utf-8", newline="") as handle:
            rows = list(csv.DictReader(handle, delimiter="\t"))
    except (OSError, ValueError):
        return []  # unreadable files are reported elsewhere

    issues = _wrong_code_issues(sidecar, sidecar_path)
    for column in rows[0].keys() if rows else []:
        if column == "participant_id":
            continue
        values = {(row.get(column) or "").strip() for row in rows} - _MISSING
        spec = sidecar.get(column) if isinstance(sidecar, dict) else None
        spec = spec if isinstance(spec, dict) else {}
        levels = spec.get("Levels")
        if isinstance(levels, dict):
            swapped = swapped_codes(levels, spec.get("Annotations"))
            if swapped:
                issues.append(
                    (
                        "ERROR",
                        (
                            f"participants.json column '{column}': Levels and "
                            f"Annotations.Levels contradict each other for codes "
                            f"{', '.join(swapped)}. Check the codebook and correct "
                            "the wrong block."
                        ),
                        str(sidecar_path),
                    )
                )
            missing = sorted(values - set(levels))
            if missing:
                issues.append(
                    (
                        "ERROR",
                        (
                            f"participants.json value labels for column '{column}' "
                            f"miss {', '.join(missing)}: add each value to Levels."
                        ),
                        str(sidecar_path),
                    )
                )
        elif (
            values
            and len(values) <= MAX_CODES
            and "Unit" not in spec
            and all(_is_integer_like(v) for v in values)
        ):
            issues.append(
                (
                    "WARNING",
                    (
                        f"participants.json has no value labels for column '{column}' "
                        f"(values: {', '.join(sorted(values))}). If these are codes, "
                        "add Levels; if it is a measurement, add a Unit."
                    ),
                    str(sidecar_path),
                )
            )
    return issues
