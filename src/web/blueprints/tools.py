import os
import sys
import json
import tempfile
import subprocess
from pathlib import Path
from flask import Blueprint, render_template, request, jsonify, send_file, current_app

tools_bp = Blueprint("tools", __name__)

@tools_bp.route("/survey-generator")
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

@tools_bp.route("/converter")
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

@tools_bp.route("/derivatives")
def derivatives():
    return render_template("derivatives.html")

@tools_bp.route("/api/derivatives-surveys", methods=["POST"])
def api_derivatives_surveys():
    """Run survey-derivatives generation inside an existing PRISM dataset."""
    try:
        from derivatives_surveys import compute_survey_derivatives
    except ImportError:
        compute_survey_derivatives = None

    if not compute_survey_derivatives:
        return jsonify({"error": "Data processing module not available"}), 500

    data = request.get_json(silent=True) or {}
    dataset_path = (data.get("dataset_path") or "").strip()
    modality = (data.get("modality") or "survey").strip().lower() or "survey"
    out_format = (data.get("format") or "csv").strip().lower() or "csv"
    survey_filter = (data.get("survey") or "").strip() or None

    if not dataset_path or not os.path.exists(dataset_path) or not os.path.isdir(dataset_path):
        return jsonify({"error": "Invalid dataset path"}), 400

    # Validate that the dataset is PRISM-valid before writing outputs.
    from src.web import run_validation
    issues, _stats = run_validation(
        dataset_path, verbose=False, schema_version=None, run_bids=False
    )
    error_issues = [
        i for i in (issues or []) if (len(i) >= 1 and str(i[0]).upper() == "ERROR")
    ]
    if error_issues:
        first = error_issues[0][1] if len(error_issues[0]) > 1 else "Dataset has validation errors"
        return jsonify({"error": f"Dataset is not PRISM-valid (errors: {len(error_issues)}). First error: {first}"}), 400

    try:
        result = compute_survey_derivatives(
            prism_root=dataset_path,
            repo_root=current_app.root_path,
            survey=survey_filter,
            out_format=out_format,
            modality=modality,
        )
    except Exception as e:
        return jsonify({"error": str(e)}), 500

    msg = f"✅ Data processing complete: wrote {result.written_files} file(s)"
    if result.flat_out_path:
        msg = f"✅ Data processing complete: wrote {result.flat_out_path}"
    if result.fallback_note:
        msg += f" (note: {result.fallback_note})"
    return jsonify({
        "ok": True,
        "message": msg,
        "written_files": result.written_files,
        "processed_files": result.processed_files,
        "out_format": result.out_format,
        "out_root": str(result.out_root),
        "flat_out_path": str(result.flat_out_path) if result.flat_out_path else None,
    })

@tools_bp.route("/api/browse-folder")
def api_browse_folder():
    """Open a system dialog to select a folder"""
    folder_path = ""
    try:
        if sys.platform == "darwin":
            try:
                script = "POSIX path of (choose folder)"
                result = subprocess.check_output(["osascript", "-e", script], stderr=subprocess.STDOUT)
                folder_path = result.decode("utf-8").strip()
            except subprocess.CalledProcessError:
                folder_path = ""
        else:
            import tkinter as tk
            from tkinter import filedialog
            root = tk.Tk()
            root.withdraw()
            root.attributes("-topmost", True)
            folder_path = filedialog.askdirectory()
            root.destroy()

        return jsonify({"path": folder_path})
    except Exception as e:
        print(f"Error opening file dialog: {e}")
        return jsonify({"error": "Could not open file dialog. Please enter path manually."}), 500

def _extract_template_info(full_path, filename):
    """Helper to extract metadata and questions from a PRISM JSON template"""
    desc = ""
    original_name = ""
    questions = []
    i18n = {}
    try:
        with open(full_path, "r") as jf:
            data = json.load(jf)
            study = data.get("Study", {})
            desc = study.get("Description", "")
            original_name = study.get("OriginalName", "")
            i18n = data.get("I18n", {})

            if not desc:
                desc = data.get("TaskName", "")

            def _get_q_info(k, v):
                if not isinstance(v, dict):
                    return {"id": k, "description": str(v)}
                return {
                    "id": k,
                    "description": v.get("Description", ""),
                    "levels": v.get("Levels", {}),
                    "scale": v.get("Scale", ""),
                    "units": v.get("Units", ""),
                    "min_value": v.get("MinValue"),
                    "max_value": v.get("MaxValue"),
                }

            if "Questions" in data and isinstance(data["Questions"], dict):
                for k, v in data["Questions"].items():
                    questions.append(_get_q_info(k, v))
            else:
                reserved = ["Technical", "Study", "Metadata", "Categories", "TaskName", "Name", "BIDSVersion", "Description", "URL", "License", "Authors", "Acknowledgements", "References", "Funding", "I18n"]
                for k, v in data.items():
                    if k not in reserved:
                        questions.append(_get_q_info(k, v))
    except Exception:
        pass

    return {
        "filename": filename,
        "path": str(full_path),
        "description": desc,
        "original_name": original_name,
        "questions": questions,
        "question_count": len(questions),
        "i18n": i18n,
    }

@tools_bp.route("/api/list-library-files")
def list_library_files():
    """List JSON files in a user-specified library path, grouped by modality"""
    library_path = request.args.get("path")
    if not library_path or not os.path.exists(library_path) or not os.path.isdir(library_path):
        return jsonify({"error": "Invalid path"}), 400

    results = {"participants": [], "survey": [], "biometrics": [], "other": []}
    try:
        participants_path = os.path.join(library_path, "participants.json")
        if os.path.exists(participants_path):
            results["participants"].append(_extract_template_info(participants_path, "participants.json"))

        for folder in ["survey", "biometrics"]:
            folder_path = os.path.join(library_path, folder)
            if os.path.exists(folder_path) and os.path.isdir(folder_path):
                for filename in os.listdir(folder_path):
                    if filename.endswith(".json") and not filename.startswith("."):
                        results[folder].append(_extract_template_info(os.path.join(folder_path, filename), filename))

        if not results["survey"] and not results["biometrics"]:
            for filename in os.listdir(library_path):
                if filename.endswith(".json") and not filename.startswith(".") and filename != "participants.json":
                    results["other"].append(_extract_template_info(os.path.join(library_path, filename), filename))

        return jsonify(results)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@tools_bp.route("/api/generate-lss", methods=["POST"])
def generate_lss_endpoint():
    """Generate LSS from selected JSON files"""
    try:
        from src.limesurvey_exporter import generate_lss
    except ImportError:
        generate_lss = None

    if not generate_lss:
        return jsonify({"error": "LSS exporter not available"}), 500

    try:
        data = request.get_json()
        files = data.get("files", [])
        if not files:
            return jsonify({"error": "No files selected"}), 400

        valid_files = [f for f in files if os.path.exists(f.get("path") if isinstance(f, dict) else f)]
        if not valid_files:
            return jsonify({"error": "No valid files found"}), 404

        fd, temp_path = tempfile.mkstemp(suffix=".lss")
        os.close(fd)

        language = data.get("language", "en")
        ls_version = data.get("ls_version", "6")
        generate_lss(valid_files, temp_path, language=language, ls_version=ls_version)

        return send_file(temp_path, as_attachment=True, download_name=f"survey_export_{language}.lss", mimetype="application/xml")
    except Exception as e:
        return jsonify({"error": str(e)}), 500
