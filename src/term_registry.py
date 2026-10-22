"""Term registry: shipped terms (parent = analyte, child = analyte in one specimen).

JSON only (the validator image has no pandas). Spec:
docs/superpowers/specs/2026-10-22-biosample-term-registry-design.md
"""

from __future__ import annotations

import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path

_REPO = Path(__file__).resolve().parents[1]
_SCHEMA = _REPO / "app" / "schemas" / "stable" / "biosample.schema.json"


def terms_root() -> Path:
    """`official/library/terms` in dev, in the validator image and in the frozen build.

    The frozen onedir build bundles `official/` at `<_MEIPASS>/official`
    (scripts/build/build_app.py), like the schemas.
    """
    candidates = [_REPO / "official" / "library" / "terms"]
    meipass = getattr(sys, "_MEIPASS", None) if getattr(sys, "frozen", False) else None
    if meipass:
        candidates.append(Path(meipass).resolve() / "official" / "library" / "terms")
    return next((c for c in candidates if c.is_dir()), candidates[0])


ID_PREFIXES = ("prism", "bids")
_SLUG = re.compile(r"^[a-z][a-z0-9-]*$")
_LOINC = re.compile(r"^\d+-\d$")
_STATUSES = ("official", "deprecated")


def load_registry(modality: str = "biosample", root: Path | None = None) -> dict[str, dict]:
    """Map each term file's stem (the local part of its TermID) to the parsed term.

    A missing folder gives an empty registry; unreadable files are skipped
    (check_registry is the place that reports problems).
    """
    folder = Path(root or terms_root()) / modality
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

        for name in [term.get("Label")] + list(term.get("Aliases") or []) + list(term.get("Equivalents") or []):
            if not name:
                continue
            owner = claims.setdefault(str(name).lower(), key)
            if owner != key:
                problems.append(f"{key}: {name!r} is already claimed by {owner!r}")
    return problems


@dataclass(frozen=True)
class Resolution:
    """How a sidecar column relates to the registry.

    kind: term | specimen_mismatch | known_analyte_new_specimen | suggestion |
    deprecated | unknown. `term` is the resolved child (or the parent when no
    child exists for the specimen); `similar` lists term IDs worth showing.
    """

    kind: str
    term: dict | None = None
    similar: tuple[str, ...] = ()
    message: str = ""


def _names(key: str, term: dict) -> list[str]:
    """Every string a term answers to, lowercased."""
    names = [term.get("TermID"), key, term.get("Label")]
    names += list(term.get("Aliases") or []) + list(term.get("Equivalents") or [])
    return [n.lower() for n in names if isinstance(n, str)]


def find_term(registry: dict[str, dict], name: str) -> tuple[str, dict] | None:
    """Exact full ID, then bare slug, then label/alias/equivalent (case-insensitive)."""
    if not isinstance(name, str) or not name:
        return None
    for key, term in registry.items():
        if term.get("TermID") == name:
            return key, term
    if name in registry:
        return name, registry[name]
    lowered = name.lower()
    for key, term in registry.items():
        if lowered in _names(key, term):
            return key, term
    return None


def _similar(registry: dict[str, dict], probe: str) -> tuple[str, ...]:
    """Parent terms whose name is contained in the probe or contains it (substring only)."""
    lowered = probe.lower()
    hits = []
    for key, term in registry.items():
        if term.get("Level") != "analyte":
            continue
        if any(len(n) >= 3 and (n in lowered or lowered in n) for n in _names(key, term)):
            hits.append(term["TermID"])
    return tuple(sorted(hits))


def resolve_column(registry: dict[str, dict], column: str, col_def: dict, specimen: str | None) -> Resolution:
    """Resolve one sidecar column against the registry (spec: "How a sidecar column refers to a term")."""
    ref = col_def.get("Term")
    ref = ref if isinstance(ref, str) and ref else None  # anything else is not a Term
    found = find_term(registry, ref) if ref else None
    if not found:
        hit = None if ref else find_term(registry, column)
        if hit and hit[1].get("Status") != "deprecated":
            tid = hit[1]["TermID"]
            return Resolution("suggestion", hit[1], (tid,), f"{column!r} looks like {tid}; add Term to use it")
        if not hit:
            return Resolution("unknown", None, _similar(registry, ref or column))
        found = hit

    _key, term = found
    res = _by_specimen(registry, term, specimen)
    # A deprecated term (itself or the child reached through it) still supplies
    # its definition, so a rename or merge never breaks a file.
    old = next((t for t in (term, res.term) if t and t.get("Status") == "deprecated"), None)
    if old and res.kind in ("term", "known_analyte_new_specimen"):
        new = old.get("ReplacedBy", "")
        return Resolution("deprecated", res.term, (new,) if new else (), f"{old['TermID']} is deprecated; use {new}")
    return res


def _by_specimen(registry: dict[str, dict], term: dict, specimen: str | None) -> Resolution:
    """Pick the child of `term` for the specimen (or check a child against it)."""
    if term.get("Level") == "analyte-specimen":
        if term.get("SpecimenType") == specimen:
            return Resolution("term", term)
        return Resolution(
            "specimen_mismatch", term, (),
            f"{term['TermID']} is a {term.get('SpecimenType')} term but the sidecar SpecimenType is {specimen!r}",
        )
    for child in registry.values():
        if child.get("Parent") == term["TermID"] and specimen and child.get("SpecimenType") == specimen:
            return Resolution("term", child)
    return Resolution(
        "known_analyte_new_specimen", term, (),
        f"{term['TermID']} is known, but not yet for specimen {specimen!r}",
    )
