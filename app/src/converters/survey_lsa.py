"""LimeSurvey Archive (LSA) handling utilities for survey conversion.

This module consolidates LSA-specific logic including:
- Metadata inference (language, software version)
- Structure analysis (parsing .lss, matching groups)
- Preprocessing (read-result unpacking, strict-mode resolution)
- Participant column handling
- Unmatched group aggregation
"""

from __future__ import annotations

import re
import zipfile
from pathlib import Path

try:
    import defusedxml.ElementTree as ET
except ImportError:
    import xml.etree.ElementTree as ET

from .survey_core import _NON_ITEM_TOPLEVEL_KEYS


# -----------------------------------------------------------------------------
# Metadata Inference
# -----------------------------------------------------------------------------


def infer_lsa_metadata(input_path: str | Path) -> dict:
    """Infer metadata from a LimeSurvey .lsa archive (best-effort)."""

    input_path = Path(input_path).resolve()
    language: str | None = None
    software_version: str | None = None

    def _mode(values: list[str]) -> str | None:
        if not values:
            return None
        counts: dict[str, int] = {}
        for v in values:
            counts[v] = counts.get(v, 0) + 1
        return sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))[0][0]

    def _find_first_text(root: ET.Element, *paths: str) -> str | None:
        for path in paths:
            el = root.find(path)
            if el is not None and el.text and el.text.strip():
                return el.text.strip()
        return None

    def _safe_parse_xml(xml_bytes: bytes) -> ET.Element | None:
        try:
            return ET.fromstring(xml_bytes)
        except Exception:
            try:
                text = xml_bytes.decode("utf-8", errors="replace")
                text = re.sub(r"<\?xml.*?\?>", "", text, 1)
                return ET.fromstring(text.strip())
            except Exception:
                return None

    try:
        with zipfile.ZipFile(input_path) as zf:
            resp_members = [n for n in zf.namelist() if n.endswith("_responses.lsr")]
            resp_members.sort()
            if resp_members:
                try:
                    xml_bytes = zf.read(resp_members[0])
                    root = _safe_parse_xml(xml_bytes)
                    if root is not None:
                        vals: list[str] = []
                        for row in root.findall(".//row"):
                            for child in row:
                                tag = child.tag
                                if "}" in tag:
                                    tag = tag.split("}", 1)[1]
                                if tag.lower() in {"startlanguage", "start_language"}:
                                    v = (child.text or "").strip()
                                    if v:
                                        vals.append(v)
                                    break
                            if len(vals) >= 2000:
                                break
                        language = _mode(vals)
                except Exception:
                    pass

            lss_members = [n for n in zf.namelist() if n.lower().endswith(".lss")]
            lss_members.sort()
            if lss_members:
                try:
                    lss_bytes = zf.read(lss_members[0])
                    root = _safe_parse_xml(lss_bytes)
                    if root is not None:
                        if not language:
                            language = _find_first_text(
                                root,
                                ".//surveys/rows/row/language",
                                ".//surveys_languagesettings/rows/row/surveyls_language",
                            )
                        software_version = _find_first_text(
                            root,
                            ".//LimeSurveyVersion",
                            ".//limesurveyversion",
                            ".//dbversion",
                            ".//DBVersion",
                        )
                except Exception:
                    pass
    except Exception:
        pass

    return {
        "language": language,
        "software_platform": "LimeSurvey",
        "software_version": software_version,
    }


def _infer_lsa_language_and_tech(*, input_path: Path, df) -> tuple[str | None, dict]:
    """Infer language and technical fields from a LimeSurvey .lsa archive."""

    inferred_language: str | None = None
    tech: dict = {
        "SoftwarePlatform": "LimeSurvey",
        "CollectionMethod": "online",
        "ResponseType": ["mouse_click", "keypress"],
    }

    meta = infer_lsa_metadata(input_path)
    inferred_language = meta.get("language") or None
    if meta.get("software_version"):
        tech["SoftwareVersion"] = meta["software_version"]

    return inferred_language, tech


# -----------------------------------------------------------------------------
# Structure Analysis
# -----------------------------------------------------------------------------


def _analyze_lsa_structure(
    input_path: Path,
    project_path: str | Path | None = None,
) -> dict | None:
    """Parse .lss structure from .lsa and match groups against template library."""
    from .limesurvey import parse_lss_xml_by_groups
    from .survey_templates import match_groups_against_library

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


# -----------------------------------------------------------------------------
# Preprocessing
# -----------------------------------------------------------------------------


def _unpack_lsa_read_result(result):
    """Unpack table read result for LSA inputs."""
    if isinstance(result, tuple):
        df, lsa_questions_map = result
    else:
        df = result
        lsa_questions_map = None
    return df, lsa_questions_map


def _resolve_lsa_language_and_strict(
    *,
    input_path,
    df,
    language: str | None,
    strict_levels: bool | None,
    infer_lsa_language_and_tech_fn=None,  # Kept for signature compatibility
) -> tuple[str | None, dict, bool]:
    """Resolve effective language/technical overrides/strict-level mode for LSA conversion."""
    # Use internal implementation if no external fn provided
    fn = infer_lsa_language_and_tech_fn or _infer_lsa_language_and_tech
    inferred_lang, inferred_tech = fn(
        input_path=input_path,
        df=df,
    )
    effective_language = language
    if not effective_language or effective_language.strip().lower() == "auto":
        effective_language = inferred_lang

    effective_strict_levels = False if strict_levels is None else bool(strict_levels)
    return effective_language, inferred_tech, effective_strict_levels


# -----------------------------------------------------------------------------
# Participant Handling
# -----------------------------------------------------------------------------


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


# -----------------------------------------------------------------------------
# Unmatched Group Handling
# -----------------------------------------------------------------------------


def _collect_unmatched_lsa_group(
    *,
    group_name: str,
    group_info: dict,
    unmatched_groups: list[dict],
    non_item_toplevel_keys,
    sanitize_task_name_fn,
) -> None:
    """Normalize/merge one unmatched LSA group into unmatched_groups."""
    from .survey_templates import _normalize_item_codes, _strip_run_from_group_name
    from .survey_templates import _strip_run_suffix

    task_key = sanitize_task_name_fn(group_name).lower()
    if not task_key:
        task_key = group_name.lower().replace(" ", "")

    base_key = _strip_run_from_group_name(task_key)
    if not base_key:
        base_key = task_key

    raw_codes = group_info["item_codes"]
    base_codes, _ = _normalize_item_codes(
        raw_codes if isinstance(raw_codes, set) else set(raw_codes)
    )
    base_prism = {}
    for k, v in group_info["prism_json"].items():
        if k in non_item_toplevel_keys or not isinstance(v, dict):
            base_prism[k] = v
        else:
            stripped, _ = _strip_run_suffix(k)
            if stripped not in base_prism:
                base_prism[stripped] = v

    existing = next((g for g in unmatched_groups if g["task_key"] == base_key), None)
    if existing is None:
        unmatched_groups.append(
            {
                "group_name": group_name,
                "task_key": base_key,
                "item_codes": base_codes,
                "prism_json": base_prism,
            }
        )
    else:
        existing["item_codes"] = existing["item_codes"] | base_codes
