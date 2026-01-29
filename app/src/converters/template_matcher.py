"""Template matching for LimeSurvey imports.

Compares imported questionnaire structures against the template library
(both global and project-specific) to detect whether imported questionnaire
groups match known standardized instruments.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from typing import Optional

from pathlib import Path

from .survey import (
    _extract_template_structure,
    _load_global_templates,
    _load_global_participants_template,
    _is_participant_template,
    _NON_ITEM_TOPLEVEL_KEYS,
)
from ..utils.io import read_json as _read_json

logger = logging.getLogger(__name__)

# Hidden metadata questions injected by the LimeSurvey exporter.
# These store PRISM template metadata and are never shown to participants.
# They should be excluded from structural matching.
_METADATA_CODE_RE = re.compile(r"^PRISMMETA", re.IGNORECASE)

# Patterns to detect run suffixes in item codes.
# LimeSurvey codes can't have underscores, so the exporter uses formats like:
#   BRS01run02, BRS01run03  (no separator)
# PRISM/BIDS data files use:
#   BRS01_run-02, BRS01_run-03  (underscore + dash)
# We need to handle both.
_RUN_SUFFIX_PATTERNS = [
    re.compile(r"^(.+?)run(\d{2,})$", re.IGNORECASE),       # BRS01run02
    re.compile(r"^(.+?)_run-?(\d+)$", re.IGNORECASE),       # BRS01_run-02
]


@dataclass
class TemplateMatch:
    """Result of matching an imported questionnaire against the library."""

    template_key: str  # e.g. "gad7"
    template_path: str  # e.g. "survey-gad7.json"
    confidence: str  # "exact" | "high" | "medium" | "low"
    overlap_count: int  # number of matching items
    template_items: int  # total items in library template
    imported_items: int  # total items in imported group
    levels_match: Optional[bool] = None  # None = not checked
    runs_detected: int = 1
    only_in_import: list[str] = field(default_factory=list)
    only_in_library: list[str] = field(default_factory=list)
    is_participants: bool = False  # True if matched against participants.json
    source: str = "global"  # "global" | "project" — where the matched template lives

    def to_dict(self) -> dict:
        """Serialize for JSON API responses."""
        d = {
            "template_key": self.template_key,
            "template_path": self.template_path,
            "confidence": self.confidence,
            "overlap_count": self.overlap_count,
            "template_items": self.template_items,
            "imported_items": self.imported_items,
            "levels_match": self.levels_match,
            "runs_detected": self.runs_detected,
            "only_in_import": self.only_in_import,
            "only_in_library": self.only_in_library,
            "is_participants": self.is_participants,
            "source": self.source,
        }
        # Add suggested action based on confidence
        if self.is_participants:
            d["suggested_action"] = "use_participants"
        elif self.confidence in ("exact", "high"):
            d["suggested_action"] = "use_library"
        elif self.confidence == "medium":
            d["suggested_action"] = "review"
        else:
            d["suggested_action"] = "create_new"
        return d


def _strip_run_suffix(code: str) -> tuple[str, Optional[int]]:
    """Strip run suffix from a single item code.

    Args:
        code: Item code, possibly with run suffix.

    Returns:
        Tuple of (base_code, run_number or None).
    """
    for pattern in _RUN_SUFFIX_PATTERNS:
        m = pattern.match(code)
        if m:
            return m.group(1), int(m.group(2))
    return code, None


def _normalize_item_codes(codes: set[str]) -> tuple[set[str], int]:
    """Strip run suffixes from item codes and count runs.

    Handles both LimeSurvey format (BRS01run02) and BIDS format (BRS01_run-02).

    Args:
        codes: Set of item code strings (potentially with run suffixes).

    Returns:
        Tuple of (normalized codes without run suffixes, number of runs detected).
    """
    normalized = set()
    run_numbers: set[int] = set()
    for code in codes:
        base, run_num = _strip_run_suffix(code)
        normalized.add(base)
        if run_num is not None:
            run_numbers.add(run_num)
    runs = max(len(run_numbers), 1) if run_numbers else 1
    return normalized, runs


def _compare_levels(
    imported_item: dict, template_item: dict
) -> Optional[bool]:
    """Compare Levels keys between imported and library items.

    Only compares the keys (codes), not the label text, since labels
    may differ due to language or minor wording changes.

    Args:
        imported_item: Item dict from imported template.
        template_item: Item dict from library template.

    Returns:
        True if keys match, False if they differ, None if either has no Levels.
    """
    imp_levels = imported_item.get("Levels")
    lib_levels = template_item.get("Levels")
    if not imp_levels or not lib_levels:
        return None
    if not isinstance(imp_levels, dict) or not isinstance(lib_levels, dict):
        return None
    return set(imp_levels.keys()) == set(lib_levels.keys())


def _strip_run_from_group_name(name: str) -> str:
    """Strip run indicator from a group name for matching.

    E.g., "resiliencebrsrun2" -> "resiliencebrs", "brsrun03" -> "brs"
    """
    # Try various run patterns in group names
    m = re.match(r"^(.+?)run\d+$", name, re.IGNORECASE)
    if m:
        return m.group(1)
    return name


def _load_project_templates(project_path: str | Path) -> dict[str, dict]:
    """Load templates from a project's local library.

    Looks for survey-*.json files in {project_path}/code/library/survey/.
    Returns the same format as _load_global_templates().

    Args:
        project_path: Path to the project root directory.

    Returns:
        Dict mapping task_name -> {"path": Path, "json": dict, "structure": set}.
        Empty dict if project has no local templates.
    """
    project_dir = Path(project_path)
    survey_dir = project_dir / "code" / "library" / "survey"
    if not survey_dir.is_dir():
        return {}

    templates = {}
    for json_path in sorted(survey_dir.glob("survey-*.json")):
        if _is_participant_template(json_path):
            continue
        try:
            sidecar = _read_json(json_path)
        except Exception:
            continue

        task_from_name = json_path.stem.replace("survey-", "")
        task = str(sidecar.get("Study", {}).get("TaskName") or task_from_name).strip()
        task_norm = task.lower() or task_from_name.lower()

        templates[task_norm] = {
            "path": json_path,
            "json": sidecar,
            "structure": _extract_template_structure(sidecar),
            "source": "project",
        }

    if templates:
        logger.debug(
            "Loaded %d project templates from %s", len(templates), survey_dir
        )

    return templates


def _match_by_name(
    group_name: str, templates: dict[str, dict]
) -> list[str]:
    """Find candidate templates by name matching.

    Compares the group name (and its run-stripped version) against
    Study.Abbreviation, Study.TaskName, and the template key.

    Args:
        group_name: The LimeSurvey group name or abbreviation.
        templates: Global templates dict from _load_global_templates().

    Returns:
        List of matching template keys (may be empty).
    """
    name_lower = group_name.lower().strip()
    if not name_lower:
        return []

    # Also try with run suffix stripped
    base_name = _strip_run_from_group_name(name_lower)
    names_to_try = {name_lower}
    if base_name != name_lower:
        names_to_try.add(base_name)

    candidates = []
    for task_key, tdata in templates.items():
        # Strip __project__ prefix for name comparison
        real_key = task_key.removeprefix("__project__")
        sidecar = tdata["json"]
        study = sidecar.get("Study", {})
        abbreviation = str(study.get("Abbreviation", "")).lower().strip()
        task_name = str(study.get("TaskName", "")).lower().strip()

        for name in names_to_try:
            if name == real_key:
                candidates.append(task_key)
                break
            elif name == abbreviation:
                candidates.append(task_key)
                break
            elif name == task_name:
                candidates.append(task_key)
                break
            elif abbreviation and abbreviation in name:
                candidates.append(task_key)
                break
            elif task_name and task_name in name:
                candidates.append(task_key)
                break

    return candidates


def _match_against_participants(
    prism_json: dict, group_name: str = ""
) -> Optional[TemplateMatch]:
    """Check if an imported template matches the global participants template.

    The participants template (participants.json) is separate from survey
    templates and uses different item codes (age, sex, gender, etc.).

    Args:
        prism_json: The imported PRISM template dict.
        group_name: Optional group name for heuristic detection.

    Returns:
        TemplateMatch if it matches participants, None otherwise.
    """
    participants_template = _load_global_participants_template()
    if not participants_template:
        return None

    # Extract participant field keys (excluding metadata)
    participant_keys = {
        k for k in participants_template.keys()
        if k not in _NON_ITEM_TOPLEVEL_KEYS
        and isinstance(participants_template.get(k), dict)
    }
    # Also check for "Columns" wrapper structure
    columns = participants_template.get("Columns")
    if isinstance(columns, dict):
        participant_keys.update(columns.keys())

    if not participant_keys:
        return None

    imported_struct = {
        k for k in _extract_template_structure(prism_json)
        if not _METADATA_CODE_RE.match(k)
    }
    if not imported_struct:
        return None

    # Normalize imported codes (lowercase for participant fields)
    imported_lower = {c.lower() for c in imported_struct}
    participant_lower = {c.lower() for c in participant_keys}

    overlap = imported_lower & participant_lower
    if not overlap:
        # Also check group name heuristics
        name_lower = group_name.lower()
        participant_hints = {
            "participant", "demographics", "sociodemographic",
            "demographic", "socio", "prismsocio",
        }
        if not any(hint in name_lower for hint in participant_hints):
            return None

    overlap_count = len(overlap)
    if overlap_count == 0:
        return None

    only_in_import = sorted(imported_lower - participant_lower)
    only_in_library = sorted(participant_lower - imported_lower)

    total = max(len(imported_lower), len(participant_lower))
    ratio = overlap_count / total if total > 0 else 0.0

    if ratio < 0.3:
        return None

    if ratio >= 0.9 and len(only_in_import) == 0:
        confidence = "exact"
    elif ratio >= 0.7:
        confidence = "high"
    elif ratio >= 0.5:
        confidence = "medium"
    else:
        confidence = "low"

    return TemplateMatch(
        template_key="participants",
        template_path="participants.json",
        confidence=confidence,
        overlap_count=overlap_count,
        template_items=len(participant_lower),
        imported_items=len(imported_lower),
        levels_match=None,
        runs_detected=1,
        only_in_import=only_in_import,
        only_in_library=only_in_library,
        is_participants=True,
    )


def match_against_library(
    prism_json: dict,
    global_templates: Optional[dict[str, dict]] = None,
    group_name: str = "",
    project_path: Optional[str | Path] = None,
) -> Optional[TemplateMatch]:
    """Match a single PRISM template against the template library.

    Checks both global templates and project-specific templates (if a project
    path is provided). Project templates take priority over global ones.

    Uses a multi-signal approach:
    1. Name pre-filter (group name vs Study.Abbreviation/TaskName)
    2. Run detection (strip run suffixes in both LimeSurvey and BIDS formats)
    3. Item code overlap ratio
    4. Levels key verification for overlapping items
    5. Participants template check (separate from survey templates)

    Args:
        prism_json: The imported PRISM template dict.
        global_templates: Pre-loaded global templates. If None, loads automatically.
        group_name: Optional LimeSurvey group name for name-based matching.
        project_path: Optional project root path to also check project templates.

    Returns:
        TemplateMatch if a match is found, None otherwise.
    """
    if global_templates is None:
        global_templates = _load_global_templates()

    # Build combined template pool with source tracking.
    # Global templates get source="global"; project templates already have
    # source="project" from _load_project_templates().
    # Project templates are added separately (not merged) so both versions
    # can compete — the best structural match wins regardless of source.
    all_templates: dict[str, dict] = {}
    if global_templates:
        for key, tdata in global_templates.items():
            entry = dict(tdata)
            entry.setdefault("source", "global")
            all_templates[key] = entry
    if project_path:
        project_templates = _load_project_templates(project_path)
        for key, tdata in project_templates.items():
            # Use a prefixed key so project and global versions both compete
            proj_key = f"__project__{key}"
            all_templates[proj_key] = tdata

    # Extract imported item codes, excluding hidden metadata questions
    imported_struct = {
        k for k in _extract_template_structure(prism_json)
        if not _METADATA_CODE_RE.match(k)
    }
    if not imported_struct:
        return None

    # Normalize (strip run suffixes)
    imported_normalized, runs_detected = _normalize_item_codes(imported_struct)

    # Build a mapping from normalized code -> original code(s) for levels lookup
    norm_to_original: dict[str, str] = {}
    for code in imported_struct:
        base, _ = _strip_run_suffix(code)
        if base not in norm_to_original:
            norm_to_original[base] = code

    # Name-based candidates (for prioritization, not exclusion).
    # _match_by_name works on the real task key, so we need to resolve
    # __project__ prefixed keys back to their real names for comparison.
    name_candidates_raw = set()
    if group_name:
        name_candidates_raw = set(_match_by_name(group_name, all_templates))
    imp_study = prism_json.get("Study", {})
    imp_abbr = str(imp_study.get("Abbreviation", "")).strip()
    imp_task = str(imp_study.get("TaskName", "")).strip()
    for label in (imp_abbr, imp_task):
        if label:
            name_candidates_raw.update(_match_by_name(label, all_templates))
    # Also add __project__ prefixed versions so project entries get the boost
    name_candidates = set(name_candidates_raw)
    for key in name_candidates_raw:
        name_candidates.add(f"__project__{key}")

    best_match: Optional[TemplateMatch] = None
    best_overlap_ratio = 0.0

    for task_key, tdata in (all_templates.items() if all_templates else []):
        lib_struct = tdata["structure"]
        if not lib_struct:
            continue

        # Resolve the real template key (strip __project__ prefix)
        real_key = task_key.removeprefix("__project__")
        template_source = tdata.get("source", "global")

        # Compute overlap using normalized imported codes
        overlap = imported_normalized & lib_struct
        overlap_count = len(overlap)

        if overlap_count == 0:
            continue

        only_in_import = sorted(imported_normalized - lib_struct)
        only_in_library = sorted(lib_struct - imported_normalized)

        # Overlap ratio relative to the larger set
        max_size = max(len(imported_normalized), len(lib_struct))
        overlap_ratio = overlap_count / max_size if max_size > 0 else 0.0

        # Skip low overlap unless name matched
        if overlap_ratio < 0.5 and task_key not in name_candidates:
            continue

        # Verify Levels for overlapping items
        levels_results = []
        for item_key in overlap:
            # Use the original (possibly run-suffixed) code to look up in prism_json
            original_code = norm_to_original.get(item_key, item_key)
            imp_item = prism_json.get(original_code) or prism_json.get(item_key, {})
            lib_item = tdata["json"].get(item_key, {})
            if isinstance(imp_item, dict) and isinstance(lib_item, dict):
                lev_match = _compare_levels(imp_item, lib_item)
                if lev_match is not None:
                    levels_results.append(lev_match)

        # Determine levels_match summary
        if levels_results:
            all_match = all(levels_results)
            levels_match = all_match
        else:
            all_match = False
            levels_match = None

        # Determine confidence
        full_item_overlap = (
            len(only_in_import) == 0 and len(only_in_library) == 0
        )
        if full_item_overlap and (levels_match is True or levels_match is None):
            confidence = "exact"
        elif full_item_overlap:
            confidence = "high"
        elif overlap_ratio > 0.7:
            confidence = "medium" if not all_match else "high"
        elif overlap_ratio > 0.5 or task_key in name_candidates:
            confidence = "low"
        else:
            continue

        # Select best match by overlap ratio, preferring name matches
        effective_ratio = overlap_ratio
        if task_key in name_candidates:
            effective_ratio += 0.1  # slight boost for name match

        if effective_ratio > best_overlap_ratio:
            best_overlap_ratio = effective_ratio
            best_match = TemplateMatch(
                template_key=real_key,
                template_path=str(tdata["path"].name),
                confidence=confidence,
                overlap_count=overlap_count,
                template_items=len(lib_struct),
                imported_items=len(imported_normalized),
                levels_match=levels_match,
                runs_detected=runs_detected,
                only_in_import=only_in_import,
                only_in_library=only_in_library,
                source=template_source,
            )

    # If no survey template matched, check against participants template
    if best_match is None:
        participants_match = _match_against_participants(prism_json, group_name)
        if participants_match:
            best_match = participants_match

    if best_match:
        logger.info(
            "Template match: %s -> %s (confidence=%s, overlap=%d/%d, source=%s%s)",
            group_name or "unknown",
            best_match.template_key,
            best_match.confidence,
            best_match.overlap_count,
            best_match.template_items,
            best_match.source,
            ", participants" if best_match.is_participants else "",
        )

    return best_match


def match_groups_against_library(
    groups: dict[str, dict],
    global_templates: Optional[dict[str, dict]] = None,
    project_path: Optional[str | Path] = None,
) -> dict[str, Optional[TemplateMatch]]:
    """Match multiple questionnaire groups against the library.

    Args:
        groups: Dict mapping group_name -> prism_json template dict.
        global_templates: Pre-loaded global templates. If None, loads once.
        project_path: Optional project root path to also check project templates.

    Returns:
        Dict mapping group_name -> TemplateMatch or None.
    """
    if global_templates is None:
        global_templates = _load_global_templates()

    results = {}
    for group_name, prism_json in groups.items():
        results[group_name] = match_against_library(
            prism_json, global_templates, group_name=group_name,
            project_path=project_path,
        )
    return results
