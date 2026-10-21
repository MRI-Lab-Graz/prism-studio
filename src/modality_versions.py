"""Per-modality schema versions: which exist, which one applies, pins in project.json."""

from __future__ import annotations

import json
import os
import re
import shutil
import sys
import tempfile
from pathlib import Path

from src.cross_platform import _replace_with_retry
from src.schema_manager import DEFAULT_SCHEMA_DIR, _read_schema_file, load_schema, parse_version

VERSION_RE = re.compile(r"\d+\.\d+\.\d+")


class ModalityVersionError(ValueError):
    """A modality name or version that does not exist (the message lists what does)."""


def _dir(schema_dir) -> Path:
    return Path(schema_dir or DEFAULT_SCHEMA_DIR)


def modality_names(schema_dir=None) -> list[str]:
    stable = _dir(schema_dir) / "stable"
    entities = json.loads((stable / "entities.schema.json").read_text(encoding="utf-8"))
    return [n for n in entities.get("modalities", {}) if (stable / f"{n}.schema.json").is_file()]


def current_version(name: str, schema_dir=None) -> str:
    names = modality_names(schema_dir)
    if name not in names:
        raise ModalityVersionError(f"unknown modality '{name}'; known: {', '.join(names)}")
    path = _dir(schema_dir) / "stable" / f"{name}.schema.json"
    return json.loads(path.read_text(encoding="utf-8")).get("version", "1.0.0")


def available_versions(name: str, schema_dir=None) -> list[str]:
    current = current_version(name, schema_dir)
    archived = {
        p.name[: -len(".schema.json")]
        for p in (_dir(schema_dir) / "archive" / name).glob("*.schema.json")
    }
    return sorted({current, *archived}, key=parse_version)


def load_modality_schema(name: str, version: str, schema_dir=None) -> dict:
    base = _dir(schema_dir)
    if version == current_version(name, schema_dir):  # also validates the name
        return load_schema(name, str(base), "stable")
    if not VERSION_RE.fullmatch(version):
        raise ModalityVersionError(f"'{version}' is not a version (use X.Y.Z)")
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
        if not (sep and name and VERSION_RE.fullmatch(version)):
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
    return {k: v for k, v in value.items() if isinstance(k, str) and isinstance(v, str) and VERSION_RE.fullmatch(v)}


def read_pins(project_root) -> tuple[dict[str, str], dict[str, str]]:
    """(SchemaVersions, SchemaVersionsAcknowledged) of a project; empty when absent or unreadable."""
    data = _read_project(project_root) or {}
    return _clean_map(data.get("SchemaVersions")), _clean_map(data.get("SchemaVersionsAcknowledged"))


def _write_pins(project_root, pins: dict[str, str], acknowledged: dict[str, str]) -> None:
    data = _read_project(project_root)
    if data is None:
        raise ModalityVersionError(f"no readable project.json in {project_root}")
    data["SchemaVersions"] = dict(sorted(pins.items()))
    if acknowledged:
        data["SchemaVersionsAcknowledged"] = dict(sorted(acknowledged.items()))
    else:
        data.pop("SchemaVersionsAcknowledged", None)
    path = Path(project_root) / "project.json"
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=".project.json.")
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="") as fh:
            fh.write(json.dumps(data, indent=2, ensure_ascii=False) + "\n")
        shutil.copymode(path, tmp)
        _replace_with_retry(tmp, path)
    except BaseException:
        Path(tmp).unlink(missing_ok=True)
        raise


def present_modalities(project_root, schema_dir=None) -> list[str]:
    root = Path(project_root)
    found = []
    for name in modality_names(schema_dir):
        if name == "events":  # events live next to other data (no events/ folder any more)
            has_files = any(root.glob("sub-*/*/*_events.*")) or any(
                root.glob("sub-*/ses-*/*/*_events.*")
            )
        else:
            folders = [*root.glob(f"sub-*/{name}"), *root.glob(f"sub-*/ses-*/{name}")]
            has_files = any(f.is_dir() and any(f.iterdir()) for f in folders)
        if has_files:
            found.append(name)
    return found


def pin_modalities(project_root, names, schema_dir=None) -> dict[str, str]:
    """Pin the current version of each named, not yet pinned modality; returns the new pins."""
    pins, acknowledged = read_pins(project_root)
    new = {n: current_version(n, schema_dir) for n in names if n not in pins}
    if new:
        _write_pins(project_root, {**pins, **new}, acknowledged)
    return new


def pin_present_modalities(project_root, schema_dir=None) -> dict[str, str]:
    if _read_project(project_root) is None:
        return {}
    return pin_modalities(project_root, present_modalities(project_root, schema_dir), schema_dir)


def pending_updates(project_root, schema_dir=None) -> list[tuple[str, str, str]]:
    pins, acknowledged = read_pins(project_root)
    out = []
    for name, pinned in sorted(pins.items()):
        try:
            latest = current_version(name, schema_dir)
        except ModalityVersionError:
            continue
        if parse_version(latest) > parse_version(pinned) and acknowledged.get(name) != latest:
            out.append((name, pinned, latest))
    return out


def _require_pinned(name: str, pins: dict[str, str]) -> None:
    if name not in pins:
        raise ModalityVersionError(
            f"'{name}' is not pinned in this project; pin it first: modality-version pin <project> {name}"
        )


def update_modality(project_root, name: str, schema_dir=None) -> str:
    pins, acknowledged = read_pins(project_root)
    _require_pinned(name, pins)
    latest = current_version(name, schema_dir)
    pins[name] = acknowledged[name] = latest
    _write_pins(project_root, pins, acknowledged)
    return latest


def freeze_modality(project_root, name: str, schema_dir=None) -> str:
    pins, acknowledged = read_pins(project_root)
    _require_pinned(name, pins)
    acknowledged[name] = current_version(name, schema_dir)
    _write_pins(project_root, pins, acknowledged)
    return pins[name]


def pin_after_import(output_root) -> None:
    """Pin modalities a conversion just wrote; a problem here must never fail the conversion."""
    try:
        new = pin_present_modalities(output_root)
    except Exception as exc:  # noqa: BLE001 - pinning is best effort
        print(f"Warning: could not record modality versions in project.json: {exc}", file=sys.stderr)
        return
    for name, version in new.items():
        print(f"Pinned {name} schema version {version} in project.json", file=sys.stderr)


def format_pending_hint(pending) -> list[str]:
    lines = [
        f"A newer {name} schema is available: {latest} (this project uses {pinned})."
        for name, pinned, latest in pending
    ]
    if lines:
        lines.append(
            "Decide with: prism_tools modality-version update <project> <name> | freeze <project> <name>"
        )
    return lines
