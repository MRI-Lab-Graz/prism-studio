import shutil
import tempfile
import zipfile
from pathlib import Path

from flask import current_app, jsonify, request, session
from werkzeug.utils import secure_filename

try:
    import defusedxml.ElementTree as ET
except ImportError:
    import xml.etree.ElementTree as ET

from src.web.survey_utils import list_survey_template_languages
from src.web.validation import run_validation


def handle_api_survey_languages(participant_json_candidates):
    """List available languages for the selected survey template library folder."""
    library_path = (request.args.get("library_path") or "").strip()
    base_dir = Path(current_app.root_path)

    if not library_path:
        project_path = (session.get("current_project_path") or "").strip()
        if project_path:
            candidate = Path(project_path) / "code" / "library"
            try:
                candidate = candidate.expanduser().resolve()
            except (OSError, ValueError):
                candidate = Path(project_path).resolve() / "code" / "library"

            if candidate.exists() and candidate.is_dir():
                library_path = str(candidate)
            else:
                candidate = Path(project_path) / "library"
                try:
                    candidate = candidate.expanduser().resolve()
                except (OSError, ValueError):
                    candidate = Path(project_path).resolve() / "library"

                if candidate.exists() and candidate.is_dir():
                    library_path = str(candidate)

    if not library_path:
        candidates = [
            base_dir / "library" / "survey_i18n",
            base_dir / "official" / "library",
            base_dir.parent / "official" / "library",
            base_dir / "survey_library",
        ]

        for candidate_path in candidates:
            try:
                candidate_path = candidate_path.resolve()
                if candidate_path.exists() and (
                    any(candidate_path.glob("survey-*.json"))
                    or any(candidate_path.glob("*/survey-*.json"))
                ):
                    library_path = str(candidate_path)
                    break
            except (OSError, ValueError):
                continue

        if not library_path:
            library_path = str((base_dir / "survey_library").resolve())

    try:
        library_root = Path(library_path).resolve()
    except (OSError, ValueError):
        library_root = Path(library_path)

    structure_info = {
        "has_survey_folder": False,
        "has_biometrics_folder": False,
        "has_participants_json": False,
        "missing_items": [],
    }

    survey_dir = None
    for survey_candidate in [
        library_root / "library" / "survey",
        library_root / "survey",
        library_root,
    ]:
        if survey_candidate.exists() and survey_candidate.is_dir():
            if any(survey_candidate.glob("survey-*.json")):
                survey_dir = survey_candidate
                break

    if not survey_dir:
        survey_dir = library_root / "survey"

    biometrics_dir = None
    for biometrics_candidate in [
        library_root / "library" / "biometrics",
        library_root / "biometrics",
    ]:
        if biometrics_candidate.exists() and biometrics_candidate.is_dir():
            biometrics_dir = biometrics_candidate
            break

    if not biometrics_dir:
        biometrics_dir = library_root / "biometrics"

    participant_candidates = participant_json_candidates(library_root)

    structure_info["has_survey_folder"] = survey_dir.is_dir()
    structure_info["has_biometrics_folder"] = biometrics_dir.is_dir()
    structure_info["has_participants_json"] = any(
        candidate.is_file() for candidate in participant_candidates
    )

    if not structure_info["has_survey_folder"]:
        structure_info["missing_items"].append("survey/")
    if not structure_info["has_participants_json"]:
        structure_info["missing_items"].append(
            "participants.json (or ../participants.json)"
        )

    if survey_dir.is_dir():
        effective_survey_dir = str(survey_dir)
    else:
        effective_survey_dir = library_path

    print("[PRISM DEBUG] /api/survey-languages resolved library:")
    print(f"  - library_path: {library_path}")
    print(f"  - survey_dir: {survey_dir}")
    print(f"  - effective_survey_dir: {effective_survey_dir}")
    if survey_dir.is_dir():
        try:
            surveys = list(survey_dir.glob("survey-*.json"))
            print(f"  - found {len(surveys)} survey templates")
        except Exception as error:
            print(f"  - error listing surveys: {error}")

    langs, default, template_count, i18n_count = list_survey_template_languages(
        effective_survey_dir
    )
    return jsonify(
        {
            "languages": langs,
            "default": default,
            "library_path": effective_survey_dir,
            "template_count": template_count,
            "i18n_count": i18n_count,
            "structure": structure_info,
        }
    )


def handle_api_survey_convert_preview(
    *,
    convert_survey_xlsx_to_prism_dataset,
    convert_survey_lsa_to_prism_dataset,
    resolve_effective_library_path,
    run_survey_with_official_fallback,
    format_unmatched_groups_response,
    id_column_not_detected_error_cls,
    unmatched_groups_error_cls,
):
    """Run a dry-run conversion to preview what will be created without writing files."""
    if (
        not convert_survey_xlsx_to_prism_dataset
        and not convert_survey_lsa_to_prism_dataset
    ):
        return jsonify({"error": "Survey conversion module not available"}), 500

    uploaded_file = request.files.get("excel") or request.files.get("file")
    alias_upload = request.files.get("alias") or request.files.get("alias_file")
    id_map_upload = request.files.get("id_map")

    if not uploaded_file or not getattr(uploaded_file, "filename", ""):
        return jsonify({"error": "Missing input file"}), 400

    filename = secure_filename(uploaded_file.filename)
    suffix = Path(filename).suffix.lower()
    if suffix not in {".xlsx", ".lsa", ".csv", ".tsv"}:
        return jsonify({"error": "Supported formats: .xlsx, .lsa, .csv, .tsv"}), 400

    alias_filename = None
    if alias_upload and getattr(alias_upload, "filename", ""):
        alias_filename = secure_filename(alias_upload.filename)
        alias_suffix = Path(alias_filename).suffix.lower()
        if alias_suffix and alias_suffix not in {".tsv", ".txt"}:
            return (
                jsonify({"error": "Alias file must be a .tsv or .txt mapping file"}),
                400,
            )

    id_map_filename = None
    if id_map_upload and getattr(id_map_upload, "filename", ""):
        id_map_filename = secure_filename(id_map_upload.filename)
        id_map_suffix = Path(id_map_filename).suffix.lower()
        if id_map_suffix and id_map_suffix not in {".tsv", ".txt", ".csv"}:
            return (
                jsonify({"error": "ID map file must be a .tsv, .csv, or .txt file"}),
                400,
            )

    try:
        library_path = resolve_effective_library_path()
    except FileNotFoundError as error:
        return jsonify({"error": str(error)}), 400

    if (library_path / "survey").is_dir():
        survey_dir = library_path / "survey"
    else:
        survey_dir = library_path

    effective_survey_dir = survey_dir

    print(f"[PRISM DEBUG] DRY-RUN Preview using library: {effective_survey_dir}")
    print(f"[PRISM DEBUG] Session project path: {session.get('current_project_path')}")
    print(
        f"[PRISM DEBUG] Available templates: {list(effective_survey_dir.glob('survey-*.json'))}"
    )

    survey_templates = list(effective_survey_dir.glob("survey-*.json"))
    if not survey_templates:
        return (
            jsonify({"error": f"No survey templates found in: {effective_survey_dir}"}),
            400,
        )

    survey_filter = (request.form.get("survey") or "").strip() or None
    id_column = (request.form.get("id_column") or "").strip() or None
    session_column = (request.form.get("session_column") or "").strip() or None
    session_override = (request.form.get("session") or "").strip() or None
    sheet = (request.form.get("sheet") or "0").strip() or 0
    unknown = (request.form.get("unknown") or "warn").strip() or "warn"
    language = (request.form.get("language") or "").strip() or None
    strict_levels_raw = (request.form.get("strict_levels") or "").strip().lower()
    strict_levels = strict_levels_raw in {"1", "true", "yes", "on"}
    validate_raw = (request.form.get("validate") or "").strip().lower()
    validate_preview = (
        True if validate_raw == "" else validate_raw in {"1", "true", "yes", "on"}
    )
    duplicate_handling = (request.form.get("duplicate_handling") or "error").strip()
    if duplicate_handling not in {"error", "keep_first", "keep_last", "sessions"}:
        duplicate_handling = "error"

    tmp_dir = tempfile.mkdtemp(prefix="prism_survey_preview_")
    try:
        tmp_dir_path = Path(tmp_dir)
        input_path = tmp_dir_path / filename
        uploaded_file.save(str(input_path))

        alias_path = None
        if alias_filename:
            alias_path = tmp_dir_path / alias_filename
            alias_upload.save(str(alias_path))

        id_map_path = None
        if id_map_filename:
            id_map_path = tmp_dir_path / id_map_filename
            id_map_upload.save(str(id_map_path))

        project_path = session.get("current_project_path")
        if project_path:
            project_path = Path(project_path)
            if project_path.is_file():
                project_path = project_path.parent

            mapping_candidates = [
                project_path / "participants_mapping.json",
                project_path / "code" / "participants_mapping.json",
                project_path / "code" / "library" / "participants_mapping.json",
                project_path
                / "code"
                / "library"
                / "survey"
                / "participants_mapping.json",
            ]

            for mapping_file in mapping_candidates:
                if mapping_file.exists():
                    dest_mapping = tmp_dir_path / "code" / "participants_mapping.json"
                    dest_mapping.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(mapping_file, dest_mapping)
                    print(
                        f"[PRISM DEBUG] Using participants mapping from: {mapping_file}"
                    )
                    break

        output_root = tmp_dir_path / "rawdata"

        if suffix in {".xlsx", ".csv", ".tsv"}:
            result = run_survey_with_official_fallback(
                convert_survey_xlsx_to_prism_dataset,
                input_path=input_path,
                library_dir=str(effective_survey_dir),
                output_root=output_root,
                survey=survey_filter,
                id_column=id_column,
                session_column=session_column,
                session=session_override,
                sheet=sheet,
                unknown=unknown,
                dry_run=True,
                force=True,
                name="preview",
                authors=[],
                language=language,
                alias_file=alias_path,
                id_map_file=id_map_path,
                duplicate_handling=duplicate_handling,
                skip_participants=True,
                fallback_project_path=str(project_path) if project_path else None,
            )
        elif suffix == ".lsa":
            result = run_survey_with_official_fallback(
                convert_survey_lsa_to_prism_dataset,
                input_path=input_path,
                library_dir=str(effective_survey_dir),
                output_root=output_root,
                survey=survey_filter,
                id_column=id_column,
                session_column=session_column,
                session=session_override,
                unknown=unknown,
                dry_run=True,
                force=True,
                name="preview",
                authors=[],
                language=language,
                alias_file=alias_path,
                id_map_file=id_map_path,
                strict_levels=True if strict_levels else None,
                duplicate_handling=duplicate_handling,
                skip_participants=True,
                project_path=str(project_path) if project_path else None,
                fallback_project_path=str(project_path) if project_path else None,
            )
        else:
            return jsonify({"error": "Unsupported file format"}), 400

        validation_result = None
        if validate_preview:
            try:
                validate_root = tmp_dir_path / "rawdata_validate"
                validate_root.mkdir(parents=True, exist_ok=True)

                if suffix in {".xlsx", ".csv", ".tsv"}:
                    run_survey_with_official_fallback(
                        convert_survey_xlsx_to_prism_dataset,
                        input_path=input_path,
                        library_dir=str(effective_survey_dir),
                        output_root=validate_root,
                        survey=survey_filter,
                        id_column=id_column,
                        session_column=session_column,
                        session=session_override,
                        sheet=sheet,
                        unknown=unknown,
                        dry_run=False,
                        force=True,
                        name="preview",
                        authors=[],
                        language=language,
                        alias_file=alias_path,
                        id_map_file=id_map_path,
                        duplicate_handling=duplicate_handling,
                        skip_participants=True,
                        fallback_project_path=(
                            str(project_path) if project_path else None
                        ),
                    )
                elif suffix == ".lsa":
                    run_survey_with_official_fallback(
                        convert_survey_lsa_to_prism_dataset,
                        input_path=input_path,
                        library_dir=str(effective_survey_dir),
                        output_root=validate_root,
                        survey=survey_filter,
                        id_column=id_column,
                        session_column=session_column,
                        session=session_override,
                        unknown=unknown,
                        dry_run=False,
                        force=True,
                        name="preview",
                        authors=[],
                        language=language,
                        alias_file=alias_path,
                        id_map_file=id_map_path,
                        strict_levels=True if strict_levels else None,
                        duplicate_handling=duplicate_handling,
                        skip_participants=True,
                        project_path=str(project_path) if project_path else None,
                        fallback_project_path=(
                            str(project_path) if project_path else None
                        ),
                    )

                v_res = run_validation(
                    str(validate_root),
                    schema_version="stable",
                    library_path=str(effective_survey_dir),
                )
                if v_res and isinstance(v_res, tuple):
                    issues, stats = v_res

                    from src.web.reporting_utils import format_validation_results

                    formatted = format_validation_results(
                        issues, stats, str(validate_root)
                    )

                    validation_result = {"formatted": formatted}
                    validation_result.update(formatted)
            except Exception as validation_error:
                validation_result = {"error": str(validation_error)}

        response_data = {
            "preview": result.dry_run_preview,
            "tasks_included": result.tasks_included,
            "unknown_columns": result.unknown_columns,
            "missing_items_by_task": result.missing_items_by_task,
            "id_column": result.id_column,
            "session_column": result.session_column,
            "detected_sessions": result.detected_sessions,
            "conversion_warnings": result.conversion_warnings,
            "task_runs": result.task_runs,
        }

        if validation_result is not None:
            response_data["validation"] = validation_result

        conv_summary = {}
        if result.tasks_included:
            conv_summary["tasks_included"] = result.tasks_included
        if result.task_runs:
            conv_summary["task_runs"] = result.task_runs
        if result.unknown_columns:
            conv_summary["unknown_columns"] = result.unknown_columns
        if getattr(result, "tool_columns", None):
            conv_summary["tool_columns"] = result.tool_columns
        if result.conversion_warnings:
            conv_summary["conversion_warnings"] = result.conversion_warnings

        if result.template_matches:
            response_data["template_matches"] = result.template_matches
            conv_summary["template_matches"] = result.template_matches

        if conv_summary:
            response_data["conversion_summary"] = conv_summary

        return jsonify(response_data)

    except Exception as error:
        if (
            isinstance(id_column_not_detected_error_cls, type)
            and issubclass(id_column_not_detected_error_cls, BaseException)
            and isinstance(error, id_column_not_detected_error_cls)
        ):
            return (
                jsonify(
                    {
                        "error": "id_column_required",
                        "message": str(error),
                        "columns": getattr(error, "available_columns", []),
                    }
                ),
                409,
            )

        if (
            isinstance(unmatched_groups_error_cls, type)
            and issubclass(unmatched_groups_error_cls, BaseException)
            and isinstance(error, unmatched_groups_error_cls)
        ):
            return jsonify(format_unmatched_groups_response(error)), 409

        if isinstance(error, zipfile.BadZipFile):
            return (
                jsonify(
                    {
                        "error": "❌ Invalid or corrupted archive file.\n\n"
                        "The .lsa file appears to be damaged or not a valid LimeSurvey Archive.\n\n"
                        "💡 Solutions:\n"
                        "   • Re-export the survey from LimeSurvey\n"
                        "   • Ensure the file was completely downloaded\n"
                        "   • Try uploading from a different location"
                    }
                ),
                400,
            )

        if isinstance(error, ET.ParseError):
            return (
                jsonify(
                    {
                        "error": f"❌ XML parsing error in LimeSurvey archive.\n\n"
                        f"The survey structure file (.lss) inside the archive is malformed.\n\n"
                        f"Technical details: {str(error)}\n\n"
                        f"💡 Solutions:\n"
                        f"   • Re-export the survey from LimeSurvey\n"
                        f"   • Check for special characters in question text that might cause XML issues"
                    }
                ),
                400,
            )

        error_msg = str(error)
        if "No module named" in error_msg:
            return (
                jsonify(
                    {
                        "error": "❌ Missing required Python module.\n\n"
                        f"{error_msg}\n\n"
                        "Please run setup or install required dependencies."
                    }
                ),
                500,
            )

        return jsonify({"error": error_msg}), 500

    finally:
        try:
            shutil.rmtree(tmp_dir)
        except Exception:
            pass