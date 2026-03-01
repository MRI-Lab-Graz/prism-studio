"""Survey template management: loading, matching, and assignment.

This module consolidates logic for:
1. Loading templates from global and project libraries.
2. Matching imported survey structures against these templates.
3. Assigning matched templates to imported data.
"""

from __future__ import annotations

import logging
import re
import os
from copy import deepcopy
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional, Any

from ..config import get_effective_library_paths, load_app_settings
from ..utils.io import read_json as _read_json
from .survey_core import (
    _extract_template_structure,
    _NON_ITEM_TOPLEVEL_KEYS,
)
# Note: cyclic import risk with survey_participants if not careful.
# Ideally survey_participants should be imported only where needed or refactored.
# For now, we import the specific functions we need.
from .survey_participants_logic import (
    _is_participant_template,
    _normalize_participant_template_dict,
)

logger = logging.getLogger(__name__)

# --- Constants ---

# Hidden metadata questions injected by the LimeSurvey exporter.
_METADATA_CODE_RE = re.compile(r"^PRISMMETA", re.IGNORECASE)

# Patterns to detect run suffixes in item codes.
_RUN_SUFFIX_PATTERNS = [
    re.compile(r"^(.+?)run(\d+)$", re.IGNORECASE),  # BRS01run02
    re.compile(r"^(.+?)_run-?(\d+)$", re.IGNORECASE),  # BRS01_run-02
]


# --- Data Structures ---

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
    source: str = "global"  # "global" | "project"

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
        if self.is_participants:
            d["suggested_action"] = "use_participants"
        elif self.confidence in ("exact", "high"):
            d["suggested_action"] = "use_library"
        elif self.confidence == "medium":
            d["suggested_action"] = "review"
        else:
            d["suggested_action"] = "create_new"
        return d


# --- Helper Functions (Matching Logic) ---

def _strip_run_suffix(code: str) -> tuple[str, Optional[int]]:
    """Strip run suffix from a single item code."""
    for pattern in _RUN_SUFFIX_PATTERNS:
        m = pattern.match(code)
        if m:
            return m.group(1), int(m.group(2))
    return code, None


def _ls_normalize_code(code: str) -> str:
    """Normalize an item code to its LimeSurvey-sanitized form."""
    return re.sub(r"[^a-zA-Z0-9]", "", code).lower()


def _normalize_item_codes(codes: set[str]) -> tuple[set[str], int]:
    """Strip run suffixes from item codes and count runs."""
    normalized = set()
    run_numbers: set[int] = set()
    for code in codes:
        base, run_num = _strip_run_suffix(code)
        normalized.add(base)
        if run_num is not None:
            run_numbers.add(run_num)
    runs = max(len(run_numbers), 1) if run_numbers else 1
    return normalized, runs


def _compare_levels(imported_item: dict, template_item: dict) -> Optional[bool]:
    """Compare Levels keys between imported and library items."""
    imp_levels = imported_item.get("Levels")
    lib_levels = template_item.get("Levels")
    if not imp_levels or not lib_levels:
        return None
    if not isinstance(imp_levels, dict) or not isinstance(lib_levels, dict):
        return None
    return set(imp_levels.keys()) == set(lib_levels.keys())


def _strip_run_from_group_name(name: str) -> str:
    """Strip run indicator from a group name for matching."""
    m = re.match(r"^(.+?)run\d+$", name, re.IGNORECASE)
    if m:
        return m.group(1)
    return name


# --- Template Loading (Global & Project) ---

def _load_global_library_path() -> Path | None:
    """Find the global library path from config."""
    try:
        app_root = Path(__file__).parent.parent.parent.resolve()
        settings = load_app_settings(app_root=str(app_root))

        if settings.global_library_root:
            root = settings.global_library_root
            if not os.path.isabs(root):
                root = os.path.normpath(os.path.join(app_root, root))
            p = Path(root).expanduser().resolve()

            candidates = [
                p / "library" / "survey",
                p / "survey",
            ]
            for candidate in candidates:
                if candidate.is_dir():
                    return candidate

            if (p / "library").is_dir():
                return p / "library"

        lib_paths = get_effective_library_paths(app_root=str(app_root))
        global_path = lib_paths.get("global_library_path")
        if global_path:
            p = Path(global_path).expanduser().resolve()
            if (p / "survey").is_dir():
                return p / "survey"
            if p.is_dir():
                return p
    except Exception:
        pass
    return None


def _load_global_templates() -> dict[str, dict]:
    """Load all templates from the global library."""
    global_path = _load_global_library_path()
    if not global_path or not global_path.exists():
        return {}

    templates = {}
    for json_path in sorted(global_path.glob("survey-*.json")):
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
        }

    return templates


def _load_project_templates(project_path: str | Path) -> dict[str, dict]:
    """Load templates from a project's local library."""
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

    return templates


# --- Participants Template Logic ---

def _load_global_participants_template() -> dict | None:
    """Load the global participants.json template."""
    global_path = _load_global_library_path()
    if not global_path or not global_path.exists():
        return None

    candidates = [
        global_path.parent / "participants.json",
        global_path / "participants.json",
    ]
    for ancestor in global_path.parents[:2]:
        candidates.append(ancestor / "participants.json")

    for p in candidates:
        if p.exists() and p.is_file():
            try:
                return _read_json(p)
            except Exception:
                pass
    return None


def _compare_participants_templates(
    project_template: dict | None,
    global_template: dict | None,
) -> tuple[bool, set[str], set[str], list[str]]:
    """Compare project participants template against global template.

    Template customization is expected in projects, so structural differences
    from the global participants template are informational only and should
    not generate conversion warnings.
    """
    warnings: list[str] = []

    if not project_template and not global_template:
        return True, set(), set(), warnings

    if not project_template:
        return False, set(), set(), ["No project participants.json found"]

    if not global_template:
        return True, set(), set(), warnings

    project_norm = _normalize_participant_template_dict(project_template) or {}
    global_norm = _normalize_participant_template_dict(global_template) or {}

    project_cols = {k for k in project_norm.keys() if not k.startswith("_")}
    global_cols = {k for k in global_norm.keys() if not k.startswith("_")}

    only_in_project = project_cols - global_cols
    only_in_global = global_cols - project_cols

    is_equivalent = len(only_in_project) == 0 and len(only_in_global) == 0

    # Differences are allowed: users can customize project participants.json
    # independently from the global template.

    return is_equivalent, only_in_project, only_in_global, warnings


# --- Matching Logic (Core) ---

def _match_by_name(group_name: str, templates: dict[str, dict]) -> list[str]:
    """Find candidate templates by name matching."""
    name_lower = group_name.lower().strip()
    if not name_lower:
        return []

    base_name = _strip_run_from_group_name(name_lower)
    names_to_try = {name_lower}
    if base_name != name_lower:
        names_to_try.add(base_name)

    candidates = []
    for task_key, tdata in templates.items():
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
    prism_json: dict,
    group_name: str = "",
    prismmeta: dict | None = None,
) -> Optional[TemplateMatch]:
    """Check if an imported template matches the global participants template."""
    if prismmeta and prismmeta.get("type") == "participants":
        meta_vars = prismmeta.get("variables", [])
        imported_struct = {
            k
            for k in _extract_template_structure(prism_json)
            if not _METADATA_CODE_RE.match(k)
        }
        return TemplateMatch(
            template_key="participants",
            template_path="participants.json",
            confidence="exact",
            overlap_count=len(meta_vars) if meta_vars else len(imported_struct),
            template_items=len(meta_vars) if meta_vars else len(imported_struct),
            imported_items=len(imported_struct),
            levels_match=None,
            runs_detected=1,
            only_in_import=[],
            only_in_library=[],
            is_participants=True,
        )

    participants_template = _load_global_participants_template()
    if not participants_template:
        return None

    participant_keys = {
        k
        for k in participants_template.keys()
        if k not in _NON_ITEM_TOPLEVEL_KEYS
        and isinstance(participants_template.get(k), dict)
    }
    columns = participants_template.get("Columns")
    if isinstance(columns, dict):
        participant_keys.update(columns.keys())

    if not participant_keys:
        return None

    imported_struct = {
        k
        for k in _extract_template_structure(prism_json)
        if not _METADATA_CODE_RE.match(k)
    }
    if not imported_struct:
        return None

    imported_lower = {c.lower() for c in imported_struct}
    participant_lower = {c.lower() for c in participant_keys}

    overlap = imported_lower & participant_lower
    if not overlap:
        name_lower = group_name.lower()
        participant_hints = {
            "participant",
            "demographics",
            "sociodemographic",
            "demographic",
            "socio",
            "prismsocio",
        }
        if not any(hint in name_lower for hint in participant_hints):
            return None

    overlap_count = len(overlap)
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
    """Match a single PRISM template against the template library."""
    if global_templates is None:
        global_templates = _load_global_templates()

    all_templates: dict[str, dict] = {}
    if global_templates:
        for key, tdata in global_templates.items():
            entry = dict(tdata)
            entry.setdefault("source", "global")
            all_templates[key] = entry
    if project_path:
        project_templates = _load_project_templates(project_path)
        for key, tdata in project_templates.items():
            proj_key = f"__project__{key}"
            all_templates[proj_key] = tdata

    imported_struct = {
        k
        for k in _extract_template_structure(prism_json)
        if not _METADATA_CODE_RE.match(k)
    }
    if not imported_struct:
        return None

    imported_normalized, runs_detected = _normalize_item_codes(imported_struct)
    imported_ls_norm = {_ls_normalize_code(c): c for c in imported_normalized}

    norm_to_original: dict[str, str] = {}
    for code in imported_struct:
        base, _ = _strip_run_suffix(code)
        if base not in norm_to_original:
            norm_to_original[base] = code

    name_candidates = set()
    raw_name_candidates = set()
    if group_name:
        raw_name_candidates.update(_match_by_name(group_name, all_templates))
    
    imp_study = prism_json.get("Study", {})
    imp_abbr = str(imp_study.get("Abbreviation", "")).strip()
    imp_task = str(imp_study.get("TaskName", "")).strip()
    for label in (imp_abbr, imp_task):
        if label:
            raw_name_candidates.update(_match_by_name(label, all_templates))
    
    name_candidates = set(raw_name_candidates)
    for key in raw_name_candidates:
        name_candidates.add(f"__project__{key}")

    best_match: Optional[TemplateMatch] = None
    best_overlap_ratio = 0.0

    for task_key, tdata in all_templates.items() if all_templates else []:
        lib_struct = tdata["structure"]
        if not lib_struct:
            continue

        real_key = task_key.removeprefix("__project__")
        template_source = tdata.get("source", "global")

        lib_run_normalized, _ = _normalize_item_codes(lib_struct)
        lib_ls_norm = {_ls_normalize_code(c): c for c in lib_run_normalized}
        
        lib_norm_to_original: dict[str, str] = {}
        for code in lib_struct:
            base, _ = _strip_run_suffix(code)
            if base not in lib_norm_to_original:
                lib_norm_to_original[base] = code
        
        ls_overlap_keys = set(imported_ls_norm.keys()) & set(lib_ls_norm.keys())
        overlap_count = len(ls_overlap_keys)

        if overlap_count == 0:
            continue

        overlap = {lib_ls_norm[k] for k in ls_overlap_keys}
        matched_import_keys = {imported_ls_norm[k] for k in ls_overlap_keys}
        only_in_import = sorted(imported_normalized - matched_import_keys)
        only_in_library = sorted(lib_run_normalized - overlap)

        max_size = max(len(imported_normalized), len(lib_run_normalized))
        overlap_ratio = overlap_count / max_size if max_size > 0 else 0.0

        if overlap_ratio < 0.5 and task_key not in name_candidates:
            continue

        levels_results = []
        for ls_key in ls_overlap_keys:
            lib_code_norm = lib_ls_norm[ls_key]
            imp_code = imported_ls_norm[ls_key]
            original_code = norm_to_original.get(imp_code, imp_code)
            lib_orig_code = lib_norm_to_original.get(lib_code_norm, lib_code_norm)
            
            imp_item = prism_json.get(original_code) or prism_json.get(imp_code, {})
            lib_item = tdata["json"].get(lib_orig_code) or tdata["json"].get(
                lib_code_norm, {}
            )
            
            if isinstance(imp_item, dict) and isinstance(lib_item, dict):
                lev_match = _compare_levels(imp_item, lib_item)
                if lev_match is not None:
                    levels_results.append(lev_match)

        levels_match = None
        if levels_results:
            levels_match = all(levels_results)

        full_item_overlap = len(only_in_import) == 0 and len(only_in_library) == 0
        if full_item_overlap and (levels_match is True or levels_match is None):
            confidence = "exact"
        elif full_item_overlap:
            confidence = "high"
        elif overlap_ratio > 0.7:
            confidence = "medium" if levels_match is not False else "medium" # simplifies logic slightly
        elif overlap_ratio > 0.5 or task_key in name_candidates:
            confidence = "low"
        else:
            continue

        effective_ratio = overlap_ratio
        if task_key in name_candidates:
            effective_ratio += 0.1

        if effective_ratio > best_overlap_ratio:
            best_overlap_ratio = effective_ratio
            best_match = TemplateMatch(
                template_key=real_key,
                template_path=str(tdata["path"].name),
                confidence=confidence,
                overlap_count=overlap_count,
                template_items=len(lib_run_normalized),
                imported_items=len(imported_normalized),
                levels_match=levels_match,
                runs_detected=runs_detected,
                only_in_import=only_in_import,
                only_in_library=only_in_library,
                source=template_source,
            )

    if best_match is None:
        prismmeta = prism_json.get("_prismmeta")
        participants_match = _match_against_participants(
            prism_json, group_name, prismmeta=prismmeta
        )
        if participants_match:
            best_match = participants_match

    return best_match


def _find_matching_global_template(
    project_template: dict,
    global_templates: dict[str, dict],
) -> tuple[str | None, bool, set[str], set[str]]:
    """Legacy helper: search global templates for a match."""
    # Note: Refactored to use common matching logic if possible, 
    # but for now we keep the original implementation from survey_global_templates.py 
    # to avoid subtle regressions.
    
    project_struct = _extract_template_structure(project_template)

    best_match = None
    best_overlap = 0
    best_only_project: set[str] = set()
    best_only_global: set[str] = set()

    for task_name, global_data in global_templates.items():
        global_struct = global_data["structure"]

        overlap = len(project_struct & global_struct)
        only_in_project = project_struct - global_struct
        only_in_global = global_struct - project_struct

        if len(only_in_project) == 0 and len(only_in_global) == 0:
            return task_name, True, set(), set()

        if overlap > best_overlap:
            best_overlap = overlap
            best_match = task_name
            best_only_project = only_in_project
            best_only_global = only_in_global

    if best_match and best_overlap > len(project_struct) * 0.5:
        return best_match, False, best_only_project, best_only_global

    return None, False, set(), set()


# --- Assignment & IO Logic ---

def _load_and_preprocess_templates(
    library_dir: Path,
    canonical_aliases: dict[str, list[str]] | None,
    compare_with_global: bool = True,
    *,
    read_json_fn=_read_json,
    canonicalize_template_items_fn=None,  # Dependency injection
    non_item_keys=_NON_ITEM_TOPLEVEL_KEYS,
    load_global_library_path_fn=None,
    load_global_templates_fn=None,
    is_participant_template_fn=None,
    find_matching_global_template_fn=None,
) -> tuple[
    dict[str, dict],
    dict[str, str],
    dict[str, set[str]],
    dict[str, list[str]],
]:
    """Load and prepare survey templates from library."""
    load_global_library_path_fn = (
        load_global_library_path_fn or _load_global_library_path
    )
    load_global_templates_fn = load_global_templates_fn or _load_global_templates
    is_participant_template_fn = (
        is_participant_template_fn or _is_participant_template
    )
    find_matching_global_template_fn = (
        find_matching_global_template_fn or _find_matching_global_template
    )

    templates: dict[str, dict] = {}
    item_to_task: dict[str, str] = {}
    duplicates: dict[str, set[str]] = {}
    template_warnings_by_task: dict[str, list[str]] = {}

    global_templates: dict[str, dict] = {}
    global_library_path = load_global_library_path_fn()
    is_using_global_library = False

    if compare_with_global and global_library_path:
        try:
            if library_dir.resolve() == global_library_path.resolve():
                is_using_global_library = True
            else:
                global_templates = load_global_templates_fn()
        except Exception:
            pass

    if library_dir.exists():
        for json_path in sorted(library_dir.glob("survey-*.json")):
            if is_participant_template_fn(json_path):
                continue
            try:
                sidecar = read_json_fn(json_path)
            except Exception:
                continue

            task_from_name = json_path.stem.replace("survey-", "")
            task = str(sidecar.get("Study", {}).get("TaskName") or task_from_name).strip()
            task_norm = task.lower() or task_from_name.lower()

            logger.info(f"Loading template: {json_path} (task: {task_norm})")

            # Dependency injection handling for circular imports or late binding
            if canonical_aliases and canonicalize_template_items_fn:
                sidecar = canonicalize_template_items_fn(
                    sidecar=sidecar, canonical_aliases=canonical_aliases
                )

            if "_aliases" not in sidecar:
                sidecar["_aliases"] = {}
            if "_reverse_aliases" not in sidecar:
                sidecar["_reverse_aliases"] = {}

            for k, v in list(sidecar.items()):
                if k in non_item_keys or not isinstance(v, dict):
                    continue
                if "Aliases" in v and isinstance(v["Aliases"], list):
                    for alias in v["Aliases"]:
                        sidecar["_aliases"][alias] = k
                        sidecar["_reverse_aliases"].setdefault(k, []).append(alias)
                if "AliasOf" in v:
                    target = v["AliasOf"]
                    sidecar["_aliases"][k] = target
                    sidecar["_reverse_aliases"].setdefault(target, []).append(k)

                has_levels = isinstance(v.get("Levels"), dict)
                has_range = "MinValue" in v or "MaxValue" in v
                if has_levels and has_range:
                    template_warnings_by_task.setdefault(task_norm, []).append(
                        f"Template '{task_norm}' item '{k}' defines both Levels and Min/Max; numeric range takes precedence and Levels will be treated as labels only."
                    )

            template_source = "project"
            global_match_task = None
            if is_using_global_library:
                template_source = "global"
            elif global_templates:
                matched_task, is_exact, only_project, only_global = (
                    find_matching_global_template_fn(sidecar, global_templates)
                )
                if matched_task:
                    global_match_task = matched_task
                    if is_exact:
                        template_source = "global"
                    else:
                        template_source = "modified"
                        # Project-local template customization is allowed and
                        # expected; do not emit conversion warnings for diffs
                        # against global templates.

            templates[task_norm] = {
                "path": json_path,
                "json": sidecar,
                "task": task_norm,
                "source": template_source,
                "global_match": global_match_task,
            }

            for k, v in sidecar.items():
                if k in non_item_keys:
                    continue
                if k in item_to_task and item_to_task[k] != task_norm:
                    duplicates.setdefault(k, set()).update({item_to_task[k], task_norm})
                else:
                    item_to_task[k] = task_norm
                if (
                    isinstance(v, dict)
                    and "Aliases" in v
                    and isinstance(v["Aliases"], list)
                ):
                    for alias in v["Aliases"]:
                        if alias in item_to_task and item_to_task[alias] != task_norm:
                            duplicates.setdefault(alias, set()).update(
                                {item_to_task[alias], task_norm}
                            )
                        else:
                            item_to_task[alias] = task_norm

    return templates, item_to_task, duplicates, template_warnings_by_task


def _add_ls_code_aliases(
    sidecar: dict,
    imported_codes: list[str],
    *,
    non_item_keys=_NON_ITEM_TOPLEVEL_KEYS,
) -> None:
    """Register LS-mangled item codes as aliases."""
    imported_ls_norm = {_ls_normalize_code(c): c for c in imported_codes}
    aliases = sidecar.setdefault("_aliases", {})
    reverse_aliases = sidecar.setdefault("_reverse_aliases", {})

    for lib_key in list(sidecar.keys()):
        if lib_key in non_item_keys or not isinstance(sidecar.get(lib_key), dict):
            continue
        ls_norm = _ls_normalize_code(lib_key)
        imp_code = imported_ls_norm.get(ls_norm)
        if imp_code and imp_code != lib_key and imp_code not in aliases:
            aliases[imp_code] = lib_key
            reverse_aliases.setdefault(lib_key, []).append(imp_code)


def _add_matched_template(
    templates: dict[str, dict],
    item_to_task: dict[str, str],
    match,
    group_info: dict,
    *,
    read_json_fn=_read_json,
    non_item_keys=_NON_ITEM_TOPLEVEL_KEYS,
) -> None:
    """Add a library-matched template to the templates and item_to_task dicts."""
    task_key = match.template_key
    if task_key in templates:
        _add_ls_code_aliases(templates[task_key]["json"], group_info["item_codes"], non_item_keys=non_item_keys)
        # Update mapping for any new aliases
        for code in group_info["item_codes"]:
            if code not in item_to_task:
                item_to_task[code] = task_key
        return

    template_path = None
    if match.source == "global":
        global_templates = _load_global_templates()
        gt = global_templates.get(task_key)
        if gt:
            template_path = gt["path"]
    elif match.source == "project" and hasattr(match, "template_path"):
        # We need the full path, but Match object typically only stores filename or relative path
        # Re-resolve it if possible, or assume it came from project library
        pass  # TODO: Handle project path resolution if strictly needed, though rarely hit here

    # Fallback/Safety: if we have a path in match and it's absolute/exists
    if hasattr(match, "template_path") and os.path.isabs(match.template_path) and os.path.exists(match.template_path):
        template_path = Path(match.template_path)

    if template_path and template_path.exists():
        try:
            sidecar = read_json_fn(template_path)
        except Exception:
            return

        if "_aliases" not in sidecar:
            sidecar["_aliases"] = {}
        if "_reverse_aliases" not in sidecar:
            sidecar["_reverse_aliases"] = {}

        for k, v in list(sidecar.items()):
            if k in non_item_keys or not isinstance(v, dict):
                continue
            if "Aliases" in v and isinstance(v["Aliases"], list):
                for alias in v["Aliases"]:
                    sidecar["_aliases"][alias] = k
                    sidecar["_reverse_aliases"].setdefault(k, []).append(alias)
            if "AliasOf" in v:
                target = v["AliasOf"]
                sidecar["_aliases"][k] = target
                sidecar["_reverse_aliases"].setdefault(target, []).append(k)

        _add_ls_code_aliases(sidecar, group_info["item_codes"], non_item_keys=non_item_keys)

        templates[task_key] = {
            "path": template_path,
            "json": sidecar,
            "task": task_key,
            "source": match.source,
            "global_match": task_key if match.source == "global" else None,
        }

        for k, v in sidecar.items():
            if k in non_item_keys:
                continue
            if k not in item_to_task:
                item_to_task[k] = task_key
            if (
                isinstance(v, dict)
                and "Aliases" in v
                and isinstance(v["Aliases"], list)
            ):
                for alias in v["Aliases"]:
                    if alias not in item_to_task:
                        item_to_task[alias] = task_key

    for code in group_info["item_codes"]:
        if code not in item_to_task:
            item_to_task[code] = task_key


def _add_generated_template(
    templates: dict[str, dict],
    item_to_task: dict[str, str],
    group_name: str,
    group_info: dict,
    *,
    sanitize_task_name_fn, # dependency injection
) -> None:
    """Add a generated (unmatched) template from .lss parsing."""
    task_key = sanitize_task_name_fn(group_name).lower()
    if not task_key:
        task_key = group_name.lower().replace(" ", "")
    if task_key in templates:
        return

    prism_json = group_info["prism_json"]

    if "_aliases" not in prism_json:
        prism_json["_aliases"] = {}
    if "_reverse_aliases" not in prism_json:
        prism_json["_reverse_aliases"] = {}

    templates[task_key] = {
        "path": None,
        "json": prism_json,
        "task": task_key,
        "source": "generated",
        "global_match": None,
    }

    for code in group_info["item_codes"]:
        if code not in item_to_task:
            item_to_task[code] = task_key


def _copy_templates_to_project(
    *,
    templates: dict,
    tasks_with_data: set[str],
    dataset_root,
    language: str | None,
    technical_overrides: dict | None,
    missing_token: str,
    localize_survey_template_fn,
    inject_missing_token_fn,
    apply_technical_overrides_fn,
    write_json_fn,
) -> None:
    """Copy used templates to project's code/library/survey/ for reproducibility."""
    project_root = dataset_root
    library_dir = project_root / "code" / "library" / "survey"
    library_dir.mkdir(parents=True, exist_ok=True)

    for task in sorted(tasks_with_data):
        if task not in templates:
            continue

        template_data = templates[task]["json"]
        output_filename = f"survey-{task}.json"
        output_path = library_dir / output_filename

        if not output_path.exists():
            localized = localize_survey_template_fn(template_data, language=language)
            localized = inject_missing_token_fn(localized, token=missing_token)
            if technical_overrides:
                localized = apply_technical_overrides_fn(
                    localized, technical_overrides
                )
            write_json_fn(output_path, localized)


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
            prism_json,
            global_templates,
            group_name=group_name,
            project_path=project_path,
        )
    return results

# =============================================================================
# I18N / LOCALIZATION HELPERS
# =============================================================================


_LANGUAGE_KEY_RE = re.compile(r"^[a-z]{2}(?:-[a-z]{2})?$", re.IGNORECASE)


def _normalize_language(lang: str | None) -> str | None:
    if not lang:
        return None
    norm = str(lang).strip().lower()
    return norm or None


def _default_language_from_template(template: dict) -> str:
    i18n = template.get("I18n")
    if isinstance(i18n, dict):
        default = i18n.get("DefaultLanguage") or i18n.get("defaultlanguage")
        if default:
            return str(default).strip().lower() or "en"

    tech = template.get("Technical")
    if isinstance(tech, dict):
        lang = tech.get("Language")
        if lang:
            return str(lang).strip().lower() or "en"

    return "en"


def _is_language_dict(value: dict) -> bool:
    if not value:
        return False
    return all(_LANGUAGE_KEY_RE.match(str(k)) for k in value.keys())


def _pick_language_value(value: dict, language: str) -> object:
    preference = [language, language.split("-")[0] if "-" in language else language]
    for candidate in preference:
        if candidate in value and value[candidate] not in (None, ""):
            return value[candidate]

    for fallback in value.values():
        if fallback not in (None, ""):
            return fallback
    return next(iter(value.values()))


def _localize_survey_template(template: dict, language: str | None) -> dict:
    if not isinstance(template, dict):
        return template

    lang = _normalize_language(language) or _default_language_from_template(template)

    def _recurse(value):
        if isinstance(value, dict):
            if _is_language_dict(value):
                return _pick_language_value(value, lang)
            return {k: _recurse(v) for k, v in value.items()}
        if isinstance(value, list):
            return [_recurse(v) for v in value]
        return value

    return _recurse(deepcopy(template))
