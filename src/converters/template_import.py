"""What every template source (Excel, LimeSurvey, Pavlovia) does after it has built a template.

A source only builds the template; this step matches it against the template library, optionally
swaps in the library version, and returns the payload the Template Editor reads. A source that
does not go through here would miss the library check and the offer to share a new template.
"""

from __future__ import annotations

import unicodedata
from pathlib import Path

from src.converters.library_wording_match import apply_library_template, public_library_match
from src.item_map import save_item_map, template_items
from src.utils.naming import sanitize_task_name
from src.prism_template_validation import strip_template_editor_internal_keys

# Top-level keys of a template that are not items.
TEMPLATE_SECTIONS = {"Technical", "Study", "Metadata", "I18n", "LimeSurvey", "Scoring", "Normative"}


def task_name(name):
    """File-safe Study.TaskName for a human name. Transliterates first: sanitize_task_name
    drops non-ASCII ("Händigkeit" -> "hndigkeit")."""
    ascii_name = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode()
    return sanitize_task_name(ascii_name) or "imported"


def _describe_library_match(name, match):
    if not match:
        return f"[PRISM] Library match for '{name}': none"
    changed = [f"{a}->{b}" for a, b in match["id_map"].items() if a != b]
    ids = "IDs identical" if not changed else f"IDs differ ({', '.join(changed[:3])}{', ...' if len(changed) > 3 else ''})"
    levels = "levels equal" if match["levels_ok"] else "levels DIFFER"
    return (
        f"[PRISM] Library match for '{name}': {match['template_key']} ({match['source']}) "
        f"{match['confidence']} — {match['paired']}/{match['imported_items']} items paired, {levels}, {ids}"
    )


def match_questionnaire_to_library(template, name, project_path=None):
    """Best library match for one imported questionnaire; logs, never raises."""
    try:
        from src.converters.library_wording_match import best_library_match

        match = best_library_match(template, project_path)
    except Exception as exc:  # a library problem must not block a plain import
        print(f"[PRISM] Library match skipped: {exc}")
        return None
    print(_describe_library_match(name, match))
    return match


def finish_import(template, name, project_path=None, use_library=False, notes=(), rename=None):
    """Payload for one imported template.

    ``name`` labels the terminal log; ``notes`` (what the source could not represent) are printed
    and returned for the preview. With ``use_library`` the matching library template (the
    imported item codes saved in the project item map) is returned instead; ValueError if it cannot be
    adopted or there is no project to hold the map.
    ``rename`` replaces the source's name (e.g. a LimeSurvey group called "Part 2"): it becomes
    ``Study.OriginalName`` and, sanitized, ``Study.TaskName`` and so the file name.
    """
    rename = (rename or "").strip()
    if rename and use_library:
        raise ValueError("rename cannot be combined with the library template (it keeps its own name)")
    if rename:
        template["Study"]["OriginalName"] = rename
        template["Study"]["TaskName"] = task_name(rename)
    if use_library and not project_path:
        raise ValueError(
            "Using a library template saves the survey's item codes in the project item map, "
            "so a project is needed (--project)"
        )
    for note in notes:
        print(f"[PRISM] WARNING {note}")
    match = match_questionnaire_to_library(template, name, project_path)
    item_map = None
    if use_library:
        template = apply_library_template(match)
        filename = match["template_file"]
        # Library templates mostly have no Study.TaskName: the file name (survey-<task>.json) names the task.
        task = (template.get("Study") or {}).get("TaskName") or task_name(Path(filename).stem.removeprefix("survey-"))
        # {library item: survey column}; identical codes need no entry
        mapping = {lib: imp for imp, lib in match["id_map"].items() if imp != lib}
        saved = save_item_map(project_path, task, mapping, template_items(template)) if mapping else None
        if saved:
            item_map = {"task": task, "path": Path(saved).relative_to(project_path).as_posix(), "entries": len(mapping)}
        print(f"[PRISM] Using library template '{match['template_key']}' ({match['source']}): "
              f"{len(mapping)} item code(s) saved to the project item map")
    else:
        filename = f"survey-{template['Study']['TaskName']}.json"
    template = strip_template_editor_internal_keys(template)
    i18n = template.get("I18n") or {}
    return {
        "template": template,
        "suggested_filename": filename,
        "item_count": len([key for key in template if key not in TEMPLATE_SECTIONS]),
        "languages": i18n.get("Languages") or [lang for lang in [(template.get("Technical") or {}).get("Language")] if lang],
        "library_match": public_library_match(match),
        "notes": list(notes),
        "item_map": item_map,
    }
