"""Check a term registry folder: IDs, parents, specimens, aliases, deprecations.

Stdlib only and independent of Studio's code: it runs in prism-studio and in the
prism-specification repository.

Usage: python scripts/check_terms.py --terms DIR --schema FILE
  DIR   folder with one <local-id>.json per term (for example terms/biosample)
  FILE  the modality schema whose Technical.SpecimenType enum lists the specimens
Spec: docs/superpowers/specs/2026-10-22-biosample-term-registry-design.md
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

ID_PREFIXES = ("prism", "bids")
_SLUG = re.compile(r"^[a-z][a-z0-9-]{0,62}$")  # at most 63 characters per segment
_LOINC = re.compile(r"^\d+-\d$")
_STATUSES = ("official", "deprecated")


_STRINGS = ("Level", "Label", "Description", "Parent", "SpecimenType", "Units", "LOINC")
_STRING_LISTS = ("Aliases", "AlternativeUnits", "Equivalents")
_NUMBERS = ("MinValue", "WarnMaxValue")


def type_problems(term: dict, where: str) -> list[str]:
    """Value types: the checks assume them, and a wrong type must be a message, not a crash."""
    problems = []
    for key in _STRINGS:
        if key in term and not isinstance(term[key], str):
            problems.append(f"{where}: {key} must be a string")
    for key in _STRING_LISTS:
        if key in term and not (isinstance(term[key], list) and all(isinstance(v, str) for v in term[key])):
            problems.append(f"{where}: {key} must be a list of strings")
    for key in _NUMBERS:
        if key in term and (isinstance(term[key], bool) or not isinstance(term[key], (int, float))):
            problems.append(f"{where}: {key} must be a number")
    return problems


def load_terms(folder: Path) -> tuple[dict[str, dict], list[str]]:
    """Map each file stem to its parsed term; unreadable files become problems."""
    registry: dict[str, dict] = {}
    problems: list[str] = []
    for path in sorted(Path(folder).glob("*.json")):
        try:
            term = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            problems.append(f"{path.name}: cannot read ({exc})")
            continue
        if isinstance(term, dict):
            registry[path.stem] = term
        else:
            problems.append(f"{path.name}: a term file must hold a JSON object")
    return registry, problems


def check_registry(registry: dict[str, dict], specimen_types: list[str]) -> list[str]:
    """Return human-readable problems of a registry (empty list = valid)."""
    problems: list[str] = []
    specimens = specimen_types
    full_ids = {t.get("TermID") for t in registry.values()}
    # Every name a term answers to; a second claimant is a collision.
    claims: dict[str, str] = {}
    for key, term in registry.items():
        for name in (term.get("TermID"), key):
            if isinstance(name, str):
                claims.setdefault(name.lower(), key)

    for key, term in registry.items():
        bad_types = type_problems(term, key)
        if bad_types:  # everything below assumes the types
            problems += bad_types
            continue
        tid = term.get("TermID")
        prefix, _, local = tid.partition(":") if isinstance(tid, str) else ("", "", "")
        if prefix not in ID_PREFIXES:
            problems.append(f"{key}: TermID {tid!r} needs a prefix from {', '.join(ID_PREFIXES)}")
        if local != key:
            problems.append(f"{key}: local part of TermID {tid!r} must equal the file name {key!r}")
        if term.get("Status") not in _STATUSES:
            problems.append(f"{key}: Status must be one of {', '.join(_STATUSES)}")
        if term.get("Status") == "deprecated":
            replaced = term.get("ReplacedBy")
            if not replaced:
                problems.append(f"{key}: deprecated term needs ReplacedBy")
            elif replaced not in full_ids:
                problems.append(f"{key}: ReplacedBy {replaced!r} is not a term of this registry")
        if "LOINC" in term and not _LOINC.fullmatch(str(term["LOINC"])):
            problems.append(f"{key}: LOINC {term['LOINC']!r} does not look like 2143-6")

        level = term.get("Level")
        if level == "analyte":
            if not _SLUG.fullmatch(local.split(".")[0] or "") or "." in local:
                problems.append(f"{key}: parent ID local part {local!r} must match {_SLUG.pattern}")
            if not term.get("Label"):
                problems.append(f"{key}: parent term needs a Label")
        elif level == "analyte-specimen":
            specimen = term.get("SpecimenType")
            if specimens and specimen not in specimens:
                problems.append(f"{key}: SpecimenType {specimen!r} is not a biosample SpecimenType")
            parent_id = term.get("Parent")
            parent_key = parent_id.partition(":")[2] if isinstance(parent_id, str) else ""
            parent = registry.get(parent_key)
            if not parent or parent.get("TermID") != parent_id or parent.get("Level") != "analyte":
                problems.append(f"{key}: Parent {parent_id!r} is not a parent term of this registry")
            elif local != f"{parent_key}.{specimen}":
                problems.append(f"{key}: child ID must be {prefix}:{parent_key}.{specimen}")
            if not term.get("Units"):
                problems.append(f"{key}: child term needs Units")
        else:
            problems.append(f"{key}: Level must be 'analyte' or 'analyte-specimen'")

        for name in [term.get("Label")] + list(term.get("Aliases") or []) + list(term.get("Equivalents") or []):
            if not name:
                continue
            owner = claims.setdefault(str(name).lower(), key)
            if owner != key:
                problems.append(f"{key}: {name!r} is already claimed by {owner!r}")
    return problems


def specimen_types(schema_file: Path) -> list[str]:
    """The Technical.SpecimenType enum of a modality schema."""
    schema = json.loads(Path(schema_file).read_text(encoding="utf-8"))
    return schema["properties"]["Technical"]["properties"]["SpecimenType"]["enum"]


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--terms", required=True, type=Path)
    ap.add_argument("--schema", required=True, type=Path)
    args = ap.parse_args(argv)
    registry, problems = load_terms(args.terms)
    problems += check_registry(registry, specimen_types(args.schema))
    for problem in problems:
        print(problem)
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
