from pathlib import Path

from flask import Blueprint, jsonify, request

from src.project_manager import get_available_modalities
from .projects import get_current_project, get_bids_file_path

projects_library_bp = Blueprint("projects_library", __name__)


@projects_library_bp.route("/api/projects/modalities", methods=["GET"])
def get_modalities():
    """Get list of available PRISM modalities."""
    return jsonify({"success": True, "modalities": get_available_modalities()})


@projects_library_bp.route("/api/settings/global-library", methods=["GET"])
def get_global_library_settings():
    """Get the global template library settings."""
    from src.config import load_app_settings
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
            "default_library_path": default_library_path,
            "default_modalities": settings.default_modalities,
        }
    )


@projects_library_bp.route("/api/settings/global-library", methods=["POST"])
def set_global_library_settings():
    """Update the global template library settings."""
    from src.config import load_app_settings, save_app_settings
    from flask import current_app
    import os

    data = request.get_json()
    if not data:
        return jsonify({"success": False, "error": "No data provided"}), 400

    app_root = Path(current_app.root_path)
    settings = load_app_settings(app_root=str(app_root))

    if "global_template_library_path" in data:
        path = data["global_template_library_path"]
        if path and path.strip():
            if not os.path.exists(path):
                return (
                    jsonify({"success": False, "error": f"Path does not exist: {path}"}),
                    400,
                )
            settings.global_template_library_path = path
        else:
            settings.global_template_library_path = None

    if "global_recipes_path" in data:
        path = data["global_recipes_path"]
        if path and path.strip():
            if not os.path.exists(path):
                return (
                    jsonify({"success": False, "error": f"Path does not exist: {path}"}),
                    400,
                )
            settings.global_recipes_path = path
        else:
            settings.global_recipes_path = None

    if "default_modalities" in data:
        settings.default_modalities = data["default_modalities"]

    try:
        app_root = Path(current_app.root_path)
        settings_path = save_app_settings(settings, str(app_root))
        return jsonify(
            {
                "success": True,
                "message": f"Settings saved to {settings_path}",
                "global_template_library_path": settings.global_template_library_path,
            }
        )
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


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
