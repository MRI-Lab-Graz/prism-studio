import os
import sys
import json
import io
import tempfile
import subprocess
from pathlib import Path
from flask import (
    Blueprint,
    render_template,
    request,
    jsonify,
    send_file,
    session,
)
from src.config import load_config
from src.web.blueprints.projects import get_current_project
from .tools_helpers import (
    _default_library_root_for_templates,
    _safe_expand_path,
    _global_survey_library_root,
    _global_recipes_root,
    _resolve_library_root,
    _template_dir,
    _project_library_root,
    _project_template_folder,
    _load_prism_schema,
    _pick_enum_value,
    _schema_example,
    _deep_merge,
    _new_template_from_schema,
    _validate_against_schema,
    _strip_template_editor_internal_keys,
)
from .tools_survey_customizer_handlers import (
    get_survey_customizer_formats_payload,
    handle_survey_customizer_export,
    handle_survey_customizer_load,
)
from .tools_file_browser_handlers import (
    handle_api_browse_file,
    handle_api_browse_folder,
)
from .tools_library_handlers import (
    handle_get_library_template,
    handle_list_library_files,
    handle_list_library_files_merged,
)
from .tools_generation_handlers import (
    handle_detect_columns,
    handle_generate_boilerplate_endpoint,
    handle_generate_lss_endpoint,
)
from .tools_limesurvey_handlers import handle_limesurvey_to_prism
from .tools_post_conversion_handlers import (
    handle_fix_participants_bids,
    handle_limesurvey_save_to_project,
)
from .tools_recipes_surveys_handlers import handle_api_recipes_surveys
from .tools_template_info_helpers import (
    detect_languages_from_template as _detect_languages_from_template,
    extract_template_info as _extract_template_info,
)
from .tools_pages_handlers import (
    handle_api_recipes_sessions,
    handle_converter,
    handle_recipes,
)

tools_bp = Blueprint("tools", __name__)


@tools_bp.route("/survey-generator")
def survey_generator():
    """Survey generator page – library is auto-loaded via the merged API."""
    return render_template("survey_generator.html")


@tools_bp.route("/survey-customizer")
def survey_customizer():
    """Survey customizer page for organizing questions before export"""
    return render_template("survey_customizer.html")


@tools_bp.route("/api/survey-customizer/load", methods=["POST"])
def api_survey_customizer_load():
    """Load selected templates and convert to customization groups.

    Expects JSON body:
    {
        "files": [
            {
                "path": "/path/to/survey.json",
                "includeQuestions": ["Q1", "Q2", ...],
                "matrix": true,
                "matrix_global": true,
                "runNumber": 1
            }
        ]
    }

    Returns customization groups ready for the customizer UI.
    """
    data = request.get_json(silent=True) or {}
    return handle_survey_customizer_load(
        data=data,
        detect_languages_from_template=_detect_languages_from_template,
    )


@tools_bp.route("/api/survey-customizer/export", methods=["POST"])
def api_survey_customizer_export():
    """Export survey with customization state applied.

    Expects JSON body with CustomizationState:
    {
        "survey": {"title": "...", "language": "en"},
        "groups": [...],
        "exportFormat": "limesurvey",
        "exportOptions": {"ls_version": "3", "matrix": true, "matrix_global": false}
    }
    """
    data = request.get_json(silent=True) or {}
    return handle_survey_customizer_export(
        data=data,
        project_path=session.get("current_project_path"),
    )


@tools_bp.route("/api/survey-customizer/formats", methods=["GET"])
def api_survey_customizer_formats():
    """List available export formats for the survey customizer."""
    return jsonify(get_survey_customizer_formats_payload())


@tools_bp.route("/converter")
def converter():
    """Converter page"""
    return handle_converter(project_path=session.get("current_project_path"))


@tools_bp.route("/file-management")
def file_management():
    """File Management tools page (Renamer and Organizer)"""
    return render_template("file_management.html")


@tools_bp.route("/recipes")
def recipes():
    project = get_current_project()
    return handle_recipes(project_path=(project.get("path") or "").strip())


@tools_bp.route("/api/recipes-surveys", methods=["POST"])
def api_recipes_surveys():
    """Run survey-recipes generation inside an existing PRISM dataset."""
    return handle_api_recipes_surveys(data=request.get_json(silent=True) or {})


@tools_bp.route("/api/browse-file")
def api_browse_file():
    """Open a system dialog to select a file (filtering for project.json)"""
    return handle_api_browse_file()


@tools_bp.route("/api/browse-folder")
def api_browse_folder():
    """Open a system dialog to select a folder"""
    return handle_api_browse_folder()


@tools_bp.route("/api/list-library-files-merged")
def list_library_files_merged():
    """List JSON files from BOTH global and project libraries, merged with source tags.

    No path parameter needed — auto-resolves global via settings and project via session.
    Templates from both sources appear as separate rows (both visible, not overriding).
    """
    return handle_list_library_files_merged(
        extract_template_info=_extract_template_info,
        global_survey_library_root=_global_survey_library_root,
    )


@tools_bp.route("/api/recipes-sessions", methods=["GET"])
def api_recipes_sessions():
    """List available session folders in a PRISM dataset."""
    return handle_api_recipes_sessions(
        dataset_path=(request.args.get("dataset_path") or "").strip()
    )


@tools_bp.route("/api/list-library-files")
def list_library_files():
    """List JSON files in a user-specified library path, grouped by modality"""
    return handle_list_library_files(
        extract_template_info=_extract_template_info,
    )


@tools_bp.route("/api/generate-lss", methods=["POST"])
def generate_lss_endpoint():
    """Generate LSS from selected JSON files"""
    return handle_generate_lss_endpoint()


@tools_bp.route("/api/generate-boilerplate", methods=["POST"])
def generate_boilerplate_endpoint():
    """Generate Methods Boilerplate from selected JSON files"""
    return handle_generate_boilerplate_endpoint()


@tools_bp.route("/api/detect-columns", methods=["POST"])
def detect_columns():
    """Detect column names from uploaded file for ID column selection.

    Supports .lsa, .xlsx, .csv, .tsv files.
    Returns list of columns and suggests likely ID column.
    """
    return handle_detect_columns()


@tools_bp.route("/api/limesurvey-to-prism", methods=["POST"])
def limesurvey_to_prism():
    """Convert LimeSurvey (.lss/.lsa) or Excel/CSV/TSV file to PRISM JSON sidecar(s).

    Supports three modes (via 'mode' parameter or legacy 'split_by_groups'):
    - mode=combined (default): Single combined JSON with all questions
    - mode=groups: Separate JSON per questionnaire group
    - mode=questions: Separate JSON per individual question (for template library)
    """
    return handle_limesurvey_to_prism()


@tools_bp.route("/api/library-template/<template_key>", methods=["GET"])
def get_library_template(template_key):
    """Fetch a library template by its key (task name).

    Checks both project-specific and global templates. Project templates
    take priority over global ones.

    Returns the full template JSON so the frontend can swap a generated
    template with the library version.
    """
    return handle_get_library_template(template_key)


@tools_bp.route("/api/limesurvey-save-to-project", methods=["POST"])
def limesurvey_save_to_project():
    """Save converted LimeSurvey JSON templates directly to project's library folder.

    Expects JSON body with:
    {
        "templates": [
            {"filename": "survey-name.json", "content": {...json object...}},
            ...
        ]
    }

    Templates are saved to: {project_path}/code/library/survey/
    """
    return handle_limesurvey_save_to_project(
        project_path=session.get("current_project_path"),
        data=request.get_json(),
    )


@tools_bp.route("/api/fix-participants-bids", methods=["POST"])
def fix_participants_bids():
    """
    Fix common BIDS compliance issues in participants.tsv:
    - Convert age/numeric columns from strings to numbers
    - Convert sex column from numeric codes (1,2,3) to BIDS values (M,F,O)
    """
    return handle_fix_participants_bids(data=request.get_json())
