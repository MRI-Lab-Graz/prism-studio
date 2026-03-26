import os
import sys
import json
import io
import re
import tempfile
from pathlib import Path
from typing import cast
import pandas as pd
from flask import (
    Blueprint,
    render_template,
    request,
    jsonify,
    send_file,
    session,
)
from src.config import load_config
from src.constants import DEFAULT_BIDS_VERSION
from src.cross_platform import normalize_path
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
from src.converters.wide_to_long import (
    detect_wide_session_prefixes,
    inspect_wide_to_long_columns,
    convert_wide_to_long_dataframe,
)

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


@tools_bp.route("/api/config", methods=["GET"])
def api_config():
    """Return global frontend configuration constants."""
    return jsonify({"BIDSVersion": DEFAULT_BIDS_VERSION})


@tools_bp.route("/api/tools/parse-session-map", methods=["GET"])
def api_parse_session_map():
    """Parse a session map string into valid and invalid pairs.

    Query param ``map`` accepts entries separated by ``,`` or ``;``.
    Each entry must be ``source:target`` or ``source=target``.
    Returns ``{parsed: [[source, target], ...], invalid: [...]}``,
    mirroring the JS parseSessionMap return shape so the preview can
    delegate to this canonical backend implementation.
    """
    raw = request.args.get("map", "")
    parsed: list[list[str]] = []
    invalid: list[str] = []
    for item in raw.replace(";", ",").split(","):
        token = item.strip()
        if not token:
            continue
        if ":" in token:
            left, right = token.split(":", 1)
        elif "=" in token:
            left, right = token.split("=", 1)
        else:
            invalid.append(token)
            continue
        source = left.strip()
        target = right.strip()
        if not source or not target:
            invalid.append(token)
            continue
        parsed.append([source, target])
    return jsonify({"parsed": parsed, "invalid": invalid})


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


def _parse_json_payload(text: str):
    """Lenient JSON parser for noisy backend stdout."""
    if not isinstance(text, str):
        return None

    raw = text.strip()
    if not raw:
        return None

    # Try normal JSON first
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        pass

    # Try to extract JSON object substring if there is noise around it
    obj_start = raw.find("{")
    obj_end = raw.rfind("}")
    if obj_start != -1 and obj_end != -1 and obj_end > obj_start:
        try:
            return json.loads(raw[obj_start : obj_end + 1])
        except json.JSONDecodeError:
            pass

    # Try array payload if backend output is list-like
    arr_start = raw.find("[")
    arr_end = raw.rfind("]")
    if arr_start != -1 and arr_end != -1 and arr_end > arr_start:
        try:
            parsed = json.loads(raw[arr_start : arr_end + 1])
            if isinstance(parsed, dict):
                return parsed
            return {"items": parsed}
        except json.JSONDecodeError:
            pass

    return None


def _parse_session_indicators(raw_value: str | None) -> list[str]:
    return [item.strip() for item in str(raw_value or "").split(",") if item.strip()]


def _parse_session_value_map(raw_value: str | None) -> dict[str, str]:
    mapping_text = str(raw_value or "").strip()
    if not mapping_text:
        return {}

    session_value_map: dict[str, str] = {}
    entries = [
        item.strip()
        for item in mapping_text.replace(";", ",").split(",")
        if item.strip()
    ]
    for entry in entries:
        if ":" in entry:
            left, right = entry.split(":", 1)
        elif "=" in entry:
            left, right = entry.split("=", 1)
        else:
            raise ValueError(
                "Invalid session map format. Use entries like T1_:pre,T2_:post or T1_=1,T2_=2."
            )

        source = left.strip()
        target = right.strip()
        if not source or not target:
            raise ValueError(
                "Invalid session map format. Empty source/target values are not allowed."
            )
        session_value_map[source] = target

    return session_value_map


def _read_wide_to_long_input(input_path: Path, sheet: str | int = 0) -> pd.DataFrame:
    suffix = input_path.suffix.lower()
    from src.converters.file_reader import read_tabular_file

    if suffix in {".csv", ".tsv", ".xlsx"}:
        kind = "xlsx" if suffix == ".xlsx" else suffix.lstrip(".")
        return read_tabular_file(input_path, kind=kind, sheet=sheet).df
    raise ValueError("Supported formats: .csv, .tsv, .xlsx")


def _wide_to_long_indicator_counts(
    plan: dict[str, object], indicators: list[str]
) -> dict[str, int]:
    indicator_upper_to_cols = plan.get("indicator_upper_to_cols") or {}
    if not isinstance(indicator_upper_to_cols, dict):
        return {indicator: 0 for indicator in indicators}

    counts: dict[str, int] = {}
    for indicator in indicators:
        value = indicator_upper_to_cols.get(str(indicator).upper(), [])
        counts[indicator] = len(value) if isinstance(value, list) else 0
    return counts


def _wide_to_long_json_payload(
    *,
    input_path: Path,
    indicators: list[str],
    plan: dict[str, object],
    preview_limit: int,
    long_df: pd.DataFrame | None = None,
    output_path: Path | None = None,
    error: str | None = None,
) -> dict[str, object]:
    matched_columns = list(cast(list, plan.get("matched_columns") or []))
    ambiguous_columns = list(cast(list, plan.get("ambiguous_columns") or []))
    shared_columns = list(cast(list, plan.get("shared_columns") or []))

    payload: dict[str, object] = {
        "filename": input_path.name,
        "input_path": normalize_path(input_path),
        "detected_indicators": indicators,
        "detected_prefixes": indicators,
        "indicator_counts": _wide_to_long_indicator_counts(plan, indicators),
        "matched_columns": len(matched_columns),
        "ambiguous_columns": ambiguous_columns,
        "shared_columns": len(shared_columns),
        "can_convert": not bool(ambiguous_columns),
        "column_rename_preview": matched_columns[:preview_limit],
        "rows_total": 0,
        "rows_shown": 0,
        "columns": [],
        "rows": [],
    }

    if long_df is not None:
        preview_df = long_df.head(preview_limit).fillna("").astype(str)
        payload.update(
            {
                "rows_total": int(len(long_df)),
                "rows_shown": int(len(preview_df)),
                "columns": list(preview_df.columns),
                "rows": preview_df.to_dict(orient="records"),
            }
        )

    if output_path is not None:
        payload["output_path"] = normalize_path(output_path)

    if error:
        payload["error"] = error

    return payload


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
    """Execute wide-to-long backend logic in-process and return JSON plus output bytes."""

    with tempfile.TemporaryDirectory(prefix="prism_wide_to_long_") as tmpdir:
        temp_root = Path(tmpdir)
        input_path = temp_root / f"input{suffix}"
        input_path.write_bytes(payload)

        try:
            df = _read_wide_to_long_input(input_path, sheet=0)
            indicators = _parse_session_indicators(raw_indicators)
            indicators = indicators or detect_wide_session_prefixes(
                list(df.columns), min_count=2
            )
            if not indicators:
                raise ValueError(
                    "No session-coded columns detected. Provide --session-indicators like T1_,T2_,T3_ "
                    "or leave it empty only when the file uses detectable prefixes."
                )

            session_value_map = _parse_session_value_map(raw_session_value_map)
            plan = inspect_wide_to_long_columns(
                list(df.columns), session_indicators=indicators
            )
            can_convert = not bool(plan.get("ambiguous_columns"))

            output_path = None
            long_df = None
            if inspect_only:
                if can_convert:
                    long_df = convert_wide_to_long_dataframe(
                        df,
                        session_indicators=indicators,
                        session_column_name=session_column_name,
                        session_value_map=session_value_map,
                    )
            else:
                if not can_convert:
                    message = "Ambiguous session indicator matches found. Use a more specific indicator."
                    return None, None, (jsonify({"error": message}), 400)

                output_path = temp_root / "wide_to_long_output.csv"
                long_df = convert_wide_to_long_dataframe(
                    df,
                    session_indicators=indicators,
                    session_column_name=session_column_name,
                    session_value_map=session_value_map,
                )
                long_df.to_csv(output_path, index=False)

            response_payload = _wide_to_long_json_payload(
                input_path=input_path,
                indicators=indicators,
                plan=plan,
                preview_limit=preview_limit,
                long_df=long_df,
                output_path=output_path,
            )
            response_payload["filename"] = filename
            output_bytes = output_path.read_bytes() if output_path is not None else None
            return response_payload, output_bytes, None
        except ValueError as exc:
            return None, None, (jsonify({"error": str(exc)}), 400)
        except Exception as exc:
            return (
                None,
                None,
                (
                    jsonify({"error": f"Wide-to-long backend command failed: {exc}"}),
                    400,
                ),
            )


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
