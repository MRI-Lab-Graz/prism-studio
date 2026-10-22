"""Term registry: shipped terms (parent = analyte, child = analyte in one specimen).

JSON only (the validator image has no pandas). Spec:
docs/superpowers/specs/2026-10-22-biosample-term-registry-design.md
"""

from __future__ import annotations

import json
import re
from pathlib import Path

_REPO = Path(__file__).resolve().parents[1]
DEFAULT_TERMS_ROOT = _REPO / "official" / "library" / "terms"
_SCHEMA = _REPO / "app" / "schemas" / "stable" / "biosample.schema.json"

ID_PREFIXES = ("prism", "bids")
_SLUG = re.compile(r"^[a-z][a-z0-9-]*$")
_LOINC = re.compile(r"^\d+-\d$")
_STATUSES = ("official", "deprecated")


def load_registry(modality: str = "biosample", root: Path | None = None) -> dict[str, dict]:
    """Map each term file's stem (the local part of its TermID) to the parsed term.

    A missing folder gives an empty registry; unreadable files are skipped
    (check_registry is the place that reports problems).
    """
    folder = Path(root or DEFAULT_TERMS_ROOT) / modality
    registry: dict[str, dict] = {}
    for path in sorted(folder.glob("*.json")):
        try:
            term = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if isinstance(term, dict):
            registry[path.stem] = term
    return registry


def _specimen_types() -> list[str]:
    """SpecimenType enum from the biosample schema (single source of truth)."""
    try:
        schema = json.loads(_SCHEMA.read_text(encoding="utf-8"))
        return schema["properties"]["Technical"]["properties"]["SpecimenType"]["enum"]
    except (OSError, ValueError, KeyError):
        return []


def check_registry(registry: dict[str, dict]) -> list[str]:
    """Return human-readable problems of a registry (empty list = valid)."""
    problems: list[str] = []
    specimens = _specimen_types()
    full_ids = {t.get("TermID") for t in registry.values()}
    # Every name a term answers to; a second claimant is a collision.
    claims: dict[str, str] = {}
    for key, term in registry.items():
        for name in (term.get("TermID"), key):
            if isinstance(name, str):
                claims.setdefault(name.lower(), key)

    for key, term in registry.items():
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
        if "LOINC" in term and not _LOINC.match(str(term["LOINC"])):
            problems.append(f"{key}: LOINC {term['LOINC']!r} does not look like 2143-6")

        level = term.get("Level")
        if level == "analyte":
            if not _SLUG.match(local.split(".")[0] or "") or "." in local:
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

        for name in list(term.get("Aliases") or []) + list(term.get("Equivalents") or []):
            owner = claims.setdefault(str(name).lower(), key)
            if owner != key:
                problems.append(f"{key}: {name!r} is already claimed by {owner!r}")
    return problems
