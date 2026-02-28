"""Survey conversion handlers extracted from the conversion blueprint."""

import base64
import io
import shutil
import tempfile
import zipfile
from pathlib import Path
from typing import Any

from flask import current_app, jsonify, request, send_file, session
from werkzeug.utils import secure_filename

try:
    import defusedxml.ElementTree as ET
except ImportError:
    import xml.etree.ElementTree as ET

from src.web.reporting_utils import sanitize_jsonable
from src.web.validation import run_validation
from src.web.services.project_registration import register_session_in_project
from .conversion_survey_preview_handlers import (
    handle_api_survey_convert_preview,
    handle_api_survey_languages,
)

from .conversion_utils import (
    extract_tasks_from_output,
    log_file_head,
    normalize_filename,
    participant_json_candidates,
    resolve_effective_library_path,
    should_retry_with_official_library,
)

convert_survey_xlsx_to_prism_dataset: Any = None
convert_survey_lsa_to_prism_dataset: Any = None
infer_lsa_metadata: Any = None
MissingIdMappingError: Any = None
UnmatchedGroupsError: Any = None
_NON_ITEM_TOPLEVEL_KEYS: set[str] = set()

try:
    from src.converters.survey import (
        MissingIdMappingError,
        UnmatchedGroupsError,
        _NON_ITEM_TOPLEVEL_KEYS,
        convert_survey_lsa_to_prism_dataset,
        convert_survey_xlsx_to_prism_dataset,
        infer_lsa_metadata,
    )
except ImportError:
    pass

IdColumnNotDetectedError: Any = None
try:
    from src.converters.id_detection import IdColumnNotDetectedError
except ImportError:
    pass

_participant_json_candidates = participant_json_candidates
_log_file_head = log_file_head
_resolve_effective_library_path = resolve_effective_library_path
_normalize_filename = normalize_filename
_should_retry_with_official_library = should_retry_with_official_library
_extract_tasks_from_output = extract_tasks_from_output
_register_session_in_project = register_session_in_project


def _resolve_official_survey_dir(project_path: str | None) -> Path | None:
    candidates: list[Path] = []

    if project_path:
        project_root = Path(project_path).expanduser().resolve()
        if project_root.is_file():
            project_root = project_root.parent

        project_official = project_root / "official" / "library"
        candidates.extend([project_official / "survey", project_official])

    base_dir = Path(current_app.root_path).parent.resolve()
    candidates.append(base_dir / "official" / "library" / "survey")
    candidates.append(base_dir / "official" / "library")

    for candidate in candidates:
        if candidate.exists() and candidate.is_dir():
            if list(candidate.glob("survey-*.json")):
                return candidate
    return None


def _copy_official_templates_to_project(
    official_dir: Path,
    tasks: list[str],
    project_path: str | None,
    log_fn=None,
) -> None:
    if not project_path or not tasks:
        return
    project_root = Path(project_path).expanduser().resolve()
    if project_root.is_file():
        project_root = project_root.parent

    if (official_dir / "survey").is_dir() and not list(
        official_dir.glob("survey-*.json")
    ):
        official_dir = official_dir / "survey"

    dest_dir = project_root / "code" / "library" / "survey"
    dest_dir.mkdir(parents=True, exist_ok=True)

    copied = 0
    for task in tasks:
        src = official_dir / f"survey-{task}.json"
        dest = dest_dir / f"survey-{task}.json"
        if src.exists() and not dest.exists():
            shutil.copy2(src, dest)
            copied += 1

    if copied:
        msg = f"Copied {copied} official survey template(s) into project library."
        if log_fn:
            log_fn(msg, "info")
        else:
            print(f"[PRISM DEBUG] {msg}")


def _run_survey_with_official_fallback(
    converter_fn,
    *,
    library_dir: str | Path,
    fallback_project_path: str | None,
    log_fn=None,
    **kwargs,
):
    try:
        return converter_fn(library_dir=str(library_dir), **kwargs)
    except Exception as exc:
        if _should_retry_with_official_library(exc):
            official_dir = _resolve_official_survey_dir(fallback_project_path)
            if (
                official_dir
                and Path(official_dir).resolve() != Path(library_dir).resolve()
            ):
                msg = (
                    "No matches in project templates; retrying with official templates."
                )
                if log_fn:
                    log_fn(msg, "info")
                else:
                    print(f"[PRISM DEBUG] {msg}")
                result = converter_fn(library_dir=str(official_dir), **kwargs)
                if kwargs.get("dry_run"):
                    _copy_official_templates_to_project(
                        official_dir=official_dir,
                        tasks=getattr(result, "tasks_included", []),
                        project_path=fallback_project_path,
                        log_fn=log_fn,
                    )
                return result

            msg = "No matches in project templates and no official templates found to fall back to."
            if log_fn:
                log_fn(msg, "warning")
            else:
                print(f"[PRISM DEBUG] {msg}")
        raise


def _format_unmatched_groups_response(uge, log_messages=None):
    """Build the JSON response dict for an UnmatchedGroupsError."""

    def _safe_prism_json(value):
        if isinstance(value, dict):
            return value
        return {}

    payload = {
        "error": "unmatched_groups",
        "message": str(uge),
        "unmatched": [
            {
                "group_name": g["group_name"],
                "task_key": g["task_key"],
                "item_count": len(
                    [
                        k
                        for k in _safe_prism_json(g.get("prism_json"))
                        if k not in _NON_ITEM_TOPLEVEL_KEYS
                        and isinstance(
                            _safe_prism_json(g.get("prism_json")).get(k), dict
                        )
                    ]
                ),
                "item_codes": sorted(g.get("item_codes", []))[:10],
                "prism_json": _safe_prism_json(g.get("prism_json")),
            }
            for g in uge.unmatched
        ],
    }
    if log_messages is not None:
        payload["log"] = log_messages
    return payload


def api_survey_languages():
    return handle_api_survey_languages(
        participant_json_candidates=_participant_json_candidates,
    )


def api_survey_convert_preview():
    return handle_api_survey_convert_preview(
        convert_survey_xlsx_to_prism_dataset=convert_survey_xlsx_to_prism_dataset,
        convert_survey_lsa_to_prism_dataset=convert_survey_lsa_to_prism_dataset,
        resolve_effective_library_path=_resolve_effective_library_path,
        run_survey_with_official_fallback=_run_survey_with_official_fallback,
        format_unmatched_groups_response=_format_unmatched_groups_response,
        id_column_not_detected_error_cls=IdColumnNotDetectedError,
        unmatched_groups_error_cls=UnmatchedGroupsError,
    )


def api_survey_convert():
    """Run full survey conversion and return ZIP output."""
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
        if id_map_suffix and id_map_suffix not in {".tsv", ".csv", ".txt"}:
            return (
                jsonify({"error": "ID map file must be a .tsv, .csv, or .txt file"}),
                400,
            )

    try:
        library_path = _resolve_effective_library_path()
    except FileNotFoundError as e:
        return jsonify({"error": str(e)}), 400

    if (library_path / "survey").is_dir():
        survey_dir = library_path / "survey"
    else:
        survey_dir = library_path

    effective_survey_dir = survey_dir

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
    dataset_name = (request.form.get("dataset_name") or "").strip() or None
    language = (request.form.get("language") or "").strip() or None
    strict_levels_raw = (request.form.get("strict_levels") or "").strip().lower()
    strict_levels = strict_levels_raw in {"1", "true", "yes", "on"}
    save_to_project = request.form.get("save_to_project") == "true"
    archive_sourcedata = request.form.get("archive_sourcedata") == "true"
    duplicate_handling = (request.form.get("duplicate_handling") or "error").strip()
    if duplicate_handling not in {"error", "keep_first", "keep_last", "sessions"}:
        duplicate_handling = "error"

    tmp_dir = tempfile.mkdtemp(prefix="prism_survey_convert_")
    try:
        tmp_dir_path = Path(tmp_dir)
        input_path = tmp_dir_path / filename
        uploaded_file.save(str(input_path))

        fallback_project_path = session.get("current_project_path")

        alias_path = None
        if alias_filename:
            alias_path = tmp_dir_path / alias_filename
            alias_upload.save(str(alias_path))

        id_map_path = None
        if id_map_filename:
            id_map_path = tmp_dir_path / id_map_filename
            id_map_upload.save(str(id_map_path))

        output_root = tmp_dir_path / "rawdata"
        detected_language = None
        detected_platform = None
        detected_version = None

        if suffix == ".lsa" and infer_lsa_metadata:
            try:
                meta = infer_lsa_metadata(input_path)
                detected_language = meta.get("language")
                detected_platform = meta.get("software_platform")
                detected_version = meta.get("software_version")
            except Exception:
                pass

        try:
            if suffix in {".xlsx", ".csv", ".tsv"}:
                _run_survey_with_official_fallback(
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
                    dry_run=False,
                    force=True,
                    name=dataset_name,
                    authors=[],
                    language=language,
                    alias_file=alias_path,
                    id_map_file=id_map_path,
                    duplicate_handling=duplicate_handling,
                    skip_participants=True,
                    fallback_project_path=fallback_project_path,
                )
            elif suffix == ".lsa":
                _run_survey_with_official_fallback(
                    convert_survey_lsa_to_prism_dataset,
                    input_path=input_path,
                    library_dir=str(effective_survey_dir),
                    output_root=output_root,
                    survey=survey_filter,
                    id_column=id_column,
                    session_column=session_column,
                    session=session_override,
                    unknown=unknown,
                    dry_run=False,
                    force=True,
                    name=dataset_name,
                    authors=[],
                    language=language,
                    alias_file=alias_path,
                    id_map_file=id_map_path,
                    strict_levels=True if strict_levels else None,
                    duplicate_handling=duplicate_handling,
                    skip_participants=True,
                    project_path=session.get("current_project_path"),
                    fallback_project_path=fallback_project_path,
                )
        except IdColumnNotDetectedError as e:
            return (
                jsonify(
                    {
                        "error": "id_column_required",
                        "message": str(e),
                        "columns": e.available_columns,
                    }
                ),
                409,
            )
        except MissingIdMappingError as mie:
            return (
                jsonify(
                    {
                        "error": "id_mapping_incomplete",
                        "message": str(mie),
                        "missing_ids": mie.missing_ids,
                        "suggestions": mie.suggestions,
                    }
                ),
                409,
            )
        except UnmatchedGroupsError as uge:
            return jsonify(_format_unmatched_groups_response(uge)), 409

        if save_to_project:
            p_path = session.get("current_project_path")
            if p_path:
                p_path = Path(p_path)
                if p_path.exists():
                    dest_root = p_path
                    dest_root.mkdir(parents=True, exist_ok=True)

                    for item in output_root.rglob("*"):
                        if item.is_file():
                            rel_path = item.relative_to(output_root)
                            dest = dest_root / rel_path
                            dest.parent.mkdir(parents=True, exist_ok=True)
                            shutil.copy2(item, dest)

                    if archive_sourcedata:
                        sourcedata_dir = p_path / "sourcedata"
                        sourcedata_dir.mkdir(parents=True, exist_ok=True)
                        archive_dest = sourcedata_dir / filename
                        shutil.copy2(input_path, archive_dest)

                    if session_override:
                        conv_type = "survey-lsa" if suffix == ".lsa" else "survey-xlsx"
                        tasks_out = _extract_tasks_from_output(output_root)
                        _register_session_in_project(
                            p_path,
                            session_override,
                            tasks_out,
                            "survey",
                            filename,
                            conv_type,
                        )

        mem = io.BytesIO()
        with zipfile.ZipFile(mem, mode="w", compression=zipfile.ZIP_DEFLATED) as zf:
            for p in output_root.rglob("*"):
                if p.is_file():
                    arcname = p.relative_to(output_root)
                    zf.write(p, arcname.as_posix())
        mem.seek(0)

        resp = send_file(
            mem,
            mimetype="application/zip",
            as_attachment=True,
            download_name="prism_survey_dataset.zip",
        )

        if detected_language:
            resp.headers["X-Prism-Detected-Language"] = str(detected_language)
        if detected_platform:
            resp.headers["X-Prism-Detected-SoftwarePlatform"] = str(detected_platform)
        if detected_version:
            resp.headers["X-Prism-Detected-SoftwareVersion"] = str(detected_version)

        return resp
    except zipfile.BadZipFile:
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
    except ET.ParseError as e:
        return (
            jsonify(
                {
                    "error": f"❌ XML parsing error in LimeSurvey archive.\n\n"
                    f"The survey structure file (.lss) inside the archive is malformed.\n\n"
                    f"Technical details: {str(e)}\n\n"
                    f"💡 Solutions:\n"
                    f"   • Re-export the survey from LimeSurvey\n"
                    f"   • Check for special characters in question text that might cause XML issues"
                }
            ),
            400,
        )
    except Exception as e:
        import traceback

        error_msg = str(e)
        if "No module named" in error_msg:
            error_msg = f"❌ Missing Python package: {error_msg}\n\n💡 Run the setup script to install dependencies."
        elif "Permission denied" in error_msg:
            error_msg = f"❌ File access denied: {error_msg}\n\n💡 Check file permissions and try again."
        elif "not found" in error_msg.lower() and "column" not in error_msg.lower():
            error_msg = f"❌ File or resource not found: {error_msg}"
        elif not error_msg:
            error_msg = "❌ An unknown error occurred during conversion. Check the traceback for details."

        return jsonify({"error": error_msg, "traceback": traceback.format_exc()}), 500
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


def api_survey_convert_validate():
    """Convert survey and run validation immediately, returning results + ZIP as base64."""
    if (
        not convert_survey_xlsx_to_prism_dataset
        and not convert_survey_lsa_to_prism_dataset
    ):
        return jsonify({"error": "Survey conversion module not available"}), 500

    log_messages = []
    conversion_warnings = []

    def add_log(message, level="info"):
        log_messages.append({"message": message, "level": level})

    uploaded_file = request.files.get("excel") or request.files.get("file")
    alias_upload = request.files.get("alias") or request.files.get("alias_file")
    id_map_upload = request.files.get("id_map")

    if not uploaded_file or not getattr(uploaded_file, "filename", ""):
        return jsonify({"error": "Missing input file", "log": log_messages}), 400

    filename = secure_filename(uploaded_file.filename)
    suffix = Path(filename).suffix.lower()
    if suffix not in {".xlsx", ".lsa", ".csv", ".tsv"}:
        return (
            jsonify(
                {
                    "error": "Supported formats: .xlsx, .lsa, .csv, .tsv",
                    "log": log_messages,
                }
            ),
            400,
        )

    try:
        library_path = _resolve_effective_library_path()
    except FileNotFoundError as e:
        return jsonify({"error": str(e), "log": log_messages}), 400

    if (library_path / "survey").is_dir():
        survey_dir = library_path / "survey"
    else:
        survey_dir = library_path

    effective_survey_dir = survey_dir

    survey_templates = list(effective_survey_dir.glob("survey-*.json"))
    if not survey_templates:
        return (
            jsonify(
                {
                    "error": f"No survey templates found in: {effective_survey_dir}",
                    "log": log_messages,
                }
            ),
            400,
        )

    survey_filter = (request.form.get("survey") or "").strip() or None
    id_column = (request.form.get("id_column") or "").strip() or None
    session_column = (request.form.get("session_column") or "").strip() or None
    session_override = (request.form.get("session") or "").strip() or None
    sheet = (request.form.get("sheet") or "0").strip() or 0
    unknown = (request.form.get("unknown") or "warn").strip() or "warn"
    dataset_name = (request.form.get("dataset_name") or "").strip() or None
    language = (request.form.get("language") or "").strip() or None
    strict_levels_raw = (request.form.get("strict_levels") or "").strip().lower()
    strict_levels = strict_levels_raw in {"1", "true", "yes", "on"}
    save_to_project = request.form.get("save_to_project") == "true"
    archive_sourcedata = request.form.get("archive_sourcedata") == "true"
    duplicate_handling = (request.form.get("duplicate_handling") or "error").strip()
    if duplicate_handling not in {"error", "keep_first", "keep_last", "sessions"}:
        duplicate_handling = "error"

    tmp_dir = tempfile.mkdtemp(prefix="prism_survey_convert_validate_")
    try:
        tmp_dir_path = Path(tmp_dir)
        input_path = tmp_dir_path / filename
        uploaded_file.save(str(input_path))

        alias_path = None
        if alias_upload and getattr(alias_upload, "filename", ""):
            alias_path = tmp_dir_path / secure_filename(alias_upload.filename)
            alias_upload.save(str(alias_path))

        id_map_path = None
        if id_map_upload and getattr(id_map_upload, "filename", ""):
            id_map_filename = secure_filename(id_map_upload.filename)
            id_map_path = tmp_dir_path / id_map_filename
            id_map_upload.save(str(id_map_path))
            saved_size = id_map_path.stat().st_size if id_map_path.exists() else 0
            add_log(
                f"Using ID map file: {id_map_filename} ({saved_size} bytes)", "info"
            )

        project_path = session.get("current_project_path")
        if project_path and save_to_project:
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
                    add_log(
                        f"Using participants mapping from: {mapping_file.name}", "info"
                    )
                    break

        output_root = tmp_dir_path / "rawdata"
        output_root.mkdir(parents=True, exist_ok=True)
        add_log("Starting data conversion...", "info")

        try:
            _log_file_head(input_path, suffix, add_log)
        except Exception as head_err:
            add_log(f"Header preview failed: {head_err}", "warning")

        if strict_levels:
            add_log("Strict Levels Validation: enabled", "info")

        convert_result = None
        try:
            if suffix in {".xlsx", ".csv", ".tsv"}:
                convert_result = _run_survey_with_official_fallback(
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
                    dry_run=False,
                    force=True,
                    name=dataset_name,
                    authors=[],
                    language=language,
                    alias_file=alias_path,
                    duplicate_handling=duplicate_handling,
                    skip_participants=True,
                    fallback_project_path=session.get("current_project_path"),
                    log_fn=add_log,
                )
            elif suffix == ".lsa":
                add_log(f"Processing LimeSurvey archive: {filename}", "info")
                convert_result = _run_survey_with_official_fallback(
                    convert_survey_lsa_to_prism_dataset,
                    input_path=input_path,
                    library_dir=str(effective_survey_dir),
                    output_root=output_root,
                    survey=survey_filter,
                    id_column=id_column,
                    session_column=session_column,
                    session=session_override,
                    unknown=unknown,
                    dry_run=False,
                    force=True,
                    name=dataset_name,
                    authors=[],
                    language=language,
                    alias_file=alias_path,
                    strict_levels=True if strict_levels else None,
                    duplicate_handling=duplicate_handling,
                    skip_participants=True,
                    project_path=session.get("current_project_path"),
                    fallback_project_path=session.get("current_project_path"),
                    log_fn=add_log,
                )
            add_log("Conversion completed successfully", "success")
        except IdColumnNotDetectedError as e:
            add_log(f"ID column not detected: {str(e)}", "error")
            return (
                jsonify(
                    {
                        "error": "id_column_required",
                        "message": str(e),
                        "columns": e.available_columns,
                        "log": log_messages,
                    }
                ),
                409,
            )
        except MissingIdMappingError as mie:
            add_log(f"ID mapping incomplete: {str(mie)}", "error")
            return (
                jsonify(
                    {
                        "error": "id_mapping_incomplete",
                        "message": str(mie),
                        "missing_ids": mie.missing_ids,
                        "suggestions": mie.suggestions,
                        "log": log_messages,
                    }
                ),
                409,
            )
        except UnmatchedGroupsError as uge:
            add_log(f"Unmatched groups: {str(uge)}", "error")
            return (
                jsonify(_format_unmatched_groups_response(uge, log_messages)),
                409,
            )
        except Exception as conv_err:
            import sys
            import traceback

            full_trace = traceback.format_exc()
            print(
                f"\n[CONVERSION ERROR] {type(conv_err).__name__}: {str(conv_err)}",
                file=sys.stderr,
            )
            print(f"[FULL TRACEBACK]\n{full_trace}", file=sys.stderr)
            add_log(
                f"Conversion engine failed: {type(conv_err).__name__}: {str(conv_err)}",
                "error",
            )
            for line in full_trace.split("\n"):
                if line.strip():
                    add_log(line, "error")
            raise conv_err

        if convert_result and getattr(convert_result, "missing_cells_by_subject", None):
            missing_counts = {
                sid: cnt
                for sid, cnt in convert_result.missing_cells_by_subject.items()
                if cnt > 0
            }
            if missing_counts:
                conversion_warnings.append(
                    f"Missing responses normalized: {sum(missing_counts.values())} cells."
                )

        if convert_result and getattr(convert_result, "conversion_warnings", None):
            conversion_warnings.extend(convert_result.conversion_warnings)

        add_log("Running validation...", "info")
        validation_result = {"errors": [], "warnings": [], "summary": {}}
        if request.form.get("validate") == "true":
            try:
                v_res = run_validation(
                    str(output_root),
                    schema_version="stable",
                    library_path=str(effective_survey_dir),
                )
                if v_res and isinstance(v_res, tuple):
                    issues = v_res[0]
                    stats = v_res[1]

                    from src.web.reporting_utils import format_validation_results

                    formatted = format_validation_results(
                        issues, stats, str(output_root)
                    )

                    validation_result = {"formatted": formatted}
                    validation_result.update(formatted)

                    total_err = formatted.get("summary", {}).get("total_errors", 0)
                    total_warn = formatted.get("summary", {}).get("total_warnings", 0)

                    if total_err > 0:
                        add_log(
                            f"✗ Validation failed with {total_err} error(s)", "error"
                        )
                        count = 0
                        for group in formatted.get("errors", []):
                            for f in group.get("files", []):
                                if count < 20:
                                    msg = f["message"]
                                    if ": " in msg:
                                        msg = msg.split(": ", 1)[1]
                                    add_log(f"  - {msg}", "error")
                                    count += 1
                        if total_err > 20:
                            add_log(
                                f"  ... and {total_err - 20} more errors (see details below)",
                                "error",
                            )
                    else:
                        add_log("✓ PRISM validation passed!", "success")

                    if total_warn > 0:
                        add_log(f"⚠ {total_warn} warning(s) found", "warning")

            except Exception as val_err:
                validation_result["warnings"].append(
                    f"Validation error: {str(val_err)}"
                )

        if conversion_warnings:
            if "warnings" not in validation_result:
                validation_result["warnings"] = []

            if "formatted" in validation_result:
                conv_group = {
                    "code": "CONVERSION",
                    "message": "Conversion Warnings",
                    "description": "Issues encountered during data conversion",
                    "files": [
                        {"file": filename, "message": w} for w in conversion_warnings
                    ],
                    "count": len(conversion_warnings),
                }
                validation_result["warnings"].append(conv_group)
                if "summary" in validation_result:
                    validation_result["summary"]["total_warnings"] += len(
                        conversion_warnings
                    )
            else:
                validation_result["warnings"].extend(conversion_warnings)

        if save_to_project:
            project_path = session.get("current_project_path")
            if project_path:
                project_path = Path(project_path)

                if project_path.is_file():
                    project_path = project_path.parent

                if project_path.exists() and project_path.is_dir():
                    dest_root = project_path
                    dest_root.mkdir(parents=True, exist_ok=True)
                    add_log(
                        f"Saving output to project: {project_path.name} (into project root)",
                        "info",
                    )

                    for item in output_root.rglob("*"):
                        if item.is_file():
                            rel_path = item.relative_to(output_root)
                            dest = dest_root / rel_path
                            dest.parent.mkdir(parents=True, exist_ok=True)
                            shutil.copy2(item, dest)
                    add_log("Project updated successfully!", "success")

                    if archive_sourcedata:
                        sourcedata_dir = project_path / "sourcedata"
                        sourcedata_dir.mkdir(parents=True, exist_ok=True)
                        archive_dest = sourcedata_dir / filename
                        shutil.copy2(input_path, archive_dest)
                        add_log(
                            f"Archived original file to sourcedata/{filename}", "info"
                        )

                    if session_override:
                        conv_type = "survey-lsa" if suffix == ".lsa" else "survey-xlsx"
                        tasks_out = (
                            convert_result.tasks_included
                            if convert_result
                            and getattr(convert_result, "tasks_included", None)
                            else _extract_tasks_from_output(output_root)
                        )
                        _register_session_in_project(
                            project_path,
                            session_override,
                            tasks_out,
                            "survey",
                            filename,
                            conv_type,
                        )
                        add_log(
                            f"Registered in project.json: ses-{session_override} → {', '.join(tasks_out)}",
                            "info",
                        )
                else:
                    add_log(f"Project path not found: {project_path}", "error")
            else:
                add_log(
                    "No project selected in session. Cannot save directly.", "warning"
                )

        mem = io.BytesIO()
        with zipfile.ZipFile(mem, mode="w", compression=zipfile.ZIP_DEFLATED) as zf:
            for p in output_root.rglob("*"):
                if p.is_file():
                    zf.write(p, p.relative_to(output_root).as_posix())
        mem.seek(0)
        zip_base64 = base64.b64encode(mem.read()).decode("utf-8")

        response_payload = {
            "success": True,
            "log": log_messages,
            "validation": validation_result,
            "zip_base64": zip_base64,
        }

        if convert_result:
            summary = {}
            if getattr(convert_result, "template_matches", None):
                summary["template_matches"] = convert_result.template_matches
            if getattr(convert_result, "tasks_included", None):
                summary["tasks_included"] = convert_result.tasks_included
            if getattr(convert_result, "task_runs", None):
                summary["task_runs"] = convert_result.task_runs
            if getattr(convert_result, "unknown_columns", None):
                summary["unknown_columns"] = convert_result.unknown_columns
            if getattr(convert_result, "tool_columns", None):
                summary["tool_columns"] = convert_result.tool_columns
            if conversion_warnings:
                summary["conversion_warnings"] = conversion_warnings
            if summary:
                response_payload["conversion_summary"] = summary

        return jsonify(sanitize_jsonable(response_payload))
    except Exception as e:
        return jsonify({"error": str(e), "log": log_messages}), 500
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


def api_save_unmatched_template():
    """Save a generated template for an unmatched group to the project library."""
    project_path = session.get("current_project_path")
    if not project_path:
        return jsonify({"error": "No project selected"}), 400

    data = request.get_json()
    task_key = data.get("task_key")
    prism_json = data.get("prism_json")
    if not task_key or not prism_json:
        return jsonify({"error": "Missing task_key or prism_json"}), 400

    from src.converters.survey_templates import _strip_run_suffix

    clean = {}
    for k, v in prism_json.items():
        if k.startswith("_"):
            continue
        if isinstance(v, dict) and k not in _NON_ITEM_TOPLEVEL_KEYS:
            base, _ = _strip_run_suffix(k)
            if base not in clean:
                clean[base] = v
        else:
            clean[k] = v

    library_path = Path(project_path) / "code" / "library" / "survey"
    library_path.mkdir(parents=True, exist_ok=True)

    filename = f"survey-{task_key}.json"
    filepath = library_path / filename

    from src.utils.io import write_json

    write_json(filepath, clean)

    return jsonify(
        {
            "success": True,
            "path": str(filepath),
            "filename": filename,
        }
    )
