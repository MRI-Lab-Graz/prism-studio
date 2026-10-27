"""Check a term registry folder: IDs, parents, specimens, aliases, deprecations.

Stdlib only and independent of Studio's code: it runs in prism-studio and in the
prism-specification repository.

Usage: python scripts/check_terms.py --terms DIR --schema FILE
       python scripts/check_terms.py --modality NAME [--repo DIR]
       python scripts/check_terms.py --all [--repo DIR]   (every NAME; fails when none is declared)
  DIR   folder with one <local-id>.json per term (for example terms/biosample)
  FILE  the modality schema whose context enum (Technical.SpecimenType) lists the specimens
  NAME  a modality whose entities.schema.json entry declares `terms`; reads
        REPO/terms/NAME and REPO/schemas/stable/NAME.schema.json
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
_CF_NAME = re.compile(r"^[a-z][a-z0-9_]*$")
_LOINC = re.compile(r"^\d+-\d$")
_STATUSES = ("official", "deprecated")


_STRINGS = ("Level", "Label", "Description", "Parent", "SpecimenType", "Units", "LOINC", "CFStandardName", "Group")
_STRING_LISTS = ("Aliases", "AlternativeUnits", "Equivalents")
_NUMBERS = ("MinValue", "WarnMaxValue")


def type_problems(term: dict, where: str) -> list[str]:
    """Value types: the checks assume them, and a wrong type must be a message, not a crash."""
    problems = []
    for key in _STRINGS:
        if key in term and not isinstance(term[key], str):
            problems.append(f"{where}: {key} must be a string")
    group = term.get("Group")
    if isinstance(group, str) and (not 1 <= len(group) <= 60 or "\n" in group):
        problems.append(f"{where}: Group must be 1-60 characters without a line break")
    for key in _STRING_LISTS:
        if key in term and not (isinstance(term[key], list) and all(isinstance(v, str) for v in term[key])):
            problems.append(f"{where}: {key} must be a list of strings")
    if "Levels" in term and not (
        isinstance(term["Levels"], dict)
        and all(isinstance(k, str) and isinstance(v, str) for k, v in term["Levels"].items())
    ):
        problems.append(f"{where}: Levels must be an object of strings")
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


def check_registry(registry: dict[str, dict], specimen_types: list[str] | None) -> list[str]:
    """Return human-readable problems of a registry (empty list = valid).

    specimen_types None = a one-level registry (only Level 'variable'); a list, even an
    empty one, = the two-level biosample rules.
    """
    problems: list[str] = []
    one_level = specimen_types is None
    specimens = specimen_types or []
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

        if "CFStandardName" in term and not _CF_NAME.fullmatch(term["CFStandardName"]):
            problems.append(f"{key}: CFStandardName {term['CFStandardName']!r} must match {_CF_NAME.pattern}")

        level = term.get("Level")
        if one_level:
            if level != "variable":
                problems.append(f"{key}: Level must be 'variable'")
            else:
                if not _SLUG.fullmatch(local):
                    problems.append(f"{key}: ID local part {local!r} must match {_SLUG.pattern}")
                if not term.get("Label"):
                    problems.append(f"{key}: variable term needs a Label")
                if bool(term.get("Units")) == bool(term.get("Levels")):  # an empty value counts as missing
                    problems.append(f"{key}: variable term needs exactly one of Units or Levels")
        elif level == "analyte":
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


def context_values(schema_file: Path, field: str | None) -> list[str] | None:
    """The enum at a dotted schema field such as Technical.SpecimenType ([] when absent; None without a field)."""
    if field is None:
        return None
    node = json.loads(Path(schema_file).read_text(encoding="utf-8"))
    for part in field.split("."):
        node = node.get("properties", {}).get(part, {})
    return node.get("enum", [])


def specimen_types(schema_file: Path) -> list[str]:
    """The Technical.SpecimenType enum of a modality schema ([] when it has none)."""
    return context_values(schema_file, "Technical.SpecimenType") or []


def term_modalities(repo: Path) -> dict[str, dict]:
    """Modality -> its `terms` declaration, from REPO/schemas/stable/entities.schema.json (the one reader)."""
    entities = json.loads((Path(repo) / "schemas" / "stable" / "entities.schema.json").read_text(encoding="utf-8"))
    return {n: m["terms"] for n, m in entities.get("modalities", {}).items() if isinstance(m.get("terms"), dict)}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    mode = ap.add_mutually_exclusive_group()
    mode.add_argument("--all", action="store_true", help="every modality that declares terms (fails when none does)")
    mode.add_argument("--modality")
    mode.add_argument("--terms", type=Path)
    ap.add_argument("--schema", type=Path)
    ap.add_argument("--repo", type=Path, default=Path(__file__).resolve().parent.parent)
    args = ap.parse_args(argv)
    if args.schema and not args.terms:
        ap.error("--schema goes with --terms")
    if args.all or args.modality:
        declared = term_modalities(args.repo)
        names = list(declared) if args.all else [args.modality]
        if not names:
            ap.error("no modality declares terms in entities.schema.json")
        jobs = []
        for name in names:
            if name not in declared:
                ap.error(f"{name!r} does not declare terms in entities.schema.json")
            schema = args.repo / "schemas" / "stable" / f"{name}.schema.json"
            prefix = f"{name}/" if args.all else ""
            jobs.append((prefix, args.repo / "terms" / name, context_values(schema, declared[name].get("contextField"))))
    elif args.terms and args.schema:
        jobs = [("", args.terms, specimen_types(args.schema))]
    else:
        ap.error("give --all, --modality NAME, or --terms DIR and --schema FILE")
    problems = []
    for prefix, terms, context in jobs:
        registry, found = load_terms(terms)
        problems += [prefix + p for p in found + check_registry(registry, context)]
    for problem in problems:
        print(problem)
    return 1 if problems else 0

if __name__ == "__main__":
    sys.exit(main())
