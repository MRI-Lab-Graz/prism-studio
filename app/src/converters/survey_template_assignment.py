"""Template copy and assignment helpers for survey conversion."""

from __future__ import annotations


def _copy_templates_to_project(
    *,
    templates: dict,
    tasks_with_data: set[str],
    dataset_root,
    language: str | None,
    technical_overrides: dict | None,
    missing_token: str,
    localize_survey_template_fn,
    inject_missing_token_fn,
    apply_technical_overrides_fn,
    write_json_fn,
) -> None:
    """Copy used templates to project's code/library/survey/ for reproducibility."""
    project_root = dataset_root
    library_dir = project_root / "code" / "library" / "survey"
    library_dir.mkdir(parents=True, exist_ok=True)

    for task in sorted(tasks_with_data):
        if task not in templates:
            continue

        template_data = templates[task]["json"]
        output_filename = f"survey-{task}.json"
        output_path = library_dir / output_filename

        if not output_path.exists():
            localized = localize_survey_template_fn(template_data, language=language)
            localized = inject_missing_token_fn(localized, token=missing_token)
            if technical_overrides:
                localized = apply_technical_overrides_fn(
                    localized, technical_overrides
                )
            write_json_fn(output_path, localized)


def _add_ls_code_aliases(
    sidecar: dict,
    imported_codes: list[str],
    *,
    non_item_toplevel_keys,
) -> None:
    """Register LS-mangled item codes as aliases in a library template."""
    from src.converters.template_matcher import _ls_normalize_code

    imported_ls_norm = {_ls_normalize_code(c): c for c in imported_codes}

    aliases = sidecar.setdefault("_aliases", {})
    reverse_aliases = sidecar.setdefault("_reverse_aliases", {})

    for lib_key in list(sidecar.keys()):
        if lib_key in non_item_toplevel_keys or not isinstance(sidecar.get(lib_key), dict):
            continue
        ls_norm = _ls_normalize_code(lib_key)
        imp_code = imported_ls_norm.get(ls_norm)
        if imp_code and imp_code != lib_key and imp_code not in aliases:
            aliases[imp_code] = lib_key
            reverse_aliases.setdefault(lib_key, []).append(imp_code)


def _add_matched_template(
    templates: dict[str, dict],
    item_to_task: dict[str, str],
    match,
    group_info: dict,
    *,
    add_ls_code_aliases_fn,
    load_global_templates_fn,
    read_json_fn,
    non_item_toplevel_keys,
) -> None:
    """Add a library-matched template to the templates and item_to_task dicts."""
    task_key = match.template_key
    if task_key in templates:
        add_ls_code_aliases_fn(templates[task_key]["json"], group_info["item_codes"])
        for code in group_info["item_codes"]:
            if code not in item_to_task:
                item_to_task[code] = task_key
        return

    template_path = None
    if match.source == "global":
        global_templates = load_global_templates_fn()
        gt = global_templates.get(task_key)
        if gt:
            template_path = gt["path"]
    elif match.source == "project":
        pass

    if template_path and template_path.exists():
        try:
            sidecar = read_json_fn(template_path)
        except Exception:
            return

        if "_aliases" not in sidecar:
            sidecar["_aliases"] = {}
        if "_reverse_aliases" not in sidecar:
            sidecar["_reverse_aliases"] = {}

        for k, v in list(sidecar.items()):
            if k in non_item_toplevel_keys or not isinstance(v, dict):
                continue
            if "Aliases" in v and isinstance(v["Aliases"], list):
                for alias in v["Aliases"]:
                    sidecar["_aliases"][alias] = k
                    sidecar["_reverse_aliases"].setdefault(k, []).append(alias)
            if "AliasOf" in v:
                target = v["AliasOf"]
                sidecar["_aliases"][k] = target
                sidecar["_reverse_aliases"].setdefault(target, []).append(k)

        add_ls_code_aliases_fn(sidecar, group_info["item_codes"])

        templates[task_key] = {
            "path": template_path,
            "json": sidecar,
            "task": task_key,
            "source": match.source,
            "global_match": task_key if match.source == "global" else None,
        }

        for k, v in sidecar.items():
            if k in non_item_toplevel_keys:
                continue
            if k not in item_to_task:
                item_to_task[k] = task_key
            if (
                isinstance(v, dict)
                and "Aliases" in v
                and isinstance(v["Aliases"], list)
            ):
                for alias in v["Aliases"]:
                    if alias not in item_to_task:
                        item_to_task[alias] = task_key

    for code in group_info["item_codes"]:
        if code not in item_to_task:
            item_to_task[code] = task_key


def _add_generated_template(
    templates: dict[str, dict],
    item_to_task: dict[str, str],
    group_name: str,
    group_info: dict,
    *,
    sanitize_task_name_fn,
) -> None:
    """Add a generated (unmatched) template from .lss parsing."""
    task_key = sanitize_task_name_fn(group_name).lower()
    if not task_key:
        task_key = group_name.lower().replace(" ", "")
    if task_key in templates:
        return

    prism_json = group_info["prism_json"]

    if "_aliases" not in prism_json:
        prism_json["_aliases"] = {}
    if "_reverse_aliases" not in prism_json:
        prism_json["_reverse_aliases"] = {}

    templates[task_key] = {
        "path": None,
        "json": prism_json,
        "task": task_key,
        "source": "generated",
        "global_match": None,
    }

    for code in group_info["item_codes"]:
        if code not in item_to_task:
            item_to_task[code] = task_key
