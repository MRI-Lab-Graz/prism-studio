"""Template loading and preprocessing helpers for survey conversion."""

from __future__ import annotations

from pathlib import Path


def _load_and_preprocess_templates(
    library_dir: Path,
    canonical_aliases: dict[str, list[str]] | None,
    compare_with_global: bool = True,
    *,
    load_global_library_path_fn,
    load_global_templates_fn,
    is_participant_template_fn,
    read_json_fn,
    canonicalize_template_items_fn,
    non_item_toplevel_keys,
    find_matching_global_template_fn,
) -> tuple[
    dict[str, dict],
    dict[str, str],
    dict[str, set[str]],
    dict[str, list[str]],
]:
    """Load and prepare survey templates from library."""
    templates: dict[str, dict] = {}
    item_to_task: dict[str, str] = {}
    duplicates: dict[str, set[str]] = {}
    template_warnings_by_task: dict[str, list[str]] = {}

    global_templates: dict[str, dict] = {}
    global_library_path = load_global_library_path_fn()
    is_using_global_library = False

    if compare_with_global and global_library_path:
        try:
            if library_dir.resolve() == global_library_path.resolve():
                is_using_global_library = True
            else:
                global_templates = load_global_templates_fn()
        except Exception:
            pass

    for json_path in sorted(library_dir.glob("survey-*.json")):
        if is_participant_template_fn(json_path):
            continue
        try:
            sidecar = read_json_fn(json_path)
        except Exception:
            continue

        task_from_name = json_path.stem.replace("survey-", "")
        task = str(sidecar.get("Study", {}).get("TaskName") or task_from_name).strip()
        task_norm = task.lower() or task_from_name.lower()

        print(f"[PRISM DEBUG] Loading template: {json_path} (task: {task_norm})")

        if canonical_aliases:
            sidecar = canonicalize_template_items_fn(
                sidecar=sidecar, canonical_aliases=canonical_aliases
            )

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

            has_levels = isinstance(v.get("Levels"), dict)
            has_range = "MinValue" in v or "MaxValue" in v
            if has_levels and has_range:
                template_warnings_by_task.setdefault(task_norm, []).append(
                    f"Template '{task_norm}' item '{k}' defines both Levels and Min/Max; numeric range takes precedence and Levels will be treated as labels only."
                )

        template_source = "project"
        global_match_task = None
        if is_using_global_library:
            template_source = "global"
        elif global_templates:
            matched_task, is_exact, only_project, only_global = (
                find_matching_global_template_fn(sidecar, global_templates)
            )
            if matched_task:
                global_match_task = matched_task
                if is_exact:
                    template_source = "global"
                else:
                    template_source = "modified"
                    diff_parts = []
                    if only_project:
                        diff_parts.append(
                            f"added: {', '.join(sorted(list(only_project)[:5]))}"
                        )
                        if len(only_project) > 5:
                            diff_parts[-1] += f" (+{len(only_project) - 5} more)"
                    if only_global:
                        diff_parts.append(
                            f"removed: {', '.join(sorted(list(only_global)[:5]))}"
                        )
                        if len(only_global) > 5:
                            diff_parts[-1] += f" (+{len(only_global) - 5} more)"
                    template_warnings_by_task.setdefault(task_norm, []).append(
                        f"Template '{task_norm}' differs from global '{matched_task}': {'; '.join(diff_parts)}"
                    )

        templates[task_norm] = {
            "path": json_path,
            "json": sidecar,
            "task": task_norm,
            "source": template_source,
            "global_match": global_match_task,
        }

        for k, v in sidecar.items():
            if k in non_item_toplevel_keys:
                continue
            if k in item_to_task and item_to_task[k] != task_norm:
                duplicates.setdefault(k, set()).update({item_to_task[k], task_norm})
            else:
                item_to_task[k] = task_norm
            if (
                isinstance(v, dict)
                and "Aliases" in v
                and isinstance(v["Aliases"], list)
            ):
                for alias in v["Aliases"]:
                    if alias in item_to_task and item_to_task[alias] != task_norm:
                        duplicates.setdefault(alias, set()).update(
                            {item_to_task[alias], task_norm}
                        )
                    else:
                        item_to_task[alias] = task_norm

    return templates, item_to_task, duplicates, template_warnings_by_task
