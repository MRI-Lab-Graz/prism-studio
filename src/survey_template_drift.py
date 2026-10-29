"""Warn when a project survey template changed after its data was converted.

The root ``task-<name>_survey.json`` is written from ``code/library/survey/survey-<name>.json``
at conversion. If the template is edited later (e.g. answer codes remapped to numbers), the
sidecar keeps describing the data as it was imported. Whether that is intended is the user's
call; this only makes sure they know.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

# Sections people edit in the sidecar on purpose; only the item definitions are compared.
_NOT_ITEMS = {"Technical", "Study", "Metadata", "I18n"}
_SIDECAR = re.compile(r"task-([A-Za-z0-9]+)_survey\.json")  # ponytail: acq variants are not checked


_MISSING = "n/a"  # the level the converter adds for missing answers


def _items(sidecar: dict, infer_range) -> dict:
    """The item definitions, without MinValue/MaxValue where they only restate the numeric Levels:
    the template loader adds them, the converter may not, and neither is a change."""
    items = {k: dict(v) if isinstance(v, dict) else v for k, v in sidecar.items() if k not in _NOT_ITEMS and not k.startswith("_")}
    for item in items.values():
        levels = item.get("Levels") if isinstance(item, dict) else None
        implied = infer_range({k: v for k, v in levels.items() if k != _MISSING}) if isinstance(levels, dict) else None
        for name, value in zip(("MinValue", "MaxValue"), implied or ()):
            if item.get(name) == value:
                del item[name]
    return items


def check_survey_template_drift(root_dir, project_path=None) -> list[tuple[str, str, str]]:
    root = Path(root_dir)
    library = Path(project_path or root) / "code" / "library" / "survey"
    if not library.is_dir():
        return []
    try:
        # The converter's own steps, so "what conversion would write" has one definition.
        from src.converters.survey_core import _inject_missing_token, load_survey_library
        from src.converters.survey_templates import _localize_survey_template
        from src.survey_scale_inference import infer_contiguous_numeric_levels_range

        templates = load_survey_library(str(library))
    except ImportError:  # ponytail: validator wheel has no converter; check is skipped there
        return []

    issues = []
    for sidecar_path in sorted(root.glob("task-*_survey.json")):
        match = _SIDECAR.fullmatch(sidecar_path.name)
        template = templates.get(match[1]) if match else None
        if template is None:
            continue
        try:
            sidecar = json.loads(sidecar_path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue  # an unreadable sidecar is reported by the sidecar checks
        language = (sidecar.get("Technical") or {}).get("Language") or None
        expected = _items(
            _inject_missing_token(_localize_survey_template(template, language), token=_MISSING),
            infer_contiguous_numeric_levels_range,
        )
        actual = _items(sidecar, infer_contiguous_numeric_levels_range)
        changed = sorted(k for k in expected.keys() | actual.keys() if expected.get(k) != actual.get(k))
        if changed:
            shown = ", ".join(changed[:5]) + (f" and {len(changed) - 5} more" if len(changed) > 5 else "")
            issues.append((
                "WARNING",
                f"Survey template '{match[1]}' changed since the data was converted: {sidecar_path.name} differs "
                f"from code/library/survey/survey-{match[1]}.json in {len(changed)} item(s) ({shown}). "
                "Reimport the survey with the template (survey convert --force) or revert the template.",
                str(sidecar_path),
            ))
    return issues
