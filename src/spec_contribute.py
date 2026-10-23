"""Propose-changes page backend: what can be proposed, with or without a project."""

from __future__ import annotations

import re

from src.spec_overlay import OverlayError, _enum_of, _official_schema, _vendored_or_error
from src.specification import current_specification
from src.term_proposal import ProposalError, as_v2, check_with_specification, issue_url, slugify
from src.term_registry import find_term, load_registry

_VALUE = re.compile(r"[a-z0-9][a-z0-9-]*")


def _list_label(field: str) -> str:
    words = re.sub(r"(?<!^)(?=[A-Z])", " ", field.rsplit(".", 1)[-1]).lower()
    return words[:1].upper() + words[1:]


def spec_catalog() -> dict:
    """Modalities with extendable lists, their known measurements, units and specimens."""
    from src.schema_manager import DEFAULT_SCHEMA_DIR, load_schema  # lazy: specification imports this package

    spec = current_specification()
    modalities, units = [], set()
    for name in sorted(spec.prism_modalities):
        fields = spec.patchable_fields(name)
        # The vendored check (scripts/specification/check_terms.py `specimen_types`, term_proposal.py `_specimens_of`)
        # assumes a Technical.SpecimenType enum, so other kinds of data would crash on share. Widen once
        # prism-specification tolerates schemas without it (upstream change, tag, scripts/sync_specification.py).
        if "Technical.SpecimenType" not in fields:
            continue
        schema = load_schema(name, DEFAULT_SCHEMA_DIR, "stable")
        registry = load_registry(name)
        units.update(t["Units"] for t in registry.values() if t.get("Units"))
        modalities.append({
            "name": name,
            "label": name.capitalize(),
            "lists": [{"field": f, "label": _list_label(f), "values": [v for v in _enum_of(schema, f) or [] if v != ""]} for f in fields],
            "metrics": [
                {"id": t["TermID"], "label": t.get("Label", ""), "units": t.get("Units")}
                for t in registry.values() if t.get("Level") == "analyte"
            ] if registry else None,
        })
    biosample = next((m for m in modalities if m["name"] == "biosample"), None)
    specimens = next((x["values"] for x in biosample["lists"] if x["field"] == "Technical.SpecimenType"), []) if biosample else []
    return {"modalities": modalities, "units": sorted(units), "specimens": specimens}


def proposal_for_values(modality: str, field: str, values: list[str]) -> dict:
    """The proposal for new choices in one list of a kind of data; needs no project and writes nothing.

    Returns {"proposal", "document" (format v2), "issue_url", "problems", "skipped"}; `skipped` are values already official.
    """
    kinds = {m["name"]: [x["field"] for x in m["lists"]] for m in spec_catalog()["modalities"]}
    if modality not in kinds:
        raise OverlayError(f"unknown kind of data {modality!r}; choose one of: {', '.join(kinds)}")
    if field not in kinds[modality]:
        raise OverlayError(f"unknown list {field!r} for {modality}; choose one of: {', '.join(kinds[modality])}")
    if not values:
        raise OverlayError("say which values to propose")
    for value in values:
        if not isinstance(value, str) or not _VALUE.fullmatch(value):
            raise OverlayError(f"{value!r}: use lowercase letters, digits and - (starting with a letter or digit)")
    sp = _vendored_or_error("schema_patch")
    schema = _official_schema(modality)
    try:
        adds, _ = sp.additions(schema, {"operations": [{"op": "add_enum_values", "path": field, "values": list(values)}]})
    except ValueError as exc:  # PatchError, a different class per loaded copy of the script
        if str(exc).startswith("nothing to add"):
            raise OverlayError(f"already allowed in {field}: {', '.join(values)}") from exc
        raise OverlayError(str(exc)) from exc
    new = adds[0]["values"]
    patch = {"operations": [{"op": "add_enum_values", "path": field, "values": new}]}
    if problems := sp.validate_patch(patch, schema):
        raise OverlayError("; ".join(problems))
    proposal = {"modality": modality, "terms": [], "patch": patch}
    document = as_v2(proposal)
    return {
        "proposal": proposal,
        "document": document,
        "issue_url": issue_url(document),
        "problems": check_with_specification(document, load_registry(modality)),
        "skipped": [v for v in values if v not in new],
    }


def proposal_for_new_metric(
    name: str, description: str, units: str, specimen: str,
    aliases: list[str] | None = None, modality: str = "biosample", specimens: list[str] | None = None,
) -> dict:
    """The proposal for one missing measurement (its analyte term and the specimen-specific child); needs no project.

    `specimens` replaces the allowed sample types for the check (a project's own additions).
    Same result shape as `proposal_for_values`; nothing is written.
    """
    kinds = [m["name"] for m in spec_catalog()["modalities"]]
    if modality not in kinds:
        raise OverlayError(f"unknown kind of data {modality!r}; choose one of: {', '.join(kinds)}")
    registry = load_registry(modality)
    if not registry:
        raise OverlayError(f"{modality} has no known measurements")
    fields = {"name": name, "description": description, "units": units, "specimen": specimen}
    if empty := [k for k, v in fields.items() if not isinstance(v, str) or not v.strip()]:
        raise OverlayError(f"missing: {', '.join(empty)}")
    aliases = [a for a in aliases or [] if a]
    for text in [name, *aliases]:
        # ponytail: a known measurement for a new sample type is not offered yet; add when the page needs it
        if found := find_term(registry, text):
            raise OverlayError(f"{text!r} is already an official measurement ({found[1]['TermID']})")
    try:
        parent_id = f"prism:{slugify(name)}"
    except ProposalError as exc:
        raise OverlayError(str(exc)) from exc
    parent = {"TermID": parent_id, "Level": "analyte", "Label": name, **({"Aliases": aliases} if aliases else {}), "Description": description}
    child = {"TermID": f"{parent_id}.{specimen}", "Level": "analyte-specimen", "Parent": parent_id, "SpecimenType": specimen, "Units": units}
    proposal = {"modality": modality, "terms": [parent, child]}
    document = as_v2(proposal)
    return {
        "proposal": proposal,
        "document": document,
        "issue_url": issue_url(document),
        "problems": check_with_specification(document, registry, specimens),
        "skipped": [],
    }
