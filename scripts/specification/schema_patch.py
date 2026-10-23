"""Additive patches to a modality schema: new enum values and new optional properties.

A patch is untrusted input (a project's file, or a proposal). It can only ADD, with tight limits, and every
name and path is checked with an allow-list before anything is applied. Stdlib only; used by the bot
(scripts/term_proposal.py, scripts/release_patch.py) and vendored into PRISM Studio.

Patch format:
  {"operations": [
     {"op": "add_enum_values", "path": "Technical.SpecimenType", "values": ["sweat"]},
     {"op": "add_optional_properties", "path": "Technical",
      "properties": {"SweatRate": {"type": "number", "description": "Sweat rate in mg/min"}}}]}
`path` is dotted sidecar field names (Technical.SpecimenType), resolved to properties.Technical.properties.SpecimenType.
Spec: docs/superpowers/specs/2026-10-23-specification-contributions-design.md in prism-studio
"""

from __future__ import annotations

import copy
import re

MAX_OPERATIONS = 20
MAX_ITEMS = 20  # values per operation / properties per operation
MAX_DEPTH = 3  # dotted path segments
MAX_DESCRIPTION = 500

_VALUE = re.compile(r"[a-z][a-z0-9-]{0,62}")
_PROPERTY_NAME = re.compile(r"[A-Z][A-Za-z0-9]{0,62}")
_SEGMENT = re.compile(r"[A-Za-z][A-Za-z0-9]{0,62}")
_TYPES = ("string", "number", "integer", "boolean")
_PROPERTY_KEYS = {"type", "description", "enum"}
_OPERATIONS = {
    "add_enum_values": {"op", "path", "values"},
    "add_optional_properties": {"op", "path", "properties"},
}


class PatchError(ValueError):
    """The patch is invalid or adds nothing."""


def _resolve(schema: dict, path) -> dict | None:
    """The schema node of a dotted sidecar path, or None."""
    if not isinstance(path, str):
        return None
    segments = path.split(".")
    if not 1 <= len(segments) <= MAX_DEPTH or not all(_SEGMENT.fullmatch(s) for s in segments):
        return None
    node = schema
    for segment in segments:
        properties = node.get("properties") if isinstance(node, dict) else None
        if not isinstance(properties, dict) or not isinstance(properties.get(segment), dict):
            return None
        node = properties[segment]
    return node


def _enum_problems(schema: dict, op: dict, where: str) -> list[str]:
    node = _resolve(schema, op.get("path"))
    if node is None or not isinstance(node.get("enum"), list):
        return [f"{where}: path {op.get('path')!r} is not an enum field of the schema"]
    values = op.get("values")
    if not isinstance(values, list) or not 1 <= len(values) <= MAX_ITEMS:
        return [f"{where}: values must be a list of 1 to {MAX_ITEMS} strings"]
    problems = []
    if not all(isinstance(v, str) and _VALUE.fullmatch(v) for v in values):
        problems.append(f"{where}: every value must be lowercase letters, digits and '-' (at most 63 characters)")
    if len(set(map(str, values))) != len(values):
        problems.append(f"{where}: values must not repeat")
    return problems


def _property_problems(name, definition, where: str) -> list[str]:
    here = f"{where}: property {name!r}"
    if not isinstance(name, str) or not _PROPERTY_NAME.fullmatch(name):
        return [f"{here} needs a name like SweatRate (letters and digits, starting with a capital)"]
    if not isinstance(definition, dict):
        return [f"{here} must be an object"]
    problems = [f"{here}: key {key!r} is not allowed" for key in sorted(set(definition) - _PROPERTY_KEYS)]
    if definition.get("type") not in _TYPES:
        problems.append(f"{here}: type must be one of {', '.join(_TYPES)}")
    description = definition.get("description")
    if "description" in definition and not (isinstance(description, str) and len(description) <= MAX_DESCRIPTION):
        problems.append(f"{here}: description must be a string of at most {MAX_DESCRIPTION} characters")
    if "enum" in definition:
        enum = definition["enum"]
        if not (isinstance(enum, list) and 1 <= len(enum) <= MAX_ITEMS and all(isinstance(v, str) and _VALUE.fullmatch(v) for v in enum)):
            problems.append(f"{here}: enum must be a list of 1 to {MAX_ITEMS} lowercase values")
    return problems


def _properties_problems(schema: dict, op: dict, where: str) -> list[str]:
    node = _resolve(schema, op.get("path"))
    if node is None or not isinstance(node.get("properties"), dict):
        return [f"{where}: path {op.get('path')!r} is not an object of the schema"]
    properties = op.get("properties")
    if not isinstance(properties, dict) or not 1 <= len(properties) <= MAX_ITEMS:
        return [f"{where}: properties must be an object of 1 to {MAX_ITEMS} definitions"]
    problems = []
    for name, definition in properties.items():
        problems += _property_problems(name, definition, where)
    return problems


def validate_patch(patch, schema: dict) -> list[str]:
    """Problems of a patch against the schema it targets (empty list = valid)."""
    if not isinstance(patch, dict):
        return ["the patch must be a JSON object"]
    problems = [f"field {key!r} is not allowed in a patch" for key in sorted(set(patch) - {"operations"})]
    operations = patch.get("operations")
    if not isinstance(operations, list) or not operations:
        return problems + ["operations must be a non-empty list"]
    if len(operations) > MAX_OPERATIONS:
        problems.append(f"a patch has at most {MAX_OPERATIONS} operations, found {len(operations)}")
    for i, op in enumerate(operations[:MAX_OPERATIONS], 1):
        where = f"operation {i}"
        if not isinstance(op, dict) or op.get("op") not in _OPERATIONS:
            problems.append(f"{where}: op must be one of {', '.join(_OPERATIONS)}")
            continue
        problems += [f"{where}: key {key!r} is not allowed" for key in sorted(set(op) - _OPERATIONS[op["op"]])]
        problems += (_enum_problems if op["op"] == "add_enum_values" else _properties_problems)(schema, op, where)
    return problems


def additions(schema: dict, patch) -> tuple[list[dict], list[str]]:
    """What the patch really adds to `schema` (in order, each value once), and a note per addition it already had.

    [{"kind": "enum", "path": ..., "values": [...]} | {"kind": "properties", "path": ..., "properties": {...}}].
    PatchError when the patch is invalid or adds nothing. The one decision both apply_patch and the release use.
    """
    problems = validate_patch(patch, schema)
    if problems:
        raise PatchError("; ".join(problems))
    adds: list[dict] = []
    notes: list[str] = []
    planned: dict[str, set] = {}  # what earlier operations of this patch already add, per path
    for op in patch["operations"]:
        node = _resolve(schema, op["path"])
        seen = planned.setdefault(f"{op['op']}:{op['path']}", set())
        if op["op"] == "add_enum_values":
            new = []
            for value in op["values"]:
                if value in node["enum"] or value in seen:
                    notes.append(f"{op['path']}: {value!r} is already official")
                else:
                    new.append(value)
                    seen.add(value)
            if new:
                adds.append({"kind": "enum", "path": op["path"], "values": new})
        else:
            new_properties = {}
            for name, definition in op["properties"].items():
                if name in node["properties"] or name in seen:
                    notes.append(f"{op['path']}.{name} is already official")
                else:
                    new_properties[name] = definition
                    seen.add(name)
            if new_properties:
                adds.append({"kind": "properties", "path": op["path"], "properties": new_properties})
    if not adds:
        raise PatchError("nothing to add: " + ("; ".join(notes) or "the patch is empty"))
    return adds, notes


def apply_patch(schema: dict, patch) -> tuple[dict, list[str]]:
    """A deep copy of `schema` with the patch applied, and one note per addition the schema already had.

    Only adds. PatchError when the patch is invalid or when nothing is left to add.
    """
    adds, notes = additions(schema, patch)
    patched = copy.deepcopy(schema)
    for add in adds:
        node = _resolve(patched, add["path"])
        if add["kind"] == "enum":
            node["enum"].extend(add["values"])
        else:
            node["properties"].update(copy.deepcopy(add["properties"]))
    return patched, notes


def enum_fields(schema: dict, max_depth: int = 2) -> list[str]:
    """Dotted paths of the enum fields a patch may extend (depth at most `max_depth`)."""
    found: list[str] = []

    def walk(node: dict, prefix: str, depth: int) -> None:
        for name, child in (node.get("properties") or {}).items():
            if not isinstance(child, dict) or not _SEGMENT.fullmatch(name):
                continue
            path = f"{prefix}{name}"
            if isinstance(child.get("enum"), list):
                found.append(path)
            if depth < max_depth:
                walk(child, f"{path}.", depth + 1)

    walk(schema, "", 1)
    return found
