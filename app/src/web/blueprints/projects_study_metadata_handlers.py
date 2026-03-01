import json
import re
import logging
from datetime import date
from pathlib import Path

from flask import jsonify, request

from src.readme_generator import ReadmeGenerator

from .projects_citation_helpers import _read_citation_cff_fields

logger = logging.getLogger(__name__)


def handle_get_study_metadata(
    get_current_project,
    read_project_json,
    get_bids_file_path,
    editable_sections,
    compute_methods_completeness,
    auto_detect_study_hints,
):
    """Read study-level editable sections from project.json with completeness info."""
    current = get_current_project()
    if not current.get("path"):
        return jsonify({"success": False, "error": "No project selected"}), 400

    project_path = Path(current["path"])
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
    current = get_current_project()
    if not current.get("path"):
        return jsonify({"success": False, "error": "No project selected"}), 400

    req = request.get_json()
    if not req:
        return jsonify({"success": False, "error": "No data provided"}), 400

    project_path = Path(current["path"])
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

    if dataset_desc:
        citation_fields = _read_citation_cff_fields(project_path / "CITATION.cff")
        if citation_fields:
            for key in ("Authors", "License", "HowToAcknowledge", "ReferencesAndLinks"):
                if not dataset_desc.get(key) and citation_fields.get(key):
                    dataset_desc[key] = citation_fields[key]

        try:
            project_manager.update_citation_cff(project_path, dataset_desc)
        except Exception as e:
            logger.warning("Could not refresh CITATION.cff after study metadata save: %s", e)

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
    current = get_current_project()
    if not current.get("path"):
        return jsonify({"success": False, "error": "No project selected"}), 400

    project_path = Path(current["path"])
    if not (project_path / "project.json").exists():
        return jsonify({"success": False, "error": "project.json not found"}), 404

    try:
        generator = ReadmeGenerator(project_path)
        output_path = generator.save()

        return jsonify(
            {
                "success": True,
                "message": "README.md generated successfully",
                "path": str(output_path),
            }
        )
    except Exception as e:
        logger.error(f"README generation error: {str(e)}", exc_info=True)
        return jsonify({"success": False, "error": str(e)}), 500


def handle_preview_readme(get_current_project):
    """Preview README.md content without saving."""
    current = get_current_project()
    if not current.get("path"):
        return jsonify({"success": False, "error": "No project selected"}), 400

    project_path = Path(current["path"])
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
