"""Session map for longitudinal projects.

Spec: docs/superpowers/specs/2026-09-30-session-map-design.md

In a project that declares several timepoints, every session label being
imported must have an explicit entry in ``code/session_map.json``. Nothing is
guessed: labels compare by exact string (see ``session_label``), a blank label
is never defaulted, and PRISM never suggests a target.
"""

from __future__ import annotations

import json
import os
import re
from collections.abc import Iterable, Mapping
from pathlib import Path



def _import_session_label():
    # Same fallback style as participants_converter: also loadable outside the package.
    try:
        from src.participants_sessions import session_label
    except ImportError:
        from participants_sessions import session_label
    return session_label


session_label = _import_session_label()

MAP_FILE = Path("code") / "session_map.json"
TIMEPOINT_VALUES = ("single", "multiple")
_TARGET = re.compile(r"[A-Za-z0-9]+")


class SessionMapError(ValueError):
    """Anything wrong with the session map or the project's timepoint declaration."""


class TimepointsNotDeclaredError(SessionMapError):
    def __init__(self) -> None:
        super().__init__(
            "This project does not say whether it has one timepoint or several. "
            "Set 'Timepoints' (single or multiple) under Study Design on the "
            "Projects page, then run again."
        )


class SessionsNotMappedError(SessionMapError):
    def __init__(self, labels: Iterable[str]) -> None:
        self.labels = list(labels)
        shown = ", ".join(repr(label) if label else "(empty)" for label in self.labels)
        super().__init__(
            f"Session label(s) not in the session map: {shown}. This project has "
            "several timepoints, so every session label must be mapped by you. "
            f"Add them to {MAP_FILE.as_posix()} (Survey tab of the Converter, "
            "'Session mapping' panel, or `prism_tools.py session-map set`), then run again."
        )


def _root(project_path: str | Path) -> Path:
    path = Path(project_path).expanduser()
    return path.parent if path.is_file() else path


def map_path(project_path: str | Path) -> Path:
    return _root(project_path) / MAP_FILE


def project_timepoints(project_path: str | Path) -> str | None:
    """'single', 'multiple', 'undeclared' (project.json without a valid
    StudyDesign.Timepoints) or None (no project.json: not a PRISM project)."""
    pj = _root(project_path) / "project.json"
    if not pj.is_file():
        return None
    try:
        data = json.loads(pj.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise SessionMapError(f"{pj} could not be read: {exc}") from exc
    design = data.get("StudyDesign") if isinstance(data, dict) else None
    value = design.get("Timepoints") if isinstance(design, dict) else None
    return value if value in TIMEPOINT_VALUES else "undeclared"


def _clean(mapping: object, where: str) -> dict[str, str]:
    if not isinstance(mapping, dict):
        raise SessionMapError(
            f"{where} must be a JSON object of source label to session name"
        )
    clean: dict[str, str] = {}
    for source, target in mapping.items():
        label = str(source).strip()
        if not label:
            raise SessionMapError(f"{where} has an entry with an empty source label")
        if not isinstance(target, str) or not _TARGET.fullmatch(target.strip()):
            raise SessionMapError(
                f"{where}: session name for {label!r} must be letters and digits "
                f"only, got {target!r}"
            )
        clean[label] = target.strip()
    return clean


def load_session_map(project_path: str | Path) -> dict[str, str]:
    path = map_path(project_path)
    if not path.is_file():
        return {}
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise SessionMapError(f"{path} could not be read: {exc}") from exc
    return _clean(raw, str(path))


def save_session_map(project_path: str | Path, mapping: Mapping[str, str]) -> None:
    path = map_path(project_path)
    clean = _clean(dict(mapping), str(path))
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(
        json.dumps(clean, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    os.replace(tmp, path)


def set_session_entries(
    project_path: str | Path, entries: Mapping[str, str]
) -> dict[str, str]:
    merged = load_session_map(project_path)
    merged.update(_clean(dict(entries), "entries"))
    save_session_map(project_path, merged)
    return merged


def unmapped_labels(labels: Iterable[object], mapping: Mapping[str, str]) -> list[str]:
    """Labels without an entry, deduplicated, in order of first appearance.
    A blank label is reported as '' (it is never defaulted)."""
    missing: list[str] = []
    for raw in labels:
        label = session_label(raw)
        if label not in mapping and label not in missing:
            missing.append(label)
    return missing


def apply_session_map(label: object, mapping: Mapping[str, str]) -> str:
    key = session_label(label)
    if key in mapping:
        return mapping[key]
    raise SessionsNotMappedError([key])


def session_map_for_conversion(
    project_path: str | Path | None,
) -> dict[str, str] | None:
    """None when the gate does not apply (no project, single timepoint);
    the map (possibly empty) for a multiple-timepoint project."""
    if not project_path:
        return None
    state = project_timepoints(project_path)
    if state in (None, "single"):
        return None
    if state == "undeclared":
        raise TimepointsNotDeclaredError()
    return load_session_map(project_path)


def require_sessions_mapped(
    mapping: Mapping[str, str] | None, labels: Iterable[object]
) -> None:
    if mapping is None:
        return
    missing = unmapped_labels(labels, mapping)
    if missing:
        raise SessionsNotMappedError(missing)
