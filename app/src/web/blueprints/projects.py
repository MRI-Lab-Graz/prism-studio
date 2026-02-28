"""
Flask blueprint for project management functionality.

Provides routes for:
- Creating new PRISM projects
- Validating existing project structures
- Applying fixes to repair issues
- Managing current working project
"""

from pathlib import Path
from flask import Blueprint, render_template, jsonify, session

from src.project_manager import ProjectManager, get_available_modalities
from .projects_citation_helpers import (
    _validate_recruitment_payload,
    _read_citation_cff_fields,
    _merge_citation_fields,
)
from .projects_study_metadata_handlers import (
    handle_generate_readme,
    handle_get_procedure_status,
    handle_get_study_metadata,
    handle_preview_readme,
    handle_save_study_metadata,
)
from .projects_participants_handlers import (
    handle_get_participants_columns,
    handle_get_participants_schema,
    handle_get_participants_templates,
    handle_save_participants_schema,
)
from .projects_description_handlers import (
    handle_get_dataset_description,
    handle_save_dataset_description,
    handle_validate_dataset_description_draft,
)
from .projects_sourcedata_handlers import (
    handle_get_sourcedata_file,
    handle_get_sourcedata_files,
)
from .projects_sessions_handlers import (
    handle_get_sessions,
    handle_get_sessions_declared,
    handle_register_session,
    handle_save_sessions,
)
from .projects_methods_handlers import handle_generate_methods_section
from .projects_lifecycle_handlers import (
    handle_create_project,
    handle_fix_project,
    handle_get_fixable_issues,
    handle_get_recent_projects,
    handle_project_path_status,
    handle_set_current,
    handle_set_recent_projects,
    handle_validate_project,
)
from .projects_metadata_helpers import (
    _EDITABLE_SECTIONS,
    _auto_detect_study_hints,
    _compute_methods_completeness,
    _compute_participant_stats,
    _read_project_json,
    _write_project_json,
)

projects_bp = Blueprint("projects", __name__)

# Shared project manager instance
_project_manager = ProjectManager()


def get_current_project() -> dict:
    """Get the current working project from session."""
    return {
        "path": session.get("current_project_path"),
        "name": session.get("current_project_name"),
    }


def set_current_project(path: str, name: str = None):
    """Set the current working project in session."""
    session["current_project_path"] = path
    session["current_project_name"] = name or Path(path).name


def get_bids_file_path(project_path: Path, filename: str) -> Path:
    """Get path to a BIDS metadata file at the project (dataset) root.

    Args:
        project_path: Path to the project root
        filename: Name of the file (e.g., 'participants.json', 'dataset_description.json')

    Returns:
        Path to the file at project root
    """
    return project_path / filename


def _resolve_project_root_path(project_path_value: str) -> Path | None:
    if not project_path_value:
        return None

    path_obj = Path(project_path_value)
    if not path_obj.exists():
        return None

    if path_obj.is_file() and path_obj.name == "project.json":
        return path_obj.parent

    if path_obj.is_dir():
        return path_obj

    return None


@projects_bp.route("/projects")
def projects_page():
    """Render the Projects management page."""
    current = get_current_project()
    return render_template(
        "projects.html", modalities=get_available_modalities(), current_project=current
    )


@projects_bp.route("/api/projects/current", methods=["GET"])
def get_current():
    """Get the current working project."""
    return jsonify(get_current_project())


@projects_bp.route("/api/projects/current", methods=["POST"])
def set_current():
    """Set or clear the current working project."""
    return handle_set_current(
        get_current_project=get_current_project,
        set_current_project=set_current_project,
        save_last_project=_save_last_project,
    )


def _save_last_project(path: str | None, name: str | None):
    """Save the last project to app settings for persistence."""
    try:
        from flask import current_app
        from src.config import load_app_settings, save_app_settings

        # Determine app root
        app_root = current_app.config.get("BASE_DIR")
        if not app_root:
            app_root = Path(__file__).parent.parent.parent.parent

        settings = load_app_settings(app_root=str(app_root))
        settings.last_project_path = path
        settings.last_project_name = name
        save_app_settings(settings, app_root=str(app_root))

        # Also update the app config so it's immediately available
        current_app.config["LAST_PROJECT_PATH"] = path
        current_app.config["LAST_PROJECT_NAME"] = name
    except Exception as e:
        print(f"[WARN] Could not save last project to settings: {e}")


@projects_bp.route("/api/projects/create", methods=["POST"])
def create_project():
    """
    Create a new PRISM project (YODA layout).

    Expected JSON body:
    {
        "path": "/path/to/project",
        "name": "My Study"
    }
    """
    return handle_create_project(
        project_manager=_project_manager,
        set_current_project=set_current_project,
        save_last_project=_save_last_project,
    )


@projects_bp.route("/api/projects/validate", methods=["POST"])
def validate_project():
    """
    Validate an existing project structure.

    Expected JSON body:
    {
        "path": "/path/to/project"  // or /path/to/project.json
    }
    """
    return handle_validate_project(
        project_manager=_project_manager,
        set_current_project=set_current_project,
        save_last_project=_save_last_project,
    )


@projects_bp.route("/api/projects/path-status", methods=["POST"])
def project_path_status():
    """Return lightweight availability info for a project.json path."""
    return handle_project_path_status()


@projects_bp.route("/api/projects/recent", methods=["GET"])
def get_recent_projects():
    """Get recent projects from user-scoped settings storage."""
    return handle_get_recent_projects()


@projects_bp.route("/api/projects/recent", methods=["POST"])
def set_recent_projects():
    """Replace recent projects list in user-scoped settings storage."""
    return handle_set_recent_projects()


@projects_bp.route("/api/projects/fix", methods=["POST"])
def fix_project():
    """
    Apply fixes to a project.

    Expected JSON body:
    {
        "path": "/path/to/project",
        "fix_codes": ["PRISM001", "PRISM501"]  // optional, null = fix all
    }
    """
    return handle_fix_project(project_manager=_project_manager)


@projects_bp.route("/api/projects/fixable", methods=["POST"])
def get_fixable_issues():
    """
    Get list of fixable issues for a project.

    Expected JSON body:
    {
        "path": "/path/to/project"
    }
    """
    return handle_get_fixable_issues(project_manager=_project_manager)


@projects_bp.route("/api/projects/participants", methods=["GET"])
def get_participants_schema():
    """Get the participants.json schema for the current project.

    Returns the current participants.json content and structure info.
    """
    return handle_get_participants_schema(
        get_current_project=get_current_project,
        get_bids_file_path=get_bids_file_path,
    )


@projects_bp.route("/api/projects/participants", methods=["POST"])
def save_participants_schema():
    """Save the participants.json schema for the current project.

    Expected JSON body:
    {
        "schema": {
            "participant_id": {"Description": "..."},
            "age": {"Description": "...", "Unit": "years"},
            ...
        }
    }
    """
    return handle_save_participants_schema(
        get_current_project=get_current_project,
        get_bids_file_path=get_bids_file_path,
    )


@projects_bp.route("/api/projects/description", methods=["GET"])
def get_dataset_description():
    """Get the dataset_description.json for the current project."""
    return handle_get_dataset_description(
        get_current_project=get_current_project,
        get_bids_file_path=get_bids_file_path,
        read_citation_cff_fields=_read_citation_cff_fields,
        merge_citation_fields=_merge_citation_fields,
        project_manager=_project_manager,
    )


@projects_bp.route("/api/projects/description", methods=["POST"])
def save_dataset_description():
    """Save the dataset_description.json for the current project."""
    return handle_save_dataset_description(
        get_current_project=get_current_project,
        get_bids_file_path=get_bids_file_path,
        read_citation_cff_fields=_read_citation_cff_fields,
        merge_citation_fields=_merge_citation_fields,
        project_manager=_project_manager,
        set_current_project=set_current_project,
        save_last_project=_save_last_project,
    )


@projects_bp.route("/api/projects/description/validate", methods=["POST"])
def validate_dataset_description_draft():
    """Validate a draft dataset_description payload (without saving)."""
    return handle_validate_dataset_description_draft(
        merge_citation_fields=_merge_citation_fields,
        project_manager=_project_manager,
    )


@projects_bp.route("/api/projects/participants/columns", methods=["GET"])
def get_participants_columns():
    """Extract unique values from project's participants.tsv."""
    return handle_get_participants_columns(
        get_current_project=get_current_project,
        get_bids_file_path=get_bids_file_path,
    )


@projects_bp.route("/api/projects/sourcedata-files", methods=["GET"])
def get_sourcedata_files():
    """List survey-compatible files in the project's sourcedata/ folder.

    Returns files matching converter-supported extensions (.xlsx, .csv, .tsv, .lsa, .lss)
    found in the sourcedata/ directory (non-recursive).
    """
    return handle_get_sourcedata_files(get_current_project=get_current_project)


@projects_bp.route("/api/projects/sourcedata-file", methods=["GET"])
def get_sourcedata_file():
    """Serve a file from the project's sourcedata/ folder.

    Query params:
        name: filename to serve (must be in sourcedata/)
    """
    return handle_get_sourcedata_file(get_current_project=get_current_project)


@projects_bp.route("/api/projects/participants/templates", methods=["GET"])
def get_participants_templates():
    """Get predefined BIDS-compatible field templates.

    Returns categorized field definitions with descriptions and levels.
    These are recommendations based on BIDS standard and common research needs.
    """
    return handle_get_participants_templates()



@projects_bp.route("/api/projects/export", methods=["POST"])
def export_project():
    """
    Export the current project as a ZIP file with optional anonymization.
    DEPRECATED: Use the route in projects_export_blueprint instead.
    """
    from .projects_export_blueprint import export_project as do_export_project
    return do_export_project()


@projects_bp.route("/api/projects/anc-export", methods=["POST"])
def anc_export_project():
    """
    Export the current project to AND (Austrian NeuroCloud) compatible format.
    DEPRECATED: Use the route in projects_export_blueprint instead.
    """
    from .projects_export_blueprint import anc_export_project as do_anc_export
    return do_anc_export()



# =============================================================================
# Session & Procedure Tracking Endpoints
# =============================================================================


@projects_bp.route("/api/projects/sessions", methods=["GET"])
def get_sessions():
    """Read Sessions + TaskDefinitions from project.json."""
    return handle_get_sessions(
        get_current_project=get_current_project,
        read_project_json=_read_project_json,
    )


@projects_bp.route("/api/projects/sessions", methods=["POST"])
def save_sessions():
    """Write Sessions + TaskDefinitions to project.json."""
    return handle_save_sessions(
        get_current_project=get_current_project,
        read_project_json=_read_project_json,
        write_project_json=_write_project_json,
        validate_recruitment_payload=_validate_recruitment_payload,
    )


@projects_bp.route("/api/projects/sessions/declared", methods=["GET"])
def get_sessions_declared():
    """Lightweight list of [{id, label}] for converter session picker."""
    return handle_get_sessions_declared(
        get_current_project=get_current_project,
        read_project_json=_read_project_json,
    )


@projects_bp.route("/api/projects/sessions/register", methods=["POST"])
def register_session():
    """Register a conversion result into a session in project.json.

    Expected JSON body:
    {
        "session_id": "ses-01",
        "tasks": ["panas", "bfi"],
        "modality": "survey",
        "source_file": "survey_baseline.xlsx",
        "converter": "survey-xlsx"
    }
    """
    return handle_register_session(
        get_current_project=get_current_project,
        read_project_json=_read_project_json,
        write_project_json=_write_project_json,
    )


@projects_bp.route("/api/projects/generate-methods", methods=["POST"])
def generate_methods_section():
    """Generate a publication-ready methods section from project.json metadata.

    Reads project.json, dataset_description.json, and referenced templates to
    produce a comprehensive scientific methods section in both Markdown and HTML.

    Expected JSON body:
    {
        "language": "en"  // "en" or "de"
    }
    """
    return handle_generate_methods_section(
        get_current_project=get_current_project,
        read_project_json=_read_project_json,
        get_bids_file_path=get_bids_file_path,
        compute_participant_stats=_compute_participant_stats,
    )


# =============================================================================
# Study Metadata & Methods Completeness
# =============================================================================


@projects_bp.route("/api/projects/study-metadata", methods=["GET"])
def get_study_metadata():
    """Read study-level editable sections from project.json with completeness info."""
    return handle_get_study_metadata(
        get_current_project=get_current_project,
        read_project_json=_read_project_json,
        get_bids_file_path=get_bids_file_path,
        editable_sections=_EDITABLE_SECTIONS,
        compute_methods_completeness=_compute_methods_completeness,
        auto_detect_study_hints=_auto_detect_study_hints,
    )


@projects_bp.route("/api/projects/study-metadata", methods=["POST"])
def save_study_metadata():
    """Save study-level editable sections to project.json, preserving other keys."""
    return handle_save_study_metadata(
        get_current_project=get_current_project,
        read_project_json=_read_project_json,
        write_project_json=_write_project_json,
        get_bids_file_path=get_bids_file_path,
        editable_sections=_EDITABLE_SECTIONS,
        compute_methods_completeness=_compute_methods_completeness,
    )


@projects_bp.route("/api/projects/procedure/status", methods=["GET"])
def get_procedure_status():
    """Completeness check: declared sessions/tasks vs. data on disk."""
    return handle_get_procedure_status(
        get_current_project=get_current_project,
        read_project_json=_read_project_json,
    )


@projects_bp.route("/api/projects/generate-readme", methods=["POST"])
def generate_readme():
    """Generate README.md from project.json study metadata."""
    return handle_generate_readme(get_current_project=get_current_project)


@projects_bp.route("/api/projects/preview-readme", methods=["GET"])
def preview_readme():
    """Preview README.md content without saving."""
    return handle_preview_readme(get_current_project=get_current_project)
