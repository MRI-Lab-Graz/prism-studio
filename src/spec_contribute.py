"""Propose-changes page backend: what can be proposed, with or without a project."""

from __future__ import annotations

import re

from src.specification import current_specification
from src.term_registry import load_registry


def _list_label(field: str) -> str:
    words = re.sub(r"(?<!^)(?=[A-Z])", " ", field.rsplit(".", 1)[-1]).lower()
    return words[:1].upper() + words[1:]


def spec_catalog() -> dict:
    """Modalities with extendable lists, their known measurements, units and specimens."""
    from src.schema_manager import DEFAULT_SCHEMA_DIR, load_schema  # lazy: specification imports this package
    from src.spec_overlay import _enum_of

    spec = current_specification()
    modalities, units = [], set()
    for name in sorted(spec.prism_modalities):
        fields = spec.patchable_fields(name)
        if not fields:
            continue
        schema = load_schema(name, DEFAULT_SCHEMA_DIR, "stable")
        registry = load_registry(name)
        units.update(t["Units"] for t in registry.values() if t.get("Units"))
        modalities.append({
            "name": name,
            "label": name.capitalize(),
            "lists": [{"field": f, "label": _list_label(f), "values": list(_enum_of(schema, f) or [])} for f in fields],
            "metrics": [
                {"id": t["TermID"], "label": t.get("Label", ""), "units": t.get("Units")}
                for t in registry.values() if t.get("Level") == "analyte"
            ] if registry else None,
        })
    biosample = next((m for m in modalities if m["name"] == "biosample"), None)
    specimens = next((x["values"] for x in biosample["lists"] if x["field"] == "Technical.SpecimenType"), []) if biosample else []
    return {"modalities": modalities, "units": sorted(units), "specimens": specimens}
