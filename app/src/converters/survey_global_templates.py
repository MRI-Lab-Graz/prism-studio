"""Global template/participants discovery and comparison helpers."""

from __future__ import annotations

from pathlib import Path
import os

from ..config import get_effective_library_paths, load_app_settings
from ..utils.io import read_json as _read_json
from .survey_helpers import _extract_template_structure
from .survey_participants import (
    _is_participant_template,
    _normalize_participant_template_dict,
)


def _load_global_library_path() -> Path | None:
    """Find the global library path from config."""
    try:
        app_root = Path(__file__).parent.parent.parent.resolve()
        settings = load_app_settings(app_root=str(app_root))

        if settings.global_library_root:
            root = settings.global_library_root
            if not os.path.isabs(root):
                root = os.path.normpath(os.path.join(app_root, root))
            p = Path(root).expanduser().resolve()

            candidates = [
                p / "library" / "survey",
                p / "survey",
            ]
            for candidate in candidates:
                if candidate.is_dir():
                    return candidate

            if (p / "library").is_dir():
                return p / "library"

        lib_paths = get_effective_library_paths(app_root=str(app_root))
        global_path = lib_paths.get("global_library_path")
        if global_path:
            p = Path(global_path).expanduser().resolve()
            if (p / "survey").is_dir():
                return p / "survey"
            if p.is_dir():
                return p
    except Exception:
        pass
    return None


def _load_global_templates() -> dict[str, dict]:
    """Load all templates from the global library."""
    global_path = _load_global_library_path()
    if not global_path or not global_path.exists():
        return {}

    templates = {}
    for json_path in sorted(global_path.glob("survey-*.json")):
        if _is_participant_template(json_path):
            continue
        try:
            sidecar = _read_json(json_path)
        except Exception:
            continue

        task_from_name = json_path.stem.replace("survey-", "")
        task = str(sidecar.get("Study", {}).get("TaskName") or task_from_name).strip()
        task_norm = task.lower() or task_from_name.lower()

        templates[task_norm] = {
            "path": json_path,
            "json": sidecar,
            "structure": _extract_template_structure(sidecar),
        }

    return templates


def _load_global_participants_template() -> dict | None:
    """Load the global participants.json template."""
    global_path = _load_global_library_path()
    if not global_path or not global_path.exists():
        return None

    candidates = [
        global_path.parent / "participants.json",
        global_path / "participants.json",
    ]
    for ancestor in global_path.parents[:2]:
        candidates.append(ancestor / "participants.json")

    for p in candidates:
        if p.exists() and p.is_file():
            try:
                return _read_json(p)
            except Exception:
                pass
    return None


def _compare_participants_templates(
    project_template: dict | None,
    global_template: dict | None,
) -> tuple[bool, set[str], set[str], list[str]]:
    """Compare project participants template against global template."""
    warnings: list[str] = []

    if not project_template and not global_template:
        return True, set(), set(), warnings

    if not project_template:
        return False, set(), set(), ["No project participants.json found"]

    if not global_template:
        return True, set(), set(), warnings

    project_norm = _normalize_participant_template_dict(project_template) or {}
    global_norm = _normalize_participant_template_dict(global_template) or {}

    project_cols = {k for k in project_norm.keys() if not k.startswith("_")}
    global_cols = {k for k in global_norm.keys() if not k.startswith("_")}

    only_in_project = project_cols - global_cols
    only_in_global = global_cols - project_cols

    is_equivalent = len(only_in_project) == 0 and len(only_in_global) == 0

    if not is_equivalent:
        diff_parts = []
        if only_in_project:
            diff_parts.append(f"added columns: {', '.join(sorted(only_in_project))}")
        if only_in_global:
            diff_parts.append(f"missing columns: {', '.join(sorted(only_in_global))}")
        warnings.append(
            f"participants.json differs from global: {'; '.join(diff_parts)}"
        )

    return is_equivalent, only_in_project, only_in_global, warnings


def _find_matching_global_template(
    project_template: dict,
    global_templates: dict[str, dict],
) -> tuple[str | None, bool, set[str], set[str]]:
    """Find if a project template matches any global template."""
    project_struct = _extract_template_structure(project_template)

    best_match = None
    best_overlap = 0
    best_only_project: set[str] = set()
    best_only_global: set[str] = set()

    for task_name, global_data in global_templates.items():
        global_struct = global_data["structure"]

        overlap = len(project_struct & global_struct)
        only_in_project = project_struct - global_struct
        only_in_global = global_struct - project_struct

        if len(only_in_project) == 0 and len(only_in_global) == 0:
            return task_name, True, set(), set()

        if overlap > best_overlap:
            best_overlap = overlap
            best_match = task_name
            best_only_project = only_in_project
            best_only_global = only_in_global

    if best_match and best_overlap > len(project_struct) * 0.5:
        return best_match, False, best_only_project, best_only_global

    return None, False, set(), set()
