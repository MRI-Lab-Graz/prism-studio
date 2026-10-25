"""Propose-changes page backend: what can be proposed, with or without a project."""

from __future__ import annotations

import json
import re

from src.spec_overlay import OverlayError, _enum_of, _value_at, _project_specimens, _official_schema, _vendored_or_error
from src.specification import current_specification
from src.term_proposal import ProposalError, as_v2, check_with_specification, issue_url, slugify
from src.term_registry import find_term, load_registry, terms_root

_VALUE = re.compile(r"[a-z0-9][a-z0-9-]*")


def _list_label(field: str) -> str:
    words = re.sub(r"(?<!^)(?=[A-Z])", " ", field.rsplit(".", 1)[-1]).lower()
    return words[:1].upper() + words[1:]


def _kinds() -> dict[str, list[str]]:
    """Each kind of data in the catalog with the fields of its extendable lists."""
    return {m["name"]: [x["field"] for x in m["lists"]] for m in spec_catalog()["modalities"] if m["lists"]}


def proposal_context(entries: dict[str, str] | None = None, not_sure: bool = False, closest: str | None = None) -> str | None:
    """The text for the form's Context field: "not sure" (with the closest kind of data), then one `field: value` line per entry."""
    if not isinstance(not_sure, bool) or not (closest is None or isinstance(closest, str)):
        raise OverlayError('"not_sure" must be true or false and "closest" text')
    if entries is not None and not isinstance(entries, dict):
        raise OverlayError('"entries" must be an object of text')
    entries = entries or {}
    if len(entries) > 100:
        raise OverlayError("at most 100 entries")
    if not all(isinstance(k, str) and isinstance(v, str) for k, v in entries.items()):
        raise OverlayError("entries must be text")
    if long := [k for k, v in entries.items() if len(v) > 200]:
        raise OverlayError(f"value too long (at most 200 characters): {', '.join(long)}")
    if bad := [k for k, v in entries.items() if not (k + v).isprintable()]:
        raise OverlayError(f"no line breaks or control characters allowed in: {', '.join(map(repr, bad))}")
    lines = []
    if not_sure:
        if closest and closest not in {m["name"] for m in spec_catalog()["modalities"]}:
            raise OverlayError(f"unknown kind of data {closest!r}")
        lines.append("Not sure which kind of data this belongs to" + (f" (closest: {closest})" if closest else ""))
    lines += [f"{k}: {v}" for k, v in entries.items()]
    return "\n".join(lines) or None


def _context(context, entries, not_sure, closest) -> str | None:
    """An explicit `context` text followed by the one built from `entries` / `not_sure` / `closest` (either may be empty)."""
    built = proposal_context(entries, not_sure, closest)
    return "\n".join(t for t in (context, built) if t) or None


def _result(proposal: dict, registry: dict, specimens=None, skipped=(), context: str | None = None) -> dict:
    """The result both builders return; nothing is written."""
    document = as_v2(proposal)
    return {
        "proposal": proposal,
        "document": document,
        "context": context,
        "issue_url": issue_url(document, context=context),
        "problems": check_with_specification(document, registry, specimens),
        "skipped": list(skipped),
    }


def _templates(modality: str) -> list[str]:
    """Stems of the library templates of a kind of data (`official/library/<modality>/`, next to the term registry)."""
    folder = terms_root().parent / modality
    return sorted(p.stem for p in folder.glob("*.json") if p.stem != "index") if folder.is_dir() else []


def spec_catalog() -> dict:
    """Every kind of data with its extendable lists, known measurements, units and library templates."""
    from src.schema_manager import DEFAULT_SCHEMA_DIR, load_schema  # lazy: specification imports this package

    spec = current_specification()
    rules = spec.rules
    modalities, units = [], set()
    for name in sorted(n for n in rules.modalities if n not in rules.aliases):
        rule = rules.modalities[name]
        is_prism = rule.kind == "prism"
        fields = spec.patchable_fields(name) if is_prism else []
        schema = load_schema(name, DEFAULT_SCHEMA_DIR, "stable") if fields else {}
        registry = load_registry(name) if is_prism else {}
        units.update(t["Units"] for t in registry.values() if t.get("Units"))
        modalities.append({
            "name": name,
            "label": rule.description or name,
            "kind": "prism" if is_prism else "bids",
            "lists": [{"field": f, "label": _list_label(f), "values": [v for v in _enum_of(schema, f) or [] if v != ""]} for f in fields],
            "metrics": [
                {
                    "id": t["TermID"], "label": t.get("Label", ""), "units": t.get("Units"),
                    "specimens": sorted(c["SpecimenType"] for c in registry.values() if c.get("Parent") == t["TermID"] and c.get("SpecimenType")),
                }
                for t in registry.values() if t.get("Level") == "analyte"
            ] if registry else None,
            "templates": _templates(name),
        })
    biosample = next((m for m in modalities if m["name"] == "biosample"), None)
    specimens = next((x["values"] for x in biosample["lists"] if x["field"] == "Technical.SpecimenType"), []) if biosample else []
    return {"modalities": modalities, "units": sorted(units), "specimens": specimens}


def _example_text(value) -> str | None:
    if value is None or isinstance(value, (dict, list)):
        return None
    return ("yes" if value else "no") if isinstance(value, bool) else str(value)


def example_entries(modality: str, template: str | None = None) -> dict:
    """What a kind of data accepts, field by field, with the value a library template gives as example.

    Entries are the leaf properties two levels down (section.field) of the schema, except `Metadata`.
    """
    from src.schema_manager import DEFAULT_SCHEMA_DIR, load_schema  # lazy: specification imports this package

    current = next((m for m in spec_catalog()["modalities"] if m["name"] == modality), None) if isinstance(modality, str) else None
    if current is None:
        raise OverlayError(f"{modality}: not a kind of data of this specification")
    templates = current["templates"]
    if template is not None and template not in templates:
        raise OverlayError(f"unknown template {template!r} for {modality}; choose one of: {', '.join(templates) or 'none'}")
    if current["kind"] != "prism":
        return {"modality": modality, "template": None, "templates": [], "entries": []}
    template = template or (templates[0] if templates else None)
    data = {}
    if template:
        try:
            data = json.loads((terms_root().parent / modality / f"{template}.json").read_text(encoding="utf-8"))
        except (OSError, ValueError):
            data = {}
    schema = load_schema(modality, DEFAULT_SCHEMA_DIR, "stable") or {}
    entries = []
    for section, node in (schema.get("properties") or {}).items():
        if section == "Metadata" or not isinstance(node, dict):
            continue
        for name, child in (node.get("properties") or {}).items():
            if not isinstance(child, dict) or child.get("properties"):
                continue
            field = f"{section}.{name}"
            values = [v for v in _enum_of(schema, field) or [] if v != ""]
            entries.append({
                "field": field, "label": _list_label(field),
                "example": _example_text(_value_at(data, field)), "values": values or None,
            })
    return {"modality": modality, "template": template, "templates": templates, "entries": entries}


def proposal_for_values(
    modality: str, field: str, values: list[str], context: str | None = None,
    entries: dict | None = None, not_sure: bool = False, closest: str | None = None,
) -> dict:
    """The proposal for new choices in one list of a kind of data; needs no project and writes nothing.

    Returns {"proposal", "document" (format v2), "context", "issue_url", "problems", "skipped"}; `skipped` are values already official.
    """
    context = _context(context, entries, not_sure, closest)
    kinds = _kinds()
    if modality not in kinds:
        raise OverlayError(f"unknown kind of data {modality!r}; choose one of: {', '.join(kinds)}")
    if field not in kinds[modality]:
        raise OverlayError(f"unknown list {field!r} for {modality}; choose one of: {', '.join(kinds[modality])}")
    values = list(dict.fromkeys(values))
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
    return _result({"modality": modality, "terms": [], "patch": patch}, load_registry(modality), skipped=[v for v in values if v not in new], context=context)


def proposal_for_new_metric(
    name: str, description: str, units: str, specimen: str,
    aliases: list[str] | None = None, modality: str = "biosample", project_root=None,
    context: str | None = None, entries: dict | None = None, not_sure: bool = False, closest: str | None = None,
) -> dict:
    """The proposal for one missing measurement (its analyte term and the specimen-specific child); needs no project.

    `project_root` (optional) adds that project's own sample types to the check.
    Same result shape as `proposal_for_values`; nothing is written.
    """
    context = _context(context, entries, not_sure, closest)
    kinds = _kinds()
    if modality not in kinds:
        raise OverlayError(f"unknown kind of data {modality!r}; choose one of: {', '.join(kinds)}")
    registry = load_registry(modality)
    if not registry:
        raise OverlayError(f"{modality} has no known measurements")
    specimens = _project_specimens(project_root, modality) if project_root else None
    fields = {"name": name, "description": description, "units": units, "specimen": specimen}
    if empty := [k for k, v in fields.items() if not isinstance(v, str) or not v.strip()]:
        raise OverlayError(f"missing: {', '.join(empty)}")
    name, description, units, specimen = (v.strip() for v in fields.values())
    if not _VALUE.fullmatch(specimen):
        raise OverlayError(f"{specimen!r}: use lowercase letters, digits and - for the sample type")
    seen = {name.lower()}
    cleaned = []
    for a in (a.strip() for a in aliases or [] if isinstance(a, str)):
        if a and a.lower() not in seen:
            seen.add(a.lower())
            cleaned.append(a)
    aliases = cleaned
    try:
        parent_id = f"prism:{slugify(name)}"
    except ProposalError as exc:
        raise OverlayError(str(exc)) from exc
    # ponytail: a known measurement for a new sample type is not offered yet; add when the page needs it
    for text in [name, *aliases, parent_id]:
        if found := find_term(registry, text):
            raise OverlayError(f"{text!r} is already an official measurement ({found[1]['TermID']})")
    parent = {"TermID": parent_id, "Level": "analyte", "Label": name, **({"Aliases": aliases} if aliases else {}), "Description": description}
    child = {"TermID": f"{parent_id}.{specimen}", "Level": "analyte-specimen", "Parent": parent_id, "SpecimenType": specimen, "Units": units}
    return _result({"modality": modality, "terms": [parent, child]}, registry, specimens, context=context)
