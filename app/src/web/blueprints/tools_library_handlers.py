import os
from pathlib import Path

from flask import current_app, jsonify, request, session


def handle_list_library_files_merged(extract_template_info, global_survey_library_root):
    """List JSON files from BOTH global and project libraries, merged with source tags."""
    results = {"participants": [], "survey": [], "biometrics": [], "other": []}
    sources_info = {
        "global_library_path": None,
        "project_library_path": None,
        "project_library_exists": False,
    }

    def _scan_library(library_path, source_label):
        lib_p = Path(library_path).resolve()

        participants_candidates = [lib_p / "participants.json"]
        participants_candidates.extend(
            [p / "participants.json" for p in lib_p.parents[:3]]
        )
        for p_cand in participants_candidates:
            if p_cand.exists() and p_cand.is_file():
                existing_paths = {item["path"] for item in results["participants"]}
                if str(p_cand) not in existing_paths:
                    results["participants"].append(
                        extract_template_info(
                            str(p_cand), "participants.json", source=source_label
                        )
                    )
                break

        for folder in ["survey", "biometrics"]:
            folder_path = lib_p / folder
            if folder_path.exists() and folder_path.is_dir():
                for filepath in sorted(folder_path.glob("*.json")):
                    if filepath.name.startswith("."):
                        continue
                    results[folder].append(
                        extract_template_info(
                            str(filepath), filepath.name, source=source_label
                        )
                    )

        if not (lib_p / "survey").is_dir() and not (lib_p / "biometrics").is_dir():
            for filepath in sorted(lib_p.glob("*.json")):
                if filepath.name.startswith(".") or filepath.name == "participants.json":
                    continue
                results["other"].append(
                    extract_template_info(
                        str(filepath), filepath.name, source=source_label
                    )
                )

    try:
        global_root = global_survey_library_root()
        if global_root and global_root.exists():
            sources_info["global_library_path"] = str(global_root)
            _scan_library(str(global_root), "global")

        project_path = session.get("current_project_path")
        if project_path:
            project_lib = Path(project_path) / "code" / "library"
            sources_info["project_library_path"] = str(project_lib)
            sources_info["project_library_exists"] = project_lib.exists()
            if project_lib.exists() and project_lib.is_dir():
                _scan_library(str(project_lib), "project")

        for key in results:
            by_filename = {}
            for item in results[key]:
                fn = item.get("filename", "").lower()
                if fn in by_filename:
                    existing = by_filename[fn]
                    existing["source"] = "both"
                    if item.get("source") == "project":
                        existing["path"] = item["path"]
                        existing["global_path"] = (
                            existing.get("_original_path") or existing["path"]
                        )
                        existing["project_path"] = item["path"]
                    else:
                        existing["global_path"] = item["path"]
                        existing["project_path"] = existing.get("path")
                    merged_langs = set(existing.get("detected_languages", []))
                    merged_langs.update(item.get("detected_languages", []))
                    existing["detected_languages"] = sorted(merged_langs)
                else:
                    item["_original_path"] = item["path"]
                    by_filename[fn] = item
            results[key] = sorted(
                by_filename.values(), key=lambda x: x.get("filename", "").lower()
            )
            for item in results[key]:
                item.pop("_original_path", None)

        results["sources"] = sources_info
        return jsonify(results)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


def handle_list_library_files(extract_template_info):
    """List JSON files in a user-specified library path, grouped by modality."""
    library_path = request.args.get("path")
    if not library_path:
        return jsonify({"error": "No path provided"}), 400

    path_obj = Path(library_path)
    if not path_obj.is_absolute():
        app_root = Path(current_app.root_path)
        resolved_path = (app_root / library_path).resolve()
        if resolved_path.exists() and resolved_path.is_dir():
            library_path = str(resolved_path)
        else:
            resolved_path = path_obj.resolve()
            if resolved_path.exists() and resolved_path.is_dir():
                library_path = str(resolved_path)
            else:
                return jsonify({"error": f"Path not found: {library_path}"}), 400
    elif not os.path.exists(library_path) or not os.path.isdir(library_path):
        return jsonify({"error": f"Invalid path: {library_path}"}), 400

    results = {"participants": [], "survey": [], "biometrics": [], "other": []}
    try:
        lib_p = Path(library_path).resolve()
        participants_path = None
        participants_candidates = [lib_p / "participants.json"]
        participants_candidates.extend(
            [p / "participants.json" for p in lib_p.parents[:3]]
        )

        for p_cand in participants_candidates:
            if p_cand.exists() and p_cand.is_file():
                participants_path = str(p_cand)
                break

        if participants_path:
            results["participants"].append(
                extract_template_info(participants_path, "participants.json")
            )

        for folder in ["survey", "biometrics"]:
            folder_path = os.path.join(library_path, folder)
            if os.path.exists(folder_path) and os.path.isdir(folder_path):
                for filename in os.listdir(folder_path):
                    if filename.endswith(".json") and not filename.startswith("."):
                        results[folder].append(
                            extract_template_info(
                                os.path.join(folder_path, filename), filename
                            )
                        )

        if not results["survey"] and not results["biometrics"]:
            for filename in os.listdir(library_path):
                if (
                    filename.endswith(".json")
                    and not filename.startswith(".")
                    and filename != "participants.json"
                ):
                    results["other"].append(
                        extract_template_info(
                            os.path.join(library_path, filename), filename
                        )
                    )

        return jsonify(results)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


def handle_get_library_template(template_key):
    """Fetch a library template by its key (task name)."""
    try:
        from src.converters.survey import _load_global_templates
        from src.converters.survey_templates import _load_project_templates

        key = template_key.lower().strip()

        project_path = session.get("current_project_path")
        if project_path:
            project_templates = _load_project_templates(project_path)
            if key in project_templates:
                template_data = project_templates[key]
                return jsonify(
                    {
                        "success": True,
                        "template_key": key,
                        "filename": template_data["path"].name,
                        "prism_json": template_data["json"],
                        "source": "project",
                    }
                )

        templates = _load_global_templates()
        if key not in templates:
            return (
                jsonify({"error": f"Template '{template_key}' not found in library"}),
                404,
            )

        template_data = templates[key]
        return jsonify(
            {
                "success": True,
                "template_key": key,
                "filename": template_data["path"].name,
                "prism_json": template_data["json"],
                "source": "global",
            }
        )
    except Exception as e:
        return jsonify({"error": str(e)}), 500
