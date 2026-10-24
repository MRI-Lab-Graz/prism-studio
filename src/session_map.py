"""Session map for longitudinal projects.

Spec: docs/superpowers/specs/2026-09-30-session-map-design.md

In a project that declares several timepoints, every session label being
imported must have an explicit entry in ``code/session_map.json``. Nothing is
guessed: labels compare by exact string (see ``session_label``), a blank label
is never defaulted, and PRISM never suggests a target.

A project with a single timepoint writes ``ses-1`` for every label (a declared
project rule, see ``session_target``). For several timepoints PRISM only
*pre-fills* defaults in the UI (Task 7); it never applies them unconfirmed.
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
            f"Add them to {MAP_FILE.as_posix()} (the 'Session mapping' panel on the Converter's "
            "Survey or Sociodemographics tab, or `prism_tools.py session-map set`), then run again."
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


def remove_session_entries(
    project_path: str | Path, labels: Iterable[str]
) -> dict[str, str]:
    """Drop entries by exact source label; an unknown label changes nothing and raises."""
    current = load_session_map(project_path)
    wanted = [str(label).strip() for label in labels]
    unknown = [label for label in wanted if label not in current]
    if unknown:
        shown = ", ".join(repr(label) for label in unknown)
        raise SessionMapError(f"Not in the session map (labels match exactly): {shown}")
    remaining = {k: v for k, v in current.items() if k not in wanted}
    save_session_map(project_path, remaining)
    return remaining


def unmapped_labels(labels: Iterable[object], mapping: Mapping[str, str]) -> list[str]:
    """Labels without an entry, deduplicated, in order of first appearance.
    A blank label is reported as '' (it is never defaulted)."""
    missing: list[str] = []
    for raw in labels:
        label = session_label(raw)
        if label not in mapping and label not in missing:
            missing.append(label)
    return missing


def suggest_session_map(labels: Iterable[object], mapping: Mapping[str, str]) -> dict[str, str]:
    """Editable defaults for unmapped labels: 1, 2, 3 ... in order of first appearance.
    Only a proposal: nothing is written until the user confirms."""
    used = set(mapping.values())
    out: dict[str, str] = {}
    n = 1
    for label in unmapped_labels(labels, mapping):
        if label == "":
            continue
        while str(n) in used:
            n += 1
        out[label] = str(n)
        used.add(str(n))
    return out


def apply_session_map(label: object, mapping: Mapping[str, str]) -> str:
    key = session_label(label)
    if key in mapping:
        return mapping[key]
    raise SessionsNotMappedError([key])


SINGLE_SESSION = "1"
SINGLE_SESSION_WARNING = "Project has one timepoint: session label {label!r} was written as ses-1."


def session_target(project_path, label: object) -> str | None:
    """The session name a source label becomes in this project, or None when the
    folder is not a PRISM project (callers keep their legacy behaviour)."""
    state = project_timepoints(project_path)
    if state is None:
        return None
    if state == "undeclared":
        raise TimepointsNotDeclaredError()
    if state == "single":
        return SINGLE_SESSION
    return apply_session_map(label, load_session_map(project_path))


def resolve_import_session(project_path, label: object) -> tuple[str | None, str | None]:
    """What an importer writes for a source session label, and a warning to report.

    (None, None): not a PRISM project, keep the label. Raises like ``session_target``
    for an unmapped label in a multiple-timepoint project."""
    target = session_target(project_path, label)
    if target is None or project_timepoints(project_path) != "single":
        return target, None
    return target, single_session_warning(label)


def single_session_warning(label: object) -> str | None:
    shown = session_label(label)
    if shown in ("", SINGLE_SESSION):
        return None
    return SINGLE_SESSION_WARNING.format(label=shown)


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


def unmapped_session_labels(
    project_path: str | Path | None, labels: Iterable[object]
) -> list[str]:
    """Labels of an import that still lack a map entry ([] when no gate applies)."""
    mapping = session_map_for_conversion(project_path)
    return [] if mapping is None else unmapped_labels(labels, mapping)


def require_sessions_mapped(
    mapping: Mapping[str, str] | None, labels: Iterable[object]
) -> None:
    if mapping is None:
        return
    missing = unmapped_labels(labels, mapping)
    if missing:
        raise SessionsNotMappedError(missing)
