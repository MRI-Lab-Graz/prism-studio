"""Technical metadata and missing-token helpers for survey templates."""

from __future__ import annotations

from copy import deepcopy

from .survey_helpers import _NON_ITEM_TOPLEVEL_KEYS


def _inject_missing_token(sidecar: dict, *, token: str) -> dict:
    """Ensure every item Levels includes the missing-value token."""
    if not isinstance(sidecar, dict):
        return sidecar

    for key, item in sidecar.items():
        if key in _NON_ITEM_TOPLEVEL_KEYS:
            continue
        if not isinstance(item, dict):
            continue

        levels = item.get("Levels")
        if isinstance(levels, dict):
            if token not in levels:
                levels[token] = "Missing/Not provided"
                item["Levels"] = levels

    return sidecar


def _apply_technical_overrides(sidecar: dict, overrides: dict) -> dict:
    """Apply best-effort technical metadata without breaking existing templates."""
    out = deepcopy(sidecar)
    tech = out.get("Technical")
    if not isinstance(tech, dict):
        tech = {}
        out["Technical"] = tech

    for k, v in overrides.items():
        if v is None:
            continue
        if isinstance(v, str) and v.strip() == "":
            continue
        tech[k] = v

    return out
