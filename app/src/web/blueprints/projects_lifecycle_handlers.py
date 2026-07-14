import os
import json
import shutil
from pathlib import Path
from typing import Any

from flask import jsonify, request, session
import requests

from .projects_helpers import _load_recent_projects, _save_recent_projects
from .projects_helpers import _resolve_project_json_path, _resolve_project_root_path
from .projects_citation_helpers import _validate_recruitment_payload
from src.project_icons import choose_random_project_icon, normalize_project_icon, resolve_project_icon
from src.system_files import filter_system_files

_RECRUITMENT_GEOCODING_URL = "https://geocoding-api.open-meteo.com/v1/search"
_RECRUITMENT_GEOCODING_TIMEOUT_SECONDS = 5
_DATALAD_DOCS_URL = "https://www.datalad.org/"
_DATALAD_INSTALL_HINT = "Install with: uv tool install datalad git-annex"


def _normalize_dataset_type(dataset_type):
    value = str(dataset_type or "").strip().lower()
    if value in {"raw", "derivative"}:
        return value
    return "raw"


def _derive_project_name(root_path: Path, fallback_name: str | None = None) -> str:
    """Resolve display name from project metadata with safe fallbacks."""
    project_json = root_path / "project.json"
    if project_json.exists() and project_json.is_file():
        try:
            payload = json.loads(project_json.read_text(encoding="utf-8"))
            name = str(payload.get("name") or "").strip()
            if name:
                return name
        except Exception:
            pass

    fallback = str(fallback_name or "").strip()
    if fallback:
        return fallback

    return root_path.name


def _derive_project_icon(
    root_path: Path,
    fallback_icon: Any = None,
    *,
    persist_when_missing: bool = True,
) -> str:
    """Resolve project icon with optional persistence for explicit write flows."""
    try:
        return resolve_project_icon(
            root_path,
            fallback_icon=fallback_icon,
            persist_when_missing=persist_when_missing,
        )
    except Exception:
        return normalize_project_icon(fallback_icon) or choose_random_project_icon()


def _build_project_quick_summary(root_path: Path) -> dict[str, Any]:
    """Build fast project summary metrics for UI cards.

    This intentionally avoids full validation and only scans structure basics.
    """
    try:
        from src.project_structure import get_project_quick_summary

        return get_project_quick_summary(root_path)
    except Exception:
        return {}


def _get_datalad_preflight_status() -> dict[str, Any]:
    """Return lightweight DataLad/git-annex availability for project creation."""
    datalad_executable = shutil.which("datalad")
    git_annex_executable = shutil.which("git-annex")

    if datalad_executable and git_annex_executable:
        message = "DataLad and git-annex are available for project setup."
    elif datalad_executable:
        message = (
            "git-annex is not installed, so PRISM will create the project without "
            "DataLad even if you leave the DataLad option enabled. "
            f"{_DATALAD_INSTALL_HINT}. Learn more: {_DATALAD_DOCS_URL}"
        )
    else:
        message = (
            "DataLad is not installed, so PRISM will create the project without "
            "DataLad even if you leave the DataLad option enabled. "
            f"{_DATALAD_INSTALL_HINT}. Learn more: {_DATALAD_DOCS_URL}"
        )

    return {
        "available": bool(datalad_executable),
        "annex_available": bool(git_annex_executable),
        "can_enable": bool(datalad_executable and git_annex_executable),
        "message": message,
    }


def handle_datalad_preflight_status():
    """Return lightweight DataLad/git-annex availability for project setup UI."""
    return jsonify({"success": True, "datalad_preflight": _get_datalad_preflight_status()})


def handle_remote_source_status(project_manager):
    """Return remote dataset classification plus machine requirements."""
    data = request.get_json(silent=True) or {}
    remote_url = data.get("remote_url")
    remote_source = project_manager.inspect_remote_dataset_source(remote_url)
    remote_source["datalad_preflight"] = _get_datalad_preflight_status()
    if remote_source.get("requires_datalad") and not remote_source["datalad_preflight"].get("can_enable"):
        remote_source["disabled"] = True
        remote_source["message"] = (
            "This OpenNeuro/DataLad dataset requires DataLad and git-annex on this machine before PRISM can initialise it."
        )
    else:
        remote_source["disabled"] = False
    return jsonify({"success": True, "remote_source": remote_source})


def handle_set_current(
    get_current_project,
    set_current_project,
    save_last_project,
    close_project_session=None,
    autosave_current_project=None,
):
    """Set or clear current project in session and persisted settings."""
    data = request.get_json()
    if not data:
        return jsonify({"success": False, "error": "No data provided"}), 400

    path = data.get("path")

    if not path:
        autosave_previous = None
        if autosave_current_project is not None:
            try:
                autosave_previous = autosave_current_project(
                    session.get("current_project_path"),
                    reason="project_cleared",
                )
            except Exception as exc:
                autosave_previous = {
                    "success": False,
                    "attempted": True,
                    "skipped": False,
                    "reason": "project_cleared",
                    "path": str(session.get("current_project_path") or "").strip(),
                    "error": str(exc),
                    "message": f"DataLad auto-save failed: {exc}",
                }
        if close_project_session is not None:
            try:
                close_project_session(reason="project_cleared")
            except Exception:
                pass
        session.pop("current_project_path", None)
        session.pop("current_project_name", None)
        session.pop("current_project_icon", None)
        save_last_project(None, None)
        response_payload: dict[str, Any] = {
            "success": True,
            "current": get_current_project(),
        }
        if isinstance(autosave_previous, dict):
            response_payload["autosave_previous"] = autosave_previous
        return jsonify(response_payload)

    name = data.get("name")

    if not os.path.exists(path):
        return jsonify({"success": False, "error": "Path does not exist"}), 400

    resolved_root = _resolve_project_root_path(path)
    if not resolved_root:
        return (
            jsonify(
                {
                    "success": False,
                    "error": "Path must be a project directory or project.json",
                }
            ),
            400,
        )

    path = str(resolved_root)

    resolved_name = _derive_project_name(Path(path), fallback_name=name)
    requested_icon = normalize_project_icon(data.get("icon"))
    resolved_icon = _derive_project_icon(
        Path(path),
        fallback_icon=requested_icon,
        persist_when_missing=bool(requested_icon),
    )

    autosave_previous = set_current_project(path, resolved_name)
    session["current_project_icon"] = resolved_icon
    save_last_project(path, resolved_name)

    summary = _build_project_quick_summary(Path(path))
    current = dict(get_current_project() or {})
    current["icon"] = resolved_icon

    response_payload: dict[str, Any] = {
        "success": True,
        "current": current,
        "project_summary": summary,
    }
    if isinstance(autosave_previous, dict):
        response_payload["autosave_previous"] = autosave_previous

    return jsonify(response_payload)


def handle_create_project(project_manager, set_current_project, save_last_project):
    """Create a new PRISM project and set it as current."""
    try:
        data = request.get_json()

        if not data:
            return jsonify({"success": False, "error": "No data provided"}), 400

        path = data.get("path")
        if not path:
            return jsonify({"success": False, "error": "Path is required"}), 400

        recruitment_error = _validate_recruitment_payload(data.get("Recruitment"))
        if recruitment_error:
            return jsonify({"success": False, "error": recruitment_error}), 400

        config = {
            "name": data.get("name", Path(path).name),
            "use_datalad": data.get("use_datalad", False),
            "authors": data.get("authors"),
            "license": data.get("license"),
            "doi": data.get("doi"),
            "keywords": data.get("keywords"),
            "acknowledgements": data.get("acknowledgements"),
            "ethics_approvals": data.get("ethics_approvals"),
            "how_to_acknowledge": data.get("how_to_acknowledge"),
            "funding": data.get("funding"),
            "references_and_links": data.get("references_and_links"),
            "hed_version": data.get("hed_version"),
            "dataset_type": _normalize_dataset_type(data.get("dataset_type")),
            "description": data.get("description"),
            "Basics": data.get("Basics"),
            "Overview": data.get("Overview"),
            "StudyDesign": data.get("StudyDesign"),
            "Recruitment": data.get("Recruitment"),
            "Eligibility": data.get("Eligibility"),
            "DataCollection": data.get("DataCollection"),
            "Procedure": data.get("Procedure"),
            "MissingData": data.get("MissingData"),
            "References": data.get("References"),
            "Conditions": data.get("Conditions"),
        }

        result = project_manager.create_project(path, config)

        if result.get("success"):
            project_name = config.get("name") or Path(path).name
            project_icon = _derive_project_icon(Path(path))
            set_current_project(path, project_name)
            session["current_project_icon"] = project_icon
            save_last_project(path, project_name)
            result["current_project"] = {
                "path": str(Path(path)),
                "name": project_name,
                "icon": project_icon,
                "datalad": project_manager.get_datalad_status(path),
                "project_json_path": str(Path(path) / "project.json"),
            }
            return jsonify(result)

        return jsonify(result), 400
    except Exception as error:
        return jsonify({"success": False, "error": str(error)}), 500


def handle_init_on_bids(project_manager, set_current_project, save_last_project):
    """Initialise PRISM on an existing BIDS dataset root."""
    try:
        data = request.get_json()
        if not data:
            return jsonify({"success": False, "error": "No data provided"}), 400

        remote_url = str(data.get("remote_url") or "").strip()
        has_remote_source = bool(remote_url)

        request_path = str(data.get("path") or "").strip()
        bids_path = str(data.get("bids_path") or "").strip()
        clone_path = str(data.get("clone_path") or "").strip()

        if has_remote_source:
            path = clone_path or request_path
            if not path:
                return (
                    jsonify(
                        {
                            "success": False,
                            "error": (
                                "Clone destination is required when using a Git/DataLad URL."
                            ),
                        }
                    ),
                    400,
                )
        else:
            path = bids_path or request_path
            if not path:
                return (
                    jsonify(
                        {
                            "success": False,
                            "error": (
                                "BIDS dataset root is required when no Git/DataLad URL is provided."
                            ),
                        }
                    ),
                    400,
                )

        requested_use_datalad = bool(data.get("use_datalad", False))

        config = {
            "name": data.get("name"),
            "use_datalad": requested_use_datalad if not has_remote_source else False,
            "remote_url": remote_url or None,
            "source_type": data.get("source_type") or ("remote" if has_remote_source else "local"),
            "authors": data.get("authors"),
            "license": data.get("license"),
            "doi": data.get("doi"),
            "keywords": data.get("keywords"),
            "acknowledgements": data.get("acknowledgements"),
            "ethics_approvals": data.get("ethics_approvals"),
            "how_to_acknowledge": data.get("how_to_acknowledge"),
            "funding": data.get("funding"),
            "references_and_links": data.get("references_and_links"),
            "dataset_type": _normalize_dataset_type(data.get("dataset_type")),
            "description": data.get("description"),
            "auto_environment_enrichment": bool(data.get("auto_environment_enrichment", True)),
        }

        result = project_manager.init_on_existing_bids(path, config)

        if result.get("success"):
            resolved_path = str(result.get("path") or path)
            project_name = config.get("name") or Path(resolved_path).name
            project_icon = _derive_project_icon(Path(resolved_path))
            set_current_project(resolved_path, project_name)
            session["current_project_icon"] = project_icon
            save_last_project(resolved_path, project_name)
            result["current_project"] = {
                "path": resolved_path,
                "name": project_name,
                "icon": project_icon,
                "datalad": project_manager.get_datalad_status(resolved_path),
                "project_json_path": str(Path(resolved_path) / "project.json"),
            }
            if config["auto_environment_enrichment"]:
                try:
                    from .conversion_environment_handlers import (
                        trigger_automatic_environment_enrichment,
                    )

                    job_id = trigger_automatic_environment_enrichment(Path(resolved_path))
                    result["environment_enrichment_job_id"] = job_id
                except Exception:
                    result["environment_enrichment_job_id"] = None
            return jsonify(result)

        return jsonify(result), 400
    except Exception as error:
        return jsonify({"success": False, "error": str(error)}), 500


def handle_validate_project(project_manager, set_current_project, save_last_project):
    """Validate existing project.json and set project as current when valid."""
    try:
        data = request.get_json()

        if not data:
            return jsonify({"success": False, "error": "No data provided"}), 400

        path = data.get("path")
        if not path:
            return jsonify({"success": False, "error": "Path is required"}), 400

        root_path_obj = _resolve_project_root_path(path)
        project_json = _resolve_project_json_path(path)
        if not root_path_obj or not project_json:
            return (
                jsonify(
                    {
                        "success": False,
                        "error": "Invalid selection. Select either the project folder containing project.json or the project.json file itself.",
                    }
                ),
                400,
            )

        project_json_path = str(project_json)
        root_path = str(root_path_obj)

        if not os.path.exists(root_path):
            return (
                jsonify(
                    {"success": False, "error": f"Path does not exist: {root_path}"}
                ),
                400,
            )

        result = project_manager.validate_structure(root_path)
        result["success"] = True

        project_name = _derive_project_name(
            root_path_obj,
            fallback_name=session.get("current_project_name"),
        )
        project_icon = _derive_project_icon(
            root_path_obj,
            fallback_icon=session.get("current_project_icon"),
        )
        set_current_project(root_path, project_name)
        session["current_project_icon"] = project_icon
        save_last_project(root_path, project_name)

        result["current_project"] = {
            "path": root_path,
            "name": project_name,
            "icon": project_icon,
            "datalad": project_manager.get_datalad_status(root_path),
            "project_json_path": project_json_path,
        }

        return jsonify(result)
    except Exception as error:
        return jsonify({"success": False, "error": str(error)}), 500


def _make_writable_and_retry(func, path, exc_info):
    """``shutil.rmtree`` onerror handler for read-only git-annex objects.

    DataLad/git-annex store annexed file content as read-only objects so
    accidental edits fail loudly. That same read-only bit makes a plain
    ``rmtree`` fail on those files, so we chmod the offending path writable
    and retry the failed operation once.
    """
    try:
        os.chmod(path, 0o700 if os.path.isdir(path) else 0o600)
        func(path)
    except OSError:
        raise exc_info[1]


def handle_delete_project(project_manager, get_current_project, clear_current_project):
    """Permanently delete a project directory from disk.

    This is destructive and irreversible, so it requires the caller to
    confirm by echoing back the project's exact name (mirrors the
    "type the name to confirm" pattern used for other irreversible actions),
    in addition to the path itself.
    """
    try:
        data = request.get_json()
        if not data:
            return jsonify({"success": False, "error": "No data provided"}), 400

        path = data.get("path")
        confirm_name = str(data.get("confirm_name") or "").strip()
        if not path:
            return jsonify({"success": False, "error": "Path is required"}), 400

        root_path_obj = _resolve_project_root_path(path)
        if not root_path_obj or not root_path_obj.exists():
            return (
                jsonify({"success": False, "error": f"Path does not exist: {path}"}),
                400,
            )

        # Refuse to touch anything that doesn't look like a PRISM/BIDS
        # project root, and refuse filesystem roots / home directories
        # outright — this endpoint only ever deletes recognizable project
        # folders, never arbitrary paths a caller might pass by mistake.
        looks_like_project = (root_path_obj / "project.json").exists() or (
            root_path_obj / "dataset_description.json"
        ).exists()
        if not looks_like_project:
            return (
                jsonify(
                    {
                        "success": False,
                        "error": "This folder does not look like a PRISM project "
                        "(no project.json or dataset_description.json found). "
                        "Refusing to delete it.",
                    }
                ),
                400,
            )

        if root_path_obj == root_path_obj.anchor or root_path_obj == Path.home():
            return (
                jsonify(
                    {
                        "success": False,
                        "error": "Refusing to delete a filesystem root or home directory.",
                    }
                ),
                400,
            )

        actual_name = _derive_project_name(root_path_obj, fallback_name=root_path_obj.name)
        if not confirm_name or confirm_name != actual_name:
            return (
                jsonify(
                    {
                        "success": False,
                        "error": "Confirmation name does not match the project name. "
                        f"Expected '{actual_name}'.",
                    }
                ),
                400,
            )

        root_path = str(root_path_obj)

        shutil.rmtree(root_path, onerror=_make_writable_and_retry)

        # Drop it from the recent-projects list and clear it as the active
        # project if it was loaded, so the UI doesn't point at a dead path.
        try:
            remaining = [
                entry
                for entry in _load_recent_projects()
                if str(entry.get("path") or "") != root_path
            ]
            _save_recent_projects(remaining)
        except Exception:
            pass

        current_project = get_current_project()
        if str(current_project.get("path") or "") == root_path:
            clear_current_project()

        return jsonify({"success": True, "deleted_path": root_path})
    except Exception as error:
        return jsonify({"success": False, "error": str(error)}), 500


def handle_project_path_status():
    """Return lightweight availability info for a project.json path."""
    try:
        data = request.get_json()
        if not data:
            return jsonify({"success": False, "error": "No data provided"}), 400

        path = data.get("path")
        if not isinstance(path, str) or not path.strip():
            return jsonify({"success": False, "error": "Path is required"}), 400

        path_obj = Path(path)
        exists = path_obj.exists()
        is_file = path_obj.is_file()
        is_dir = path_obj.is_dir()
        is_project_json = is_file and path_obj.name == "project.json"
        resolved_project_json = _resolve_project_json_path(path)
        non_system_entries = []
        if is_dir:
            non_system_entries = filter_system_files(
                [entry.name for entry in path_obj.iterdir()]
            )

        return jsonify(
            {
                "success": True,
                "exists": exists,
                "is_file": is_file,
                "is_dir": is_dir,
                "is_project_json": is_project_json,
                "is_empty_dir": (is_dir and not non_system_entries),
                "has_non_system_entries": (is_dir and bool(non_system_entries)),
                "available": bool(resolved_project_json),
                "project_json_path": (
                    str(resolved_project_json) if resolved_project_json else None
                ),
                "datalad_preflight": _get_datalad_preflight_status(),
            }
        )
    except Exception as error:
        return jsonify({"success": False, "error": str(error)}), 500


def handle_recruitment_location_search():
    """Search place names for Recruitment->Location in Projects UI."""
    query = (request.args.get("q") or "").strip()
    if len(query) < 2:
        return jsonify({"success": False, "error": "Query too short"}), 400

    params = {
        "name": query,
        "count": 8,
        "language": "en",
        "format": "json",
    }

    try:
        response = requests.get(
            _RECRUITMENT_GEOCODING_URL,
            params=params,
            timeout=_RECRUITMENT_GEOCODING_TIMEOUT_SECONDS,
        )
        response.raise_for_status()
        payload = response.json()

        raw_results = payload.get("results") or []
        results: list[dict[str, Any]] = []
        for item in raw_results:
            name = (item.get("name") or "").strip()
            admin1 = (item.get("admin1") or "").strip()
            country = (item.get("country") or "").strip()
            label_parts = [part for part in [name, admin1, country] if part]
            label = ", ".join(label_parts) if label_parts else name

            lat = item.get("latitude")
            lon = item.get("longitude")
            if lat is None or lon is None:
                continue

            results.append(
                {
                    "name": name,
                    "display_name": label,
                    "latitude": float(lat),
                    "longitude": float(lon),
                    "timezone": item.get("timezone") or "",
                }
            )

        return jsonify({"success": True, "results": results})
    except requests.RequestException as exc:
        return jsonify({"success": False, "error": str(exc)}), 502


def handle_get_recent_projects():
    """Get recent projects from user-scoped settings storage."""
    try:
        projects = _load_recent_projects()
        return jsonify({"success": True, "projects": projects})
    except Exception as error:
        return jsonify({"success": False, "error": str(error), "projects": []}), 500


def handle_set_recent_projects():
    """Replace recent projects list in user-scoped settings storage."""
    data = request.get_json(silent=True) or {}
    projects = data.get("projects")
    if not isinstance(projects, list):
        return jsonify({"success": False, "error": "projects must be a list"}), 400

    try:
        saved = _save_recent_projects(projects)
        return jsonify({"success": True, "projects": saved})
    except Exception as error:
        return jsonify({"success": False, "error": str(error)}), 500


def handle_fix_project(project_manager):
    """Apply fix operations to a project."""
    try:
        data = request.get_json()

        if not data:
            return jsonify({"success": False, "error": "No data provided"}), 400

        path = data.get("path")
        if not path:
            return jsonify({"success": False, "error": "Path is required"}), 400

        fix_codes = data.get("fix_codes")
        result = project_manager.apply_fixes(path, fix_codes)
        return jsonify(result)
    except Exception as error:
        return jsonify({"success": False, "error": str(error)}), 500


def handle_get_fixable_issues(project_manager):
    """List fixable issues for the given project path."""
    try:
        data = request.get_json()

        if not data:
            return jsonify({"success": False, "error": "No data provided"}), 400

        path = data.get("path")
        if not path:
            return jsonify({"success": False, "error": "Path is required"}), 400

        issues = project_manager.get_fixable_issues(path)
        return jsonify({"success": True, "issues": issues})
    except Exception as error:
        return jsonify({"success": False, "error": str(error)}), 500
