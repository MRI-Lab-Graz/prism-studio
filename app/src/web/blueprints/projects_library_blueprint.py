from pathlib import Path

from flask import Blueprint, jsonify, request

from src.project_manager import get_available_modalities
from .projects import get_current_project, get_bids_file_path

projects_library_bp = Blueprint("projects_library", __name__)


@projects_library_bp.route("/api/projects/modalities", methods=["GET"])
def get_modalities():
    """Get list of available PRISM modalities."""
    return jsonify({"success": True, "modalities": get_available_modalities()})


def _apply_settings_changes(changes: dict):
    """Studio's Settings page runs the same function as `prism_tools.py settings set`."""
    from flask import current_app

    from src.settings_update import SettingsError, update_app_settings

    try:
        return update_app_settings(Path(current_app.root_path), changes), None
    except SettingsError as exc:
        return None, (jsonify({"success": False, "error": str(exc)}), 400)
    except Exception as exc:  # the settings file could not be written
        return None, (jsonify({"success": False, "error": str(exc)}), 500)


@projects_library_bp.route("/api/settings/global-library", methods=["GET"])
def get_global_library_settings():
    """Get the global template library settings."""
    from src.config import (
        load_app_settings,
        normalize_export_defacing_confirmation_mode,
    )
    from flask import current_app

    app_root = Path(current_app.root_path)
    settings = load_app_settings(app_root=str(app_root))

    from src.config import get_effective_library_paths

    lib_paths = get_effective_library_paths(
        app_root=str(app_root), app_settings=settings
    )
    default_library_path = lib_paths["global_library_path"] or str(
        app_root / "survey_library"
    )

    return jsonify(
        {
            "success": True,
            "global_template_library_path": settings.global_template_library_path,
            "global_recipes_path": settings.global_recipes_path,
            "personal_library_path": settings.personal_library_path,
            "default_library_path": default_library_path,
            "default_modalities": settings.default_modalities,
            "backend_monitoring": bool(settings.backend_monitoring),
            "backend_monitoring_verbose": bool(settings.backend_monitoring_verbose),
            "show_dedicated_terminal": bool(settings.show_dedicated_terminal),
            "export_defacing_confirmation_mode": normalize_export_defacing_confirmation_mode(
                getattr(settings, "export_defacing_confirmation_mode", "risk")
            ),
            "enable_study_application_import": bool(
                getattr(settings, "enable_study_application_import", False)
            ),
        }
    )


@projects_library_bp.route("/api/settings/study-application-import", methods=["GET"])
def get_study_application_import_setting():
    """Get whether the MRI-Lab Graz study application import UI is enabled."""
    from src.config import load_app_settings
    from flask import current_app

    app_root = Path(current_app.root_path)
    settings = load_app_settings(app_root=str(app_root))

    return jsonify(
        {
            "success": True,
            "enable_study_application_import": bool(
                settings.enable_study_application_import
            ),
        }
    )


@projects_library_bp.route("/api/settings/study-application-import", methods=["POST"])
def set_study_application_import_setting():
    """Update whether the MRI-Lab Graz study application import UI is enabled."""
    data = request.get_json() or {}
    if "enable_study_application_import" not in data:
        return jsonify({"success": False, "error": "Missing enable_study_application_import"}), 400
    settings, error = _apply_settings_changes({"enable_study_application_import": data["enable_study_application_import"]})
    if error:
        return error
    return jsonify({"success": True, "enable_study_application_import": bool(settings.enable_study_application_import)})


@projects_library_bp.route("/api/settings/backend-monitoring", methods=["GET"])
def get_backend_monitoring_setting():
    """Get backend-action terminal monitoring setting."""
    from src.config import load_app_settings
    from flask import current_app

    app_root = Path(current_app.root_path)
    settings = load_app_settings(app_root=str(app_root))

    return jsonify(
        {
            "success": True,
            "backend_monitoring": bool(settings.backend_monitoring),
            "backend_monitoring_verbose": bool(settings.backend_monitoring_verbose),
        }
    )


@projects_library_bp.route("/api/settings/backend-monitoring", methods=["POST"])
def set_backend_monitoring_setting():
    """Update backend-action terminal monitoring setting."""
    data = request.get_json() or {}
    changes = {k: data[k] for k in ("backend_monitoring", "backend_monitoring_verbose") if k in data}
    if not changes:
        return jsonify({"success": False, "error": "Missing backend_monitoring or backend_monitoring_verbose"}), 400
    settings, error = _apply_settings_changes(changes)
    if error:
        return error
    return jsonify({
        "success": True,
        "backend_monitoring": bool(settings.backend_monitoring),
        "backend_monitoring_verbose": bool(settings.backend_monitoring_verbose),
    })


@projects_library_bp.route("/api/settings/dedicated-terminal", methods=["GET"])
def get_dedicated_terminal_setting():
    """Get dedicated terminal startup setting."""
    from src.config import load_app_settings
    from flask import current_app

    app_root = Path(current_app.root_path)
    settings = load_app_settings(app_root=str(app_root))

    return jsonify(
        {
            "success": True,
            "show_dedicated_terminal": bool(settings.show_dedicated_terminal),
        }
    )


@projects_library_bp.route("/api/settings/dedicated-terminal", methods=["POST"])
def set_dedicated_terminal_setting():
    """Update dedicated terminal startup setting."""
    data = request.get_json() or {}
    if "show_dedicated_terminal" not in data:
        return jsonify({"success": False, "error": "Missing show_dedicated_terminal"}), 400
    settings, error = _apply_settings_changes({"show_dedicated_terminal": data["show_dedicated_terminal"]})
    if error:
        return error
    return jsonify({"success": True, "show_dedicated_terminal": bool(settings.show_dedicated_terminal)})


@projects_library_bp.route("/api/settings/global-library", methods=["POST"])
def set_global_library_settings():
    """Update the global template library settings."""
    data = request.get_json()
    if not data:
        return jsonify({"success": False, "error": "No data provided"}), 400
    from src.settings_update import SETTINGS

    shared = {"global_template_library_path", "global_recipes_path", "personal_library_path", "default_modalities", "export_defacing_confirmation_mode"}
    settings, error = _apply_settings_changes({k: v for k, v in data.items() if k in shared and k in SETTINGS})
    if error:
        return error
    return jsonify({
        "success": True,
        "message": "Settings saved.",
        "global_template_library_path": settings.global_template_library_path,
        "personal_library_path": settings.personal_library_path,
        "global_recipes_path": settings.global_recipes_path,
        "export_defacing_confirmation_mode": settings.export_defacing_confirmation_mode,
    })


@projects_library_bp.route("/api/projects/library-path", methods=["GET"])
def get_library_path():
    """Get the library paths for the current project."""
    from src.config import get_effective_template_library_path, load_app_settings
    from flask import current_app

    current = get_current_project()
    app_root = Path(current_app.root_path)
    app_settings = load_app_settings(app_root=str(app_root))

    from src.config import get_effective_library_paths

    lib_paths = get_effective_library_paths(
        app_root=str(app_root), app_settings=app_settings
    )

    def resolve_library_path(path_str):
        if not path_str:
            return None
        p = Path(path_str)
        if not p.is_absolute():
            p = (app_root / p).resolve()
        else:
            p = p.resolve()
        return str(p) if p.exists() and p.is_dir() else None

    effective_global_path = (
        resolve_library_path(app_settings.global_template_library_path)
        or resolve_library_path(lib_paths["global_library_path"])
        or resolve_library_path(str(app_root / "survey_library"))
        or resolve_library_path(str(app_root / "library" / "survey_i18n"))
    )

    if not current.get("path"):
        return jsonify(
            {
                "success": False,
                "message": "No project selected",
                "project_library_path": None,
                "project_library_exists": False,
                "global_library_path": effective_global_path,
                "library_path": effective_global_path,
            }
        )

    project_path = Path(current["path"])

    library_info = get_effective_template_library_path(
        str(project_path), app_settings, app_root=str(app_root)
    )

    yoda_library = project_path / "code" / "library"
    legacy_library = project_path / "library"

    if yoda_library.exists():
        legacy_library_path = str(yoda_library)
    elif legacy_library.exists():
        legacy_library_path = str(legacy_library)
    elif library_info.get("effective_external_path"):
        legacy_library_path = library_info["effective_external_path"]
    else:
        legacy_library_path = str(project_path)

    return jsonify(
        {
            "success": True,
            "project_path": str(project_path),
            "project_name": current.get("name"),
            "project_library_path": (
                str(yoda_library)
                if yoda_library.exists()
                else (str(legacy_library) if legacy_library.exists() else None)
            ),
            "project_library_exists": yoda_library.exists() or legacy_library.exists(),
            "global_library_path": library_info.get("global_library_path")
            or effective_global_path,
            "effective_external_path": library_info.get("effective_external_path"),
            "external_source": library_info.get("source"),
            "library_path": legacy_library_path,
            "structure": {
                "has_project_library": yoda_library.exists() or legacy_library.exists(),
                "has_survey": (
                    (yoda_library / "survey").exists()
                    if yoda_library.exists()
                    else (legacy_library / "survey").exists()
                ),
                "has_biometrics": (
                    (yoda_library / "biometrics").exists()
                    if yoda_library.exists()
                    else (legacy_library / "biometrics").exists()
                ),
                "has_participants": get_bids_file_path(
                    project_path, "participants.json"
                ).exists(),
                "has_external_library": library_info.get("effective_external_path")
                is not None,
            },
        }
    )
