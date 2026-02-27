"""Helpers for LSA participant column registration and rename derivation."""

from __future__ import annotations


def _register_participant_columns_from_lsa_group(
    *,
    group_info: dict,
    participant_columns_lower: set[str],
) -> None:
    """Register participant-like columns from one LSA participant group."""
    for code in group_info.get("item_codes", set()):
        if not str(code).upper().startswith("PRISMMETA"):
            participant_columns_lower.add(str(code).lower())

    prismmeta = group_info.get("prism_json", {}).get("_prismmeta")
    if prismmeta and prismmeta.get("variables"):
        for var_code in prismmeta["variables"]:
            if not str(var_code).upper().startswith("PRISMMETA"):
                participant_columns_lower.add(str(var_code).lower())


def _derive_lsa_participant_renames(
    *,
    lsa_analysis: dict | None,
    survey_filter: str | None,
    participant_template: dict | None,
    build_participant_col_renames_fn,
) -> dict[str, str]:
    """Build participant column renames from matched LSA participant groups."""
    lsa_participant_renames: dict[str, str] = {}
    if lsa_analysis and not survey_filter:
        for _group_name, group_info in lsa_analysis.get("groups", {}).items():
            match = group_info.get("match")
            if match and match.is_participants:
                lsa_participant_renames = build_participant_col_renames_fn(
                    item_codes=group_info["item_codes"],
                    participant_template=participant_template,
                )
                break
    return lsa_participant_renames
