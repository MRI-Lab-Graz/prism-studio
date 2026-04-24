import json
import re
import logging
from datetime import date
from pathlib import Path

from flask import jsonify, request

from src.readme_generator import ReadmeGenerator

from .projects_citation_helpers import _read_citation_cff_fields
from .projects_helpers import _resolve_requested_or_current_project_root

logger = logging.getLogger(__name__)


def _normalize_semicolon_list(value):
    if isinstance(value, list):
        cleaned = [str(item).strip() for item in value if str(item).strip()]
        return "; ".join(cleaned) if cleaned else None
    if isinstance(value, str):
        return value.strip() or None
    return value


def _normalize_study_metadata_request(req: dict) -> dict:
    if not isinstance(req, dict):
        return req

    normalized = dict(req)
    recruitment = normalized.get("Recruitment")
    if isinstance(recruitment, dict):
        normalized_recruitment = dict(recruitment)
        for key in ("Method", "Location"):
            if key in normalized_recruitment:
                normalized_recruitment[key] = _normalize_semicolon_list(
                    normalized_recruitment.get(key)
                )
        normalized["Recruitment"] = normalized_recruitment

    return normalized


def _clean_metadata_text(value) -> str:
    text = str(value or "").strip()
    if not text:
        return ""

    lowered = text.lower()
    if lowered == "[object object]":
        return ""
    if (
        lowered.startswith("required.")
        or lowered.startswith("recommended.")
        or lowered.startswith("optional.")
    ):
        return ""
    return text


def _clean_metadata_list(value) -> list[str]:
    if isinstance(value, list):
        values = value
    elif value in (None, "", {}, []):
        values = []
    else:
        values = [value]

    cleaned = []
    for item in values:
        text = _clean_metadata_text(item)
        if text:
            cleaned.append(text)
    return cleaned


def _build_citation_refresh_payload(project_data: dict, dataset_desc):
    payload = dict(dataset_desc) if isinstance(dataset_desc, dict) else {}
    basics = project_data.get("Basics") if isinstance(project_data, dict) else {}
    if not isinstance(basics, dict):
        basics = {}

    name = (
        _clean_metadata_text(payload.get("Name"))
        or _clean_metadata_text(basics.get("Name"))
        or _clean_metadata_text(basics.get("DatasetName"))
        or _clean_metadata_text(project_data.get("name") if isinstance(project_data, dict) else "")
    )
    if name:
        payload["Name"] = name

    description_authors = _clean_metadata_list(payload.get("Authors"))
    basic_authors = _clean_metadata_list(basics.get("Authors"))
    if description_authors:
        payload["Authors"] = description_authors
    elif basic_authors:
        payload["Authors"] = basic_authors

    text_fallbacks = {
        "License": ("License", "license"),
        "HowToAcknowledge": ("HowToAcknowledge", "how_to_acknowledge"),
        "DatasetDOI": ("DatasetDOI", "DOI", "doi"),
        "DatasetVersion": ("DatasetVersion", "Version", "version"),
    }
    for target_key, source_keys in text_fallbacks.items():
        value = _clean_metadata_text(payload.get(target_key))
        if not value:
            for source_key in source_keys:
                value = _clean_metadata_text(basics.get(source_key))
                if value:
                    break
        if value:
            payload[target_key] = value
        else:
            payload.pop(target_key, None)

    references = _clean_metadata_list(payload.get("ReferencesAndLinks"))
    if not references:
        references = _clean_metadata_list(basics.get("ReferencesAndLinks"))
    if not references and isinstance(project_data, dict):
        references = _clean_metadata_list(project_data.get("References"))
    if references:
        payload["ReferencesAndLinks"] = references
    else:
        payload.pop("ReferencesAndLinks", None)

    keywords = _clean_metadata_list(payload.get("Keywords"))
    if not keywords:
        keywords = _clean_metadata_list(basics.get("Keywords"))
    if keywords:
        payload["Keywords"] = keywords
    else:
        payload.pop("Keywords", None)

    return payload


def handle_get_study_metadata(
    get_current_project,
    read_project_json,
    get_bids_file_path,
    editable_sections,
    compute_methods_completeness,
    auto_detect_study_hints,
):
    """Read study-level editable sections from project.json with completeness info."""
    project_path, error_message, status_code = (
        _resolve_requested_or_current_project_root(
            get_current_project,
            request.args.get("project_path"),
        )
    )
    if project_path is None:
        return jsonify({"success": False, "error": error_message}), status_code

    data = read_project_json(project_path)
    if not data:
        return jsonify({"success": False, "error": "project.json not found"}), 404

    study_metadata = {}
    for key in editable_sections:
        study_metadata[key] = data.get(key, {})

    dataset_desc = None
    desc_path = get_bids_file_path(project_path, "dataset_description.json")
    if desc_path.exists():
        try:
            with open(desc_path, "r", encoding="utf-8") as f:
                dataset_desc = json.load(f)
        except Exception:
            pass

    if dataset_desc:
        citation_fields = _read_citation_cff_fields(project_path / "CITATION.cff")
        if citation_fields:
            for key in ("Authors", "License", "HowToAcknowledge", "ReferencesAndLinks"):
                if not dataset_desc.get(key) and citation_fields.get(key):
                    dataset_desc[key] = citation_fields[key]

    completeness = compute_methods_completeness(data, dataset_desc)
    hints = auto_detect_study_hints(project_path, data)

    return jsonify(
        {
            "success": True,
            "study_metadata": study_metadata,
            "completeness": completeness,
            "hints": hints,
            "has_sessions": len(data.get("Sessions", [])) > 0,
            "has_tasks": len(data.get("TaskDefinitions", {})) > 0,
        }
    )


def handle_save_study_metadata(
    get_current_project,
    read_project_json,
    write_project_json,
    get_bids_file_path,
    editable_sections,
    compute_methods_completeness,
    project_manager,
):
    """Save study-level editable sections to project.json, preserving other keys."""
    req = request.get_json()
    if not req:
        return jsonify({"success": False, "error": "No data provided"}), 400
    req = _normalize_study_metadata_request(req)

    project_path, error_message, status_code = (
        _resolve_requested_or_current_project_root(
            get_current_project,
            req.get("project_path"),
        )
    )
    if project_path is None:
        return jsonify({"success": False, "error": error_message}), status_code

    data = read_project_json(project_path)
    if not data:
        return jsonify({"success": False, "error": "project.json not found"}), 404

    for key in editable_sections:
        if key in req:
            data[key] = req[key]

    meta = data.get("Metadata")
    if isinstance(meta, dict):
        meta["LastModified"] = date.today().isoformat()

    write_project_json(project_path, data)

    dataset_desc = None
    desc_path = get_bids_file_path(project_path, "dataset_description.json")
    if desc_path.exists():
        try:
            with open(desc_path, "r", encoding="utf-8") as f:
                dataset_desc = json.load(f)
        except Exception:
            pass

    citation_fields = _read_citation_cff_fields(project_path / "CITATION.cff")
    if dataset_desc and citation_fields:
        for key in ("Authors", "License", "HowToAcknowledge", "ReferencesAndLinks"):
            if not dataset_desc.get(key) and citation_fields.get(key):
                dataset_desc[key] = citation_fields[key]

    citation_payload = _build_citation_refresh_payload(data, dataset_desc)
    if citation_fields:
        for key in ("Authors", "License", "HowToAcknowledge", "ReferencesAndLinks"):
            if not citation_payload.get(key) and citation_fields.get(key):
                citation_payload[key] = citation_fields[key]

    if citation_payload:
        try:
            project_manager.update_citation_cff(project_path, citation_payload)
        except Exception as e:
            logger.warning(
                "Could not refresh CITATION.cff after study metadata save: %s", e
            )

    completeness = compute_methods_completeness(data, dataset_desc)

    return jsonify(
        {
            "success": True,
            "message": "Study metadata saved",
            "completeness": completeness,
        }
    )


def handle_get_procedure_status(get_current_project, read_project_json):
    """Completeness check: declared sessions/tasks vs. data on disk."""
    current = get_current_project()
    if not current.get("path"):
        return jsonify({"success": False, "error": "No project selected"}), 400

    project_path = Path(current["path"])
    data = read_project_json(project_path)
    sessions = data.get("Sessions", [])

    if not sessions:
        return jsonify(
            {
                "success": True,
                "status": "empty",
                "message": "No sessions declared in project.json",
                "declared": [],
                "on_disk": [],
                "missing": [],
                "undeclared": [],
            }
        )

    declared = set()
    for s in sessions:
        sid = s.get("id", "")
        for t in s.get("tasks", []):
            declared.add((sid, t.get("task", "")))

    dataset_root = project_path
    on_disk = set()
    if dataset_root.is_dir():
        for sub_dir in dataset_root.iterdir():
            if not sub_dir.is_dir() or not sub_dir.name.startswith("sub-"):
                continue
            for ses_dir in sub_dir.iterdir():
                if not ses_dir.is_dir() or not ses_dir.name.startswith("ses-"):
                    continue
                ses_id = ses_dir.name
                for mod_dir in ses_dir.iterdir():
                    if not mod_dir.is_dir():
                        continue
                    for f in mod_dir.iterdir():
                        if f.is_file() and "_task-" in f.name:
                            m = re.search(r"_task-([a-zA-Z0-9]+)", f.name)
                            if m:
                                on_disk.add((ses_id, m.group(1)))

    missing = sorted(declared - on_disk)
    undeclared = sorted(on_disk - declared)

    return jsonify(
        {
            "success": True,
            "status": "ok" if not missing and not undeclared else "mismatch",
            "declared": sorted(declared),
            "on_disk": sorted(on_disk),
            "missing": [{"session": s, "task": t} for s, t in missing],
            "undeclared": [{"session": s, "task": t} for s, t in undeclared],
        }
    )


def handle_generate_readme(get_current_project):
    """Generate README.md from project.json study metadata."""
    payload = request.get_json(silent=True) or {}
    project_path, error_message, status_code = (
        _resolve_requested_or_current_project_root(
            get_current_project,
            payload.get("project_path"),
        )
    )
    if project_path is None:
        return jsonify({"success": False, "error": error_message}), status_code

    if not (project_path / "project.json").exists():
        return jsonify({"success": False, "error": "project.json not found"}), 404

    try:
        generator = ReadmeGenerator(project_path)
        output_path = generator.save()

        message = "README.md generated successfully"
        merge_note = generator.merge_note
        if merge_note:
            message = f"README.md generated and updated. {merge_note}"

        return jsonify(
            {
                "success": True,
                "message": message,
                "path": str(output_path),
                "merge_note": merge_note,
            }
        )
    except Exception as e:
        logger.error(f"README generation error: {str(e)}", exc_info=True)
        return jsonify({"success": False, "error": str(e)}), 500


def handle_preview_readme(get_current_project):
    """Preview README.md content without saving."""
    project_path, error_message, status_code = (
        _resolve_requested_or_current_project_root(
            get_current_project,
            request.args.get("project_path"),
        )
    )
    if project_path is None:
        return jsonify({"success": False, "error": error_message}), status_code

    if not (project_path / "project.json").exists():
        return jsonify({"success": False, "error": "project.json not found"}), 404

    try:
        generator = ReadmeGenerator(project_path)
        content = generator.generate()

        return jsonify(
            {
                "success": True,
                "content": content,
            }
        )
    except Exception as e:
        logger.error(f"README preview error: {str(e)}", exc_info=True)
        return jsonify({"success": False, "error": str(e)}), 500
