"""
Survey template utilities for PRISM web interface.
"""

from __future__ import annotations
from pathlib import Path
import json


def list_survey_template_languages(
    library_path: str,
) -> tuple[list[str], str | None, int, int]:
    """Return (languages, default_language, template_count, i18n_count) from survey templates in a folder."""
    langs: set[str] = set()
    defaults: set[str] = set()
    template_count = 0
    i18n_count = 0

    try:
        root = Path(library_path).resolve()
    except Exception:
        return [], None, 0, 0

    if not root.exists() or not root.is_dir():
        return [], None, 0, 0

    for p in sorted(root.glob("survey-*.json")):
        template_count += 1
        has_i18n = False

        try:
            with open(p, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception:
            continue

        i18n = data.get("I18n")
        if isinstance(i18n, dict):
            i18n_langs = i18n.get("Languages")
            if isinstance(i18n_langs, list) and len(i18n_langs) > 0:
                has_i18n = True
                for v in i18n_langs:
                    if isinstance(v, str) and v.strip():
                        langs.add(v.strip())
            d = i18n.get("DefaultLanguage")
            if isinstance(d, str) and d.strip():
                defaults.add(d.strip())

        tech = data.get("Technical")
        if isinstance(tech, dict):
            tl = tech.get("Language")
            if isinstance(tl, str) and tl.strip():
                langs.add(tl.strip())

        if has_i18n:
            i18n_count += 1

    default = None
    if len(defaults) == 1:
        default = next(iter(defaults))

    return sorted(list(langs)), default, template_count, i18n_count
