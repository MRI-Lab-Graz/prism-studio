"""What every template source (Excel, LimeSurvey, Pavlovia) does after it has built a template.

A source only builds the template; this step matches it against the template library, optionally
swaps in the library version, and returns the payload the Template Editor reads. A source that
does not go through here would miss the library check and the offer to share a new template.
"""

from __future__ import annotations

from src.converters.library_wording_match import apply_library_template, public_library_match
from src.converters.limesurvey import match_questionnaire_to_library
from src.prism_template_validation import strip_template_editor_internal_keys

# Top-level keys of a template that are not items.
TEMPLATE_SECTIONS = {"Technical", "Study", "Metadata", "I18n", "LimeSurvey", "Scoring", "Normative"}


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
        "languages": i18n.get("Languages") or [(template.get("Technical") or {}).get("Language", "en")],
        "library_match": public_library_match(match),
    }
