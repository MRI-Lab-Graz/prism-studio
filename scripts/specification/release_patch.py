"""Turn a schema patch into a reviewable schema release.

The release procedure CONTRIBUTING.md describes, done by a script: archive the current stable schema
unchanged, apply the patch to the stable schema, bump its MINOR version (and the `$id` suffix), and
regenerate the field tables of the modality's spec page. The result passes scripts/check_schema_versions.py.
Reads from `source_root`, writes only what changed to `dest_root` (the same folder, or a bundle).
Stdlib only.
"""

from __future__ import annotations

import importlib.util
import json
import re
from pathlib import Path

_MODALITY = re.compile(r"[a-z][a-z0-9]*")
_VERSION = re.compile(r"(\d+)\.(\d+)\.(\d+)")


def _sibling(name: str):
    spec = importlib.util.spec_from_file_location(name, Path(__file__).resolve().parent / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


schema_patch = _sibling("schema_patch")
PatchError = schema_patch.PatchError


# --- surgical text edits: the schema file keeps whatever formatting it has --------------------------------
# A tiny JSON scanner finds the text of a value by its key path; the edit changes only that text. The caller
# checks that the result parses to the same thing as apply_patch and falls back to a full rewrite otherwise.

def _skip(text: str, i: int) -> int:
    while text[i] in " \t\r\n":
        i += 1
    return i


def _end_of_string(text: str, i: int) -> int:
    i += 1
    while text[i] != '"':
        i += 2 if text[i] == "\\" else 1
    return i + 1


def _end_of_value(text: str, i: int) -> int:
    if text[i] == '"':
        return _end_of_string(text, i)
    if text[i] in "{[":
        depth = 0
        while True:
            c = text[i]
            if c == '"':
                i = _end_of_string(text, i)
                continue
            depth += (c in "{[") - (c in "}]")
            i += 1
            if depth == 0:
                return i
    while text[i] not in ",}] \t\r\n":
        i += 1
    return i


def _member(text: str, start: int, key: str) -> tuple[int, int]:
    """(start, end) of the value of `key` in the object that starts at text[start] == "{"."""
    if text[start] != "{":
        raise ValueError("not an object")
    i = start + 1
    while True:
        i = _skip(text, i)
        if text[i] == "}":
            raise ValueError(f"no key {key!r}")
        name_end = _end_of_string(text, i)
        name = json.loads(text[i:name_end])
        i = _skip(text, _skip(text, name_end) + 1)  # the colon
        end = _end_of_value(text, i)
        if name == key:
            return i, end
        i = _skip(text, end)
        if text[i] == ",":
            i += 1


def _span(text: str, keys: list[str]) -> tuple[int, int]:
    start, end = _skip(text, 0), len(text)
    for key in keys:
        start, end = _member(text, start, key)
    return start, end


def _replace_value(text: str, keys: list[str], new_json: str) -> str:
    start, end = _span(text, keys)
    return text[:start] + new_json + text[end:]


def _extend_array(text: str, keys: list[str], values: list) -> str:
    start, end = _span(text, keys)
    array = text[start:end]
    body = array[:-1].rstrip()
    tail = array[len(body):]  # the whitespace before the closing bracket, and the bracket
    if array[0] != "[" or body == "[":
        raise ValueError("unusual array")
    if "\n" not in array:
        added = "".join(f", {json.dumps(v, ensure_ascii=False)}" for v in values)
    else:
        newline = "\r\n" if "\r\n" in array else "\n"
        last_line = body[body.rfind("\n") + 1 :]
        indent = last_line[: len(last_line) - len(last_line.lstrip())]
        added = "".join(f",{newline}{indent}{json.dumps(v, ensure_ascii=False)}" for v in values)
    return text[:start] + body + added + tail + text[end:]


def _extend_object(text: str, keys: list[str], properties: dict) -> str:
    start, end = _span(text, keys)
    obj = text[start:end]
    layout = re.match(r"\{[ \t]*(\r?\n)([ \t]*)\S", obj)
    body = obj[:-1].rstrip()
    if not layout or body == "{":
        raise ValueError("unusual object")
    newline, indent = layout.group(1), layout.group(2)
    tail = obj[len(body):]
    added = "".join(
        f",{newline}{indent}{json.dumps(name, ensure_ascii=False)}: "
        + json.dumps(definition, indent=2, ensure_ascii=False).replace("\n", newline + indent)
        for name, definition in properties.items()
    )
    return text[:start] + body + added + tail + text[end:]


def _edit_text(text: str, adds: list[dict], new_version: str, new_id: str) -> str | None:
    """The schema text with the version, the `$id` and the additions changed in place; None if the layout is unusual."""
    try:
        text = _replace_value(text, ["version"], json.dumps(new_version))
        text = _replace_value(text, ["$id"], json.dumps(new_id))
        for add in adds:
            keys = [k for segment in add["path"].split(".") for k in ("properties", segment)]
            if add["kind"] == "enum":
                text = _extend_array(text, keys + ["enum"], add["values"])
            else:
                text = _extend_object(text, keys + ["properties"], add["properties"])
    except (ValueError, IndexError):
        return None
    return text


class ReleaseError(ValueError):
    """The release cannot be prepared; the message says why."""


def release(source_root, dest_root, modality: str, patch) -> list[str]:
    """Prepare the release; returns the repository-relative paths written under `dest_root`."""
    if not isinstance(modality, str) or not _MODALITY.fullmatch(modality):
        raise ReleaseError(f"{modality!r} is not a modality name")
    source, dest = Path(source_root), Path(dest_root)
    stable_rel = f"schemas/stable/{modality}.schema.json"
    stable_path = source / stable_rel
    if not stable_path.is_file():
        raise ReleaseError(f"no schema for modality {modality!r}")
    original = stable_path.read_bytes()
    schema = json.loads(original.decode("utf-8"))

    adds, _notes = schema_patch.additions(schema, patch)  # PatchError: invalid, or nothing to add
    patched, _ = schema_patch.apply_patch(schema, patch)

    match = _VERSION.fullmatch(str(schema.get("version")))
    if not match:
        raise ReleaseError(f"{stable_rel}: version {schema.get('version')!r} is not major.minor.patch")
    old = schema["version"]
    new = f"{match[1]}.{int(match[2]) + 1}.0"
    if not str(schema.get("$id", "")).endswith(f"/v{old}"):
        raise ReleaseError(f"{stable_rel}: $id {schema.get('$id')!r} does not end with /v{old}")
    patched["version"] = new
    patched["$id"] = schema["$id"][: -len(old)] + new

    archive_rel = f"schemas/archive/{modality}/{old}.schema.json"
    if (source / archive_rel).exists():
        raise ReleaseError(f"{archive_rel} is already archived")

    written = [archive_rel, stable_rel]
    (dest / archive_rel).parent.mkdir(parents=True, exist_ok=True)
    (dest / archive_rel).write_bytes(original)
    (dest / stable_rel).parent.mkdir(parents=True, exist_ok=True)
    # edit the text in place (a small diff for the reviewer); a full rewrite only if that cannot be done exactly
    edited = _edit_text(original.decode("utf-8"), adds, new, patched["$id"])
    if edited is None or json.loads(edited) != patched:
        edited = json.dumps(patched, indent=2, ensure_ascii=False) + "\n"
    (dest / stable_rel).write_text(edited, encoding="utf-8", newline="")

    page_rel = f"specs/{modality}.md"
    if (source / page_rel).is_file():
        (dest / page_rel).parent.mkdir(parents=True, exist_ok=True)
        if dest != source:
            (dest / page_rel).write_bytes((source / page_rel).read_bytes())
        _sibling("generate_schema_reference").sync(
            write=True, schemas=dest / "schemas" / "stable", specs=dest / "specs", pages={modality: f"{modality}.md"}
        )
        written.append(page_rel)
    return written
