"""PRISM instrument IDs come from the official survey templates themselves (docs/specs/instrument-ids.md).

`prism:<TaskName>` and `prism:<TaskName>.<item key>` are known when an official template (or stub) with that
TaskName and item exists. There is no second list to keep in sync. A template that exists only in a project
is a `local:` instrument, never a `prism:` one. Library files are data: only read, never used to build a path.
"""

from __future__ import annotations

import json

from src.term_registry import terms_root

SECTIONS = {"Technical", "I18n", "Study", "Metadata"}  # the rest of a survey sidecar are items


def _items(template: dict) -> set[str]:
    """Item keys, lower case: IDs are lower case (`prism:dass.dass01`), a template key may be `DASS01`."""
    return {k.lower() for k, v in template.items() if k not in SECTIONS and isinstance(v, dict)}


def _find_items(task: str) -> set[str] | None:
    """Item keys of every official template with this TaskName, None if there is none."""
    found = None
    # ponytail: re-reads the library per stub sidecar; index it once per run if projects get many stubs
    for path in sorted((terms_root().parent / "survey").glob("survey-*.json")):
        try:
            template = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        study = template.get("Study") if isinstance(template, dict) else None
        if isinstance(study, dict) and str(study.get("TaskName")).lower() == task.lower():
            found = (found or set()) | _items(template)
    return found


def stub_id_problems(sidecar: dict) -> list[str]:
    """Why this stub does not map cleanly to PRISM IDs; empty when it does."""
    study = sidecar.get("Study")
    task = study.get("TaskName") if isinstance(study, dict) else None
    if not isinstance(task, str) or not task:
        return []  # the schema reports a missing TaskName
    known = _find_items(task)
    if known is None:
        return [f"prism:{task.lower()} is not in the official library (a project-only instrument is local:<slug>)"]
    problems = []
    for key, item in sidecar.items():
        if key in SECTIONS or not isinstance(item, dict):
            continue
        if key.lower() not in known:
            problems.append(f"item '{key}' (prism:{task.lower()}.{key.lower()}) is not an item of prism:{task.lower()}")
        elif not item.get("Fingerprint"):
            problems.append(f"item '{key}' has no Fingerprint (a stub keeps one per item)")
    return problems
