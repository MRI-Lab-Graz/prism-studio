"""LSA structure analysis helpers for survey conversion."""

from __future__ import annotations

from pathlib import Path
import zipfile

from .survey_helpers import _NON_ITEM_TOPLEVEL_KEYS


def _analyze_lsa_structure(
    input_path: Path,
    project_path: str | Path | None = None,
) -> dict | None:
    """Parse .lss structure from .lsa and match groups against template library."""
    from .limesurvey import parse_lss_xml_by_groups
    from .template_matcher import match_groups_against_library

    try:
        with zipfile.ZipFile(str(input_path), "r") as z:
            lss_names = [n for n in z.namelist() if n.endswith(".lss")]
            if not lss_names:
                return None
            xml_lss = z.read(lss_names[0])
    except Exception:
        return None

    parsed_groups = parse_lss_xml_by_groups(xml_lss, use_standard_format=True)
    if not parsed_groups:
        return None

    matches = match_groups_against_library(parsed_groups, project_path=project_path)

    groups: dict[str, dict] = {}
    column_to_group: dict[str, str] = {}

    for group_name, prism_json in parsed_groups.items():
        item_codes = {
            k
            for k in prism_json.keys()
            if k not in _NON_ITEM_TOPLEVEL_KEYS and isinstance(prism_json.get(k), dict)
        }

        groups[group_name] = {
            "prism_json": prism_json,
            "match": matches.get(group_name),
            "item_codes": item_codes,
        }

        for code in item_codes:
            column_to_group[code] = group_name

    return {
        "groups": groups,
        "column_to_group": column_to_group,
    }
