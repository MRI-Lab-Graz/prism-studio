"""Resolve incoming session labels against a project's existing directory
structure.

Sessions must be drawn from the dataset itself, not freely typed -- a typo
in a session field should never silently create a stray `ses-` folder. This
mirrors `src.subject_id_matching`'s "ground truth" approach, but for
sessions there is nothing to persist: once a session is created on disk it
becomes part of the ground truth and is picked up automatically next time.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable, Optional

from .project_structure import get_project_modalities_and_sessions


def list_known_sessions(
    project_root: Path | str, subject: Optional[str] = None
) -> list[str]:
    """Return sorted session labels (e.g. ["ses-01", "ses-02"]) already
    present in a project's rawdata structure.

    When `subject` is given (a "sub-<label>" folder name), the list is
    restricted to sessions that already exist for that specific subject.
    Returns an empty list if the project has no session level yet, or the
    subject doesn't exist -- callers should treat that as "no ground truth
    yet", not an error.
    """
    project_path = Path(project_root)
    if subject is None:
        summary = get_project_modalities_and_sessions(project_path)
        return list(summary.get("sessions") or [])

    subject_dir = project_path / subject
    if not subject_dir.is_dir():
        return []
    return sorted(
        child.name
        for child in subject_dir.iterdir()
        if child.is_dir() and child.name.startswith("ses-")
    )


@dataclass
class SessionResolution:
    """Result of resolving raw session labels against known sessions."""

    matched: list[str] = field(default_factory=list)
    unmatched: list[str] = field(default_factory=list)


def resolve_sessions(
    raw_sessions: Iterable[str],
    known_sessions: Iterable[str],
    decisions: Optional[dict[str, dict]] = None,
) -> SessionResolution:
    """Resolve raw session labels against `known_sessions`.

    A raw session matches if it's already in `known_sessions`. Otherwise it
    is unmatched, unless `decisions` (keyed by raw session label) explicitly
    resolves it:
    `{"action": "use_existing", "target_session": str}` maps it onto an
    existing session, or `{"action": "add_new"}` confirms it as a
    deliberately new session label (the caller is then responsible for
    actually creating it).

    When `known_sessions` is empty (no session level in the project yet),
    every raw session is treated as matched -- there's no ground truth to
    block against for a project's first session.
    """
    known = set(known_sessions)
    decisions = decisions or {}

    resolution = SessionResolution()
    if not known:
        for raw_session in dict.fromkeys(s for s in raw_sessions if s):
            resolution.matched.append(raw_session)
        return resolution

    for raw_session in dict.fromkeys(s for s in raw_sessions if s):
        if raw_session in known:
            resolution.matched.append(raw_session)
            continue

        decision = decisions.get(raw_session)
        if decision and decision.get("action") == "use_existing":
            target = decision.get("target_session")
            if target in known:
                resolution.matched.append(target)
                continue
        elif decision and decision.get("action") == "add_new":
            resolution.matched.append(raw_session)
            continue

        resolution.unmatched.append(raw_session)

    return resolution
