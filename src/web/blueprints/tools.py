import os
import sys
import json
import io
import tempfile
import subprocess
from pathlib import Path
from datetime import date
from flask import Blueprint, render_template, request, jsonify, send_file, current_app, session
from src.config import load_app_settings, load_config

tools_bp = Blueprint("tools", __name__)


def _default_library_root_for_templates(*, modality: str) -> Path:
    candidate = _global_survey_library_root()
    if candidate:
        return candidate
    return (Path(current_app.root_path) / "survey_library").resolve()


def _global_survey_library_root() -> Path | None:
    base_dir = Path(current_app.root_path)
    app_settings = load_app_settings(app_root=str(base_dir))

    if app_settings.global_template_library_path:
        candidate = Path(app_settings.global_template_library_path).expanduser()
        if candidate.exists() and candidate.is_dir():
            return candidate

    preferred = (base_dir / "library" / "survey_i18n").resolve()
    if preferred.exists() and any(preferred.glob("survey-*.json")):
        return preferred

    fallback = (base_dir / "survey_library").resolve()
    return fallback if fallback.exists() else None


def _resolve_library_root(library_path: str | None) -> Path:
    if library_path:
        p = Path(library_path).expanduser().resolve()
        if p.exists() and p.is_dir():
            return p
        raise FileNotFoundError(f"Invalid library folder: {library_path}")
    default_root = _default_library_root_for_templates(modality="survey")
    if default_root:
        return default_root.resolve()
    raise FileNotFoundError("No default library root found")


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
    project_path = session.get("current_project_path")
    default_library_path = None
    if project_path:
        candidate = (Path(project_path) / "library").expanduser()
        if candidate.exists() and candidate.is_dir():
            default_library_path = candidate

    if default_library_path is None:
        default_library_path = _default_library_root_for_templates(modality="survey")

    return render_template(
        "survey_generator.html",
        default_survey_library_path=str(default_library_path or ""),
    )

@tools_bp.route("/converter")
def converter():
    """Converter page"""
    project_path = session.get("current_project_path")
    default_library_path = None
    if project_path:
        # Check for standard PRISM library location (code/library)
        # We also check the legacy location (library) for backward compatibility
        candidate = (Path(project_path) / "code" / "library").expanduser()
        if candidate.exists() and candidate.is_dir():
            default_library_path = candidate
        else:
            candidate = (Path(project_path) / "library").expanduser()
            if candidate.exists() and candidate.is_dir():
                default_library_path = candidate

    if default_library_path is None:
        default_library_path = _default_library_root_for_templates(modality="survey")

    return render_template(
        "converter.html",
        default_survey_library_path=str(default_library_path or ""),
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


@tools_bp.route("/api/template-editor/list-merged", methods=["GET"])
def api_template_editor_list_merged():
    """List templates from both global and project libraries with source indicators.

    Returns templates from both:
    - Global template library (read-only, admin-managed)
    - Project template library (user's own templates)

    Project templates take priority over global templates with the same name.
    """
    modality = (request.args.get("modality") or "").strip().lower()
    if modality not in {"survey", "biometrics"}:
        return jsonify({"error": "Invalid modality"}), 400

    # Get current project from session
    project_path = session.get("current_project_path")
    app_settings = load_app_settings(app_root=str(Path(current_app.root_path)))

    templates = {}  # filename -> {name, source, path}
    sources_info = {
        "global_library_path": None,
        "project_library_path": None,
    }

    # 1. Load templates from global library (configured or default survey_library)
    global_lib_candidate = _global_survey_library_root()
    global_lib_path = str(global_lib_candidate) if global_lib_candidate else None

    if global_lib_path and Path(global_lib_path).exists():
        sources_info["global_library_path"] = global_lib_path
        global_folder = Path(global_lib_path) / modality
        if global_folder.exists() and global_folder.is_dir():
            for p in sorted(global_folder.glob("*.json")):
                if p.name.startswith("."):
                    continue
                templates[p.name] = {
                    "filename": p.name,
                    "source": "global",
                    "path": str(p),
                    "readonly": True,
                }

    # 2. Load templates from project library (if project selected)
    if project_path and Path(project_path).exists():
        # Check for project-level template library override
        project_config = load_config(project_path)
        if project_config.template_library_path:
            external_lib = Path(project_config.template_library_path)
            if external_lib.exists():
                external_folder = external_lib / modality
                if external_folder.exists() and external_folder.is_dir():
                    for p in sorted(external_folder.glob("*.json")):
                        if p.name.startswith("."):
                            continue
                        # Project override takes priority over global
                        templates[p.name] = {
                            "filename": p.name,
                            "source": "project-external",
                            "path": str(p),
                            "readonly": True,  # External library is read-only
                        }

        # Project's own library folder (always writable)
        project_lib = Path(project_path) / "library" / modality
        sources_info["project_library_path"] = str(Path(project_path) / "library")
        if project_lib.exists() and project_lib.is_dir():
            for p in sorted(project_lib.glob("*.json")):
                if p.name.startswith("."):
                    continue
                # Project templates always take priority
                templates[p.name] = {
                    "filename": p.name,
                    "source": "project",
                    "path": str(p),
                    "readonly": False,
                }

    # Convert to sorted list
    template_list = sorted(templates.values(), key=lambda x: x["filename"].lower())

    return jsonify({
        "templates": template_list,
        "sources": sources_info,
        "has_global": sources_info["global_library_path"] is not None,
        "has_project": project_path is not None,
    }), 200


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


@tools_bp.route("/api/detect-columns", methods=["POST"])
def detect_columns():
    """Detect column names from uploaded file for ID column selection.

    Supports .lsa, .xlsx, .csv, .tsv files.
    Returns list of columns and suggests likely ID column.
    """
    import pandas as pd

    if "file" not in request.files:
        return jsonify({"error": "No file uploaded"}), 400

    file = request.files["file"]
    if not file.filename:
        return jsonify({"error": "No file selected"}), 400

    filename = file.filename.lower()

    try:
        columns = []

        if filename.endswith(".lsa"):
            # Extract response data from LimeSurvey archive
            import zipfile as zf_module
            import io

            file_bytes = io.BytesIO(file.read())
            try:
                with zf_module.ZipFile(file_bytes, "r") as zf:
                    # Look for response data files
                    response_files = [f for f in zf.namelist()
                                     if f.endswith(('.txt', '.csv')) and 'response' in f.lower()]
                    if not response_files:
                        # Try any txt/csv file
                        response_files = [f for f in zf.namelist()
                                         if f.endswith(('.txt', '.csv'))]

                    if response_files:
                        with zf.open(response_files[0]) as f:
                            # Try to detect delimiter
                            content = f.read().decode('utf-8', errors='replace')
                            if '\t' in content.split('\n')[0]:
                                df = pd.read_csv(io.StringIO(content), sep='\t', nrows=1)
                            else:
                                df = pd.read_csv(io.StringIO(content), nrows=1)
                            columns = list(df.columns)
            except zf_module.BadZipFile:
                return jsonify({"error": "Invalid .lsa archive"}), 400

        elif filename.endswith(".xlsx"):
            df = pd.read_excel(file, nrows=1)
            columns = list(df.columns)

        elif filename.endswith(".csv"):
            df = pd.read_csv(file, nrows=1)
            columns = list(df.columns)

        elif filename.endswith(".tsv"):
            df = pd.read_csv(file, sep='\t', nrows=1)
            columns = list(df.columns)

        else:
            return jsonify({"columns": [], "suggested_id_column": None})

        # Suggest likely ID column
        id_candidates = ["participant_id", "id", "code", "token", "subject", "sub_id", "participant"]
        suggested = None
        for col in columns:
            if col.lower() in id_candidates:
                suggested = col
                break

        return jsonify({
            "columns": columns,
            "suggested_id_column": suggested
        })

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@tools_bp.route("/api/limesurvey-to-prism", methods=["POST"])
def limesurvey_to_prism():
    """Convert LimeSurvey .lss/.lsa file to PRISM JSON sidecar(s).

    Supports three modes (via 'mode' parameter or legacy 'split_by_groups'):
    - mode=combined (default): Single combined JSON with all questions
    - mode=groups: Separate JSON per questionnaire group
    - mode=questions: Separate JSON per individual question (for template library)
    """
    try:
        from src.converters.limesurvey import (
            parse_lss_xml,
            parse_lss_xml_by_groups,
            parse_lss_xml_by_questions
        )
    except ImportError:
        try:
            sys.path.insert(0, str(Path(current_app.root_path)))
            from src.converters.limesurvey import (
                parse_lss_xml,
                parse_lss_xml_by_groups,
                parse_lss_xml_by_questions
            )
        except ImportError:
            return jsonify({"error": "LimeSurvey converter not available"}), 500

    if "file" not in request.files:
        return jsonify({"error": "No file uploaded"}), 400

    file = request.files["file"]
    if not file.filename:
        return jsonify({"error": "No file selected"}), 400

    filename = file.filename.lower()
    if not (filename.endswith(".lss") or filename.endswith(".lsa")):
        return jsonify({"error": "Please upload a .lss or .lsa file"}), 400

    task_name = request.form.get("task_name", "").strip()

    # Support both new 'mode' parameter and legacy 'split_by_groups'
    mode = request.form.get("mode", "").strip().lower()
    if not mode:
        # Legacy support
        split_by_groups = request.form.get("split_by_groups", "false").lower() == "true"
        mode = "groups" if split_by_groups else "combined"

    if mode not in ("combined", "groups", "questions"):
        return jsonify({"error": f"Invalid mode '{mode}'. Use: combined, groups, or questions"}), 400

    if not task_name:
        task_name = Path(file.filename).stem

    try:
        xml_content = None

        if filename.endswith(".lsa"):
            import zipfile as zf_module
            import io

            file_bytes = io.BytesIO(file.read())
            try:
                with zf_module.ZipFile(file_bytes, "r") as zf:
                    lss_files = [f for f in zf.namelist() if f.endswith(".lss")]
                    if not lss_files:
                        return jsonify({"error": "No .lss file found in the .lsa archive"}), 400
                    with zf.open(lss_files[0]) as f:
                        xml_content = f.read()
            except zf_module.BadZipFile:
                return jsonify({"error": "Invalid .lsa archive"}), 400
        else:
            xml_content = file.read()

        if not xml_content:
            return jsonify({"error": "Could not read file content"}), 400

        from src.converters.excel_base import sanitize_task_name

        if mode == "questions":
            # Individual question templates (for Survey & Boilerplate)
            questions = parse_lss_xml_by_questions(xml_content)

            if not questions:
                return jsonify({"error": "Failed to parse LimeSurvey structure or no questions found"}), 400

            # Organize questions by group for UI display
            by_group = {}
            for code, q_data in questions.items():
                g = q_data["group_name"]
                if g not in by_group:
                    by_group[g] = {
                        "group_order": q_data["group_order"],
                        "questions": []
                    }
                by_group[g]["questions"].append({
                    "code": code,
                    "type": q_data["question_type"],
                    "limesurvey_type": q_data["limesurvey_type"],
                    "item_count": q_data["item_count"],
                    "mandatory": q_data["mandatory"],
                    "order": q_data["question_order"]
                })

            # Sort questions within each group
            for g in by_group.values():
                g["questions"].sort(key=lambda x: x["order"])

            return jsonify({
                "success": True,
                "mode": "questions",
                "questions": questions,
                "by_group": by_group,
                "question_count": len(questions),
                "group_count": len(by_group)
            })

        elif mode == "groups":
            # Split into multiple questionnaires by group
            questionnaires = parse_lss_xml_by_groups(xml_content)

            if not questionnaires:
                return jsonify({"error": "Failed to parse LimeSurvey structure or no groups found"}), 400

            # Build response with all questionnaires
            result = {
                "success": True,
                "mode": "groups",
                "questionnaires": {},
                "questionnaire_count": len(questionnaires),
                "total_questions": 0
            }

            for name, prism_json in questionnaires.items():
                q_count = len([k for k in prism_json.keys()
                              if k not in ["Technical", "Study", "Metadata", "I18n", "Scoring", "Normative"]])
                result["questionnaires"][name] = {
                    "prism_json": prism_json,
                    "suggested_filename": f"survey-{name}.json",
                    "question_count": q_count
                }
                result["total_questions"] += q_count

            return jsonify(result)

        else:
            # Single combined JSON (default)
            prism_data = parse_lss_xml(xml_content, task_name=task_name)

            if not prism_data:
                return jsonify({"error": "Failed to parse LimeSurvey structure"}), 400

            safe_name = sanitize_task_name(task_name)
            suggested_filename = f"survey-{safe_name}.json"

            return jsonify({
                "success": True,
                "mode": "combined",
                "prism_json": prism_data,
                "suggested_filename": suggested_filename,
                "question_count": len([k for k in prism_data.keys()
                                      if k not in ["Technical", "Study", "Metadata", "I18n", "Scoring", "Normative"]])
            })

    except Exception as e:
        return jsonify({"error": str(e)}), 500


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
    from src.cross_platform import CrossPlatformFile
    from werkzeug.utils import secure_filename

    project_path = session.get("current_project_path")
    if not project_path:
        return jsonify({"success": False, "error": "No project selected"}), 400

    project_path = Path(project_path)
    if not project_path.exists():
        return jsonify({"success": False, "error": "Project path does not exist"}), 400

    data = request.get_json()
    if not data:
        return jsonify({"success": False, "error": "No data provided"}), 400

    templates = data.get("templates", [])
    if not templates:
        return jsonify({"success": False, "error": "No templates provided"}), 400

    # Create code/library/survey folder if it doesn't exist
    library_survey_path = project_path / "code" / "library" / "survey"
    library_survey_path.mkdir(parents=True, exist_ok=True)

    saved_files = []
    errors = []

    for template in templates:
        filename = template.get("filename")
        content = template.get("content")

        if not filename or content is None:
            errors.append("Invalid template entry: missing filename or content")
            continue

        # Sanitize filename
        safe_filename = secure_filename(filename)
        if not safe_filename:
            errors.append(f"Invalid filename: {filename}")
            continue

        # Ensure .json extension
        if not safe_filename.endswith(".json"):
            safe_filename += ".json"

        file_path = library_survey_path / safe_filename

        try:
            # Write the JSON file
            json_content = json.dumps(content, indent=2, ensure_ascii=False)
            CrossPlatformFile.write_text(str(file_path), json_content)
            saved_files.append({
                "filename": safe_filename,
                "path": str(file_path)
            })
        except Exception as e:
            errors.append(f"Failed to save {safe_filename}: {str(e)}")

    return jsonify({
        "success": len(saved_files) > 0,
        "saved_files": saved_files,
        "saved_count": len(saved_files),
        "library_path": str(library_survey_path),
        "errors": errors if errors else None
    })
