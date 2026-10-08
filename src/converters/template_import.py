"""What every template source (Excel, LimeSurvey, Pavlovia) does after it has built a template.

A source only builds the template; this step matches it against the template library, optionally
swaps in the library version, and returns the payload the Template Editor reads. A source that
does not go through here would miss the library check and the offer to share a new template.
"""

from __future__ import annotations

from src.converters.library_wording_match import apply_library_template, public_library_match
from src.prism_template_validation import strip_template_editor_internal_keys

# Top-level keys of a template that are not items.
TEMPLATE_SECTIONS = {"Technical", "Study", "Metadata", "I18n", "LimeSurvey", "Scoring", "Normative"}


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


def finish_import(template, name, project_path=None, use_library=False):
    """Payload for one imported template.

    ``name`` labels the terminal log. With ``use_library`` the matching library template (the
    imported item codes kept as ``Aliases``) is returned instead; ValueError if it cannot be adopted.
    """
    match = match_questionnaire_to_library(template, name, project_path)
    if use_library:
        template = apply_library_template(match)
        print(f"[PRISM] Using library template '{match['template_key']}' ({match['source']}): "
              f"{len(match['id_map'])} item code(s) kept as aliases")
        filename = match["template_file"]  # library templates have no Study.TaskName
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
    }
