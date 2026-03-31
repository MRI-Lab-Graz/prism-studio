import io
import json
import os
from pathlib import Path

from flask import (
    Blueprint,
    current_app,
    jsonify,
    render_template,
    request,
    send_file,
    session,
)

from src.config import load_config
from src.survey_scale_inference import apply_implicit_numeric_level_ranges
from src.utils.io import dump_json_text
from .tools_helpers import (
    _global_survey_library_root,
    _load_prism_schema,
    _new_template_from_schema,
    _project_template_folder,
    _resolve_library_root,
    _strip_template_editor_internal_keys,
    _template_dir,
    _validate_against_schema,
)

tools_template_editor_bp = Blueprint("tools_template_editor", __name__)


def _autofill_single_version_variant_ids(template: dict) -> dict:
    """Fill empty VariantID values when the template has exactly one version."""
    if not isinstance(template, dict):
        return template

    study = template.get("Study")
    if not isinstance(study, dict):
        return template

    versions = [
        str(v).strip()
        for v in (study.get("Versions") or [])
        if isinstance(v, str) and str(v).strip()
    ]
    fallback_version = ""
    if len(versions) == 1:
        fallback_version = versions[0]
    elif len(versions) == 0:
        singular = study.get("Version")
        if isinstance(singular, str) and singular.strip():
            fallback_version = singular.strip()

    if not fallback_version:
        return template

    variant_defs = study.get("VariantDefinitions")
    if isinstance(variant_defs, list):
        for entry in variant_defs:
            if (
                isinstance(entry, dict)
                and not str(entry.get("VariantID") or "").strip()
            ):
                entry["VariantID"] = fallback_version

    for key, value in template.items():
        if key in {
            "Technical",
            "Study",
            "Metadata",
            "I18n",
            "LimeSurvey",
            "Scoring",
            "Normative",
        }:
            continue
        if not isinstance(value, dict):
            continue
        variant_scales = value.get("VariantScales")
        if not isinstance(variant_scales, list):
            continue
        for entry in variant_scales:
            if (
                isinstance(entry, dict)
                and not str(entry.get("VariantID") or "").strip()
            ):
                entry["VariantID"] = fallback_version

    return template


def _is_blank_localized_value(value) -> bool:
    if value is None:
        return True
    if isinstance(value, str):
        return not value.strip()
    if isinstance(value, dict):
        return all(_is_blank_localized_value(v) for v in value.values())
    if isinstance(value, list):
        return all(_is_blank_localized_value(v) for v in value)
    return False


def _is_empty_variant_definition_placeholder(entry: object) -> bool:
    if not isinstance(entry, dict):
        return False

    variant_id = str(entry.get("VariantID") or "").strip()
    item_count = entry.get("ItemCount")
    scale_type = str(entry.get("ScaleType") or "").strip().lower()
    description = entry.get("Description")
    extra_keys = set(entry.keys()) - {
        "VariantID",
        "ItemCount",
        "ScaleType",
        "Description",
    }

    return (
        not variant_id
        and item_count in {None, "", 0}
        and scale_type in {"", "likert"}
        and _is_blank_localized_value(description)
        and all(_is_blank_localized_value(entry.get(key)) for key in extra_keys)
    )


def _prune_optional_variant_placeholders(template: dict) -> dict:
    if not isinstance(template, dict):
        return template

    study = template.get("Study")
    if not isinstance(study, dict):
        return template

    versions = [
        str(value).strip()
        for value in (study.get("Versions") or [])
        if isinstance(value, str) and str(value).strip()
    ]
    has_multiple_versions = len(versions) > 1
    variant_definitions = study.get("VariantDefinitions")

    if not isinstance(variant_definitions, list):
        return template

    filtered_definitions = []
    for entry in variant_definitions:
        if not has_multiple_versions and _is_empty_variant_definition_placeholder(
            entry
        ):
            continue
        filtered_definitions.append(entry)

    if filtered_definitions:
        study["VariantDefinitions"] = filtered_definitions
    else:
        study.pop("VariantDefinitions", None)

    return template


def _normalize_template_for_validation(*, modality: str, template: dict) -> dict:
    template = _strip_template_editor_internal_keys(template)
    if modality == "survey":
        template = _autofill_single_version_variant_ids(template)
        template = _prune_optional_variant_placeholders(template)
        template = apply_implicit_numeric_level_ranges(template)
    return template


@tools_template_editor_bp.route("/template-editor")
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


@tools_template_editor_bp.route("/api/template-editor/list-merged", methods=["GET"])
def api_template_editor_list_merged():
    """List templates from both global and project libraries with source indicators."""
    modality = (request.args.get("modality") or "").strip().lower()
    schema_version = (request.args.get("schema_version") or "stable").strip()
    if modality not in {"survey", "biometrics"}:
        return jsonify({"error": "Invalid modality"}), 400

    project_path = session.get("current_project_path")

    templates = {}
    sources_info = {
        "global_library_path": None,
        "project_library_path": None,
        "project_library_exists": False,
    }

    schema = None
    try:
        schema = _load_prism_schema(modality=modality, schema_version=schema_version)
    except Exception:
        schema = None

    def _build_validation_status(template_path: Path) -> dict:
        if schema is None:
            return {
                "template_valid": None,
                "validation_error_count": 0,
                "validation_error": None,
            }

        try:
            with open(template_path, "r", encoding="utf-8") as f:
                payload = json.load(f)
        except Exception as exc:
            return {
                "template_valid": False,
                "validation_error_count": 1,
                "validation_error": f"Invalid JSON: {exc}",
            }

        try:
            payload = _normalize_template_for_validation(
                modality=modality, template=payload
            )
            errors = _validate_against_schema(instance=payload, schema=schema)
        except Exception as exc:
            return {
                "template_valid": False,
                "validation_error_count": 1,
                "validation_error": f"Validation failed: {exc}",
            }

        return {
            "template_valid": len(errors) == 0,
            "validation_error_count": len(errors),
            "validation_error": (errors[0].get("message") if errors else None),
        }

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
                    **_build_validation_status(p),
                }

    if project_path and Path(project_path).exists():
        project_config = load_config(project_path)
        if project_config.template_library_path:
            external_lib = Path(project_config.template_library_path)
            if external_lib.exists():
                external_folder = external_lib / modality
                if external_folder.exists() and external_folder.is_dir():
                    for p in sorted(external_folder.glob("*.json")):
                        if p.name.startswith("."):
                            continue
                        templates[p.name] = {
                            "filename": p.name,
                            "source": "project-external",
                            "path": str(p),
                            "readonly": True,
                            **_build_validation_status(p),
                        }

        project_library_root = Path(project_path) / "code" / "library"
        sources_info["project_library_path"] = str(project_library_root)
        sources_info["project_library_exists"] = project_library_root.exists()
        project_lib = project_library_root / modality
        if project_lib.exists() and project_lib.is_dir():
            for p in sorted(project_lib.glob("*.json")):
                if p.name.startswith("."):
                    continue
                templates[p.name] = {
                    "filename": p.name,
                    "source": "project",
                    "path": str(p),
                    "readonly": False,
                    **_build_validation_status(p),
                }

    template_list = sorted(templates.values(), key=lambda x: x["filename"].lower())

    return (
        jsonify(
            {
                "templates": template_list,
                "sources": sources_info,
                "has_global": sources_info["global_library_path"] is not None,
                "has_project": project_path is not None,
            }
        ),
        200,
    )


@tools_template_editor_bp.route("/api/template-editor/new", methods=["GET"])
def api_template_editor_new():
    modality = (request.args.get("modality") or "").strip().lower()
    schema_version = (request.args.get("schema_version") or "stable").strip()
    if modality not in {"survey", "biometrics"}:
        return jsonify({"error": "Invalid modality"}), 400

    try:
        template = _new_template_from_schema(
            modality=modality, schema_version=schema_version
        )

    except Exception as e:
        return jsonify({"error": str(e)}), 500

    suggested = f"{modality}-new.json"
    return jsonify({"template": template, "suggested_filename": suggested}), 200


@tools_template_editor_bp.route("/api/template-editor/load", methods=["GET"])
def api_template_editor_load():
    modality = (request.args.get("modality") or "").strip().lower()
    filename = (request.args.get("filename") or "").strip()
    library_path = (request.args.get("library_path") or "").strip() or None
    absolute_path = (request.args.get("absolute_path") or "").strip() or None
    if modality not in {"survey", "biometrics"}:
        return jsonify({"error": "Invalid modality"}), 400
    if not filename or "/" in filename or "\\" in filename:
        return jsonify({"error": "Invalid filename"}), 400

    # Fast path: the list-merged API already resolved the exact file path; use it directly.
    if absolute_path:
        path = Path(absolute_path).resolve()
        if path.name != filename:
            return jsonify({"error": "Filename mismatch"}), 400
        if not path.exists() or not path.is_file():
            return jsonify({"error": "Template not found"}), 404
    else:
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

    return (
        jsonify({"template": loaded, "filename": filename, "library_path": str(path)}),
        200,
    )


@tools_template_editor_bp.route("/api/template-editor/validate", methods=["POST"])
def api_template_editor_validate():
    payload = request.get_json(silent=True) or {}
    modality = (payload.get("modality") or "").strip().lower()
    schema_version = (payload.get("schema_version") or "stable").strip()
    template = payload.get("template")

    if modality not in {"survey", "biometrics"}:
        return jsonify({"error": "Invalid modality"}), 400
    if not isinstance(template, dict):
        return jsonify({"error": "Template must be a JSON object"}), 400

    template = _normalize_template_for_validation(modality=modality, template=template)

    try:
        schema = _load_prism_schema(modality=modality, schema_version=schema_version)
        errors = _validate_against_schema(instance=template, schema=schema)

        lang_warnings = []
        try:
            from src.template_validator import TemplateValidator

            lang_warnings = TemplateValidator.validate_language_consistency_from_data(
                template, file_name="template"
            )
        except Exception:
            pass

        return (
            jsonify(
                {
                    "ok": len(errors) == 0,
                    "errors": errors,
                    "language_warnings": lang_warnings,
                }
            ),
            200,
        )
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@tools_template_editor_bp.route("/api/template-editor/schema", methods=["GET"])
def api_template_editor_schema():
    modality = (request.args.get("modality") or "").strip().lower()
    schema_version = (request.args.get("schema_version") or "stable").strip()
    if modality not in {"survey", "biometrics"}:
        return jsonify({"error": "Invalid modality"}), 400

    try:
        schema = _load_prism_schema(modality=modality, schema_version=schema_version)
        return jsonify({"ok": True, "schema": schema}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@tools_template_editor_bp.route("/api/template-editor/download", methods=["POST"])
def api_template_editor_download():
    payload = request.get_json(silent=True) or {}
    modality = (payload.get("modality") or "").strip().lower()
    filename = (payload.get("filename") or "").strip()
    template = payload.get("template")

    if not filename or "/" in filename or "\\" in filename:
        return jsonify({"error": "Invalid filename"}), 400
    if not filename.lower().endswith(".json"):
        filename += ".json"
    if not isinstance(template, dict):
        return jsonify({"error": "Template must be a JSON object"}), 400

    template = _strip_template_editor_internal_keys(template)
    if modality in {"survey", "biometrics"}:
        template = _normalize_template_for_validation(
            modality=modality, template=template
        )

    data = dump_json_text(template).encode("utf-8")
    return send_file(
        io.BytesIO(data),
        mimetype="application/json",
        as_attachment=True,
        download_name=filename,
    )


@tools_template_editor_bp.route("/api/template-editor/save", methods=["POST"])
def api_template_editor_save():
    payload = request.get_json(silent=True) or {}
    modality = (payload.get("modality") or "").strip().lower()
    schema_version = (payload.get("schema_version") or "stable").strip()
    filename = (payload.get("filename") or "").strip()
    template = payload.get("template")

    if modality not in {"survey", "biometrics"}:
        return jsonify({"error": "Invalid modality"}), 400
    if not filename or "/" in filename or "\\" in filename:
        return jsonify({"error": "Invalid filename"}), 400
    if not filename.lower().endswith(".json"):
        filename += ".json"
    if not isinstance(template, dict):
        return jsonify({"error": "Template must be a JSON object"}), 400

    template = _normalize_template_for_validation(modality=modality, template=template)

    try:
        schema = _load_prism_schema(modality=modality, schema_version=schema_version)
        errors = _validate_against_schema(instance=template, schema=schema)
        if errors:
            return (
                jsonify(
                    {
                        "error": "Template validation failed",
                        "errors": errors,
                    }
                ),
                400,
            )

        folder = _project_template_folder(modality=modality)
        folder.mkdir(parents=True, exist_ok=True)
        path = folder / filename

        with open(path, "w", encoding="utf-8") as f:
            f.write(dump_json_text(template))

        return jsonify({"ok": True, "message": f"Saved to {path}"}), 200
    except RuntimeError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@tools_template_editor_bp.route("/api/template-editor/delete", methods=["DELETE"])
def api_template_editor_delete():
    """Delete a project-library template. Refuses to delete global/official templates."""
    payload = request.get_json(silent=True) or {}
    modality = (payload.get("modality") or "").strip().lower()
    filename = (payload.get("filename") or "").strip()

    if modality not in {"survey", "biometrics"}:
        return jsonify({"error": "Invalid modality"}), 400
    if not filename or "/" in filename or "\\" in filename:
        return jsonify({"error": "Invalid filename"}), 400
    if not filename.lower().endswith(".json"):
        filename += ".json"

    try:
        project_folder = _project_template_folder(modality=modality)
        target = (project_folder / filename).resolve()

        # Safety: must be inside project library — never allow deleting global templates
        if not str(target).startswith(str(project_folder.resolve())):
            return (
                jsonify(
                    {
                        "error": "Deletion is only permitted for project-library templates"
                    }
                ),
                403,
            )

        if not target.exists():
            return jsonify({"error": "Template file not found"}), 404

        target.unlink()
        return jsonify({"ok": True, "message": f"Deleted {filename}"}), 200
    except RuntimeError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@tools_template_editor_bp.route("/api/template-editor/import-lsq-lsg", methods=["POST"])
def api_template_editor_import_lsq_lsg():
    """Import a .lsq or .lsg file and return a PRISM template for the editor."""
    if "file" not in request.files:
        return jsonify({"error": "No file uploaded"}), 400

    file = request.files["file"]
    if not file.filename:
        return jsonify({"error": "No file selected"}), 400

    filename_lower = file.filename.lower()
    if filename_lower.endswith(".lsq"):
        source_type = "lsq"
    elif filename_lower.endswith(".lsg"):
        source_type = "lsg"
    else:
        return jsonify({"error": "Unsupported file type. Use .lsq or .lsg"}), 400

    try:
        xml_content = file.read()
        if not xml_content:
            return jsonify({"error": "File is empty"}), 400

        from src.converters.limesurvey import parse_lsq_xml, parse_lsg_xml

        if source_type == "lsq":
            template = parse_lsq_xml(xml_content)
        else:
            template = parse_lsg_xml(xml_content)

        if template is None:
            return jsonify({"error": "Failed to parse XML file"}), 400

        template = _strip_template_editor_internal_keys(template)

        reserved = {
            "Technical",
            "Study",
            "Metadata",
            "I18n",
            "LimeSurvey",
            "Scoring",
            "Normative",
        }
        item_keys = [k for k in template if k not in reserved]
        item_count = len(item_keys)

        languages = []
        i18n = template.get("I18n")
        if i18n and isinstance(i18n, dict):
            languages = i18n.get("Languages", [])
        if not languages:
            lang = template.get("Technical", {}).get("Language", "en")
            languages = [lang]

        task_name = template.get("Study", {}).get("TaskName", "imported")
        suggested_filename = f"survey-{task_name}.json"

        return (
            jsonify(
                {
                    "template": template,
                    "suggested_filename": suggested_filename,
                    "source_type": source_type,
                    "item_count": item_count,
                    "languages": languages,
                }
            ),
            200,
        )

    except Exception as e:
        return jsonify({"error": f"Import failed: {str(e)}"}), 500
