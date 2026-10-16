"""Per-modality schema versions: which exist, which one applies, pins in project.json."""

from __future__ import annotations

import json
import re
from pathlib import Path

from src.schema_manager import DEFAULT_SCHEMA_DIR, _read_schema_file, load_schema, parse_version

VERSION_RE = re.compile(r"^\d+\.\d+\.\d+$")


class ModalityVersionError(ValueError):
    """A modality name or version that does not exist (the message lists what does)."""


def _dir(schema_dir) -> Path:
    return Path(schema_dir or DEFAULT_SCHEMA_DIR)


def modality_names(schema_dir=None) -> list[str]:
    stable = _dir(schema_dir) / "stable"
    entities = json.loads((stable / "entities.schema.json").read_text(encoding="utf-8"))
    return [n for n in entities.get("modalities", {}) if (stable / f"{n}.schema.json").is_file()]


def current_version(name: str, schema_dir=None) -> str:
    path = _dir(schema_dir) / "stable" / f"{name}.schema.json"
    if not path.is_file():
        raise ModalityVersionError(
            f"unknown modality '{name}'; known: {', '.join(modality_names(schema_dir))}"
        )
    return json.loads(path.read_text(encoding="utf-8")).get("version", "1.0.0")


def current_versions(schema_dir=None) -> dict[str, str]:
    return {n: current_version(n, schema_dir) for n in modality_names(schema_dir)}


def available_versions(name: str, schema_dir=None) -> list[str]:
    current = current_version(name, schema_dir)
    archived = {
        p.name[: -len(".schema.json")]
        for p in (_dir(schema_dir) / "archive" / name).glob("*.schema.json")
    }
    return sorted({current, *archived}, key=parse_version)


def load_modality_schema(name: str, version: str, schema_dir=None) -> dict:
    base = _dir(schema_dir)
    if version == current_version(name, schema_dir):
        return load_schema(name, str(base), "stable")
    path = base / "archive" / name / f"{version}.schema.json"
    schema = _read_schema_file(str(path), name, f"{name}@{version}")
    if schema is None:
        raise ModalityVersionError(
            f"{name} has no version {version}; available: {', '.join(available_versions(name, schema_dir))}"
        )
    return schema


def parse_overrides(items: list[str]) -> dict[str, str]:
    """['survey=1.0.3'] -> {'survey': '1.0.3'}; anything else is an error."""
    out: dict[str, str] = {}
    for item in items or []:
        name, sep, version = item.partition("=")
        if not (sep and name and VERSION_RE.match(version)):
            raise ModalityVersionError(f"'{item}': use NAME=X.Y.Z (for example survey=1.0.3)")
        out[name] = version
    return out


def resolve_modality_versions(pins=None, overrides=None, schema_dir=None):
    """(versions, sources): per modality override > project pin > latest."""
    names = modality_names(schema_dir)
    overrides, pins = dict(overrides or {}), dict(pins or {})
    unknown = sorted(set(overrides) - set(names))
    if unknown:
        raise ModalityVersionError(f"unknown modality {unknown}; known: {', '.join(names)}")
    versions: dict[str, str] = {}
    sources: dict[str, str] = {}
    for name in names:
        if name in overrides:
            versions[name], sources[name] = overrides[name], "cli"
        elif name in pins:
            versions[name], sources[name] = pins[name], "project.json"
        else:
            versions[name], sources[name] = current_version(name, schema_dir), "latest"
    return versions, sources


def _read_project(project_root) -> dict | None:
    path = Path(project_root) / "project.json"
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return data if isinstance(data, dict) else None


def _clean_map(value) -> dict[str, str]:
    if not isinstance(value, dict):
        return {}
    return {k: v for k, v in value.items() if isinstance(k, str) and isinstance(v, str) and VERSION_RE.match(v)}


def read_pins(project_root) -> tuple[dict[str, str], dict[str, str]]:
    """(SchemaVersions, SchemaVersionsAcknowledged) of a project; empty when absent or unreadable."""
    data = _read_project(project_root) or {}
    return _clean_map(data.get("SchemaVersions")), _clean_map(data.get("SchemaVersionsAcknowledged"))
