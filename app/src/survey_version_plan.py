"""
Survey Version Plan — per-project mapping of questionnaire variants to sessions and runs.

This module handles:
- Discovering multi-variant survey templates from the official library
- Reading / writing survey_version_mapping in project.json
- Resolving the correct variant for a given (session, run) pair
- Migrating legacy projects that have no mapping yet

Resolution priority (highest first):
    1. by_session_run[session][run]
    2. by_session[session]
    3. by_run[run]
    4. default_version
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

# ---------------------------------------------------------------------------
# Library discovery
# ---------------------------------------------------------------------------


def discover_survey_variants(library_path: Path) -> dict[str, dict]:
    """Scan a survey library directory and return variant metadata per task name.

    Returns a dict keyed by TaskName:
        {
            "wellbeing-multi": {
                "filename": "survey-wellbeing-multi.json",
                "default_version": "10-likert",
                "versions": ["10-likert", "7-likert", "10-vas"],
                "variant_definitions": [...],
            },
            ...
        }

    Surveys with no ``Study.Versions`` or only one version are included with
    a single-element ``versions`` list using ``Study.Version`` as the value.
    """
    result: dict[str, dict] = {}
    survey_dir = library_path / "survey"
    if not survey_dir.is_dir():
        return result

    for json_file in sorted(survey_dir.glob("survey-*.json")):
        try:
            data = json.loads(json_file.read_text(encoding="utf-8"))
        except Exception:
            continue

        study = data.get("Study", {})
        task_name = study.get("TaskName", "")
        if not task_name:
            continue

        versions: list[str] = study.get("Versions", [])
        default_version: str = study.get("Version", "")

        # Single-variant survey: synthesise a one-element list
        if not versions:
            if default_version:
                versions = [default_version]
            else:
                versions = ["default"]
                default_version = "default"

        if not default_version:
            default_version = versions[0]

        result[task_name] = {
            "filename": json_file.name,
            "default_version": default_version,
            "versions": versions,
            "variant_definitions": study.get("VariantDefinitions", []),
        }

    return result


# ---------------------------------------------------------------------------
# project.json read / write helpers
# ---------------------------------------------------------------------------


def _read_project_json(project_path: Path) -> dict:
    pj = project_path / "project.json"
    if not pj.exists():
        return {}
    try:
        return json.loads(pj.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _write_project_json(project_path: Path, data: dict) -> None:
    from src.cross_platform import CrossPlatformFile

    pj = project_path / "project.json"
    CrossPlatformFile.write_text(
        str(pj), json.dumps(data, indent=2, ensure_ascii=False)
    )


# ---------------------------------------------------------------------------
# Load / save survey plan
# ---------------------------------------------------------------------------


def load_survey_plan(project_path: Path) -> dict:
    """Return the survey_version_mapping from project.json.

    Performs in-memory normalisation only: the file is not written here.
    Use ``enrich_and_save_survey_plan`` to persist auto-discovery results.
    """
    data = _read_project_json(project_path)
    mapping = data.get("survey_version_mapping", {})
    settings = data.get("survey_plan_settings", {"auto_discover": True})

    # Normalise legacy "version" → "default_version" in each entry
    for entry in mapping.values():
        if isinstance(entry, dict):
            if "version" in entry and "default_version" not in entry:
                entry["default_version"] = entry.pop("version")

    return {
        "survey_version_mapping": mapping,
        "survey_plan_settings": settings,
    }


def save_survey_plan(
    project_path: Path, mapping: dict, settings: Optional[dict] = None
) -> None:
    """Persist survey_version_mapping (and optionally settings) to project.json."""
    data = _read_project_json(project_path)

    # Normalise legacy key before writing
    for entry in mapping.values():
        if (
            isinstance(entry, dict)
            and "version" in entry
            and "default_version" not in entry
        ):
            entry["default_version"] = entry.pop("version")

    data["survey_version_mapping"] = mapping
    if settings is not None:
        data["survey_plan_settings"] = settings
    elif "survey_plan_settings" not in data:
        data["survey_plan_settings"] = {"auto_discover": True}

    _write_project_json(project_path, data)


# ---------------------------------------------------------------------------
# Auto-discovery  / migration
# ---------------------------------------------------------------------------


def enrich_and_save_survey_plan(project_path: Path, library_path: Path) -> dict:
    """Discover surveys in the library, merge with existing mapping, and save.

    - Existing entries are preserved unchanged.
    - New surveys discovered in the library are added with their library default version.
    - Returns the final (merged) survey_version_mapping dict for use by the caller.
    """
    plan = load_survey_plan(project_path)
    existing_mapping: dict = plan["survey_version_mapping"]
    settings: dict = plan["survey_plan_settings"]

    discovered = discover_survey_variants(library_path)
    added = []

    for task_name, info in discovered.items():
        if task_name not in existing_mapping:
            existing_mapping[task_name] = {
                "default_version": info["default_version"],
                "by_session": {},
                "by_run": {},
                "by_session_run": {},
            }
            added.append(task_name)

    # Also initialise missing sub-keys for existing entries (safe migration)
    for entry in existing_mapping.values():
        if isinstance(entry, dict):
            entry.setdefault("by_session", {})
            entry.setdefault("by_run", {})
            entry.setdefault("by_session_run", {})

    save_survey_plan(project_path, existing_mapping, settings)
    return {
        "survey_version_mapping": existing_mapping,
        "added": added,
        "available": discovered,
    }


# ---------------------------------------------------------------------------
# Version resolution
# ---------------------------------------------------------------------------


def resolve_version(
    mapping_entry: dict,
    session: Optional[str] = None,
    run: Optional[str] = None,
) -> Optional[str]:
    """Return the variant version string for the given session / run context.

    Priority:
        1. by_session_run[session][run]
        2. by_session[session]
        3. by_run[run]
        4. default_version

    Returns None if no version can be resolved (caller should emit an error).
    """
    if not isinstance(mapping_entry, dict):
        return None

    by_session_run: dict = mapping_entry.get("by_session_run", {})
    by_session: dict = mapping_entry.get("by_session", {})
    by_run: dict = mapping_entry.get("by_run", {})
    default: Optional[str] = mapping_entry.get("default_version") or mapping_entry.get(
        "version"
    )

    # 1. session + run combined
    if session and run:
        session_map = by_session_run.get(session, {})
        match = session_map.get(run)
        if match:
            return match

    # 2. session only
    if session:
        match = by_session.get(session)
        if match:
            return match

    # 3. run only
    if run:
        match = by_run.get(run)
        if match:
            return match

    # 4. default
    return default


def resolve_version_for_file(
    project_path: Path,
    task_name: str,
    session: Optional[str] = None,
    run: Optional[str] = None,
) -> Optional[str]:
    """Convenience wrapper: read mapping from project.json and resolve.

    Returns the resolved version string or None if the survey has no mapping.
    """
    plan = load_survey_plan(project_path)
    mapping = plan["survey_version_mapping"]
    entry = mapping.get(task_name)
    if entry is None:
        return None
    return resolve_version(entry, session=session, run=run)
