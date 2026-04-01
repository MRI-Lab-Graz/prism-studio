"""Helpers for reading canonical study-level metadata from PRISM survey templates.

Canonical field names (introduced in schema v0.2):
  - ``Study.ShortName``   (was ``Study.Abbreviation``)
  - ``Study.ItemCount``   (was ``Study.NumberOfItems``)

Both legacy and canonical keys are supported for backward compatibility with
project-local templates that have not yet been migrated.
"""

from __future__ import annotations

from typing import Any


def get_study_short_name(study: dict[str, Any], language: str | None = None) -> str:
    """Return the short name / abbreviation for a survey.

    Prefers the canonical ``ShortName`` key; falls back to legacy ``Abbreviation``.
    If ``ShortName`` is a translation dict, *language* (default ``"en"``) is used.

    Args:
        study: The ``Study`` sub-dict of a PRISM survey template.
        language: BCP-47 language tag for i18n lookups, e.g. ``"en"`` or ``"de"``.

    Returns:
        The short name string, or ``""`` if absent.
    """
    value = study.get("ShortName") or study.get("Abbreviation")
    if not value:
        return ""
    if isinstance(value, dict):
        lang = language or "en"
        return str(value.get(lang) or value.get("en") or next(iter(value.values()), ""))
    return str(value)


def get_template_item_count(template: dict[str, Any]) -> int | None:
    """Return the declared or derived item count for a survey template.

    Resolution order:
    1. ``Study.ItemCount``       (canonical)
    2. ``Study.NumberOfItems``   (legacy)
    3. Count of non-metadata top-level keys as a fallback.

    Args:
        template: A full PRISM survey template dict.

    Returns:
        Item count as ``int``, or ``None`` if it cannot be determined.
    """
    study = template.get("Study") or {}
    n = study.get("ItemCount") or study.get("NumberOfItems")
    if isinstance(n, int) and n > 0:
        return n
    # Derive from top-level item keys
    reserved = {"Study", "Technical", "Metadata", "I18n", "Scoring"}
    item_keys = [k for k in template if k not in reserved and isinstance(template[k], dict)]
    return len(item_keys) if item_keys else None
