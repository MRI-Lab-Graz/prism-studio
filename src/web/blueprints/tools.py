import os
import sys
import json
import io
import tempfile
import subprocess
from pathlib import Path
from datetime import date
from flask import Blueprint, render_template, request, jsonify, send_file, current_app

tools_bp = Blueprint("tools", __name__)


def _default_library_root_for_templates(*, modality: str) -> Path:
    base_dir = Path(current_app.root_path)

    preferred = (base_dir / "library" / "survey_i18n").resolve()
    if modality == "survey":
        if preferred.exists() and any(preferred.glob("survey-*.json")):
            return preferred

    return (base_dir / "survey_library").resolve()


def _resolve_library_root(library_path: str | None) -> Path:
    if library_path:
        p = Path(library_path).expanduser().resolve()
        if p.exists() and p.is_dir():
            return p
        raise FileNotFoundError(f"Invalid library folder: {library_path}")
    return Path(_default_library_root_for_templates(modality="survey")).resolve()


def _template_dir(*, modality: str, library_root: Path) -> Path:
    candidate = library_root / modality
    if candidate.is_dir():
        return candidate
    return library_root


def _load_prism_schema(*, modality: str, schema_version: str | None) -> dict:
    from src.schema_manager import load_schema

    schema_dir = os.path.join(current_app.root_path, "schemas")
    schema = load_schema(modality, schema_dir=schema_dir, version=schema_version)
    if not schema:
        raise FileNotFoundError(
            f"No schema found for modality={modality} version={schema_version}"
        )
    return schema


def _pick_enum_value(values: list) -> object:
    for v in values:
        if v != "":
            return v
    return values[0] if values else ""


def _schema_example(schema: dict) -> object:
    if not isinstance(schema, dict):
        return None

    if isinstance(schema.get("examples"), list) and schema.get("examples"):
        return schema["examples"][0]
    if "default" in schema:
        return schema.get("default")
    if isinstance(schema.get("enum"), list) and schema.get("enum"):
        return _pick_enum_value(schema["enum"])

    t = schema.get("type")
    if isinstance(t, list):
        # Prefer deterministic order
        for preferred in ("object", "array", "string", "integer", "number", "boolean", "null"):
            if preferred in t:
                t = preferred
                break
        else:
            t = t[0] if t else None

    if t == "object" or (t is None and "properties" in schema):
        out: dict[str, object] = {}
        props = schema.get("properties") or {}
        if isinstance(props, dict):
            for k, v in props.items():
                out[k] = _schema_example(v if isinstance(v, dict) else {})
        return out

    if t == "array":
        item_schema = schema.get("items") if isinstance(schema.get("items"), dict) else {}
        return [_schema_example(item_schema)]

    if t == "integer":
        return 0
    if t == "number":
        return 0
    if t == "boolean":
        return False
    if t == "null":
        return None

    # Default string-like
    return ""


def _deep_merge(base: object, override: object) -> object:
    if isinstance(base, dict) and isinstance(override, dict):
        out = dict(base)
        for k, v in override.items():
            if k in out:
                out[k] = _deep_merge(out[k], v)
            else:
                out[k] = v
        return out
    return override


def _new_template_from_schema(*, modality: str, schema_version: str | None) -> dict:
    schema = _load_prism_schema(modality=modality, schema_version=schema_version)
    out: dict[str, object] = {}

    props = schema.get("properties") if isinstance(schema.get("properties"), dict) else {}
    for k, v in props.items():
        out[k] = _schema_example(v if isinstance(v, dict) else {})

    # Sensible defaults
    schema_semver = schema.get("version")
    if isinstance(out.get("Metadata"), dict):
        md = dict(out["Metadata"])
        if isinstance(schema_semver, str):
            md["SchemaVersion"] = schema_semver
        md.setdefault("CreationDate", date.today().isoformat())
        out["Metadata"] = md

    if modality == "survey":
        # Align with schema naming conventions
        if isinstance(out.get("Technical"), dict):
            out["Technical"]["StimulusType"] = out["Technical"].get("StimulusType") or "Questionnaire"
            out["Technical"]["FileFormat"] = out["Technical"].get("FileFormat") or "tsv"

    if modality == "biometrics":
        if isinstance(out.get("Technical"), dict):
            out["Technical"]["FileFormat"] = out["Technical"].get("FileFormat") or "tsv"

    return out


def _validate_against_schema(*, instance: object, schema: dict) -> list[dict]:
    from jsonschema import Draft7Validator

    v = Draft7Validator(schema)
    errors = []
    for err in sorted(v.iter_errors(instance), key=lambda e: list(e.path)):
        path = "/".join(str(p) for p in err.path)
        errors.append(
            {
                "path": path,
                "message": err.message,
            }
        )
    return errors

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

@tools_bp.route("/recipes")
def recipes():
    return render_template("recipes.html")


@tools_bp.route("/template-editor")
def template_editor():
    """Edit or create PRISM JSON templates (survey/biometrics) based on schemas."""
    try:
        from src.schema_manager import get_available_schema_versions

        schema_versions = get_available_schema_versions(
            os.path.join(current_app.root_path, "schemas")
        )
    except Exception:
        schema_versions = ["stable"]

    return render_template(
        "template_editor.html",
        schema_versions=schema_versions,
        default_schema_version=(schema_versions[0] if schema_versions else "stable"),
    )


@tools_bp.route("/api/template-editor/list", methods=["GET"])
def api_template_editor_list():
    modality = (request.args.get("modality") or "").strip().lower()
    library_path = (request.args.get("library_path") or "").strip() or None
    if modality not in {"survey", "biometrics"}:
        return jsonify({"error": "Invalid modality"}), 400

    try:
        library_root = _resolve_library_root(library_path)
    except Exception as e:
        return jsonify({"error": str(e)}), 400

    folder = _template_dir(modality=modality, library_root=library_root)
    if not folder.exists() or not folder.is_dir():
        return jsonify({"templates": [], "library_dir": str(folder)}), 200

    out = []
    for p in sorted(folder.glob("*.json")):
        if p.name.startswith("."):
            continue
        out.append(p.name)

    return jsonify({"templates": out, "library_dir": str(folder)}), 200


@tools_bp.route("/api/template-editor/new", methods=["GET"])
def api_template_editor_new():
    modality = (request.args.get("modality") or "").strip().lower()
    schema_version = (request.args.get("schema_version") or "stable").strip()
    if modality not in {"survey", "biometrics"}:
        return jsonify({"error": "Invalid modality"}), 400

    try:
        template = _new_template_from_schema(modality=modality, schema_version=schema_version)
            
    except Exception as e:
        return jsonify({"error": str(e)}), 500

    suggested = f"{modality}-new.json"
    return jsonify({"template": template, "suggested_filename": suggested}), 200


@tools_bp.route("/api/template-editor/load", methods=["GET"])
def api_template_editor_load():
    modality = (request.args.get("modality") or "").strip().lower()
    filename = (request.args.get("filename") or "").strip()
    schema_version = (request.args.get("schema_version") or "stable").strip()
    library_path = (request.args.get("library_path") or "").strip() or None
    if modality not in {"survey", "biometrics"}:
        return jsonify({"error": "Invalid modality"}), 400
    if not filename or "/" in filename or "\\" in filename:
        return jsonify({"error": "Invalid filename"}), 400

    try:
        library_root = _resolve_library_root(library_path)
    except Exception as e:
        return jsonify({"error": str(e)}), 400

    folder = _template_dir(modality=modality, library_root=library_root)
    path = (folder / filename).resolve()
    if not str(path).startswith(str(folder.resolve())):
        return jsonify({"error": "Invalid filename"}), 400
    if not path.exists() or not path.is_file():
        return jsonify({"error": "Template not found"}), 404

    try:
        with open(path, "r", encoding="utf-8") as f:
            loaded = json.load(f)
    except Exception as e:
        return jsonify({"error": f"Could not read JSON: {e}"}), 400

    try:
        base = _new_template_from_schema(modality=modality, schema_version=schema_version)
        merged = _deep_merge(base, loaded)
    except Exception:
        merged = loaded

    return jsonify({"template": merged, "filename": filename, "library_path": str(path)}), 200


@tools_bp.route("/api/template-editor/validate", methods=["POST"])
def api_template_editor_validate():
    payload = request.get_json(silent=True) or {}
    modality = (payload.get("modality") or "").strip().lower()
    schema_version = (payload.get("schema_version") or "stable").strip()
    template = payload.get("template")

    if modality not in {"survey", "biometrics"}:
        return jsonify({"error": "Invalid modality"}), 400
    if not isinstance(template, dict):
        return jsonify({"error": "Template must be a JSON object"}), 400

    try:
        schema = _load_prism_schema(modality=modality, schema_version=schema_version)
        errors = _validate_against_schema(instance=template, schema=schema)
        return jsonify({"ok": len(errors) == 0, "errors": errors}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@tools_bp.route("/api/template-editor/schema", methods=["GET"])
def api_template_editor_schema():
    modality = (request.args.get("modality") or "").strip().lower()
    schema_version = (request.args.get("schema_version") or "stable").strip()
    if modality not in {"survey", "biometrics"}:
        return jsonify({"error": "Invalid modality"}), 400

    try:
        schema = _load_prism_schema(modality=modality, schema_version=schema_version)
        # The jsonschema Draft7Validator ignores unknown keys, but frontend tooling might not.
        # Keep schema as-is; it's useful to surface version metadata.
        return jsonify({"ok": True, "schema": schema}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@tools_bp.route("/api/template-editor/download", methods=["POST"])
def api_template_editor_download():
    payload = request.get_json(silent=True) or {}
    filename = (payload.get("filename") or "").strip()
    template = payload.get("template")

    if not filename or "/" in filename or "\\" in filename:
        return jsonify({"error": "Invalid filename"}), 400
    if not filename.lower().endswith(".json"):
        filename += ".json"
    if not isinstance(template, dict):
        return jsonify({"error": "Template must be a JSON object"}), 400

    data = json.dumps(template, indent=2, ensure_ascii=False).encode("utf-8")
    return send_file(
        io.BytesIO(data),
        mimetype="application/json",
        as_attachment=True,
        download_name=filename,
    )


@tools_bp.route("/api/template-editor/save", methods=["POST"])
def api_template_editor_save():
    payload = request.get_json(silent=True) or {}
    modality = (payload.get("modality") or "").strip().lower()
    filename = (payload.get("filename") or "").strip()
    template = payload.get("template")
    library_path = (payload.get("library_path") or "").strip() or None

    if modality not in {"survey", "biometrics"}:
        return jsonify({"error": "Invalid modality"}), 400
    if not filename or "/" in filename or "\\" in filename:
        return jsonify({"error": "Invalid filename"}), 400
    if not filename.lower().endswith(".json"):
        filename += ".json"
    if not isinstance(template, dict):
        return jsonify({"error": "Template must be a JSON object"}), 400

    try:
        library_root = _resolve_library_root(library_path)
        folder = _template_dir(modality=modality, library_root=library_root)
        folder.mkdir(parents=True, exist_ok=True)
        path = folder / filename
        
        with open(path, "w", encoding="utf-8") as f:
            json.dump(template, f, indent=2, ensure_ascii=False)
            
        return jsonify({"ok": True, "message": f"Saved to {path}"}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@tools_bp.route("/api/recipes-surveys", methods=["POST"])
def api_recipes_surveys():
    """Run survey-recipes generation inside an existing PRISM dataset."""
    try:
        from recipes_surveys import compute_survey_recipes
    except ImportError:
        compute_survey_recipes = None

    if not compute_survey_recipes:
        return jsonify({"error": "Data processing module not available"}), 500

    data = request.get_json(silent=True) or {}
    dataset_path = (data.get("dataset_path") or "").strip()
    modality = (data.get("modality") or "survey").strip().lower() or "survey"
    out_format = (data.get("format") or "csv").strip().lower() or "csv"
    survey_filter = (data.get("survey") or "").strip() or None
    lang = (data.get("lang") or "en").strip().lower() or "en"
    layout = (data.get("layout") or "long").strip().lower() or "long"
    include_raw = bool(data.get("include_raw", False))
    boilerplate = bool(data.get("boilerplate", False))

    if not dataset_path or not os.path.exists(dataset_path) or not os.path.isdir(dataset_path):
        return jsonify({"error": "Invalid dataset path"}), 400

    # Validate that the dataset is PRISM-valid. 
    # We log errors but don't block processing unless it's a critical path issue.
    from src.web import run_validation
    issues, _stats = run_validation(
        dataset_path, verbose=False, schema_version=None, run_bids=False
    )
    error_issues = [
        i for i in (issues or []) if (len(i) >= 1 and str(i[0]).upper() == "ERROR")
    ]
    
    validation_warning = None
    if error_issues:
        first = error_issues[0][1] if len(error_issues[0]) > 1 else "Dataset has validation errors"
        validation_warning = f"Dataset has {len(error_issues)} validation error(s). First: {first}"

    try:
        result = compute_survey_recipes(
            prism_root=dataset_path,
            repo_root=current_app.root_path,
            survey=survey_filter,
            out_format=out_format,
            modality=modality,
            lang=lang,
            layout=layout,
            include_raw=include_raw,
            boilerplate=boilerplate,
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
        "validation_warning": validation_warning,
        "written_files": result.written_files,
        "processed_files": result.processed_files,
        "out_format": result.out_format,
        "out_root": str(result.out_root),
        "flat_out_path": str(result.flat_out_path) if result.flat_out_path else None,
        "boilerplate_path": str(result.boilerplate_path) if result.boilerplate_path else None,
        "boilerplate_html_path": str(result.boilerplate_html_path) if result.boilerplate_html_path else None,
        "nan_report": result.nan_report,
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
    study_info = {}
    try:
        with open(full_path, "r") as jf:
            data = json.load(jf)
            study = data.get("Study", {})
            desc = study.get("Description", "")
            original_name = study.get("OriginalName", "")
            i18n = data.get("I18n", {})
            
            # Capture all study metadata for UI display
            study_info = {
                "Authors": study.get("Authors", []),
                "Citation": study.get("Citation", ""),
                "DOI": study.get("DOI", ""),
                "License": study.get("License", ""),
                "LicenseID": study.get("LicenseID", ""),
                "LicenseURL": study.get("LicenseURL", ""),
                "ItemCount": study.get("ItemCount"),
                "AgeRange": study.get("AgeRange", ""),
                "AdministrationTime": study.get("AdministrationTime", ""),
                "ScoringTime": study.get("ScoringTime", ""),
                "Norming": study.get("Norming", ""),
                "Reliability": study.get("Reliability", ""),
                "Validity": study.get("Validity", ""),
            }

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
                reserved = ["Technical", "Study", "Metadata", "Categories", "TaskName", "Name", "BIDSVersion", "Description", "URL", "License", "Authors", "Acknowledgements", "References", "Funding", "I18n", "Scoring", "Normative"]
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
        "study": study_info,
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

@tools_bp.route("/api/generate-boilerplate", methods=["POST"])
def generate_boilerplate_endpoint():
    """Generate Methods Boilerplate from selected JSON files"""
    try:
        # Add root to sys.path if needed to import from src
        root_dir = str(Path(current_app.root_path))
        if root_dir not in sys.path:
            sys.path.insert(0, root_dir)
        from src.reporting import generate_methods_text
    except ImportError:
        generate_methods_text = None

    if not generate_methods_text:
        return jsonify({"error": "Boilerplate generator not available"}), 500

    try:
        data = request.get_json()
        files = data.get("files", [])
        if not files:
            return jsonify({"error": "No files selected"}), 400

        # Extract paths from file objects
        file_paths = []
        for f in files:
            if isinstance(f, dict) and f.get("path"):
                file_paths.append(f.get("path"))
            elif isinstance(f, str):
                file_paths.append(f)

        valid_files = [f for f in file_paths if os.path.exists(f)]
        if not valid_files:
            return jsonify({"error": "No valid files found"}), 404

        fd, temp_path = tempfile.mkstemp(suffix=".md")
        os.close(fd)

        language = data.get("language", "en")
        
        # Get metadata for boilerplate
        github_url = "https://github.com/MRI-Lab-Graz/prism-studio"
        try:
            from src.schema_manager import DEFAULT_SCHEMA_VERSION
            schema_version = DEFAULT_SCHEMA_VERSION
        except ImportError:
            schema_version = "stable"

        generate_methods_text(
            valid_files, 
            temp_path, 
            lang=language,
            github_url=github_url,
            schema_version=schema_version
        )

        with open(temp_path, "r", encoding="utf-8") as f:
            md_content = f.read()
        
        html_path = Path(temp_path).with_suffix(".html")
        html_content = ""
        if html_path.exists():
            with open(html_path, "r", encoding="utf-8") as f:
                html_content = f.read()

        # Clean up
        try:
            os.remove(temp_path)
            if html_path.exists():
                os.remove(html_path)
        except:
            pass

        return jsonify({
            "md": md_content,
            "html": html_content,
            "filename_base": f"methods_boilerplate_{language}"
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500
