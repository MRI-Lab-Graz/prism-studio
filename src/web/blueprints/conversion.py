"""
Conversion Blueprint for PRISM.
Handles survey, biometrics, and physio conversion routes.
"""

import os
import io
import re
import json
import uuid
import shutil
import tempfile
import zipfile
import base64
from pathlib import Path
from flask import Blueprint, request, jsonify, send_file, render_template, current_app
from werkzeug.utils import secure_filename
from src.web.utils import list_survey_template_languages, sanitize_jsonable, run_validation

# Import conversion logic
try:
    from src.survey_convert import (
        convert_survey_xlsx_to_prism_dataset,
        convert_survey_lsa_to_prism_dataset,
        infer_lsa_metadata,
    )
except ImportError:
    convert_survey_xlsx_to_prism_dataset = None
    convert_survey_lsa_to_prism_dataset = None
    infer_lsa_metadata = None

try:
    from src.biometrics_convert import convert_biometrics_table_to_prism_dataset
except ImportError:
    convert_biometrics_table_to_prism_dataset = None

try:
    from helpers.physio.convert_varioport import convert_varioport
except ImportError:
    convert_varioport = None

try:
    from src.batch_convert import (
        batch_convert_folder,
        create_dataset_description,
        parse_bids_filename,
    )
except ImportError:
    batch_convert_folder = None
    create_dataset_description = None
    parse_bids_filename = None

conversion_bp = Blueprint('conversion', __name__)

# Batch conversion job tracking
_batch_convert_jobs = {}

@conversion_bp.route("/survey-generator")
def survey_generator():
    """Survey generator page"""
    base_dir = Path(current_app.root_path)
    preferred = (base_dir / "library" / "survey_i18n").resolve()
    default_library_path = preferred
    if not (preferred.exists() and any(preferred.glob("survey-*.json"))):
        default_library_path = (base_dir / "survey_library").resolve()
    return render_template(
        "survey_generator.html",
        default_survey_library_path=str(default_library_path),
    )

@conversion_bp.route("/converter")
def converter():
    """Converter page"""
    base_dir = Path(current_app.root_path)
    preferred = (base_dir / "library" / "survey_i18n").resolve()
    default_library_path = preferred
    if not (preferred.exists() and any(preferred.glob("survey-*.json"))):
        default_library_path = (base_dir / "survey_library").resolve()
    return render_template(
        "converter.html",
        default_survey_library_path=str(default_library_path),
    )

@conversion_bp.route("/api/survey-languages", methods=["GET"])
def api_survey_languages():
    """List available languages for the selected survey template library folder."""
    library_path = (request.args.get("library_path") or "").strip()
    base_dir = Path(current_app.root_path)
    if not library_path:
        preferred = (base_dir / "library" / "survey_i18n").resolve()
        fallback = (base_dir / "survey_library").resolve()
        if preferred.exists() and any(preferred.glob("survey-*.json")):
            library_path = str(preferred)
        else:
            library_path = str(fallback)

    # Check structure of library root
    library_root = Path(library_path)
    structure_info = {
        "has_survey_folder": False,
        "has_biometrics_folder": False,
        "has_participants_json": False,
        "missing_items": [],
    }

    # Check for expected items
    survey_dir = library_root / "survey"
    biometrics_dir = library_root / "biometrics"
    participants_json = library_root / "participants.json"

    structure_info["has_survey_folder"] = survey_dir.is_dir()
    structure_info["has_biometrics_folder"] = biometrics_dir.is_dir()
    structure_info["has_participants_json"] = participants_json.is_file()

    # Build missing items list for survey conversion
    if not structure_info["has_survey_folder"]:
        structure_info["missing_items"].append("survey/")
    if not structure_info["has_participants_json"]:
        structure_info["missing_items"].append("participants.json")

    # Determine effective survey directory
    if survey_dir.is_dir():
        effective_survey_dir = str(survey_dir)
    else:
        effective_survey_dir = library_path

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

@conversion_bp.route("/api/survey-convert", methods=["POST"])
def api_survey_convert():
    """Convert an uploaded survey file (.xlsx or .lsa) to a PRISM dataset and return it as a zip."""
    if (
        not convert_survey_xlsx_to_prism_dataset
        and not convert_survey_lsa_to_prism_dataset
    ):
        return jsonify({"error": "Survey conversion module not available"}), 500

    uploaded_file = request.files.get("excel") or request.files.get("file")
    alias_upload = request.files.get("alias") or request.files.get("alias_file")
    library_path = (request.form.get("library_path") or "").strip()

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
            return jsonify({"error": "Alias file must be a .tsv or .txt mapping file"}), 400

    if not library_path:
        return jsonify({"error": "Survey template library path is required."}), 400

    if not os.path.exists(library_path) or not os.path.isdir(library_path):
        return jsonify({"error": f"Library path is not a directory: {library_path}"}), 400

    library_root = Path(library_path)
    survey_dir = library_root / "survey"
    effective_survey_dir = survey_dir if survey_dir.is_dir() else library_root

    survey_templates = list(effective_survey_dir.glob("survey-*.json"))
    if not survey_templates:
        return jsonify({"error": f"No survey templates found in: {effective_survey_dir}"}), 400

    survey_filter = (request.form.get("survey") or "").strip() or None
    id_column = (request.form.get("id_column") or "").strip() or None
    session_column = (request.form.get("session_column") or "").strip() or None
    sheet = (request.form.get("sheet") or "0").strip() or 0
    unknown = (request.form.get("unknown") or "warn").strip() or "warn"
    dataset_name = (request.form.get("dataset_name") or "").strip() or None
    language = (request.form.get("language") or "").strip() or None

    tmp_dir = tempfile.mkdtemp(prefix="prism_survey_convert_")
    try:
        tmp_dir_path = Path(tmp_dir)
        input_path = tmp_dir_path / filename
        uploaded_file.save(str(input_path))

        alias_path = None
        if alias_filename:
            alias_path = tmp_dir_path / alias_filename
            alias_upload.save(str(alias_path))

        output_root = tmp_dir_path / "prism_dataset"
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

        if suffix in {".xlsx", ".csv", ".tsv"}:
            convert_survey_xlsx_to_prism_dataset(
                input_path=input_path,
                library_dir=str(effective_survey_dir),
                output_root=output_root,
                survey=survey_filter,
                id_column=id_column,
                session_column=session_column,
                sheet=sheet,
                unknown=unknown,
                dry_run=False,
                force=True,
                name=dataset_name,
                authors=["prism-studio"],
                language=language,
                alias_file=alias_path,
            )
        elif suffix == ".lsa":
            convert_survey_lsa_to_prism_dataset(
                input_path=input_path,
                library_dir=str(effective_survey_dir),
                output_root=output_root,
                survey=survey_filter,
                id_column=id_column,
                session_column=session_column,
                unknown=unknown,
                dry_run=False,
                force=True,
                name=dataset_name,
                authors=["prism-studio"],
                language=language,
                alias_file=alias_path,
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
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)

@conversion_bp.route("/api/survey-convert-validate", methods=["POST"])
def api_survey_convert_validate():
    """Convert survey and run validation immediately, returning results + ZIP as base64."""
    if not convert_survey_xlsx_to_prism_dataset and not convert_survey_lsa_to_prism_dataset:
        return jsonify({"error": "Survey conversion module not available"}), 500

    log_messages = []
    conversion_warnings = []

    def add_log(message, level="info"):
        log_messages.append({"message": message, "level": level})

    uploaded_file = request.files.get("excel") or request.files.get("file")
    alias_upload = request.files.get("alias") or request.files.get("alias_file")
    library_path = (request.form.get("library_path") or "").strip()

    if not uploaded_file or not getattr(uploaded_file, "filename", ""):
        return jsonify({"error": "Missing input file", "log": log_messages}), 400

    filename = secure_filename(uploaded_file.filename)
    suffix = Path(filename).suffix.lower()
    if suffix not in {".xlsx", ".lsa", ".csv", ".tsv"}:
        return jsonify({"error": "Supported formats: .xlsx, .lsa, .csv, .tsv", "log": log_messages}), 400

    if not library_path or not os.path.isdir(library_path):
        return jsonify({"error": "Valid library path is required.", "log": log_messages}), 400

    library_root = Path(library_path)
    survey_dir = library_root / "survey"
    effective_survey_dir = survey_dir if survey_dir.is_dir() else library_root

    survey_templates = list(effective_survey_dir.glob("survey-*.json"))
    if not survey_templates:
        return jsonify({"error": f"No survey templates found in: {effective_survey_dir}", "log": log_messages}), 400

    survey_filter = (request.form.get("survey") or "").strip() or None
    id_column = (request.form.get("id_column") or "").strip() or None
    session_column = (request.form.get("session_column") or "").strip() or None
    sheet = (request.form.get("sheet") or "0").strip() or 0
    unknown = (request.form.get("unknown") or "warn").strip() or "warn"
    dataset_name = (request.form.get("dataset_name") or "").strip() or None
    language = (request.form.get("language") or "").strip() or None

    tmp_dir = tempfile.mkdtemp(prefix="prism_survey_convert_validate_")
    try:
        tmp_dir_path = Path(tmp_dir)
        input_path = tmp_dir_path / filename
        uploaded_file.save(str(input_path))

        alias_path = None
        if alias_upload and getattr(alias_upload, "filename", ""):
            alias_path = tmp_dir_path / secure_filename(alias_upload.filename)
            alias_upload.save(str(alias_path))

        output_root = tmp_dir_path / "prism_dataset"
        add_log("Starting data conversion...", "info")

        convert_result = None
        if suffix in {".xlsx", ".csv", ".tsv"}:
            convert_result = convert_survey_xlsx_to_prism_dataset(
                input_path=input_path, library_dir=str(effective_survey_dir),
                output_root=output_root, survey=survey_filter, id_column=id_column,
                session_column=session_column, sheet=sheet, unknown=unknown,
                dry_run=False, force=True, name=dataset_name, authors=["prism-studio"],
                language=language, alias_file=alias_path,
            )
        elif suffix == ".lsa":
            convert_result = convert_survey_lsa_to_prism_dataset(
                input_path=input_path, library_dir=str(effective_survey_dir),
                output_root=output_root, survey=survey_filter, id_column=id_column,
                session_column=session_column, unknown=unknown, dry_run=False,
                force=True, name=dataset_name, authors=["prism-studio"],
                language=language, alias_file=alias_path,
            )
        add_log("Conversion completed", "success")

        # Process warnings and missing cells
        if convert_result and getattr(convert_result, "missing_cells_by_subject", None):
            missing_counts = {sid: cnt for sid, cnt in convert_result.missing_cells_by_subject.items() if cnt > 0}
            if missing_counts:
                conversion_warnings.append(f"Missing responses normalized: {sum(missing_counts.values())} cells.")

        if convert_result and getattr(convert_result, "conversion_warnings", None):
            conversion_warnings.extend(convert_result.conversion_warnings)

        # Run validation
        add_log("Running validation...", "info")
        validation_result = {"errors": [], "warnings": [], "summary": {}}
        try:
            result = run_validation(str(output_root), schema_version="stable")
            if result and isinstance(result, tuple):
                messages = result[0]
                for msg in messages:
                    if isinstance(msg, tuple) and len(msg) >= 2:
                        level, text = msg[0].upper(), msg[1]
                        if level == "ERROR": validation_result["errors"].append(text)
                        elif level == "WARNING": validation_result["warnings"].append(text)
        except Exception as val_err:
            validation_result["warnings"].append(f"Validation error: {str(val_err)}")

        validation_result["warnings"].extend(conversion_warnings)

        # Create ZIP
        mem = io.BytesIO()
        with zipfile.ZipFile(mem, mode="w", compression=zipfile.ZIP_DEFLATED) as zf:
            for p in output_root.rglob("*"):
                if p.is_file(): zf.write(p, p.relative_to(output_root).as_posix())
        mem.seek(0)
        zip_base64 = base64.b64encode(mem.read()).decode("utf-8")

        return jsonify(sanitize_jsonable({
            "success": True, "log": log_messages,
            "validation": validation_result, "zip_base64": zip_base64,
        }))
    except Exception as e:
        return jsonify({"error": str(e), "log": log_messages}), 500
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)

@conversion_bp.route("/api/biometrics-check-library", methods=["GET"])
def api_biometrics_check_library():
    """Check the structure of a biometrics template library folder."""
    library_path = (request.args.get("library_path") or "").strip()
    if not library_path: return jsonify({"error": "No library path provided"}), 400

    library_root = Path(library_path)
    biometrics_dir = library_root / "biometrics"
    
    structure_info = {
        "has_survey_folder": (library_root / "survey").is_dir(),
        "has_biometrics_folder": biometrics_dir.is_dir(),
        "has_participants_json": (library_root / "participants.json").is_file(),
        "missing_items": [],
        "template_count": 0,
    }

    if not structure_info["has_biometrics_folder"]: structure_info["missing_items"].append("biometrics/")
    if not structure_info["has_participants_json"]: structure_info["missing_items"].append("participants.json")
    if biometrics_dir.is_dir():
        structure_info["template_count"] = len(list(biometrics_dir.glob("biometrics-*.json")))

    return jsonify({"structure": structure_info})

@conversion_bp.route("/api/biometrics-convert", methods=["POST"])
def api_biometrics_convert():
    """Convert an uploaded biometrics table (.csv or .xlsx) into a PRISM/BIDS-style dataset ZIP."""
    if not convert_biometrics_table_to_prism_dataset:
        return jsonify({"error": "Biometrics conversion module not available"}), 500

    uploaded_file = request.files.get("data") or request.files.get("file")
    library_path = (request.form.get("library_path") or "").strip()

    if not uploaded_file or not getattr(uploaded_file, "filename", ""):
        return jsonify({"error": "Missing input file"}), 400

    filename = secure_filename(uploaded_file.filename)
    suffix = Path(filename).suffix.lower()
    if suffix not in {".csv", ".xlsx", ".tsv"}:
        return jsonify({"error": "Supported formats: .csv, .xlsx, .tsv"}), 400

    if not library_path:
        return jsonify({"error": "Biometrics template library path is required."}), 400

    if not os.path.exists(library_path) or not os.path.isdir(library_path):
        return jsonify({"error": f"Library path is not a directory: {library_path}"}), 400

    library_root = Path(library_path)
    biometrics_dir = library_root / "biometrics"
    effective_biometrics_dir = biometrics_dir if biometrics_dir.is_dir() else library_root

    biometrics_templates = list(effective_biometrics_dir.glob("biometrics-*.json"))
    if not biometrics_templates:
        return jsonify({"error": f"No biometrics templates found in: {effective_biometrics_dir}"}), 400

    id_column = (request.form.get("id_column") or "").strip() or None
    session_column = (request.form.get("session_column") or "").strip() or None
    sheet = (request.form.get("sheet") or "0").strip() or 0
    unknown = (request.form.get("unknown") or "warn").strip() or "warn"
    dataset_name = (request.form.get("dataset_name") or "").strip() or None

    tmp_dir = tempfile.mkdtemp(prefix="prism_biometrics_convert_")
    try:
        tmp_dir_path = Path(tmp_dir)
        input_path = tmp_dir_path / filename
        uploaded_file.save(str(input_path))

        output_root = tmp_dir_path / "prism_dataset"

        convert_biometrics_table_to_prism_dataset(
            input_path=input_path,
            library_dir=str(effective_biometrics_dir),
            output_root=output_root,
            id_column=id_column,
            session_column=session_column,
            sheet=sheet,
            unknown=unknown,
            force=True,
            name=dataset_name,
            authors=["prism-studio"],
        )

        mem = io.BytesIO()
        with zipfile.ZipFile(mem, mode="w", compression=zipfile.ZIP_DEFLATED) as zf:
            for p in output_root.rglob("*"):
                if p.is_file():
                    arcname = p.relative_to(output_root)
                    zf.write(p, arcname.as_posix())
        mem.seek(0)

        return send_file(
            mem,
            mimetype="application/zip",
            as_attachment=True,
            download_name="prism_biometrics_dataset.zip",
        )
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)

@conversion_bp.route("/api/physio-convert", methods=["POST"])
def api_physio_convert():
    """Convert an uploaded Varioport file (.raw/.vpd) into EDF+ (.edf) + sidecar (.json) and return as ZIP."""
    if convert_varioport is None:
        return jsonify({"error": "Physio conversion (Varioport) not available"}), 500

    uploaded_file = request.files.get("raw") or request.files.get("file")
    if not uploaded_file or not getattr(uploaded_file, "filename", ""):
        return jsonify({"error": "Missing input file"}), 400

    filename = secure_filename(uploaded_file.filename)
    suffix = Path(filename).suffix.lower()
    if suffix not in {".raw", ".vpd"}:
        return jsonify({"error": "Only Varioport .raw and .vpd files are supported"}), 400

    task = (request.form.get("task") or "rest").strip() or "rest"
    base_freq = (request.form.get("sampling_rate") or "").strip() or None
    try:
        base_freq_val = float(base_freq) if base_freq is not None else None
    except Exception:
        return jsonify({"error": "sampling_rate must be a number"}), 400

    tmp_dir = tempfile.mkdtemp(prefix="prism_physio_convert_")
    try:
        tmp_dir_path = Path(tmp_dir)
        input_path = tmp_dir_path / filename
        uploaded_file.save(str(input_path))

        out_edf = tmp_dir_path / (input_path.stem + ".edf")
        out_json = tmp_dir_path / (input_path.stem + ".json")

        convert_varioport(
            str(input_path),
            str(out_edf),
            str(out_json),
            task_name=task,
            base_freq=base_freq_val,
        )

        mem = io.BytesIO()
        with zipfile.ZipFile(mem, mode="w", compression=zipfile.ZIP_DEFLATED) as zf:
            if out_edf.exists():
                zf.write(out_edf, out_edf.name)
            if out_json.exists():
                zf.write(out_json, out_json.name)
        mem.seek(0)

        return send_file(
            mem,
            mimetype="application/zip",
            as_attachment=True,
            download_name="varioport_edfplus.zip",
        )
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)

@conversion_bp.route("/api/batch-convert", methods=["POST"])
def api_batch_convert():
    """Batch convert physio/eyetracking files from a flat folder structure."""
    if not batch_convert_folder:
        return jsonify({"error": "Batch conversion not available"}), 500

    job_id = str(uuid.uuid4())[:8]
    logs = []

    def log_callback(message: str, level: str = "info"):
        logs.append({"message": message, "level": level})

    dataset_name = (request.form.get("dataset_name") or "Converted Dataset").strip()
    modality_filter = request.form.get("modality", "all")
    sampling_rate_str = request.form.get("sampling_rate", "").strip()
    return_format = request.form.get("format", "zip")

    try:
        sampling_rate = float(sampling_rate_str) if sampling_rate_str else None
    except ValueError:
        return jsonify({"error": "sampling_rate must be a number", "logs": logs}), 400

    files = request.files.getlist("files[]") or request.files.getlist("files")
    if not files:
        return jsonify({"error": "No files uploaded", "logs": logs}), 400

    valid_extensions = {".raw", ".vpd", ".edf"}
    validated_files = []
    for f in files:
        if not f or not f.filename: continue
        filename = secure_filename(f.filename)
        ext = Path(filename).suffix.lower()
        if ext in valid_extensions and parse_bids_filename(filename):
            validated_files.append((f, filename))

    if not validated_files:
        return jsonify({"error": "No valid files to convert.", "logs": logs}), 400

    tmp_dir = tempfile.mkdtemp(prefix="prism_batch_convert_")
    try:
        tmp_path = Path(tmp_dir)
        input_dir = tmp_path / "input"
        output_dir = tmp_path / "output"
        input_dir.mkdir(); output_dir.mkdir()

        for f, filename in validated_files:
            f.save(str(input_dir / filename))

        result = batch_convert_folder(
            input_dir, output_dir,
            physio_sampling_rate=sampling_rate,
            modality_filter=modality_filter,
            log_callback=log_callback,
        )

        create_dataset_description(output_dir, name=dataset_name)

        if return_format == "json":
            return jsonify({"job_id": job_id, "status": "complete", "logs": logs})

        mem = io.BytesIO()
        with zipfile.ZipFile(mem, mode="w", compression=zipfile.ZIP_DEFLATED) as zf:
            for file_path in output_dir.rglob("*"):
                if file_path.is_file():
                    zf.write(file_path, file_path.relative_to(output_dir))
        mem.seek(0)

        safe_name = re.sub(r"[^a-zA-Z0-9_-]", "_", dataset_name)[:50]
        return send_file(
            mem, mimetype="application/zip", as_attachment=True,
            download_name=f"{safe_name}_prism.zip"
        )
    except Exception as e:
        return jsonify({"error": str(e), "logs": logs}), 500
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)
