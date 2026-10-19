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

    issues: list[tuple[str, str, str]] = []
    for column in rows[0].keys() if rows else []:
        if column == "participant_id":
            continue
        values = {(row.get(column) or "").strip() for row in rows} - _MISSING
        spec = sidecar.get(column) if isinstance(sidecar, dict) else None
        spec = spec if isinstance(spec, dict) else {}
        levels = spec.get("Levels")
        if isinstance(levels, dict):
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
