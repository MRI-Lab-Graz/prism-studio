import os
import sys
import json
import io
import re
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
from src.system_files import filter_system_files
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

try:
    from .tools_prism_app_runner_handlers import (
        handle_prism_app_runner,
        handle_api_prism_app_runner_compatibility,
        handle_api_prism_app_runner_delete_profile,
        handle_api_prism_app_runner_docker_pull,
        handle_api_prism_app_runner_docker_tags,
        handle_api_prism_app_runner_get_profile,
        handle_api_prism_app_runner_help,
        handle_api_prism_app_runner_list_profiles,
        handle_api_prism_app_runner_run,
        handle_api_prism_app_runner_scan_images,
        handle_api_prism_app_runner_save_profile,
    )

    _PRISM_APP_RUNNER_AVAILABLE = True
    _PRISM_APP_RUNNER_IMPORT_ERROR = None
except Exception as e:
    _PRISM_APP_RUNNER_AVAILABLE = False
    _PRISM_APP_RUNNER_IMPORT_ERROR = str(e)

    def handle_prism_app_runner(project_path: str | None):
        return (
            jsonify(
                {
                    "error": "PRISM App Runner is unavailable in this build.",
                    "details": _PRISM_APP_RUNNER_IMPORT_ERROR,
                }
            ),
            503,
        )

    def handle_api_prism_app_runner_compatibility(data: dict):
        return (
            jsonify(
                {
                    "error": "PRISM App Runner API is unavailable in this build.",
                    "details": _PRISM_APP_RUNNER_IMPORT_ERROR,
                }
            ),
            503,
        )

    def handle_api_prism_app_runner_delete_profile(
        project_path: str | None, profile_name: str
    ):
        return (
            jsonify(
                {
                    "error": "PRISM App Runner API is unavailable in this build.",
                    "details": _PRISM_APP_RUNNER_IMPORT_ERROR,
                }
            ),
            503,
        )

    def handle_api_prism_app_runner_docker_pull(data: dict):
        return (
            jsonify(
                {
                    "error": "PRISM App Runner API is unavailable in this build.",
                    "details": _PRISM_APP_RUNNER_IMPORT_ERROR,
                }
            ),
            503,
        )

    def handle_api_prism_app_runner_docker_tags(data: dict):
        return (
            jsonify(
                {
                    "error": "PRISM App Runner API is unavailable in this build.",
                    "details": _PRISM_APP_RUNNER_IMPORT_ERROR,
                }
            ),
            503,
        )

    def handle_api_prism_app_runner_get_profile(
        project_path: str | None, profile_name: str
    ):
        return (
            jsonify(
                {
                    "error": "PRISM App Runner API is unavailable in this build.",
                    "details": _PRISM_APP_RUNNER_IMPORT_ERROR,
                }
            ),
            503,
        )

    def handle_api_prism_app_runner_help(data: dict):
        return (
            jsonify(
                {
                    "error": "PRISM App Runner API is unavailable in this build.",
                    "details": _PRISM_APP_RUNNER_IMPORT_ERROR,
                }
            ),
            503,
        )

    def handle_api_prism_app_runner_list_profiles(project_path: str | None):
        return (
            jsonify(
                {
                    "error": "PRISM App Runner API is unavailable in this build.",
                    "details": _PRISM_APP_RUNNER_IMPORT_ERROR,
                }
            ),
            503,
        )

    def handle_api_prism_app_runner_run(data: dict, project_path: str | None):
        return (
            jsonify(
                {
                    "error": "PRISM App Runner API is unavailable in this build.",
                    "details": _PRISM_APP_RUNNER_IMPORT_ERROR,
                }
            ),
            503,
        )

    def handle_api_prism_app_runner_scan_images(data: dict):
        return (
            jsonify(
                {
                    "error": "PRISM App Runner API is unavailable in this build.",
                    "details": _PRISM_APP_RUNNER_IMPORT_ERROR,
                }
            ),
            503,
        )

    def handle_api_prism_app_runner_save_profile(data: dict, project_path: str | None):
        return (
            jsonify(
                {
                    "error": "PRISM App Runner API is unavailable in this build.",
                    "details": _PRISM_APP_RUNNER_IMPORT_ERROR,
                }
            ),
            503,
        )


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


def _load_wide_to_long_request():
    """Parse request payload and return upload bytes plus wide-to-long options."""
    upload = request.files.get("data")
    if upload is None or not upload.filename:
        return (
            None,
            None,
            None,
            None,
            None,
            None,
            None,
            (jsonify({"error": "Please upload a file."}), 400),
        )

    filtered = filter_system_files([upload.filename])
    if not filtered:
        return (
            None,
            None,
            None,
            None,
            None,
            None,
            None,
            (
                jsonify({"error": "System files are not accepted."}),
                400,
            ),
        )

    filename = filtered[0]
    suffix = Path(filename).suffix.lower()
    if suffix not in {".csv", ".tsv", ".xlsx"}:
        return (
            None,
            None,
            None,
            None,
            None,
            None,
            None,
            (
                jsonify({"error": "Supported formats: .csv, .tsv, .xlsx"}),
                400,
            ),
        )

    session_col_name = (request.form.get("session_column") or "session").strip()
    if not session_col_name:
        session_col_name = "session"

    raw_indicators = (
        request.form.get("session_indicators")
        or request.form.get("session_prefixes")
        or ""
    ).strip()

    raw_session_value_map = (request.form.get("session_value_map") or "").strip()

    try:
        payload = upload.read()
    except Exception as exc:
        return (
            None,
            None,
            None,
            None,
            None,
            None,
            None,
            (
                jsonify({"error": f"Could not parse input file: {exc}"}),
                400,
            ),
        )

    raw_limit = (request.form.get("preview_limit") or "8").strip()
    try:
        preview_limit = int(raw_limit)
    except ValueError:
        preview_limit = 8
    preview_limit = max(1, min(preview_limit, 50))

    return (
        filename,
        suffix,
        payload,
        session_col_name,
        raw_indicators,
        raw_session_value_map,
        preview_limit,
        None,
    )


def _run_wide_to_long_backend_command(
    *,
    filename: str,
    suffix: str,
    payload: bytes,
    session_column_name: str,
    raw_indicators: str,
    raw_session_value_map: str,
    preview_limit: int,
    inspect_only: bool,
):
    """Execute prism.py wide-to-long and return structured JSON plus output bytes."""
    repo_root = Path(__file__).resolve().parents[4]

    with tempfile.TemporaryDirectory(prefix="prism_wide_to_long_") as tmpdir:
        temp_root = Path(tmpdir)
        input_path = temp_root / f"input{suffix}"
        input_path.write_bytes(payload)

        command = [
            sys.executable,
            "prism.py",
            "wide-to-long",
            "--input",
            str(input_path),
            "--session-column",
            session_column_name,
            "--preview-limit",
            str(preview_limit),
            "--json",
        ]
        if raw_indicators:
            command.extend(["--session-indicators", raw_indicators])
        if raw_session_value_map:
            command.extend(["--session-map", raw_session_value_map])

        output_path = None
        if inspect_only:
            command.append("--inspect-only")
        else:
            output_path = temp_root / "wide_to_long_output.csv"
            command.extend(["--output", str(output_path)])

        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            cwd=str(repo_root),
        )

        stdout = (result.stdout or "").strip()
        stderr = (result.stderr or "").strip()
        response_payload = None
        if stdout:
            try:
                response_payload = json.loads(stdout)
            except json.JSONDecodeError:
                response_payload = None

        if result.returncode != 0:
            message = None
            if isinstance(response_payload, dict) and response_payload.get("error"):
                message = str(response_payload.get("error"))
            elif stderr:
                message = stderr
            elif stdout:
                message = stdout
            else:
                message = "Wide-to-long backend command failed."
            return None, None, (jsonify({"error": message}), 400)

        if not isinstance(response_payload, dict):
            return (
                None,
                None,
                (
                    jsonify(
                        {"error": "Wide-to-long backend command returned invalid JSON."}
                    ),
                    500,
                ),
            )

        response_payload["filename"] = filename
        output_bytes = output_path.read_bytes() if output_path is not None else None
        return response_payload, output_bytes, None


@tools_bp.route("/api/file-management/wide-to-long-preview", methods=["POST"])
def api_file_management_wide_to_long_preview():
    """Return a preview of converted wide-to-long output rows."""
    (
        filename,
        suffix,
        payload,
        session_col_name,
        raw_indicators,
        raw_session_value_map,
        preview_limit,
        error_response,
    ) = _load_wide_to_long_request()
    if error_response is not None:
        return error_response

    response_payload, _, command_error = _run_wide_to_long_backend_command(
        filename=filename,
        suffix=suffix,
        payload=payload,
        session_column_name=session_col_name,
        raw_indicators=raw_indicators,
        raw_session_value_map=raw_session_value_map,
        preview_limit=preview_limit,
        inspect_only=True,
    )
    if command_error is not None:
        return command_error

    return jsonify(response_payload)


@tools_bp.route("/api/file-management/wide-to-long", methods=["POST"])
def api_file_management_wide_to_long():
    """Convert a wide-format CSV/TSV/XLSX table into long format by session indicator."""
    (
        filename,
        suffix,
        payload,
        session_col_name,
        raw_indicators,
        raw_session_value_map,
        preview_limit,
        error_response,
    ) = _load_wide_to_long_request()
    if error_response is not None:
        return error_response

    _, output_bytes, command_error = _run_wide_to_long_backend_command(
        filename=filename,
        suffix=suffix,
        payload=payload,
        session_column_name=session_col_name,
        raw_indicators=raw_indicators,
        raw_session_value_map=raw_session_value_map,
        preview_limit=preview_limit,
        inspect_only=False,
    )
    if command_error is not None:
        return command_error

    output_name = f"{Path(filename).stem}_long.csv"

    return send_file(
        io.BytesIO(output_bytes or b""),
        mimetype="text/csv",
        as_attachment=True,
        download_name=output_name,
    )


@tools_bp.route("/recipes")
def recipes():
    project = get_current_project()
    return handle_recipes(project_path=(project.get("path") or "").strip())


@tools_bp.route("/prism-app-runner")
def prism_app_runner():
    project = get_current_project()
    return handle_prism_app_runner(project_path=(project.get("path") or "").strip())


@tools_bp.route("/api/recipes-surveys", methods=["POST"])
def api_recipes_surveys():
    """Run survey-recipes generation inside an existing PRISM dataset."""
    return handle_api_recipes_surveys(data=request.get_json(silent=True) or {})


@tools_bp.route("/api/prism-app-runner/compatibility", methods=["POST"])
def api_prism_app_runner_compatibility():
    """Assess compatibility for integrating bids_apps_runner in derivatives."""
    return handle_api_prism_app_runner_compatibility(
        data=request.get_json(silent=True) or {}
    )


@tools_bp.route("/api/prism-app-runner/run", methods=["POST"])
def api_prism_app_runner_run():
    """Prepare and execute bids_apps_runner against the active PRISM project."""
    project = get_current_project()
    return handle_api_prism_app_runner_run(
        data=request.get_json(silent=True) or {},
        project_path=(project.get("path") or "").strip(),
    )


@tools_bp.route("/api/prism-app-runner/scan-images", methods=["POST"])
def api_prism_app_runner_scan_images():
    """Scan local folder for Apptainer/Singularity images."""
    return handle_api_prism_app_runner_scan_images(
        data=request.get_json(silent=True) or {}
    )


@tools_bp.route("/api/prism-app-runner/load-help", methods=["POST"])
def api_prism_app_runner_load_help():
    """Load container help/options from selected image."""
    return handle_api_prism_app_runner_help(data=request.get_json(silent=True) or {})


@tools_bp.route("/api/prism-app-runner/docker-tags", methods=["POST"])
def api_prism_app_runner_docker_tags():
    """List tags from Docker Hub for a repository."""
    return handle_api_prism_app_runner_docker_tags(
        data=request.get_json(silent=True) or {}
    )


@tools_bp.route("/api/prism-app-runner/docker-pull", methods=["POST"])
def api_prism_app_runner_docker_pull():
    """Pull a Docker image locally."""
    return handle_api_prism_app_runner_docker_pull(
        data=request.get_json(silent=True) or {}
    )


@tools_bp.route("/api/prism-app-runner/remote-profiles", methods=["GET"])
def api_prism_app_runner_list_profiles():
    """List saved remote SSH profiles for current PRISM project."""
    project = get_current_project()
    return handle_api_prism_app_runner_list_profiles(
        project_path=(project.get("path") or "").strip(),
    )


@tools_bp.route("/api/prism-app-runner/remote-profiles", methods=["POST"])
def api_prism_app_runner_save_profile():
    """Save remote SSH profile for current PRISM project."""
    project = get_current_project()
    return handle_api_prism_app_runner_save_profile(
        data=request.get_json(silent=True) or {},
        project_path=(project.get("path") or "").strip(),
    )


@tools_bp.route("/api/prism-app-runner/remote-profiles/<profile_name>", methods=["GET"])
def api_prism_app_runner_get_profile(profile_name):
    """Get one saved remote SSH profile by name."""
    project = get_current_project()
    return handle_api_prism_app_runner_get_profile(
        project_path=(project.get("path") or "").strip(),
        profile_name=profile_name,
    )


@tools_bp.route(
    "/api/prism-app-runner/remote-profiles/<profile_name>", methods=["DELETE"]
)
def api_prism_app_runner_delete_profile(profile_name):
    """Delete one saved remote SSH profile by name."""
    project = get_current_project()
    return handle_api_prism_app_runner_delete_profile(
        project_path=(project.get("path") or "").strip(),
        profile_name=profile_name,
    )


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
