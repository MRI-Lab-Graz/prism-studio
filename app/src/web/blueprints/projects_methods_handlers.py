import json
from pathlib import Path

from flask import current_app, jsonify, request


def handle_generate_methods_section(
    get_current_project,
    read_project_json,
    get_bids_file_path,
    compute_participant_stats,
):
    """Generate a publication-ready methods section from project.json metadata."""
    from src.reporting import generate_full_methods, _md_to_html
    from src.config import (
        get_effective_template_library_path,
        load_app_settings,
    )

    current = get_current_project()
    if not current.get("path"):
        return jsonify({"success": False, "error": "No project selected"}), 400

    data = request.get_json() or {}
    lang = str(data.get("language", "en") or "en").strip().lower()
    if lang not in {"en", "de"}:
        lang = "en"
    detail_level = data.get("detail_level", "standard")
    # Methods output is always generated as continuous prose.
    continuous = True

    project_path = Path(current["path"])
    project_data = read_project_json(project_path)
    if not project_data:
        return (
            jsonify(
                {
                    "success": False,
                    "error": "No project metadata available. Fill in your project.json to generate a methods section.",
                }
            ),
            404,
        )

    dataset_desc = None
    desc_path = get_bids_file_path(project_path, "dataset_description.json")
    if desc_path.exists():
        try:
            with open(desc_path, "r", encoding="utf-8") as f:
                dataset_desc = json.load(f)
        except Exception:
            pass

    task_defs = project_data.get("TaskDefinitions") or {}
    app_root = Path(current_app.root_path)
    app_settings = load_app_settings(app_root=str(app_root))
    lib_info = get_effective_template_library_path(
        str(project_path), app_settings, app_root=str(app_root)
    )

    search_dirs = []
    yoda_lib = project_path / "code" / "library"
    legacy_lib = project_path / "library"
    if yoda_lib.exists():
        search_dirs.append(yoda_lib)
    elif legacy_lib.exists():
        search_dirs.append(legacy_lib)
    ext_path = lib_info.get("effective_external_path")
    if ext_path:
        search_dirs.append(Path(ext_path))
    global_path = lib_info.get("global_library_path")
    if global_path:
        search_dirs.append(Path(global_path))

    def _candidate_template_names(task_name: str, task_definition: dict) -> list[str]:
        """Build likely template filenames from task metadata and naming conventions."""
        candidates: list[str] = []

        def _add(value: str | None) -> None:
            text = str(value or "").strip()
            if not text:
                return
            candidates.append(text)
            if not text.lower().endswith(".json"):
                candidates.append(f"{text}.json")

        tpl_filename = task_definition.get("template")
        modality = str(task_definition.get("modality") or "").strip().lower()

        _add(tpl_filename)

        if tpl_filename and modality:
            plain_name = str(tpl_filename).strip()
            if plain_name.lower().endswith(".json"):
                plain_name = plain_name[:-5]
            if plain_name and not plain_name.lower().startswith(f"{modality}-"):
                _add(f"{modality}-{plain_name}")

        normalized_names = {
            str(task_name).strip(),
            str(task_name).replace("_", "-").strip(),
            str(task_name).replace("-", "_").strip(),
        }
        normalized_names = {name for name in normalized_names if name}

        known_prefixes = [
            "survey",
            "biometrics",
            "physio",
            "eeg",
            "eyetracking",
            "func",
            "anat",
        ]
        if modality and modality not in known_prefixes:
            known_prefixes.insert(0, modality)
        elif modality:
            known_prefixes = [modality] + [p for p in known_prefixes if p != modality]

        for name in normalized_names:
            _add(name)
            for prefix in known_prefixes:
                _add(f"{prefix}-{name}")

        deduped: list[str] = []
        seen: set[str] = set()
        for candidate in candidates:
            key = candidate.casefold()
            if key in seen:
                continue
            seen.add(key)
            deduped.append(candidate)
        return deduped

    template_data = {}
    for task_name, task_definition in task_defs.items():
        template_name_candidates = _candidate_template_names(task_name, task_definition)
        if not template_name_candidates:
            continue

        for search_dir in search_dirs:
            candidate_dirs = [
                search_dir,
                search_dir / "survey",
                search_dir / "biometrics",
                search_dir / "physio",
                search_dir / "eeg",
                search_dir / "eyetracking",
                search_dir / "func",
                search_dir / "anat",
            ]
            for template_name in template_name_candidates:
                for candidate_dir in candidate_dirs:
                    candidate = candidate_dir / template_name
                    if not candidate.exists():
                        continue
                    try:
                        with open(candidate, "r", encoding="utf-8") as f:
                            template_data[task_name] = json.load(f)
                    except Exception:
                        pass
                    break
                if task_name in template_data:
                    break
            if task_name in template_data:
                break

    participant_stats = compute_participant_stats(project_path, lang=lang)

    try:
        md_text, sections_used = generate_full_methods(
            project_data,
            dataset_desc,
            template_data,
            participant_stats=participant_stats,
            lang=lang,
            detail_level=detail_level,
            continuous=continuous,
        )
        html_text = _md_to_html(md_text)
        filename_base = f"methods_section_{lang}"

        return jsonify(
            {
                "success": True,
                "md": md_text,
                "html": html_text,
                "filename_base": filename_base,
                "sections_used": sections_used,
            }
        )
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500
