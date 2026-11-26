"""Project code maps: ``code/<modality>[_task-X][_ses-Y]_code_map.tsv``.

A map links the codes people typed to participant numbers, so it re-identifies them:
every export asks ``is_code_map`` and git is told to ignore the files (``src.git_exclude``).
"""

from __future__ import annotations

import csv
import re
from collections.abc import Iterable
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass
from pathlib import Path

from src.git_exclude import SENSITIVE_PATHS, ensure_git_excluded, tracked_sensitive_files
from src.session_map import SessionMapError, project_timepoints, session_map_for_conversion

_IGNORED: ContextVar[bool] = ContextVar("ignore_project_code_maps", default=False)


@contextmanager
def without_project_code_maps():
    """For pre-checks that only look at templates and sessions: nobody is assigned to a participant."""
    token = _IGNORED.set(True)
    try:
        yield
    finally:
        _IGNORED.reset(token)


def project_code_maps_ignored() -> bool:
    return _IGNORED.get()


class CodeMapError(ValueError):
    """A code map is invalid, or the maps do not agree about who a row belongs to."""


class UnknownCodeError(CodeMapError):
    def __init__(self, codes: Iterable[str]) -> None:
        self.codes = sorted(set(codes))
        more = "" if len(self.codes) <= 20 else f" (+{len(self.codes) - 20} more)"
        super().__init__(
            f"ID mapping incomplete: {len(self.codes)} IDs from data are missing in the mapping: "
            f"{', '.join(self.codes[:20])}{more}."
        )


@dataclass(frozen=True)
class CodeMap:
    name: str  # file name
    task: str | None
    session: str | None  # without "ses-"
    entries: dict[str, str]  # code.strip().casefold() -> "sub-<label>"


def _read_entries(path: Path) -> dict[str, str]:
    try:
        with path.open(encoding="utf-8-sig", newline="") as handle:
            reader = csv.DictReader(handle, delimiter="\t")
            if not {"code", "participant_id"} <= set(reader.fieldnames or []):
                raise CodeMapError(f"{path.name}: the first line must name the columns 'code' and 'participant_id', tab-separated.")
            rows = list(reader)
    except (OSError, UnicodeError, csv.Error) as exc:
        raise CodeMapError(f"{path.name}: cannot be read as a UTF-8 table ({type(exc).__name__}).") from exc

    entries: dict[str, str] = {}
    for row in rows:
        code = (row.get("code") or "").strip()
        participant = (row.get("participant_id") or "").strip()
        if not code or not participant:
            continue
        label = participant.removeprefix("sub-")
        if not re.fullmatch(r"[A-Za-z0-9]+", label):
            raise CodeMapError(f"{path.name}: '{participant}' is not a participant ID (sub-<letters and digits>).")
        if entries.setdefault(code.casefold(), f"sub-{label}") != f"sub-{label}":
            raise CodeMapError(f"{path.name}: code '{code}' is listed with two different participants.")
    return entries


def load_code_maps(project_root: str | Path, modality: str) -> list[CodeMap]:
    """The maps of one modality in ``<project>/code``; a file that looks like one but is not stops."""
    folder = Path(project_root) / "code"
    maps = []
    for path in sorted(folder.iterdir()) if folder.is_dir() else []:
        lower = path.name.lower()
        if not (path.is_file() and lower.startswith(f"{modality}_") and "code_map" in lower):
            continue
        parsed = re.fullmatch(rf"{modality}(?:_task-([A-Za-z0-9]+))?(?:_ses-([A-Za-z0-9]+))?_code_map\.tsv", path.name)
        if not parsed:
            expected = f"{modality}_code_map.tsv"
            if lower not in (expected, f"{modality}_code_map.csv", f"{modality}_code_map.xlsx"):
                expected = f"{modality}[_task-<label>][_ses-<label>]_code_map.tsv"
            raise CodeMapError(f"code/{path.name} is not a code map name; expected {expected}.")
        maps.append(CodeMap(path.name, parsed[1], parsed[2], _read_entries(path)))
    return maps


def _lookup(maps: list[CodeMap], code: str, task: str | None, session: str | None) -> tuple[str, list[str]] | None:
    """The participant for one task: the narrowest files that list the code decide."""
    key = code.strip().casefold()
    hits = [m for m in maps if m.task in (None, task) and m.session in (None, session) and key in m.entries]
    if not hits:
        return None
    narrowest = max((m.task is not None) + (m.session is not None) for m in hits)
    hits = [m for m in hits if (m.task is not None) + (m.session is not None) == narrowest]
    if len({m.entries[key] for m in hits}) > 1:
        raise CodeMapError(
            f"Code '{code.strip()}' has different participants in equally specific maps: "
            + ", ".join(f"{m.name} says {m.entries[key]}" for m in hits)
        )
    return hits[0].entries[key], [m.name for m in hits]


def resolve_row(maps: list[CodeMap], code: str, tasks: Iterable[str], session: str | None) -> tuple[str, tuple[str, ...]] | None:
    """``(participant_id, files used)`` for one response row; None when a task has no entry for the code.

    All tasks of a row belong to one person: maps that say otherwise stop the import."""
    tasks = sorted(set(tasks)) or [None]
    session = str(session).strip().removeprefix("ses-") or None if session is not None else None
    if session is None:
        key = code.strip().casefold()
        needing = [m.name for m in maps if m.session and (m.task is None or m.task in tasks) and key in m.entries]
        if needing:
            raise CodeMapError(
                f"Code '{code.strip()}' is listed in {', '.join(needing)}, but this row has no session. "
                "Give --session or a session column (sessions numbered from response dates cannot be used)."
            )

    found = {task: _lookup(maps, code, task, session) for task in tasks}
    if any(hit is None for hit in found.values()):
        return None
    if len({participant for participant, _ in found.values()}) > 1:
        raise CodeMapError(
            f"Code '{code.strip()}': the questionnaires of one row belong to different participants - "
            + "; ".join(f"{task}: {participant} ({', '.join(files)})" for task, (participant, files) in found.items())
            + ". One row is one person: make the maps agree."
        )
    participant = next(iter(found.values()))[0]
    return participant, tuple(sorted({name for _, files in found.values() for name in files}))


def _known_sessions(project_root) -> set[str] | None:
    """The session names this project writes, or None when it does not say."""
    try:
        if project_timepoints(project_root) == "single":
            return {"1"}
        mapping = session_map_for_conversion(project_root)
    except SessionMapError:
        return None
    return set(mapping.values()) if mapping else None


class ProjectCodeMaps:
    """One import's use of a project's code maps; every importer goes through this."""

    def __init__(self, maps: list[CodeMap], warnings: list[str]) -> None:
        self.maps = maps
        self.warnings = warnings
        self._used: dict[str, set[str]] = {}

    @classmethod
    def open(cls, project_root, modality: str, known_tasks=None, known_sessions=None) -> ProjectCodeMaps | None:
        """None without a project, without maps for ``modality``, or inside ``without_project_code_maps``."""
        if not project_root or project_code_maps_ignored():
            return None
        if find_code_map_files(project_root):
            ensure_git_excluded(project_root, *SENSITIVE_PATHS)
        maps = load_code_maps(project_root, modality)
        if not maps:
            return None

        warnings = []
        tracked = {Path(rel).name for rel in tracked_sensitive_files(project_root)}
        if known_sessions is None:
            known_sessions = _known_sessions(project_root)
        sessions = None if known_sessions is None else {str(v).removeprefix("ses-") for v in known_sessions}
        for code_map in maps:
            if code_map.task and known_tasks is not None and code_map.task not in known_tasks:
                same = [task for task in known_tasks if task.lower() == code_map.task.lower()]
                if same:
                    raise CodeMapError(f"Code map {code_map.name}: the task is written task-{same[0]}; rename the file.")
                warnings.append(f"Code map {code_map.name}: no template for task '{code_map.task}'.")
            if code_map.session and sessions is not None and code_map.session not in sessions:
                warnings.append(f"Code map {code_map.name}: the project has no session '{code_map.session}'.")
            if code_map.name in tracked:
                warnings.append(f"Code map {code_map.name} is tracked by git; it stays in the history.")
        return cls(maps, warnings)

    @property
    def codes(self) -> list[str]:
        """Every code any map lists (to choose a column and to suggest matches)."""
        return list({code: None for code_map in self.maps for code in code_map.entries})

    def resolve(self, code, tasks: Iterable[str] = (), session=None) -> str | None:
        hit = resolve_row(self.maps, str(code), tasks, session)
        if hit is None:
            return None
        for name in hit[1]:
            self._used.setdefault(name, set()).add(str(code).strip().casefold())
        return hit[0]

    def resolve_all(self, rows, keep_targets: bool = False) -> list[str]:
        """Participants for ``(code, tasks, session)`` rows; every unlisted value is reported at once.

        ``keep_targets``: a value that already is a participant of a map ("004" or "sub-004") stays."""
        targets = {p.casefold(): p for m in self.maps for p in m.entries.values()} if keep_targets else {}
        resolved, missing = [], []
        for code, tasks, session in rows:
            value = str(code).strip()
            hit = self.resolve(value, tasks, session) or targets.get("sub-" + value.casefold().removeprefix("sub-"))
            if hit is None:
                missing.append(value)
            resolved.append(hit)
        if missing:
            raise UnknownCodeError(missing)
        return resolved

    def notes(self) -> list[str]:
        return self.warnings + [
            f"Applied code map {name}: {len(codes)} code(s)." for name, codes in sorted(self._used.items())
        ]


def is_code_map(rel_parts: tuple[str, ...]) -> bool:
    """True for a map, a copy or a backup of one anywhere under ``code/`` (parts relative to the project)."""
    return len(rel_parts) > 1 and rel_parts[0] == "code" and any("code_map" in part.lower() for part in rel_parts[1:])


def find_code_map_files(project_root: str | Path) -> list[str]:
    """Every file ``is_code_map`` names, as sorted posix paths relative to the project."""
    root = Path(project_root)
    found = (p.relative_to(root) for p in (root / "code").rglob("*") if p.is_file())
    return sorted(rel.as_posix() for rel in found if is_code_map(rel.parts))


def left_out_message(paths: list[str]) -> str:
    return "Left out of the export (they re-identify participants): " + ", ".join(paths)
