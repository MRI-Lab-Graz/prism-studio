"""Survey conversion utilities.

This module provides a programmatic API for converting wide survey tables (e.g. .xlsx)
into a PRISM/BIDS-style survey dataset.

It is extracted from the CLI implementation in `prism_tools.py` so the Web UI and
GUI can call the same logic without invoking subprocesses or relying on `sys.exit`.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
import csv
import zipfile
try:
    import defusedxml.ElementTree as ET
except ImportError:
    import xml.etree.ElementTree as ET
from copy import deepcopy
import re
from typing import Iterable

try:
    import pandas as pd
except ImportError:
    pd = None

from ..utils.io import ensure_dir as _ensure_dir, read_json as _read_json, write_json as _write_json
from ..utils.naming import sanitize_id
from ..bids_integration import check_and_update_bidsignore

_NON_ITEM_TOPLEVEL_KEYS = {
    "Technical",
    "Study",
    "Metadata",
    "Normative",
    "Scoring",
    # Template metadata (not survey response columns)
    "I18n",
    "LimeSurvey",
    "_aliases",
    "_reverse_aliases",
}

# Keys that are considered "styling" or metadata, not structural
_STYLING_KEYS = {
    "Description", "Levels", "MinValue", "MaxValue", "Units",
    "HelpText", "Aliases", "AliasOf", "Derivative", "TermURL",
}


def _extract_template_structure(template: dict) -> set[str]:
    """Extract the structural signature of a template (item keys only).

    This ignores styling/metadata and only looks at what items exist.
    Used to compare if two templates are structurally equivalent.

    Args:
        template: The template dictionary

    Returns:
        Set of item keys (excluding non-item keys like Study, Technical, etc.)
    """
    return {
        k for k in template.keys()
        if k not in _NON_ITEM_TOPLEVEL_KEYS and isinstance(template.get(k), dict)
    }


def _compare_template_structures(
    template_a: dict, template_b: dict
) -> tuple[bool, set[str], set[str]]:
    """Compare two templates structurally.

    Args:
        template_a: First template
        template_b: Second template

    Returns:
        Tuple of (is_equivalent, only_in_a, only_in_b)
        - is_equivalent: True if templates have the same item keys
        - only_in_a: Item keys only in template_a
        - only_in_b: Item keys only in template_b
    """
    struct_a = _extract_template_structure(template_a)
    struct_b = _extract_template_structure(template_b)

    only_in_a = struct_a - struct_b
    only_in_b = struct_b - struct_a

    return (len(only_in_a) == 0 and len(only_in_b) == 0), only_in_a, only_in_b


def _load_global_library_path() -> Path | None:
    """Find the global library path from config.

    Returns:
        Path to global survey library or None if not configured/found.
    """
    try:
        from ..config import load_app_settings
        import os

        # Determine app root (parent of src folder)
        app_root = Path(__file__).parent.parent.parent.resolve()
        settings = load_app_settings(app_root=str(app_root))

        if settings.global_library_root:
            # Resolve relative paths from app_root
            root = settings.global_library_root
            if not os.path.isabs(root):
                root = os.path.normpath(os.path.join(app_root, root))
            p = Path(root).expanduser().resolve()

            # Check for survey subfolder in various locations
            candidates = [
                p / "library" / "survey",  # official/library/survey
                p / "survey",              # official/survey (alternative layout)
            ]
            for candidate in candidates:
                if candidate.is_dir():
                    return candidate

            # If we have a library folder, use that
            if (p / "library").is_dir():
                return p / "library"

        # Fallback to default path resolution
        from ..config import get_effective_library_paths
        lib_paths = get_effective_library_paths(app_root=str(app_root))
        global_path = lib_paths.get("global_library_path")
        if global_path:
            p = Path(global_path).expanduser().resolve()
            # Check for survey subfolder
            if (p / "survey").is_dir():
                return p / "survey"
            if p.is_dir():
                return p
    except Exception:
        pass
    return None


def _load_global_templates() -> dict[str, dict]:
    """Load all templates from the global library.

    Returns:
        Dict mapping task_name -> {"path": Path, "json": dict, "structure": set}
    """
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


def _load_global_participants_template() -> dict | None:
    """Load the global participants.json template.

    Returns:
        The participants template dict or None if not found.
    """
    global_path = _load_global_library_path()
    if not global_path or not global_path.exists():
        return None

    # Try various locations relative to the global survey library
    candidates = [
        global_path.parent / "participants.json",  # library/participants.json
        global_path / "participants.json",  # library/survey/participants.json
    ]
    # Also try parent directories
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

    Args:
        project_template: Project's participants.json (normalized)
        global_template: Global participants.json (normalized)

    Returns:
        Tuple of (is_equivalent, only_in_project, only_in_global, warnings)
    """
    warnings: list[str] = []

    if not project_template and not global_template:
        return True, set(), set(), warnings

    if not project_template:
        return False, set(), set(), ["No project participants.json found"]

    if not global_template:
        # No global to compare against - project is custom
        return True, set(), set(), warnings

    # Normalize both templates
    project_norm = _normalize_participant_template_dict(project_template) or {}
    global_norm = _normalize_participant_template_dict(global_template) or {}

    # Extract column keys (excluding internal keys starting with _)
    project_cols = {k for k in project_norm.keys() if not k.startswith("_")}
    global_cols = {k for k in global_norm.keys() if not k.startswith("_")}

    only_in_project = project_cols - global_cols
    only_in_global = global_cols - project_cols

    is_equivalent = len(only_in_project) == 0 and len(only_in_global) == 0

    if not is_equivalent:
        diff_parts = []
        if only_in_project:
            diff_parts.append(f"added columns: {', '.join(sorted(only_in_project))}")
        if only_in_global:
            diff_parts.append(f"missing columns: {', '.join(sorted(only_in_global))}")
        warnings.append(f"participants.json differs from global: {'; '.join(diff_parts)}")

    return is_equivalent, only_in_project, only_in_global, warnings


def _find_matching_global_template(
    project_template: dict,
    global_templates: dict[str, dict],
) -> tuple[str | None, bool, set[str], set[str]]:
    """Find if a project template matches any global template.

    Args:
        project_template: The project template dict
        global_templates: Dict of global templates from _load_global_templates()

    Returns:
        Tuple of (matched_task, is_exact, only_in_project, only_in_global)
        - matched_task: Task name of matching global template, or None
        - is_exact: True if structure matches exactly
        - only_in_project: Items only in project template
        - only_in_global: Items only in global template
    """
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

        # Exact match
        if len(only_in_project) == 0 and len(only_in_global) == 0:
            return task_name, True, set(), set()

        # Track best partial match (most overlap)
        if overlap > best_overlap:
            best_overlap = overlap
            best_match = task_name
            best_only_project = only_in_project
            best_only_global = only_in_global

    # Return best partial match if significant overlap (>50%)
    if best_match and best_overlap > len(project_struct) * 0.5:
        return best_match, False, best_only_project, best_only_global

    return None, False, set(), set()

_MISSING_TOKEN = "n/a"
_LANGUAGE_KEY_RE = re.compile(r"^[a-z]{2}(?:-[a-z]{2})?$", re.IGNORECASE)

# Pattern to detect run suffix in column names: _run-01, _run-02, _run01, _run02, etc.
# Format: {QUESTIONNAIRE}_{ITEM}_run-{NN} or {QUESTIONNAIRE}_{ITEM}_run{NN}
_RUN_SUFFIX_PATTERN = re.compile(r"^(.+)_run-?(\d+)$", re.IGNORECASE)

# LimeSurvey system columns - these are platform metadata, not questionnaire responses
# They should be extracted to a separate tool-limesurvey file
LIMESURVEY_SYSTEM_COLUMNS = {
    # Core system fields
    "id",               # LimeSurvey response ID
    "submitdate",       # Survey completion timestamp
    "startdate",        # Survey start timestamp
    "datestamp",        # Date stamp
    "lastpage",         # Last page viewed
    "startlanguage",    # Language at start
    "seed",             # Randomization seed
    "token",            # Participant token
    "ipaddr",           # IP address (sensitive)
    "refurl",           # Referrer URL
    # Timing fields
    "interviewtime",    # Total interview time
    # Other common LimeSurvey fields
    "optout",           # Opt-out status
    "emailstatus",      # Email status
    "attribute_1",      # Custom attributes
    "attribute_2",
    "attribute_3",
}

# Pattern for LimeSurvey group timing columns: groupTime123, grouptime456, etc.
_LS_TIMING_PATTERN = re.compile(r"^grouptime\d+$", re.IGNORECASE)


def _is_limesurvey_system_column(column_name: str) -> bool:
    """Check if a column is a LimeSurvey system/metadata column.

    Args:
        column_name: Column name to check

    Returns:
        True if this is a LimeSurvey system column that should be
        extracted to tool-limesurvey file instead of questionnaire data.
    """
    col_lower = column_name.strip().lower()

    # Check against known system columns
    if col_lower in LIMESURVEY_SYSTEM_COLUMNS:
        return True

    # Check timing pattern (groupTimeXXX)
    if _LS_TIMING_PATTERN.match(col_lower):
        return True

    # Check for Duration_ prefix (group duration columns)
    if col_lower.startswith("duration_"):
        return True

    return False


def _extract_limesurvey_columns(df_columns: list[str]) -> tuple[list[str], list[str]]:
    """Separate LimeSurvey system columns from questionnaire columns.

    Args:
        df_columns: List of all column names from dataframe

    Returns:
        Tuple of (ls_system_cols, other_cols)
        - ls_system_cols: Columns that are LimeSurvey system metadata
        - other_cols: Remaining columns (questionnaire data, participant info, etc.)
    """
    ls_cols = []
    other_cols = []

    for col in df_columns:
        if _is_limesurvey_system_column(col):
            ls_cols.append(col)
        else:
            other_cols.append(col)

    return ls_cols, other_cols


def _parse_run_from_column(column_name: str) -> tuple[str, int | None]:
    """Parse run information from a column name.

    Detects PRISM naming convention: {QUESTIONNAIRE}_{ITEM}_run-{NN}

    Args:
        column_name: Column name to parse (e.g., 'PANAS_1_run-01', 'PHQ9_3')

    Returns:
        Tuple of (base_column_name, run_number)
        - If run detected: ('PANAS_1', 1)
        - If no run: ('PHQ9_3', None)
    """
    match = _RUN_SUFFIX_PATTERN.match(column_name.strip())
    if match:
        base_name = match.group(1)
        run_num = int(match.group(2))
        return base_name, run_num
    return column_name, None


def _group_columns_by_run(columns: list[str]) -> dict[str, dict[int | None, list[str]]]:
    """Group columns by their base name and run number.

    Args:
        columns: List of column names

    Returns:
        Dict mapping base_column_name -> {run_number -> [original_column_names]}
        Example: {'PANAS_1': {1: ['PANAS_1_run-01'], 2: ['PANAS_1_run-02']}}
    """
    grouped: dict[str, dict[int | None, list[str]]] = {}
    for col in columns:
        base_name, run_num = _parse_run_from_column(col)
        if base_name not in grouped:
            grouped[base_name] = {}
        if run_num not in grouped[base_name]:
            grouped[base_name][run_num] = []
        grouped[base_name][run_num].append(col)
    return grouped


def _strip_internal_keys(sidecar: dict) -> dict:
    """Remove internal underscore-prefixed keys that would fail schema validation."""
    if not isinstance(sidecar, dict):
        return sidecar
    # Create a copy to avoid side effects
    out = dict(sidecar)
    # Filter keys matching internal patterns
    for k in list(out.keys()):
        if str(k).startswith("_"):
            del out[k]
    return out


def _resolve_dataset_root(output_root: Path) -> Path:
    """Resolve dataset root to avoid writing sidecars into subject/session folders."""
    parts = list(output_root.parts)
    cut_idx = None
    for idx, part in enumerate(parts):
        if part.startswith("sub-") or part.startswith("ses-"):
            cut_idx = idx
            break
    if cut_idx is None or cut_idx == 0:
        return output_root
    return Path(*parts[:cut_idx])


@dataclass(frozen=True)
class SurveyConvertResult:
    tasks_included: list[str]
    unknown_columns: list[str]
    missing_items_by_task: dict[str, int]
    id_column: str
    session_column: str | None
    missing_cells_by_subject: dict[str, int] = field(default_factory=dict)
    missing_value_token: str = _MISSING_TOKEN
    conversion_warnings: list[str] = field(default_factory=list)
    task_runs: dict[str, int | None] = field(default_factory=dict)  # task -> max run number (None if single occurrence)
    # Enhanced dry-run information
    dry_run_preview: dict | None = None  # Detailed preview of what will be created


def _build_bids_survey_filename(
    sub_id: str,
    ses_id: str,
    task: str,
    run: int | None = None,
    extension: str = "tsv"
) -> str:
    """Build a BIDS-compliant survey filename.

    Args:
        sub_id: Subject ID (e.g., 'sub-001')
        ses_id: Session ID (e.g., 'ses-01')
        task: Task name (e.g., 'panas')
        run: Run number (1, 2, 3...) or None if single occurrence
        extension: File extension without dot (default: 'tsv')

    Returns:
        Filename like 'sub-001_ses-01_task-panas_survey.tsv' (no run)
        or 'sub-001_ses-01_task-panas_run-01_survey.tsv' (with run)
    """
    parts = [sub_id, ses_id, f"task-{task}"]
    if run is not None:
        parts.append(f"run-{run:02d}")
    parts.append("survey")  # Add suffix without extension
    return "_".join(parts) + f".{extension}"


def _determine_task_runs(tasks_with_data: set[str], task_occurrences: dict[str, int]) -> dict[str, int | None]:
    """Determine which tasks need run numbers based on occurrence count.

    Args:
        tasks_with_data: Set of task names that have data
        task_occurrences: Dict mapping task name to number of occurrences in session

    Returns:
        Dict mapping task name to max run number (None if single occurrence)
    """
    task_runs: dict[str, int | None] = {}
    for task in tasks_with_data:
        count = task_occurrences.get(task, 1)
        if count > 1:
            task_runs[task] = count
        else:
            task_runs[task] = None
    return task_runs


def _load_participants_mapping(output_root: Path, log_fn=None) -> dict | None:
    """Load participants_mapping.json from the project.

    The mapping file specifies which source columns should be included in
    participants.tsv and how they map to standard variable names.

    Args:
        output_root: Path to the output root (rawdata/ or dataset root)
        log_fn: Optional logging function (callable taking message string)

    Returns:
        Mapping dict if found, None otherwise
    """
    # Determine project root from output_root
    if output_root.name == "rawdata":
        project_root = output_root.parent
    else:
        project_root = output_root

    # Search locations for participants_mapping.json
    candidates = [
        project_root / "participants_mapping.json",
        project_root / "code" / "participants_mapping.json",
        project_root / "code" / "library" / "participants_mapping.json",
    ]

    for p in candidates:
        if p.exists() and p.is_file():
            try:
                mapping = _read_json(p)
                if log_fn:
                    log_fn(f"Loaded participants_mapping.json from: {p}")
                return mapping
            except Exception as e:
                if log_fn:
                    log_fn(f"Warning: Failed to load {p}: {e}")
                continue
    
    if log_fn:
        log_fn("No participants_mapping.json found (using template columns only)")
    return None


def _get_mapped_columns(mapping: dict | None) -> tuple[set[str], dict[str, str], dict[str, dict]]:
    """Extract column information from participants mapping.

    Args:
        mapping: The participants_mapping.json content

    Returns:
        Tuple of:
        - allowed_columns: Set of source column names that should be included
        - column_renames: Dict mapping source_column -> standard_variable
        - value_mappings: Dict mapping standard_variable -> {source_val: target_val}
    """
    if not mapping or "mappings" not in mapping:
        return set(), {}, {}

    allowed_columns: set[str] = set()
    column_renames: dict[str, str] = {}
    value_mappings: dict[str, dict] = {}

    for var_name, spec in mapping.get("mappings", {}).items():
        if not isinstance(spec, dict):
            continue
        source_col = spec.get("source_column")
        standard_var = spec.get("standard_variable", var_name)

        if source_col:
            allowed_columns.add(source_col.lower())
            column_renames[source_col.lower()] = standard_var

            if "value_mapping" in spec:
                value_mappings[standard_var] = spec["value_mapping"]

    return allowed_columns, column_renames, value_mappings


def _load_participants_template(library_dir: Path) -> dict | None:
    """Load a participant template from the survey library, if present.

    We prioritize a library-level `participants.json` (sibling of the survey/
    folder) and fall back to legacy names `survey-participants.json` and
    `survey-participant.json` placed alongside the survey templates.
    
    Finally, we fall back to the official participants template as a global reference.
    """

    library_dir = library_dir.resolve()
    candidates: list[Path] = []
    if library_dir.name == "survey":
        candidates.append(library_dir.parent / "participants.json")

    candidates.extend(
        [
            library_dir / "participants.json",
            library_dir / "survey-participants.json",
            library_dir / "survey-participant.json",
        ]
    )

    # Also try a few ancestor folders (code/library -> project root) for participants.json
    for ancestor in library_dir.parents[:3]:
        candidates.append(ancestor / "participants.json")

    # Add the official template as a fallback
    try:
        app_root = Path(__file__).parent.parent.parent.resolve()
        official_template = app_root / "official" / "participants.json"
        candidates.append(official_template)
    except Exception:
        pass

    seen: set[Path] = set()
    for p in candidates:
        if p in seen:
            continue
        seen.add(p)
        if p.exists() and p.is_file():
            try:
                return _read_json(p)
            except Exception:
                return None
    return None


def _is_participant_template(path: Path) -> bool:
    stem = path.stem.lower()
    return stem in {"survey-participant", "survey-participants"}


def _normalize_participant_template_dict(template: dict | None) -> dict | None:
    """Extract column definitions from a participant template structure."""

    if not isinstance(template, dict):
        return None
    if "Columns" in template and isinstance(template.get("Columns"), dict):
        return template.get("Columns")
    return template


def _participants_json_from_template(
    *,
    columns: list[str],
    template: dict | None,
    extra_descriptions: dict[str, str] | None = None,
) -> dict:
    """Create a BIDS/NeuroBagel-compatible participants.json for the given TSV columns.

    All columns in the output TSV must be documented in participants.json.
    This function ensures NeuroBagel compatibility by:
    - Including full metadata from the official template (with semantic annotations)
    - Adding descriptions for extra columns from participants_mapping.json

    Args:
        columns: List of column names in the output TSV
        template: The official participants template (from official/participants.json)
        extra_descriptions: Additional descriptions from participants_mapping.json
                           for columns not in the template

    Returns:
        Dict suitable for writing as participants.json
    """
    template = _normalize_participant_template_dict(template)
    extra_descriptions = extra_descriptions or {}
    out: dict[str, dict] = {}

    def _template_meta(col: str) -> dict:
        if not template:
            return {}
        if col not in template:
            return {}
        v = template.get(col)
        if not isinstance(v, dict):
            return {}
        meta: dict[str, object] = {}

        # Copy all relevant metadata fields for NeuroBagel compatibility
        desc = v.get("Description")
        if desc:
            meta["Description"] = desc
        levels = v.get("Levels")
        if isinstance(levels, dict) and levels:
            meta["Levels"] = levels
        units = v.get("Units") or v.get("Unit")
        if units:
            meta["Units"] = units
        # Include additional metadata for NeuroBagel
        for key in ("DataType", "VariableType", "MinValue", "MaxValue", "Annotations"):
            if key in v:
                meta[key] = v[key]
        return meta

    for col in columns:
        if col == "participant_id":
            out[col] = {
                "Description": "Participant identifier (BIDS subject label)",
            }
            continue

        # Try to get metadata from official template first
        meta = _template_meta(col)

        if not meta:
            # Column not in template - check for description from mapping
            if col in extra_descriptions:
                meta = {"Description": extra_descriptions[col]}
            else:
                # Minimal fallback - column must still be documented
                meta = {"Description": col}
                # Add sensible defaults for common columns
                if col == "age":
                    meta["Description"] = "Age of participant"
                    meta["Units"] = "years"
                elif col == "sex":
                    meta["Description"] = "Biological sex"
                elif col == "gender":
                    meta["Description"] = "Gender identity"

        out[col] = dict(meta)

    return out


def _normalize_language(lang: str | None) -> str | None:
    if not lang:
        return None
    norm = str(lang).strip().lower()
    return norm or None


def _copy_templates_to_project(
    *,
    templates: dict,
    tasks_with_data: set[str],
    dataset_root: Path,
    language: str | None,
    technical_overrides: dict | None
) -> None:
    """Copy used templates to project's code/library/survey/ for reproducibility.
    
    Following YODA principles, this ensures the exact templates used during conversion
    are preserved in the project, making it self-contained and reproducible.
    
    Args:
        templates: Dict of loaded templates (task -> {path, json})
        tasks_with_data: Set of tasks that were actually used
        dataset_root: Root of the dataset (parent of rawdata/)
        language: Language used for localization
        technical_overrides: Any technical field overrides applied
    """
    # Determine project root (parent of rawdata/)
    if dataset_root.name == "rawdata":
        project_root = dataset_root.parent
    else:
        # Dataset root might be the project root itself
        rawdata_path = dataset_root / "rawdata"
        if rawdata_path.exists() and rawdata_path.is_dir():
            project_root = dataset_root
        else:
            # Can't determine project root, skip copying
            return
    
    # Create code/library/survey/ folder (YODA-compliant)
    library_dir = project_root / "code" / "library" / "survey"
    library_dir.mkdir(parents=True, exist_ok=True)
    
    # Copy each used template
    for task in sorted(tasks_with_data):
        if task not in templates:
            continue
            
        template_data = templates[task]["json"]
        output_filename = f"survey-{task}.json"
        output_path = library_dir / output_filename
        
        # Only copy if it doesn't already exist (don't overwrite user customizations)
        if not output_path.exists():
            # Apply same transformations as the sidecar
            localized = _localize_survey_template(template_data, language=language)
            localized = _inject_missing_token(localized, token=_MISSING_TOKEN)
            if technical_overrides:
                localized = _apply_technical_overrides(localized, technical_overrides)
            
            # Keep internal keys in the library copy (unlike sidecars)
            # This preserves all metadata for potential future use
            _write_json(output_path, localized)


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


def convert_survey_xlsx_to_prism_dataset(
    *,
    input_path: str | Path,
    library_dir: str | Path,
    output_root: str | Path,
    survey: str | None = None,
    id_column: str | None = None,
    session_column: str | None = None,
    session: str | None = None,
    sheet: str | int = 0,
    unknown: str = "warn",
    dry_run: bool = False,
    force: bool = False,
    name: str | None = None,
    authors: list[str] | None = None,
    language: str | None = None,
    alias_file: str | Path | None = None,
    id_map_file: str | Path | None = None,
    duplicate_handling: str = "error",
) -> SurveyConvertResult:
    """Convert a wide survey Excel table into a PRISM dataset.

    Parameters mirror `prism_tools.py survey convert`.

    Raises:
        ValueError: for user errors (missing files, invalid columns, etc.)
        RuntimeError: for unexpected conversion failures
    """

    input_path = Path(input_path).resolve()
    sheet_arg: str | int = sheet
    if isinstance(sheet_arg, str) and sheet_arg.isdigit():
        sheet_arg = int(sheet_arg)

    suffix = input_path.suffix.lower()
    if suffix not in {".xlsx", ".csv", ".tsv"}:
        raise ValueError("Supported formats: .xlsx, .csv, .tsv")

    kind = "xlsx" if suffix == ".xlsx" else ("csv" if suffix == ".csv" else "tsv")
    df = _read_table_as_dataframe(input_path=input_path, kind=kind, sheet=sheet_arg)

    return _convert_survey_dataframe_to_prism_dataset(
        df=df,
        library_dir=library_dir,
        output_root=output_root,
        survey=survey,
        id_column=id_column,
        session_column=session_column,
        session=session,
        unknown=unknown,
        dry_run=dry_run,
        force=force,
        name=name,
        authors=authors,
        language=language,
        alias_file=alias_file,
        id_map_file=id_map_file,
        strict_levels=True,
        duplicate_handling=duplicate_handling,
    )


def convert_survey_lsa_to_prism_dataset(
    *,
    input_path: str | Path,
    library_dir: str | Path,
    output_root: str | Path,
    survey: str | None = None,
    id_column: str | None = None,
    session_column: str | None = None,
    session: str | None = None,
    unknown: str = "warn",
    dry_run: bool = False,
    force: bool = False,
    name: str | None = None,
    authors: list[str] | None = None,
    language: str | None = None,
    alias_file: str | Path | None = None,
    id_map_file: str | Path | None = None,
    strict_levels: bool | None = None,
    duplicate_handling: str = "error",
) -> SurveyConvertResult:
    """Convert a LimeSurvey response archive (.lsa) into a PRISM dataset.

    The .lsa file is a zip archive. We extract the embedded *_responses.lsr XML and
    treat it as a wide table where each column is a survey item / variable.
    """

    input_path = Path(input_path).resolve()
    if input_path.suffix.lower() not in {".lsa"}:
        raise ValueError("Currently only .lsa input is supported.")

    result = _read_table_as_dataframe(input_path=input_path, kind="lsa")
    # LSA returns (df, questions_map); other formats return just df
    if isinstance(result, tuple):
        df, lsa_questions_map = result
    else:
        df = result
        lsa_questions_map = None

    # If language was not explicitly specified, try to infer it from the LSA.
    inferred_lang, inferred_tech = _infer_lsa_language_and_tech(input_path=input_path, df=df)
    effective_language = language
    if not effective_language or effective_language.strip().lower() == "auto":
        effective_language = inferred_lang

    effective_strict_levels = False if strict_levels is None else bool(strict_levels)

    return _convert_survey_dataframe_to_prism_dataset(
        df=df,
        library_dir=library_dir,
        output_root=output_root,
        survey=survey,
        id_column=id_column,
        session_column=session_column,
        session=session,
        unknown=unknown,
        dry_run=dry_run,
        force=force,
        name=name,
        authors=authors,
        language=effective_language,
        technical_overrides=inferred_tech,
        alias_file=alias_file,
        id_map_file=id_map_file,
        strict_levels=effective_strict_levels,
        duplicate_handling=duplicate_handling,
        lsa_questions_map=lsa_questions_map,
    )


def _debug_print_file_head(input_path: Path, num_lines: int = 4):
    """Print the first few lines of a text file for debugging/visibility in terminal."""
    try:
        # Avoid binary files
        if input_path.suffix.lower() in {".xlsx", ".xls", ".lsa", ".zip", ".gz"}:
            return

        with open(input_path, "r", encoding="utf-8", errors="replace") as f:
            print(f"\n[DEBUG] --- First {num_lines} lines of {input_path.name} ---")
            for i in range(num_lines):
                line = f.readline()
                if not line:
                    break
                print(f"L{i+1}: {line.rstrip()}")
            header_len = 26 + len(input_path.name)
            print("-" * header_len + "\n")
    except Exception:
        # Silently fail if we can't read/print
        pass


def _load_id_mapping(path: str | Path | None) -> dict[str, str] | None:
    """Load subject ID mapping (source -> participant_id) from TSV/CSV.

    The mapping file must have at least two columns; the first is treated as the
    source/LimeSurvey ID and the second as the target participant_id.
    """
    if not path:
        return None

    p = Path(path)
    if not p.exists():
        raise ValueError(f"ID map file not found: {p}")

    # DEBUG: Log file details
    file_size = p.stat().st_size
    print(f"[PRISM DEBUG] Loading ID map: {p} (size: {file_size} bytes)")

    try:
        import pandas as pd
    except Exception as e:  # pragma: no cover
        raise RuntimeError(
            "pandas is required for survey conversion. Ensure dependencies are installed via setup.sh"
        ) from e

    # Choose delimiter based on extension, fall back to auto-sniff
    sep = None
    suffix = p.suffix.lower()
    if suffix == ".tsv":
        sep = "\t"
    elif suffix == ".csv":
        sep = ","

    # First, manually inspect the file to debug
    try:
        with open(p, "r", encoding="utf-8-sig") as f:
            first_line = f.readline()
            if first_line:
                print(f"[PRISM DEBUG] First line of ID map: {repr(first_line[:100])}")
    except Exception as debug_e:
        print(f"[PRISM DEBUG] Could not read first line: {debug_e}")

    try:
        df = pd.read_csv(p, sep=sep, engine="python", encoding="utf-8-sig")
    except Exception as e:
        # Last attempt: sniff delimiter, then manual parse to avoid pandas edge cases on small files
        try:
            import csv
            with open(p, "r", encoding="utf-8-sig", errors="replace") as f:
                sample = f.read(4096)
                if not sample.strip():
                    raise ValueError("ID map file is empty")
                sniff_sep = csv.Sniffer().sniff(sample).delimiter
                print(f"[PRISM DEBUG] Sniffed delimiter: {repr(sniff_sep)}")
                f.seek(0)
                reader = csv.reader(f, delimiter=sniff_sep)
                rows = list(reader)
                if not rows:
                    raise ValueError("ID map file contains no rows")
                if len(rows[0]) < 2:
                    raise ValueError(f"ID map must have at least two columns, got {len(rows[0])}")
                print(f"[PRISM DEBUG] Manually parsed {len(rows)} rows")
                df = pd.DataFrame(rows)
        except Exception as inner:
            raise ValueError(
                f"Error loading ID map {p}: {inner}. Try saving as UTF-8 TSV with a tab delimiter or CSV with commas."
            ) from inner

    if df is None or df.empty:
        raise ValueError(f"ID map file is empty: {p}")

    if df.shape[1] < 2:
        raise ValueError(f"ID map file {p} must have at least two columns (source_id, participant_id)")

    df = df.iloc[:, :2].copy()
    df.columns = ["source_id", "participant_id"]
    df["source_id"] = df["source_id"].astype(str).str.strip()
    df["participant_id"] = df["participant_id"].astype(str).str.strip()

    mapping = {
        row["source_id"]: row["participant_id"]
        for _, row in df.iterrows()
        if row["source_id"] and row["participant_id"]
    }

    if not mapping:
        raise ValueError(f"ID map file {p} contains no valid mappings")

    print(f"[PRISM DEBUG] Loaded ID map with {len(mapping)} entries")
    return mapping


def _extract_lsa_questions_map(input_path: Path) -> dict | None:
    """Extract questions_map from LSA file for metadata lookup.
    
    Returns a dict mapping qid -> {title, question, type, ...} or None if extraction fails.
    """
    try:
        with zipfile.ZipFile(input_path) as zf:
            # Find and read the .lss (structure) file
            lss_members = [n for n in zf.namelist() if n.endswith(".lss")]
            if not lss_members:
                return None
            
            xml_bytes = zf.read(lss_members[0])
            
            # Parse XML
            try:
                lss_root = ET.fromstring(xml_bytes)
            except Exception:
                try:
                    text = xml_bytes.decode("utf-8", errors="replace")
                    text = re.sub(r'<\?xml.*?\?>', '', text, 1)
                    lss_root = ET.fromstring(text.strip())
                except Exception:
                    return None
            
            # Helper to extract text
            def get_text(element, tag):
                child = element.find(tag)
                return (child.text or "").strip() if child is not None else ""
            
            # Parse questions section to build qid -> title + question mapping
            questions_map = {}
            questions_section = lss_root.find("questions")
            if questions_section is not None:
                rows = questions_section.find("rows")
                if rows is not None:
                    for row in rows.findall("row"):
                        qid = get_text(row, "qid")
                        title = get_text(row, "title")  # Variable name like 'ADS01'
                        question_text = get_text(row, "question")
                        
                        # Clean HTML tags
                        clean_question = re.sub("<[^<]+?>", "", question_text).strip()
                        
                        if qid:
                            questions_map[qid] = {
                                "title": title,
                                "question": clean_question
                            }
            
            return questions_map if questions_map else None
    except Exception:
        return None


def _read_table_as_dataframe(*, input_path: Path, kind: str, sheet: str | int = 0):
    # Print head for visibility in terminal
    _debug_print_file_head(input_path)

    try:
        import pandas as pd
    except Exception as e:  # pragma: no cover
        raise RuntimeError(
            "pandas is required for survey conversion. Ensure dependencies are installed via setup.sh"
        ) from e

    EmptyDataError = getattr(pd.errors, "EmptyDataError", ValueError)

    if kind == "xlsx":
        try:
            df = pd.read_excel(input_path, sheet_name=sheet)
        except EmptyDataError:
            raise ValueError("Input Excel is empty (no content in file).")
        except Exception as e:
            raise ValueError(f"Failed to read Excel: {e}") from e

        if df is None or df.empty:
            raise ValueError("Input Excel is empty (no content in file).")

        return df.rename(columns={c: str(c).strip() for c in df.columns})

    if kind == "csv":
        try:
            df = pd.read_csv(input_path)
        except EmptyDataError:
            raise ValueError("Input CSV is empty (no content in file).")
        except Exception as e:
            raise ValueError(f"Failed to read CSV: {e}") from e

        if df is None or df.empty:
            raise ValueError("Input CSV is empty (no content in file).")

        return df.rename(columns={c: str(c).strip() for c in df.columns})

    if kind == "tsv":
        try:
            df = pd.read_csv(input_path, sep="\t")
        except EmptyDataError:
            raise ValueError("Input TSV is empty (no content in file).")
        except Exception as e:
            raise ValueError(f"Failed to read TSV: {e}") from e

        if df is None or df.empty:
            raise ValueError("Input TSV is empty (no content in file).")

        # Check if file was parsed correctly (wrong delimiter detection)
        if len(df.columns) == 1:
            col_name = str(df.columns[0])
            # If the single column name contains semicolons or commas, likely wrong delimiter
            if ";" in col_name:
                raise ValueError(
                    "TSV file appears to use semicolons (;) as delimiter instead of tabs. "
                    "Please convert to tab-separated format or save as CSV."
                )
            elif "," in col_name:
                raise ValueError(
                    "TSV file appears to use commas as delimiter instead of tabs. "
                    "Please save as .csv file or convert to tab-separated format."
                )

        return df.rename(columns={c: str(c).strip() for c in df.columns})

    if kind == "lsa":
        def _normalize_lsa_columns(cols: list[str], questions_map: dict | None = None) -> list[str]:
            """Normalize LimeSurvey export column names using QID lookup.
            
            Args:
                cols: List of column names from LSR responses
                questions_map: Optional dict mapping qid -> {title, question}
            
            Returns:
                List of normalized column names with QIDs replaced by question codes
            """
            # Pattern to match: _SurveyIDXGroupIDXQuestionID[suffix]
            pattern = re.compile(r"^_?(\d+)X(\d+)X(\d+)(.*)$")
            
            # Build qid_to_title lookup if questions_map is available
            qid_to_title = {}
            if questions_map:
                qid_to_title = {qid: info["title"] for qid, info in questions_map.items()}
            
            used: set[str] = set()
            out_cols: list[str] = []
            
            for c in cols:
                s = str(c).strip()
                m = pattern.match(s)
                candidate = s
                
                if m:
                    # Extract QID and suffix
                    qid = m.group(3)
                    suffix = (m.group(4) or "").strip()
                    
                    # If suffix exists, use it
                    if suffix:
                        candidate = suffix
                    # Otherwise, try QID lookup
                    elif qid in qid_to_title:
                        candidate = qid_to_title[qid]
                    # Fallback: use QID as-is
                    else:
                        candidate = qid
                
                # Avoid collisions
                base_candidate = candidate
                counter = 1
                while candidate in used:
                    candidate = f"{base_candidate}_{counter}"
                    counter += 1
                used.add(candidate)
                out_cols.append(candidate)
            
            return out_cols

        def _find_responses_member(zf: zipfile.ZipFile) -> str:
            matches = [name for name in zf.namelist() if name.endswith("_responses.lsr")]
            if not matches:
                # Some LSA exports use different naming or case
                matches = [name for name in zf.namelist() if "_responses" in name.lower()]
            if not matches:
                raise ValueError("No survey response file (e.g. *_responses.lsr) found inside the .lsa archive")
            matches.sort()
            return matches[0]

        def _parse_rows(xml_bytes: bytes) -> list[dict[str, str]]:
            """Robust XML parsing for LimeSurvey LSR data."""
            try:
                # Try to handle potential encoding issues by decoding with replacement if it's not valid XML
                # although ET.fromstring usually handles bytes with encoding declarations correctly.
                root = ET.fromstring(xml_bytes)
            except Exception as e:
                # Fallback: try decoding as utf-8 and remove encoding declaration if ET failed
                try:
                    text = xml_bytes.decode("utf-8", errors="replace")
                    # Remove XML declaration if it conflicts with our decoded string
                    text = re.sub(r'<\?xml.*?\?>', '', text, 1)
                    root = ET.fromstring(text.strip())
                except Exception:
                    raise ValueError(f"XML parsing failed: {e}")

            rows: list[dict[str, str]] = []
            for row in root.findall(".//row"):
                record: dict[str, str] = {}
                for child in row:
                    tag = child.tag
                    if "}" in tag:
                        tag = tag.split("}", 1)[1]
                    # Handle multiple children with same tag if they ever occur
                    val = (child.text or "").strip()
                    if tag in record and record[tag]:
                        record[tag] = f"{record[tag]}; {val}"
                    else:
                        record[tag] = val
                if record:
                    rows.append(record)
            return rows

        try:
            with zipfile.ZipFile(input_path) as zf:
                member = _find_responses_member(zf)
                try:
                    xml_bytes = zf.read(member)
                except Exception as e:
                    raise ValueError(f"Failed to read member '{member}' from LSA: {e}")
        except zipfile.BadZipFile as e:
            raise ValueError(f"Invalid .lsa archive (not a valid zip file): {e}") from e
        except Exception as e:
            raise ValueError(str(e)) from e

        rows = _parse_rows(xml_bytes)
        if not rows:
            raise ValueError("No response rows found in the LimeSurvey data.")

        df = pd.DataFrame(rows)
        # Drop completely empty columns
        df = df.dropna(axis=1, how='all')
        
        # Strip all string values
        for col in df.columns:
            if df[col].dtype == object:
                df[col] = df[col].str.strip()

        df = df.rename(columns={c: str(c).strip() for c in df.columns})
        
        # Extract questions_map for metadata lookup BEFORE normalizing columns
        questions_map = _extract_lsa_questions_map(input_path)
        
        # Normalize columns using questions_map for QID lookup
        df.columns = _normalize_lsa_columns([str(c) for c in df.columns], questions_map)
        
        # Return tuple of (df, questions_map) for LSA files
        return (df, questions_map)

    raise ValueError(f"Unsupported table kind: {kind}")

def _convert_survey_dataframe_to_prism_dataset(
    *,
    df,
    library_dir: str | Path,
    output_root: str | Path,
    survey: str | None,
    id_column: str | None,
    session_column: str | None,
    session: str | None = None,
    unknown: str,
    dry_run: bool,
    force: bool,
    name: str | None,
    authors: list[str] | None,
    language: str | None,
    technical_overrides: dict | None = None,
    alias_file: str | Path | None = None,
    id_map_file: str | Path | None = None,
    strict_levels: bool = True,
    duplicate_handling: str = "error",
    lsa_questions_map: dict | None = None,
) -> SurveyConvertResult:
    if unknown not in {"error", "warn", "ignore"}:
        raise ValueError("unknown must be one of: error, warn, ignore")
    if duplicate_handling not in {"error", "keep_first", "keep_last", "sessions"}:
        raise ValueError("duplicate_handling must be one of: error, keep_first, keep_last, sessions")

    library_dir = Path(library_dir).resolve()
    output_root = Path(output_root).resolve()

    if not library_dir.exists() or not library_dir.is_dir():
        raise ValueError(f"Library folder does not exist or is not a directory: {library_dir}")

    if output_root.exists() and any(output_root.iterdir()) and not force:
        raise ValueError(
            f"Output directory is not empty: {output_root}. Use force=True to write into a non-empty directory."
        )

    try:
        import pandas as pd
    except Exception as e:  # pragma: no cover
        raise RuntimeError(
            "pandas is required for survey conversion. Ensure dependencies are installed via setup.sh"
        ) from e

    # Determine normalization logic
    def _normalize_sub_id(val) -> str:
        s = sanitize_id(str(val).strip())
        if not s:
            return s
        if s.startswith("sub-"):
            return s
        if s.isdigit() and len(s) < 3:
            s = s.zfill(3)
        return f"sub-{s}"

    def _normalize_ses_id(val) -> str:
        s = sanitize_id(str(val).strip())
        if not s:
            return "ses-1"
        if s.startswith("ses-"):
            return s
        return f"ses-{s}"

    def _is_missing_value(val) -> bool:
        if pd.isna(val):
            return True
        if isinstance(val, str) and val.strip() == "":
            return True
        return False

    # --- Load Aliases and Templates ---
    alias_map: dict[str, str] | None = None
    canonical_aliases: dict[str, list[str]] | None = None
    if alias_file:
        alias_path = Path(alias_file).resolve()
        if alias_path.exists() and alias_path.is_file():
            rows = _read_alias_rows(alias_path)
            if rows:
                alias_map = _build_alias_map(rows)
                canonical_aliases = _build_canonical_aliases(rows)

    # Initialize conversion warnings list early (will be extended throughout processing)
    conversion_warnings: list[str] = []

    # Load participant template and compare with global
    raw_participant_template = _load_participants_template(library_dir)
    participant_template = _normalize_participant_template_dict(raw_participant_template)
    participant_columns_lower: set[str] = set()
    if participant_template:
        participant_columns_lower = {
            str(k).strip().lower() for k in participant_template.keys() if isinstance(k, str)
        }

    # Compare participants.json with global
    global_participants = _load_global_participants_template()
    if raw_participant_template and global_participants:
        _, _, _, part_warnings = _compare_participants_templates(
            raw_participant_template, global_participants
        )
        conversion_warnings.extend(part_warnings)

    templates, item_to_task, duplicates, template_warnings = _load_and_preprocess_templates(
        library_dir, canonical_aliases, compare_with_global=True
    )
    if duplicates:
        msg_lines = ["Duplicate item IDs found across survey templates (ambiguous mapping):"]
        for it_id, tsks in sorted(duplicates.items()):
            msg_lines.append(f"- {it_id}: {', '.join(sorted(tsks))}")
        raise ValueError("\n".join(msg_lines))

    # Add template comparison warnings to conversion warnings
    if template_warnings:
        conversion_warnings.extend(template_warnings)

    # --- Survey Filtering ---
    selected_tasks: set[str] | None = None
    if survey:
        parts = [p.strip() for p in str(survey).replace(";", ",").split(",")]
        parts = [p for p in parts if p]
        selected = {p.lower().replace("survey-", "") for p in parts}
        unknown_surveys = sorted([t for t in selected if t not in templates])
        if unknown_surveys:
            raise ValueError(
                "Unknown surveys: " + ", ".join(unknown_surveys) + ". Available: " + ", ".join(sorted(templates.keys()))
            )
        selected_tasks = selected

    # --- Determine Columns ---
    res_id_col, res_ses_col = _resolve_id_and_session_cols(
        df, id_column, session_column, participants_template=participant_template
    )

    # --- Apply subject ID mapping if provided ---
    id_map: dict[str, str] | None = _load_id_mapping(id_map_file)
    if id_map:
        df = df.copy()
        df[res_id_col] = df[res_id_col].astype(str).str.strip()
        ids_in_data = set(df[res_id_col].unique())
        missing = sorted([i for i in ids_in_data if i not in id_map])
        if missing:
            sample = ", ".join(missing[:20])
            more = "" if len(missing) <= 20 else f" (+{len(missing) - 20} more)"
            raise ValueError(
                f"ID mapping incomplete: {len(missing)} IDs from data are missing in the mapping: {sample}{more}."
            )

        df[res_id_col] = df[res_id_col].map(lambda x: id_map.get(str(x).strip(), x))
        conversion_warnings.append(
            f"Applied subject ID mapping from {Path(id_map_file).name} ({len(id_map)} entries)."
        )

    if alias_map:
        df = _apply_alias_map_to_dataframe(df=df, alias_map=alias_map)

    # --- Extract LimeSurvey System Columns ---
    # These are platform metadata (timestamps, tokens, timings) that should be
    # written to a separate tool-limesurvey file, not mixed with questionnaire data
    ls_system_cols, _ = _extract_limesurvey_columns(list(df.columns))

    # Handle duplicate IDs based on duplicate_handling parameter
    normalized_ids = df[res_id_col].astype(str).map(_normalize_sub_id)
    if normalized_ids.duplicated().any():
        dup_ids = sorted(set(normalized_ids[normalized_ids.duplicated()]))
        dup_count = len(dup_ids)

        if duplicate_handling == "error":
            raise ValueError(f"Duplicate participant_id values after normalization: {', '.join(dup_ids[:5])}")
        elif duplicate_handling == "keep_first":
            # Keep first occurrence, drop subsequent duplicates
            df = df[~normalized_ids.duplicated(keep="first")].copy()
            normalized_ids = df[res_id_col].astype(str).map(_normalize_sub_id)
            conversion_warnings.append(f"Duplicate IDs found ({dup_count} duplicates). Kept first occurrence for: {', '.join(dup_ids[:5])}")
        elif duplicate_handling == "keep_last":
            # Keep last occurrence, drop earlier duplicates
            df = df[~normalized_ids.duplicated(keep="last")].copy()
            normalized_ids = df[res_id_col].astype(str).map(_normalize_sub_id)
            conversion_warnings.append(f"Duplicate IDs found ({dup_count} duplicates). Kept last occurrence for: {', '.join(dup_ids[:5])}")
        elif duplicate_handling == "sessions":
            # Create multiple sessions for duplicates (ses-1, ses-2, etc.)
            # Add a session counter column based on occurrence order
            df = df.copy()
            df["_dup_session_num"] = df.groupby(normalized_ids.values).cumcount() + 1
            # Override session column with the computed session numbers
            res_ses_col = "_dup_session_num"
            conversion_warnings.append(f"Duplicate IDs found ({dup_count} duplicates). Created multiple sessions for: {', '.join(dup_ids[:5])}")

    col_to_mapping, unknown_cols, map_warnings, task_runs = _map_survey_columns(
        df=df,
        item_to_task=item_to_task,
        participant_columns_lower=participant_columns_lower,
        id_col=res_id_col,
        ses_col=res_ses_col,
        unknown_mode=unknown,
    )
    conversion_warnings.extend(map_warnings)

    # Extract tasks from mappings
    tasks_with_data = {m.task for m in col_to_mapping.values()}
    if selected_tasks is not None:
        tasks_with_data = tasks_with_data.intersection(selected_tasks)
    if not tasks_with_data:
        raise ValueError("No survey item columns matched the selected templates.")

    # Build col_to_task for backward compatibility with existing functions
    col_to_task = {col: m.task for col, m in col_to_mapping.items()}

    # Group columns by (task, run) for run-aware processing
    task_run_columns: dict[tuple[str, int | None], list[str]] = {}
    for col, mapping in col_to_mapping.items():
        key = (mapping.task, mapping.run)
        if key not in task_run_columns:
            task_run_columns[key] = []
        task_run_columns[key].append(col)

    # --- Results Preparation ---
    missing_items_by_task = _compute_missing_items_report(tasks_with_data, templates, col_to_task)

    if dry_run:
        # Generate detailed dry-run preview
        dry_run_preview = _generate_dry_run_preview(
            df=df,
            tasks_with_data=tasks_with_data,
            task_run_columns=task_run_columns,
            col_to_mapping=col_to_mapping,
            templates=templates,
            res_id_col=res_id_col,
            res_ses_col=res_ses_col,
            session=session,
            selected_tasks=selected_tasks,
            normalize_sub_fn=_normalize_sub_id,
            normalize_ses_fn=_normalize_ses_id,
            is_missing_fn=_is_missing_value,
            ls_system_cols=ls_system_cols,
            participant_template=participant_template,
            output_root=output_root,
            dataset_root=_resolve_dataset_root(output_root),
            lsa_questions_map=lsa_questions_map,
        )
        
        return SurveyConvertResult(
            tasks_included=sorted(tasks_with_data),
            unknown_columns=unknown_cols,
            missing_items_by_task=missing_items_by_task,
            id_column=res_id_col,
            session_column=res_ses_col,
            conversion_warnings=conversion_warnings,
            task_runs=task_runs,
            dry_run_preview=dry_run_preview,
        )

    # --- Write Output ---
    _ensure_dir(output_root)
    dataset_root = _resolve_dataset_root(output_root)
    _ensure_dir(dataset_root)
    _write_survey_description(dataset_root, name, authors)

    # Write LimeSurvey system metadata sidecar at root level (if LS columns present)
    if ls_system_cols:
        _write_limesurvey_sidecar(
            dataset_root=dataset_root,
            ls_columns=ls_system_cols,
            ls_version=technical_overrides.get("SoftwareVersion") if technical_overrides else None,
            force=force,
        )

    _write_survey_participants(
        df=df,
        output_root=dataset_root,
        id_col=res_id_col,
        ses_col=res_ses_col,
        participant_template=participant_template,
        normalize_sub_fn=_normalize_sub_id,
        is_missing_fn=_is_missing_value,
    )

    # Write task sidecars
    for task in sorted(tasks_with_data):
        sidecar_path = dataset_root / f"task-{task}_survey.json"
        if not sidecar_path.exists() or force:
            localized = _localize_survey_template(templates[task]["json"], language=language)
            localized = _inject_missing_token(localized, token=_MISSING_TOKEN)
            if technical_overrides:
                localized = _apply_technical_overrides(localized, technical_overrides)
            # Remove internal keys before writing to avoid schema validation errors
            cleaned = _strip_internal_keys(localized)
            _write_json(sidecar_path, cleaned)

    # Copy used templates to project's code/library/ for reproducibility (YODA)
    # This ensures the exact template used for conversion is preserved in the project
    _copy_templates_to_project(
        templates=templates,
        tasks_with_data=tasks_with_data,
        dataset_root=dataset_root,
        language=language,
        technical_overrides=technical_overrides
    )

    # --- Process and Write Responses ---
    missing_cells_by_subject: dict[str, int] = {}
    items_using_tolerance: dict[str, set[str]] = {}

    for _, row in df.iterrows():
        sub_id = _normalize_sub_id(row[res_id_col])
        ses_id = _normalize_ses_id(session) if session else (
            _normalize_ses_id(row[res_ses_col]) if res_ses_col else "ses-1"
        )
        modality_dir = _ensure_dir(output_root / sub_id / ses_id / "survey")

        # Write LimeSurvey system data for this subject/session (if LS columns present)
        if ls_system_cols:
            _write_limesurvey_data(
                row=row,
                ls_columns=ls_system_cols,
                sub_id=sub_id,
                ses_id=ses_id,
                modality_dir=modality_dir,
                normalize_val_fn=_normalize_item_value,
            )

        # Process each (task, run) combination separately
        for (task, run), columns in sorted(task_run_columns.items()):
            if selected_tasks is not None and task not in selected_tasks:
                continue

            schema = templates[task]["json"]

            # Build mapping from base item names to actual column names for this run
            run_col_mapping = {col_to_mapping[c].base_item: c for c in columns}

            out_row, missing_count = _process_survey_row_with_run(
                row=row,
                df_cols=df.columns,
                task=task,
                run=run,
                schema=schema,
                run_col_mapping=run_col_mapping,
                sub_id=sub_id,
                strict_levels=strict_levels,
                items_using_tolerance=items_using_tolerance,
                is_missing_fn=_is_missing_value,
                normalize_val_fn=_normalize_item_value,
            )
            missing_cells_by_subject[sub_id] = missing_cells_by_subject.get(sub_id, 0) + missing_count

            # Write TSV with run number if needed
            expected_cols = [k for k in schema.keys() if k not in _NON_ITEM_TOPLEVEL_KEYS and k not in schema.get("_aliases", {})]

            # Determine if run number should be in filename
            # Only include run if this task has multiple runs detected
            include_run = task_runs.get(task) is not None
            effective_run = run if include_run else None

            filename = _build_bids_survey_filename(sub_id, ses_id, task, effective_run, "tsv")
            res_file = modality_dir / filename

            with open(res_file, "w", encoding="utf-8", newline="") as f:
                writer = csv.DictWriter(f, fieldnames=expected_cols, delimiter="\t", lineterminator="\n")
                writer.writeheader()
                writer.writerow(out_row)

    # Add summary for items using numeric range tolerance
    if items_using_tolerance:
        for task, item_ids in sorted(items_using_tolerance.items()):
            sorted_items = sorted(list(item_ids))
            shown = ", ".join(sorted_items[:10])
            more = "" if len(sorted_items) <= 10 else f" (+{len(sorted_items)-10} more)"
            conversion_warnings.append(
                f"Task '{task}': Numeric values for items [{shown}{more}] were accepted via range tolerance."
            )

    # Automatically update .bidsignore to exclude PRISM-specific metadata/folders
    # that standard BIDS validators don't recognize.
    check_and_update_bidsignore(dataset_root, ["survey"])

    return SurveyConvertResult(
        tasks_included=sorted(tasks_with_data),
        unknown_columns=unknown_cols,
        missing_items_by_task=missing_items_by_task,
        id_column=res_id_col,
        session_column=res_ses_col,
        missing_cells_by_subject=missing_cells_by_subject,
        missing_value_token=_MISSING_TOKEN,
        conversion_warnings=conversion_warnings,
        task_runs=task_runs,
    )


def _normalize_item_value(val) -> str:
    from pandas import isna
    if isna(val) or (isinstance(val, str) and str(val).strip() == ""):
        return _MISSING_TOKEN
    if isinstance(val, bool):
        return str(val).lower()
    if isinstance(val, int):
        return str(int(val))
    if isinstance(val, float):
        if val.is_integer():
            return str(int(val))
        return str(val)
    return str(val)


def _resolve_id_and_session_cols(
    df, id_column: str | None, session_column: str | None,
    participants_template: dict | None = None
) -> tuple[str, str | None]:
    """Helper to determine participant ID and session columns from dataframe.

    Priority for ID column detection:
    1. Explicit id_column parameter
    2. _sourceField from participants.json (if participant_id has _sourceField)
    3. Common column name patterns (participant_id, subject, id, code, token)
    """

    def _find_col(candidates: set[str]) -> str | None:
        lower_map = {str(c).strip().lower(): str(c).strip() for c in df.columns}
        for c in candidates:
            if c in lower_map:
                return lower_map[c]
        return None

    def _find_col_exact_or_lower(col_name: str) -> str | None:
        """Find column by exact match first, then case-insensitive."""
        # Exact match
        if col_name in df.columns:
            return col_name
        # Case-insensitive match
        lower_map = {str(c).strip().lower(): str(c).strip() for c in df.columns}
        if col_name.lower() in lower_map:
            return lower_map[col_name.lower()]
        return None

    resolved_id = id_column
    if resolved_id:
        if resolved_id not in df.columns:
            raise ValueError(
                f"id_column '{resolved_id}' not found. Columns: {', '.join([str(c) for c in df.columns])}"
            )
    else:
        # Priority 1: Check participants_template for _sourceField
        source_field = None
        if participants_template:
            # Check if participant_id has _sourceField defined
            pid_def = participants_template.get("participant_id")
            if isinstance(pid_def, dict) and "_sourceField" in pid_def:
                source_field = pid_def.get("_sourceField")
                if source_field:
                    resolved_id = _find_col_exact_or_lower(source_field)
                    if not resolved_id:
                        # _sourceField specified but column not found, try common patterns
                        source_field = None

        # Priority 2: Common column name patterns
        if not resolved_id:
            # LimeSurvey response archives commonly use `token`.
            resolved_id = _find_col(
                {"participant_id", "subject", "id", "sub_id", "participant", "code", "token"}
            )
            if not resolved_id:
                if source_field:
                    raise ValueError(
                        f"participants.json specifies _sourceField='{source_field}' but column not found. "
                        f"Columns: {', '.join([str(c) for c in df.columns])}"
                    )
                raise ValueError(
                    "Could not determine participant id column. Provide id_column explicitly (e.g., participant_id, CODE)."
                )

    resolved_ses: str | None
    if session_column:
        if session_column not in df.columns:
            raise ValueError(f"session_column '{session_column}' not found in input columns")
        resolved_ses = session_column
    else:
        resolved_ses = _find_col({"session", "ses", "visit", "timepoint"})

    return str(resolved_id), resolved_ses


@dataclass
class ColumnMapping:
    """Mapping information for a single column."""
    task: str
    run: int | None  # None if single occurrence, 1/2/3... if multiple runs
    base_item: str   # Item name without run suffix (for template lookup)


def _map_survey_columns(
    *,
    df,
    item_to_task: dict[str, str],
    participant_columns_lower: set[str],
    id_col: str,
    ses_col: str | None,
    unknown_mode: str,
) -> tuple[dict[str, ColumnMapping], list[str], list[str], dict[str, int | None]]:
    """Determine which columns map to which surveys and identify unmapped columns.

    Now also detects run information from PRISM naming convention:
    {QUESTIONNAIRE}_{ITEM}_run-{NN}

    Returns:
        col_to_mapping: Dict mapping column name to ColumnMapping(task, run, base_item)
        unknown_cols: List of unmapped column names
        warnings: List of warning messages
        task_runs: Dict mapping task name to max run number (None if single occurrence)
    """
    lower_to_col = {str(c).strip().lower(): str(c).strip() for c in df.columns}

    # Detect participant-related columns first so they are not treated as unmapped survey items.
    participant_fallbacks = {
        "age",
        "sex",
        "gender",
        "education",
        "handedness",
        "completion_date",
    }

    participant_columns_present = {
        lower_to_col[c]
        for c in (participant_columns_lower | participant_fallbacks)
        if c in lower_to_col
    }

    cols = [c for c in df.columns if c not in {id_col} and c != ses_col]
    col_to_mapping: dict[str, ColumnMapping] = {}
    unknown_cols: list[str] = []

    # Track runs per task: task -> set of run numbers seen
    task_run_tracker: dict[str, set[int | None]] = {}

    for c in cols:
        col_lower = str(c).strip().lower()

        # Skip participant columns
        if c in participant_columns_present or col_lower in participant_columns_present:
            continue
        if col_lower in participant_columns_lower:
            continue

        # Parse run suffix from column name
        base_name, run_num = _parse_run_from_column(c)

        # Try to match against templates (original name first, then base name)
        matched_task = None
        matched_base = c

        if c in item_to_task:
            # Direct match (e.g., 'PANAS_1' without run suffix)
            matched_task = item_to_task[c]
            matched_base = c
        elif base_name in item_to_task:
            # Match after stripping run suffix (e.g., 'PANAS_1' from 'PANAS_1_run-01')
            matched_task = item_to_task[base_name]
            matched_base = base_name

        if matched_task:
            col_to_mapping[c] = ColumnMapping(
                task=matched_task,
                run=run_num,
                base_item=matched_base
            )
            # Track runs for this task
            if matched_task not in task_run_tracker:
                task_run_tracker[matched_task] = set()
            task_run_tracker[matched_task].add(run_num)
        else:
            unknown_cols.append(c)

    # Determine final run assignments per task
    # If a task has only items with run=None, no runs needed
    # If a task has items with run numbers, all items for that task get run numbers
    task_runs: dict[str, int | None] = {}
    for task, runs in task_run_tracker.items():
        # Remove None and get max run number
        run_numbers = [r for r in runs if r is not None]
        if run_numbers:
            task_runs[task] = max(run_numbers)
        else:
            task_runs[task] = None

    warnings: list[str] = []
    bookkeeping = {
        "id", "submitdate", "lastpage", "startlanguage", "seed", "startdate", "datestamp",
        "token", "refurl", "ipaddr", "googleid", "session_id", "participant_id",
        "attribute_1", "attribute_2", "attribute_3"
    }
    filtered_unknown = [c for c in unknown_cols if str(c).lower() not in bookkeeping]

    if filtered_unknown:
        if unknown_mode == "error":
            raise ValueError("Unmapped columns: " + ", ".join(filtered_unknown))
        if unknown_mode == "warn":
            shown = ", ".join(filtered_unknown[:10])
            more = "" if len(filtered_unknown) <= 10 else f" (+{len(filtered_unknown)-10} more)"
            warnings.append(f"Unmapped columns (not in any survey template): {shown}{more}")

    return col_to_mapping, unknown_cols, warnings, task_runs


def _write_limesurvey_sidecar(
    dataset_root: Path,
    ls_columns: list[str],
    ls_version: str | None = None,
    force: bool = False,
) -> Path | None:
    """Write the root-level tool-limesurvey_survey.json sidecar.

    This sidecar describes the LimeSurvey system columns present in the data.
    It's written once at the dataset root and applies to all subjects via BIDS inheritance.

    Args:
        dataset_root: Path to dataset root directory
        ls_columns: List of LimeSurvey system column names present in data
        ls_version: LimeSurvey version string (if detected)
        force: Overwrite existing file if True

    Returns:
        Path to written sidecar, or None if nothing written
    """
    if not ls_columns:
        return None

    sidecar_path = dataset_root / "tool-limesurvey_survey.json"
    if sidecar_path.exists() and not force:
        return sidecar_path

    # Build sidecar content
    from datetime import date
    today = date.today().isoformat()

    sidecar = {
        "Metadata": {
            "SchemaVersion": "1.0.0",
            "CreationDate": today,
            "Tool": "LimeSurvey",
        },
        "SystemFields": {},
    }

    if ls_version:
        sidecar["Metadata"]["ToolVersion"] = ls_version

    # Field descriptions for common LimeSurvey columns
    field_descriptions = {
        "id": {"Description": "LimeSurvey response ID", "DataType": "integer"},
        "submitdate": {"Description": "Survey completion timestamp", "DataType": "string", "Format": "ISO8601"},
        "startdate": {"Description": "Survey start timestamp", "DataType": "string", "Format": "ISO8601"},
        "datestamp": {"Description": "Date stamp of response", "DataType": "string"},
        "lastpage": {"Description": "Last page number viewed by participant", "DataType": "integer"},
        "startlanguage": {"Description": "Language code at survey start", "DataType": "string"},
        "seed": {"Description": "Randomization seed for question/answer order", "DataType": "string"},
        "token": {"Description": "Participant access token", "DataType": "string"},
        "ipaddr": {"Description": "IP address of respondent", "DataType": "string", "SensitiveData": True},
        "refurl": {"Description": "Referrer URL", "DataType": "string"},
        "interviewtime": {"Description": "Total time spent on survey", "DataType": "float", "Unit": "seconds"},
        "optout": {"Description": "Opt-out status", "DataType": "string"},
        "emailstatus": {"Description": "Email delivery status", "DataType": "string"},
    }

    # Add descriptions for columns present in data
    for col in ls_columns:
        col_lower = col.lower()
        if col_lower in field_descriptions:
            sidecar["SystemFields"][col] = field_descriptions[col_lower]
        elif col_lower.startswith("grouptime"):
            # Extract group number if possible
            sidecar["SystemFields"][col] = {
                "Description": f"Time spent on question group",
                "DataType": "float",
                "Unit": "seconds",
            }
        elif col_lower.startswith("duration_"):
            group_name = col[9:]  # Remove "Duration_" prefix
            sidecar["SystemFields"][col] = {
                "Description": f"Time spent on group: {group_name}",
                "DataType": "float",
                "Unit": "seconds",
            }
        elif col_lower.startswith("attribute_"):
            sidecar["SystemFields"][col] = {
                "Description": "Custom participant attribute",
                "DataType": "string",
            }
        else:
            sidecar["SystemFields"][col] = {
                "Description": f"LimeSurvey system field: {col}",
            }

    _write_json(sidecar_path, sidecar)
    return sidecar_path


def _write_limesurvey_data(
    *,
    row,
    ls_columns: list[str],
    sub_id: str,
    ses_id: str,
    modality_dir: Path,
    normalize_val_fn,
) -> Path | None:
    """Write LimeSurvey system data for a single subject/session.

    Args:
        row: DataFrame row with the data
        ls_columns: List of LimeSurvey system columns to extract
        sub_id: Subject ID (e.g., 'sub-001')
        ses_id: Session ID (e.g., 'ses-01')
        modality_dir: Path to survey modality directory
        normalize_val_fn: Function to normalize values

    Returns:
        Path to written TSV file, or None if no data
    """
    if not ls_columns:
        return None

    # Filter to only columns present in this row
    present_cols = [c for c in ls_columns if c in row.index]
    if not present_cols:
        return None

    # Build output row
    out_row = {}
    for col in present_cols:
        val = row[col]
        out_row[col] = normalize_val_fn(val)

    # Write TSV
    filename = f"{sub_id}_{ses_id}_tool-limesurvey_survey.tsv"
    res_file = modality_dir / filename

    with open(res_file, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=present_cols, delimiter="\t", lineterminator="\n")
        writer.writeheader()
        writer.writerow(out_row)

    return res_file


def _write_survey_description(output_root: Path, name: str | None, authors: list[str] | None):
    """Write dataset_description.json if it doesn't exist."""
    ds_desc = output_root / "dataset_description.json"
    if ds_desc.exists():
        return

    dataset_description = {
        "Name": name or "PRISM Survey Dataset",
        "BIDSVersion": "1.10.1",
        "DatasetType": "raw",
        "Authors": authors or ["PRISM Survey Converter"],
        "Acknowledgements": "This dataset was created using the PRISM framework.",
        "HowToAcknowledge": "Please cite the original survey publication and the PRISM framework.",
        "Keywords": ["psychology", "survey", "PRISM"],
        "GeneratedBy": [
            {
                "Name": "PRISM Survey Converter",
                "Version": "1.1.1",
                "Description": "Manual survey template mapping and TSV conversion."
            }
        ],
        "HEDVersion": "8.2.0"
    }
    _write_json(ds_desc, dataset_description)


def _write_survey_participants(
    *,
    df,
    output_root: Path,
    id_col: str,
    ses_col: str | None,
    participant_template: dict | None,
    normalize_sub_fn,
    is_missing_fn,
):
    """Write participants.tsv and participants.json.

    Column inclusion logic:
    1. If participants_mapping.json exists in project:
       - Only include columns explicitly defined in the mapping
       - Apply value transformations as specified
       - Rename columns to standard variable names
    2. If no mapping exists:
       - Only include columns that exist in the official participants template
       - No arbitrary extra columns from source data

    All columns in the output must have documentation in participants.json.
    """
    import pandas as pd

    lower_to_col = {str(c).strip().lower(): str(c).strip() for c in df.columns}

    # Try to load participants_mapping.json from the project
    # Determine project root for searching
    if output_root.name == "rawdata":
        search_root = output_root.parent
    else:
        search_root = output_root
    
    participants_mapping = _load_participants_mapping(output_root)
    mapped_cols, col_renames, value_mappings = _get_mapped_columns(participants_mapping)
    
    # Log what was found
    if participants_mapping:
        print(f"[INFO] Using participants_mapping.json from project ({len(mapped_cols)} mapped columns)")
        if col_renames:
            print(f"[INFO]   Column renames: {col_renames}")
        if value_mappings:
            print(f"[INFO]   Value transformations for: {list(value_mappings.keys())}")
    else:
        print(f"[INFO] No participants_mapping.json found (using template columns only)")

    # Start with participant_id column
    df_part = pd.DataFrame({"participant_id": df[id_col].astype(str).map(normalize_sub_fn)})

    # Normalize template to get column definitions
    template_norm = _normalize_participant_template_dict(participant_template)
    template_cols = set(template_norm.keys()) if template_norm else set()
    # Remove non-column keys from template
    non_column_keys = {"@context", "Technical", "I18n", "Study", "Metadata", "_aliases", "_reverse_aliases"}
    template_cols = template_cols - non_column_keys

    # Determine which columns to include
    extra_cols: list[str] = []
    col_output_names: dict[str, str] = {}  # Maps source col -> output name
    mapping_descriptions: dict[str, str] = {}  # Extra descriptions from mapping

    if participants_mapping and mapped_cols:
        # MODE 1: Use mapping - only include explicitly mapped columns
        for source_col_lower in mapped_cols:
            if source_col_lower in lower_to_col:
                actual_col = lower_to_col[source_col_lower]
                if actual_col not in {id_col, ses_col}:
                    extra_cols.append(actual_col)
                    # Get the standard variable name (renamed output)
                    output_name = col_renames.get(source_col_lower, source_col_lower)
                    col_output_names[actual_col] = output_name

        # Extract descriptions from mapping for columns not in template
        for var_name, spec in participants_mapping.get("mappings", {}).items():
            if isinstance(spec, dict):
                standard_var = spec.get("standard_variable", var_name)
                if standard_var not in template_cols and "description" in spec:
                    mapping_descriptions[standard_var] = spec["description"]
    else:
        # MODE 2: No mapping - only include columns defined in the official template
        for col in template_cols:
            if col in lower_to_col:
                actual_col = lower_to_col[col]
                if actual_col not in {id_col, ses_col}:
                    extra_cols.append(actual_col)
                    col_output_names[actual_col] = col

    if extra_cols:
        extra_cols = list(dict.fromkeys(extra_cols))
        df_extra = df[[id_col] + extra_cols].copy()

        # Apply value mappings and missing value handling
        for c in extra_cols:
            output_name = col_output_names.get(c, c)

            # Apply value mapping if specified
            if output_name in value_mappings:
                val_map = value_mappings[output_name]
                df_extra[c] = df_extra[c].astype(str).map(
                    lambda v, vm=val_map: vm.get(v, v) if v not in ("nan", "None", "") else _MISSING_TOKEN
                )
            else:
                df_extra[c] = df_extra[c].apply(lambda v: _MISSING_TOKEN if is_missing_fn(v) else v)

        df_extra[id_col] = df_extra[id_col].astype(str).map(normalize_sub_fn)
        df_extra = df_extra.groupby("participant_id", dropna=False)[extra_cols].first().reset_index()

        # Rename columns to standard variable names
        rename_map = {c: col_output_names.get(c, c) for c in extra_cols}
        df_extra = df_extra.rename(columns=rename_map)

        df_part = df_part.merge(df_extra, on="participant_id", how="left")

    df_part = df_part.drop_duplicates(subset=["participant_id"]).reset_index(drop=True)
    df_part.to_csv(output_root / "participants.tsv", sep="\t", index=False)

    # participants.json - all columns must be documented
    parts_json_path = output_root / "participants.json"
    p_json = _participants_json_from_template(
        columns=[str(c) for c in df_part.columns],
        template=participant_template,
        extra_descriptions=mapping_descriptions,
    )
    _write_json(parts_json_path, p_json)


def _load_and_preprocess_templates(
    library_dir: Path,
    canonical_aliases: dict[str, list[str]] | None,
    compare_with_global: bool = True,
) -> tuple[dict[str, dict], dict[str, str], dict[str, set[str]], list[str]]:
    """Load and prepare survey templates from library.

    Also compares project templates against global library templates to detect
    if they are structurally identical (same item keys) or modified.

    Args:
        library_dir: Path to the survey library directory
        canonical_aliases: Optional alias mappings
        compare_with_global: Whether to compare with global library

    Returns:
        Tuple of (templates, item_to_task, duplicates, template_warnings)
        - templates: Dict mapping task_name -> template data
        - item_to_task: Dict mapping item_key -> task_name
        - duplicates: Dict of duplicate item keys across templates
        - template_warnings: List of warnings about template differences
    """
    templates: dict[str, dict] = {}
    item_to_task: dict[str, str] = {}
    duplicates: dict[str, set[str]] = {}
    template_warnings: list[str] = []

    # Load global templates for comparison
    global_templates: dict[str, dict] = {}
    global_library_path = _load_global_library_path()
    is_using_global_library = False

    if compare_with_global and global_library_path:
        # Check if we're already using the global library
        try:
            if library_dir.resolve() == global_library_path.resolve():
                is_using_global_library = True
            else:
                global_templates = _load_global_templates()
        except Exception:
            pass

    for json_path in sorted(library_dir.glob("survey-*.json")):
        if _is_participant_template(json_path):
            continue
        try:
            sidecar = _read_json(json_path)
        except Exception:
            continue

        task_from_name = json_path.stem.replace("survey-", "")
        task = str(sidecar.get("Study", {}).get("TaskName") or task_from_name).strip()
        task_norm = task.lower() or task_from_name.lower()
        
        # DEBUG: Log which template is being loaded
        print(f"[PRISM DEBUG] Loading template: {json_path} (task: {task_norm})")

        if canonical_aliases:
            sidecar = _canonicalize_template_items(sidecar=sidecar, canonical_aliases=canonical_aliases)

        # Pre-process Aliases
        if "_aliases" not in sidecar:
            sidecar["_aliases"] = {}
        if "_reverse_aliases" not in sidecar:
            sidecar["_reverse_aliases"] = {}

        for k, v in list(sidecar.items()):
            if k in _NON_ITEM_TOPLEVEL_KEYS or not isinstance(v, dict):
                continue
            if "Aliases" in v and isinstance(v["Aliases"], list):
                for alias in v["Aliases"]:
                    sidecar["_aliases"][alias] = k
                    sidecar["_reverse_aliases"].setdefault(k, []).append(alias)
            if "AliasOf" in v:
                target = v["AliasOf"]
                sidecar["_aliases"][k] = target
                sidecar["_reverse_aliases"].setdefault(target, []).append(k)

            # Warn when an item mixes discrete Levels with numeric range
            has_levels = isinstance(v.get("Levels"), dict)
            has_range = "MinValue" in v or "MaxValue" in v
            if has_levels and has_range:
                template_warnings.append(
                    f"Template '{task_norm}' item '{k}' defines both Levels and Min/Max; numeric range takes precedence and Levels will be treated as labels only."
                )

        # Compare with global template if available
        template_source = "project"
        global_match_task = None
        if is_using_global_library:
            template_source = "global"
        elif global_templates:
            matched_task, is_exact, only_project, only_global = _find_matching_global_template(
                sidecar, global_templates
            )
            if matched_task:
                global_match_task = matched_task
                if is_exact:
                    template_source = "global"  # Identical to global
                else:
                    template_source = "modified"
                    # Add warning about structural differences
                    diff_parts = []
                    if only_project:
                        diff_parts.append(f"added: {', '.join(sorted(list(only_project)[:5]))}")
                        if len(only_project) > 5:
                            diff_parts[-1] += f" (+{len(only_project) - 5} more)"
                    if only_global:
                        diff_parts.append(f"removed: {', '.join(sorted(list(only_global)[:5]))}")
                        if len(only_global) > 5:
                            diff_parts[-1] += f" (+{len(only_global) - 5} more)"
                    template_warnings.append(
                        f"Template '{task_norm}' differs from global '{matched_task}': {'; '.join(diff_parts)}"
                    )

        templates[task_norm] = {
            "path": json_path,
            "json": sidecar,
            "task": task_norm,
            "source": template_source,
            "global_match": global_match_task,
        }

        for k, v in sidecar.items():
            if k in _NON_ITEM_TOPLEVEL_KEYS:
                continue
            if k in item_to_task and item_to_task[k] != task_norm:
                duplicates.setdefault(k, set()).update({item_to_task[k], task_norm})
            else:
                item_to_task[k] = task_norm
            # Aliases also mapped to task
            if isinstance(v, dict) and "Aliases" in v and isinstance(v["Aliases"], list):
                for alias in v["Aliases"]:
                    if alias in item_to_task and item_to_task[alias] != task_norm:
                        duplicates.setdefault(alias, set()).update({item_to_task[alias], task_norm})
                    else:
                        item_to_task[alias] = task_norm

    return templates, item_to_task, duplicates, template_warnings


def _compute_missing_items_report(tasks: set[str], templates: dict, col_to_task: dict) -> dict[str, int]:
    report: dict[str, int] = {}
    for task in sorted(tasks):
        schema = templates[task]["json"]
        expected = [k for k in schema.keys() if k not in _NON_ITEM_TOPLEVEL_KEYS]
        present = [c for c, t in col_to_task.items() if t == task]
        missing = [k for k in expected if k not in present]
        report[task] = len(missing)
    return report


def _generate_participants_preview(
    *,
    df,
    res_id_col: str,
    res_ses_col: str | None,
    session: str | None,
    normalize_sub_fn,
    normalize_ses_fn,
    is_missing_fn,
    participant_template: dict | None,
    output_root: Path,
    survey_columns: set[str] | None = None,
    ls_system_columns: list[str] | None = None,
    lsa_questions_map: dict | None = None,
) -> dict:
    """Generate a preview of what will be written to participants.tsv.
    
    Args:
        df: Input DataFrame
        res_id_col: Participant ID column name
        res_ses_col: Session column name (if any)
        session: Default session value
        normalize_sub_fn: Function to normalize subject IDs
        normalize_ses_fn: Function to normalize session IDs
        is_missing_fn: Function to check if a value is missing
        participant_template: Participant template dict
        output_root: Output root path
        survey_columns: Set of columns being used for survey items (optional)
        ls_system_columns: List of LimeSurvey system columns (optional)
    
    Returns:
        Dictionary with structure:
        {
            "columns": [...],  # Column names that will be in participants.tsv
            "sample_rows": [...],  # Sample rows (up to 10 first participants)
            "mappings": {...},  # Details about which source columns -> output columns
            "total_rows": int,  # Total number of participant rows
            "unused_columns": [...],  # Columns not used in survey or participants (candidates for mapping)
            "notes": [...]  # Any notes about the mapping
        }
    """
    import pandas as pd
    
    preview = {
        "columns": [],
        "sample_rows": [],
        "mappings": {},
        "total_rows": 0,
        "unused_columns": [],
        "notes": [],
    }
    
    # Load participants mapping if it exists
    participants_mapping = _load_participants_mapping(output_root)
    mapped_cols, col_renames, value_mappings = _get_mapped_columns(participants_mapping)
    
    # Get template columns
    lower_to_col = {str(c).strip().lower(): str(c).strip() for c in df.columns}
    template_norm = _normalize_participant_template_dict(participant_template)
    template_cols = set(template_norm.keys()) if template_norm else set()
    non_column_keys = {"@context", "Technical", "I18n", "Study", "Metadata", "_aliases", "_reverse_aliases"}
    template_cols = template_cols - non_column_keys
    
    # Determine which columns will be included
    extra_cols: list[str] = []
    col_output_names: dict[str, str] = {}  # source col -> output name
    
    if participants_mapping and mapped_cols:
        # Using explicit mapping
        for source_col_lower in mapped_cols:
            if source_col_lower in lower_to_col:
                actual_col = lower_to_col[source_col_lower]
                if actual_col not in {res_id_col, res_ses_col}:
                    extra_cols.append(actual_col)
                    output_name = col_renames.get(source_col_lower, source_col_lower)
                    col_output_names[actual_col] = output_name
        
        preview["notes"].append(
            f"Using participants_mapping.json with {len(mapped_cols)} explicit column mappings"
        )
    else:
        # Using template columns only
        for col in template_cols:
            if col in lower_to_col:
                actual_col = lower_to_col[col]
                if actual_col not in {res_id_col, res_ses_col}:
                    extra_cols.append(actual_col)
                    col_output_names[actual_col] = col
        
        if not extra_cols:
            preview["notes"].append(
                "No participants_mapping.json found. Using template columns only (or none available in data)."
            )
        else:
            preview["notes"].append(
                f"No participants_mapping.json found. Using {len(extra_cols)} columns from participant template."
            )
    
    # Build list of columns that will be in output
    output_columns = ["participant_id"] + [col_output_names.get(c, c) for c in extra_cols]
    preview["columns"] = output_columns
    
    # Build sample rows with actual data
    extra_cols = list(dict.fromkeys(extra_cols))  # Remove duplicates
    sample_rows = []
    
    for idx, row in df.iterrows():
        if len(sample_rows) >= 10:  # Limit to 10 sample rows
            break
        
        sub_id_raw = row[res_id_col]
        sub_id = normalize_sub_fn(sub_id_raw)
        
        row_data = {"participant_id": sub_id}
        
        for col in extra_cols:
            output_name = col_output_names.get(col, col)
            val = row.get(col)
            
            # Apply value mapping if specified
            if output_name in value_mappings:
                val_map = value_mappings[output_name]
                display_val = val_map.get(str(val), str(val)) if val not in ("nan", "None", "") else _MISSING_TOKEN
            else:
                if is_missing_fn(val):
                    display_val = _MISSING_TOKEN
                else:
                    display_val = str(val)
            
            row_data[output_name] = display_val
        
        sample_rows.append(row_data)
    
    preview["sample_rows"] = sample_rows
    preview["total_rows"] = len(df[res_id_col].unique())
    
    # Build mapping details
    if extra_cols:
        for col in extra_cols:
            output_name = col_output_names.get(col, col)
            preview["mappings"][output_name] = {
                "source_column": col,
                "has_value_mapping": output_name in value_mappings,
                "value_mapping": value_mappings.get(output_name, {}),
            }
    
    # Identify unused columns (potential participants.tsv candidates)
    # Unused columns are those that are:
    # - Not in col_output_names (not already mapped to participants.tsv)
    # - Not in survey_columns (not used for survey items)
    # - Not in ls_system_columns (not LimeSurvey system columns)
    # - Not the participant ID or session columns
    
    used_in_participants = set(extra_cols) | {res_id_col, res_ses_col} if res_ses_col else set(extra_cols) | {res_id_col}
    survey_cols = survey_columns or set()
    ls_sys_cols = set(ls_system_columns) if ls_system_columns else set()
    
    unused_cols = []
    
    for col in df.columns:
        if col not in used_in_participants and col not in survey_cols and col not in ls_sys_cols:
            # Skip completely empty columns (all NaN or all empty strings)
            has_data = df[col].notna().any()
            has_non_empty = (df[col].astype(str).str.strip() != "").any()
            
            if has_data and has_non_empty:
                unused_cols.append(col)
    
    # Decode cryptic LimeSurvey field names if we have questions_map
    unused_cols_with_descriptions = []
    if lsa_questions_map:
        # Build mapping from field code/qid to question title/text
        field_descriptions = {}
        for qid, q_info in lsa_questions_map.items():
            title = q_info.get("title", "")
            question = q_info.get("question", "")
            # Use title if available, otherwise use question text
            description = title if title else question
            field_descriptions[qid] = description
        
        # For each unused column, try to find matching description
        for col in sorted(unused_cols):
            # Try to extract QID from column name (format: suffix from _XXX pattern)
            # or use the column name directly if it's already a QID
            qid_match = re.search(r'^_\d+X\d+X(\d+)', col)
            qid = qid_match.group(1) if qid_match else col
            
            description = field_descriptions.get(qid, "")
            if description:
                unused_cols_with_descriptions.append({
                    "field_code": col,
                    "description": description
                })
            else:
                unused_cols_with_descriptions.append({
                    "field_code": col,
                    "description": ""
                })
        
        preview["unused_columns"] = unused_cols_with_descriptions
    else:
        # No LSA metadata, just show column names
        preview["unused_columns"] = sorted(unused_cols)
    
    return preview


def _generate_dry_run_preview(
    *,
    df,
    tasks_with_data: set[str],
    task_run_columns: dict[tuple[str, int | None], list[str]],
    col_to_mapping: dict,
    templates: dict,
    res_id_col: str,
    res_ses_col: str | None,
    session: str | None,
    selected_tasks: set[str] | None,
    normalize_sub_fn,
    normalize_ses_fn,
    is_missing_fn,
    ls_system_cols: list[str],
    participant_template: dict | None,
    output_root: Path,
    dataset_root: Path,
    lsa_questions_map: dict | None = None,
) -> dict:
    """Generate a detailed preview of what will be created during conversion.
    
    This shows:
    - Files that will be created
    - Participant mapping
    - Data quality issues (missing values, wrong formats, etc.)
    - Column mapping details
    """
    
    preview = {
        "summary": {},
        "participants": [],
        "files_to_create": [],
        "data_issues": [],
        "column_mapping": {},
    }
    
    # Summary
    preview["summary"] = {
        "total_participants": len(df),
        "unique_participants": df[res_id_col].nunique(),
        "tasks": sorted(tasks_with_data),
        "output_root": str(output_root),
        "dataset_root": str(dataset_root),
    }
    
    # Track data issues
    issues = []
    
    # Analyze each participant
    participants_info = []
    sub_ids_normalized = []
    
    for idx, row in df.iterrows():
        sub_id_raw = row[res_id_col]
        sub_id = normalize_sub_fn(sub_id_raw)
        sub_ids_normalized.append(sub_id)
        
        ses_id = normalize_ses_fn(session) if session else (
            normalize_ses_fn(row[res_ses_col]) if res_ses_col else "ses-1"
        )
        
        # Count missing values for this participant
        missing_count = 0
        total_items = 0
        
        for (task, run), columns in task_run_columns.items():
            if selected_tasks is not None and task not in selected_tasks:
                continue
            
            for col in columns:
                val = row.get(col)
                total_items += 1
                if is_missing_fn(val):
                    missing_count += 1
        
        participants_info.append({
            "participant_id": sub_id,
            "session_id": ses_id,
            "raw_id": str(sub_id_raw),
            "missing_values": missing_count,
            "total_items": total_items,
            "completeness_percent": round((total_items - missing_count) / total_items * 100, 1) if total_items > 0 else 100,
        })
    
    preview["participants"] = participants_info
    
    # Check for duplicate participants
    from collections import Counter
    id_counts = Counter(sub_ids_normalized)
    duplicates = {sub_id: count for sub_id, count in id_counts.items() if count > 1}
    if duplicates:
        issues.append({
            "type": "duplicate_ids",
            "severity": "error",
            "message": f"Found {len(duplicates)} duplicate participant IDs after normalization",
            "details": {k: v for k, v in list(duplicates.items())[:10]},  # Show first 10
        })
    
    # Analyze column mapping and data quality
    col_mapping_details = {}
    for col, mapping in col_to_mapping.items():
        task = mapping.task
        run = mapping.run
        base_item = mapping.base_item
        
        # Get schema for this task
        schema = templates[task]["json"]
        item_def = schema.get(base_item, {})
        
        # Analyze this column's data
        col_values = df[col]
        missing = col_values.apply(is_missing_fn).sum()
        total = len(col_values)
        unique_vals = col_values.dropna().unique()
        
        col_info = {
            "task": task,
            "run": run,
            "base_item": base_item,
            "missing_count": int(missing),
            "missing_percent": round(missing / total * 100, 1) if total > 0 else 0,
            "unique_values": len(unique_vals),
            "data_type": item_def.get("DataType", "unknown"),
        }
        
        # Check for Levels validation issues
        # BUT: If MinValue/MaxValue are defined, they take precedence (allow any numeric value in range)
        has_numeric_range = "MinValue" in item_def or "MaxValue" in item_def
        
        if "Levels" in item_def and isinstance(item_def["Levels"], dict) and not has_numeric_range:
            # Only validate against Levels if NO numeric range is defined
            expected_levels = set(str(k) for k in item_def["Levels"].keys())
            actual_values = set(str(v) for v in unique_vals if not is_missing_fn(v))
            unexpected = actual_values - expected_levels
            
            if unexpected:
                issues.append({
                    "type": "unexpected_values",
                    "severity": "warning",
                    "column": col,
                    "task": task,
                    "item": base_item,
                    "message": f"Column '{col}' has {len(unexpected)} unexpected value(s)",
                    "expected": sorted(expected_levels),
                    "unexpected": sorted(list(unexpected)[:20]),  # Show first 20
                })
                col_info["has_unexpected_values"] = True
        
        # Check for numeric range issues
        if "MinValue" in item_def or "MaxValue" in item_def:
            try:
                import pandas as pd
                numeric_vals = pd.to_numeric(col_values, errors='coerce').dropna()
                if len(numeric_vals) > 0:
                    min_val = item_def.get("MinValue")
                    max_val = item_def.get("MaxValue")
                    
                    out_of_range = []
                    if min_val is not None:
                        out_of_range.extend(numeric_vals[numeric_vals < min_val])
                    if max_val is not None:
                        out_of_range.extend(numeric_vals[numeric_vals > max_val])
                    
                    if len(out_of_range) > 0:
                        issues.append({
                            "type": "out_of_range",
                            "severity": "warning",
                            "column": col,
                            "task": task,
                            "item": base_item,
                            "message": f"Column '{col}' has {len(out_of_range)} value(s) outside expected range",
                            "range": f"[{min_val}, {max_val}]",
                            "out_of_range_count": len(out_of_range),
                        })
            except Exception:
                pass
        
        col_mapping_details[col] = col_info
    
    preview["column_mapping"] = col_mapping_details
    preview["data_issues"] = issues
    
    # List files that will be created
    files_to_create = []
    
    # Dataset description
    files_to_create.append({
        "path": "dataset_description.json",
        "type": "metadata",
        "description": "Dataset description (BIDS required)",
    })
    
    # Participants files
    files_to_create.append({
        "path": "participants.tsv",
        "type": "metadata",
        "description": f"Participant list ({len(participants_info)} participants)",
    })
    
    files_to_create.append({
        "path": "participants.json",
        "type": "metadata",
        "description": "Participant column definitions",
    })
    
    # Task sidecars
    for task in sorted(tasks_with_data):
        files_to_create.append({
            "path": f"task-{task}_survey.json",
            "type": "sidecar",
            "description": f"Survey template for {task}",
        })
    
    # LimeSurvey metadata (if present)
    if ls_system_cols:
        files_to_create.append({
            "path": "tool-limesurvey.json",
            "type": "sidecar",
            "description": f"LimeSurvey system metadata ({len(ls_system_cols)} columns)",
        })
    
    # Individual subject/session files
    for p_info in participants_info:
        sub_id = p_info["participant_id"]
        ses_id = p_info["session_id"]
        
        # LimeSurvey data file
        if ls_system_cols:
            files_to_create.append({
                "path": f"{sub_id}/{ses_id}/survey/{sub_id}_{ses_id}_tool-limesurvey.tsv",
                "type": "data",
                "description": "LimeSurvey system data",
            })
        
        # Survey data files
        for task in sorted(tasks_with_data):
            # Determine if this task has multiple runs
            max_run = max((r for t, r in task_run_columns.keys() if t == task and r is not None), default=None)
            
            if max_run is not None:
                # Multiple runs - create separate files
                for run_num in range(1, max_run + 1):
                    files_to_create.append({
                        "path": f"{sub_id}/{ses_id}/survey/{sub_id}_{ses_id}_task-{task}_run-{run_num:02d}_survey.tsv",
                        "type": "data",
                        "description": f"Survey responses for {task} (run {run_num})",
                    })
            else:
                # Single occurrence
                files_to_create.append({
                    "path": f"{sub_id}/{ses_id}/survey/{sub_id}_{ses_id}_task-{task}_survey.tsv",
                    "type": "data",
                    "description": f"Survey responses for {task}",
                })
    
    preview["files_to_create"] = files_to_create
    preview["summary"]["total_files"] = len(files_to_create)
    
    # Generate participants.tsv preview
    participants_tsv_preview = _generate_participants_preview(
        df=df,
        res_id_col=res_id_col,
        res_ses_col=res_ses_col,
        session=session,
        normalize_sub_fn=normalize_sub_fn,
        normalize_ses_fn=normalize_ses_fn,
        is_missing_fn=is_missing_fn,
        participant_template=participant_template,
        output_root=output_root,
        survey_columns=set(col_to_mapping.keys()),  # Columns used for survey items
        ls_system_columns=ls_system_cols,  # LimeSurvey system columns
        lsa_questions_map=lsa_questions_map,  # LSA metadata for decoding field names
    )
    preview["participants_tsv"] = participants_tsv_preview
    
    return preview


def _process_survey_row(
    *,
    row,
    df_cols,
    task: str,
    schema: dict,
    col_to_task: dict,
    sub_id: str,
    strict_levels: bool,
    items_using_tolerance: dict[str, set[str]],
    is_missing_fn,
    normalize_val_fn,
) -> tuple[dict[str, str], int]:
    """Process a single task's data for one subject/session."""
    all_items = [k for k in schema.keys() if k not in _NON_ITEM_TOPLEVEL_KEYS]
    expected = [k for k in all_items if k not in schema.get("_aliases", {})]
    
    out: dict[str, str] = {}
    missing_count = 0

    for item_id in expected:
        candidates = [item_id] + schema.get("_reverse_aliases", {}).get(item_id, [])
        found_val = None
        found_col = None

        for cand in candidates:
            if cand in df_cols and not is_missing_fn(row[cand]):
                found_val = row[cand]
                found_col = cand
                break

        if found_col:
            # Inline validation using the helper's logic
            _validate_survey_item_value(
                item_id=item_id,
                val=found_val,
                item_schema=schema.get(item_id),
                sub_id=sub_id,
                task=task,
                strict_levels=strict_levels,
                items_using_tolerance=items_using_tolerance,
                normalize_fn=normalize_val_fn,
                is_missing_fn=is_missing_fn,
            )
            norm = normalize_val_fn(found_val)
            if norm == _MISSING_TOKEN:
                missing_count += 1
            out[item_id] = norm
        else:
            out[item_id] = _MISSING_TOKEN
            missing_count += 1
            
    return out, missing_count


def _process_survey_row_with_run(
    *,
    row,
    df_cols,
    task: str,
    run: int | None,
    schema: dict,
    run_col_mapping: dict[str, str],  # base_item -> actual column name
    sub_id: str,
    strict_levels: bool,
    items_using_tolerance: dict[str, set[str]],
    is_missing_fn,
    normalize_val_fn,
) -> tuple[dict[str, str], int]:
    """Process a single task/run's data for one subject/session.

    Similar to _process_survey_row but uses run_col_mapping to find
    the correct column for each item (accounting for _run-XX suffixes).
    """
    all_items = [k for k in schema.keys() if k not in _NON_ITEM_TOPLEVEL_KEYS]
    expected = [k for k in all_items if k not in schema.get("_aliases", {})]

    out: dict[str, str] = {}
    missing_count = 0

    for item_id in expected:
        # Get candidates: item itself plus any aliases
        candidates = [item_id] + schema.get("_reverse_aliases", {}).get(item_id, [])
        found_val = None
        found_col = None

        for cand in candidates:
            # First check if there's a direct mapping for this candidate
            if cand in run_col_mapping:
                actual_col = run_col_mapping[cand]
                if actual_col in df_cols and not is_missing_fn(row[actual_col]):
                    found_val = row[actual_col]
                    found_col = actual_col
                    break
            # Fallback: check if candidate itself is in df_cols (for non-run data)
            elif cand in df_cols and not is_missing_fn(row[cand]):
                found_val = row[cand]
                found_col = cand
                break

        if found_col:
            # Inline validation using the helper's logic
            _validate_survey_item_value(
                item_id=item_id,
                val=found_val,
                item_schema=schema.get(item_id),
                sub_id=sub_id,
                task=task,
                strict_levels=strict_levels,
                items_using_tolerance=items_using_tolerance,
                normalize_fn=normalize_val_fn,
                is_missing_fn=is_missing_fn,
            )
            norm = normalize_val_fn(found_val)
            if norm == _MISSING_TOKEN:
                missing_count += 1
            out[item_id] = norm
        else:
            out[item_id] = _MISSING_TOKEN
            missing_count += 1

    return out, missing_count


def _validate_survey_item_value(
    *,
    item_id: str,
    val,
    item_schema: dict | None,
    sub_id: str,
    task: str,
    strict_levels: bool,
    items_using_tolerance: dict[str, set[str]],
    normalize_fn,
    is_missing_fn,
):
    """Internal validation for a single survey item value."""
    if is_missing_fn(val) or not isinstance(item_schema, dict):
        return

    levels = item_schema.get("Levels")
    if not isinstance(levels, dict) or not levels:
        return

    v_str = normalize_fn(val)
    if v_str == _MISSING_TOKEN:
        return

    if v_str in levels:
        return

    # Try numeric range tolerance
    try:
        def _to_float(x):
            try: return float(str(x).strip())
            except: return None
        
        v_num = _to_float(v_str)
        min_v = _to_float(item_schema.get("MinValue"))
        max_v = _to_float(item_schema.get("MaxValue"))
        
        if v_num is not None and min_v is not None and max_v is not None:
            if min_v <= v_num <= max_v:
                return

        if not strict_levels:
            l_nums = [n for n in [_to_float(k) for k in levels.keys()] if n is not None]
            if len(l_nums) >= 2 and v_num is not None:
                if min(l_nums) <= v_num <= max(l_nums):
                    items_using_tolerance.setdefault(task, set()).add(item_id)
                    return
    except:
        pass

    allowed = ", ".join(sorted(levels.keys()))
    raise ValueError(f"Invalid value '{val}' for '{item_id}' (Sub: {sub_id}, Task: {task}). Expected: {allowed}")


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
        else:
            item["Levels"] = {token: "Missing/Not provided"}

    return sidecar


def _read_alias_rows(path: Path) -> list[list[str]]:
    rows: list[list[str]] = []
    with open(path, "r", encoding="utf-8") as f:
        for raw in f:
            line = raw.strip()
            if not line:
                continue
            if line.startswith("#"):
                continue
            parts = [p.strip() for p in (line.split("\t") if "\t" in line else line.split())]
            parts = [p for p in parts if p]
            if len(parts) < 2:
                continue
            rows.append(parts)
    # allow header row
    if rows:
        first = [p.lower() for p in rows[0]]
        if first[0] in {"canonical", "canonical_id", "canonicalid", "id"}:
            rows = rows[1:]
    return rows


def _build_alias_map(rows: Iterable[list[str]]) -> dict[str, str]:
    """Return mapping alias -> canonical (canonical maps to itself)."""
    out: dict[str, str] = {}
    for parts in rows:
        canonical = str(parts[0]).strip()
        if not canonical:
            continue
        # canonical maps to itself
        out.setdefault(canonical, canonical)
        for alias in parts[1:]:
            a = str(alias).strip()
            if not a:
                continue
            if a in out and out[a] != canonical:
                raise ValueError(f"Alias '{a}' maps to multiple canonical IDs: {out[a]} vs {canonical}")
            out[a] = canonical
    return out


def _build_canonical_aliases(rows: Iterable[list[str]]) -> dict[str, list[str]]:
    out: dict[str, list[str]] = {}
    for parts in rows:
        canonical = str(parts[0]).strip()
        if not canonical:
            continue
        aliases = [str(p).strip() for p in parts[1:] if str(p).strip()]
        if not aliases:
            continue
        out.setdefault(canonical, [])
        for a in aliases:
            if a not in out[canonical]:
                out[canonical].append(a)
    return out


def _apply_alias_file_to_dataframe(*, df, alias_file: str | Path) -> "object":
    """Apply alias mapping to dataframe columns.

    Alias file format: TSV/whitespace; each line is:
      <canonical_id> <alias1> <alias2> ...
    """

    try:
        pass
    except Exception as e:  # pragma: no cover
        raise RuntimeError(
            "pandas is required for survey conversion. Ensure dependencies are installed via setup.sh"
        ) from e

    path = Path(alias_file).resolve()
    if not path.exists() or not path.is_file():
        raise ValueError(f"Alias file not found: {path}")

    rows = _read_alias_rows(path)
    if not rows:
        return df
    alias_map = _build_alias_map(rows)

    return _apply_alias_map_to_dataframe(df=df, alias_map=alias_map)


def _apply_alias_map_to_dataframe(*, df, alias_map: dict[str, str]) -> "object":
    """Apply an alias->canonical mapping to dataframe columns."""

    # Determine which existing columns would map to which canonical ID.
    canonical_to_cols: dict[str, list[str]] = {}
    for c in list(df.columns):
        canonical = alias_map.get(str(c), str(c))
        if canonical != str(c):
            canonical_to_cols.setdefault(canonical, []).append(str(c))

    if not canonical_to_cols:
        return df

    df = df.copy()

    def _as_na(series):
        # Treat empty/whitespace strings as missing for coalescing.
        if series.dtype == object:
            s = series.astype(str)
            s = s.map(lambda v: v.strip() if isinstance(v, str) else v)
            s = s.replace({"": pd.NA, "nan": pd.NA, "None": pd.NA})
            return s
        return series

    for canonical, cols in canonical_to_cols.items():
        cols_present = [c for c in cols if c in df.columns]
        if not cols_present:
            continue

        # Also include canonical itself if present (and coalesce into it).
        if canonical in df.columns and canonical not in cols_present:
            cols_present = [canonical] + cols_present

        if len(cols_present) == 1:
            src = cols_present[0]
            if src != canonical:
                # Only rename if it doesn't collide.
                if canonical not in df.columns:
                    df = df.rename(columns={src: canonical})
            continue

        # Coalesce multiple columns into canonical.
        combined = _as_na(df[cols_present[0]])
        for c in cols_present[1:]:
            combined = combined.combine_first(_as_na(df[c]))

        df[canonical] = combined
        for c in cols_present:
            if c != canonical and c in df.columns:
                df = df.drop(columns=[c])

    return df


def _canonicalize_template_items(*, sidecar: dict, canonical_aliases: dict[str, list[str]]) -> dict:
    """Remove/merge alias item IDs inside a survey template (in-memory).

    If a template contains both canonical and alias item IDs, keep only the canonical key.
    If it contains only the alias key, move it to the canonical key.
    """

    out = dict(sidecar)
    for canonical, aliases in (canonical_aliases or {}).items():
        for alias in aliases:
            if alias not in out:
                continue
            if canonical not in out:
                out[canonical] = out[alias]
            # Always drop the alias key to avoid duplicate columns.
            try:
                del out[alias]
            except Exception:
                pass
    return out


def _apply_technical_overrides(sidecar: dict, overrides: dict) -> dict:
    """Apply best-effort technical metadata without breaking existing templates."""
    out = deepcopy(sidecar)
    tech = out.get("Technical")
    if not isinstance(tech, dict):
        tech = {}
        out["Technical"] = tech

    for k, v in overrides.items():
        # Do not clobber required keys with empty values.
        if v is None:
            continue
        if isinstance(v, str) and v.strip() == "":
            continue
        tech[k] = v

    return out


def _infer_lsa_language_and_tech(*, input_path: Path, df) -> tuple[str | None, dict]:
    """Infer language and technical fields from a LimeSurvey .lsa archive.

    - Language:
      1) response column `startlanguage` if present (mode)
      2) first language found in embedded .lss (structure) export

    - Tech: inject LimeSurvey platform and (if found) version.
    """

    inferred_language: str | None = None
    tech: dict = {
        "SoftwarePlatform": "LimeSurvey",
        # More accurate than many library templates (paper-pencil).
        "CollectionMethod": "online",
        "ResponseType": ["mouse_click", "keypress"],
    }

    meta = infer_lsa_metadata(input_path)
    inferred_language = meta.get("language") or None
    if meta.get("software_version"):
        tech["SoftwareVersion"] = meta["software_version"]

    return inferred_language, tech


def infer_lsa_metadata(input_path: str | Path) -> dict:
    """Infer metadata from a LimeSurvey .lsa archive (best-effort).

    Returns keys:
      - language: str | None
      - software_platform: str (always 'LimeSurvey')
      - software_version: str | None
    """

    input_path = Path(input_path).resolve()
    language: str | None = None
    software_version: str | None = None

    def _mode(values: list[str]) -> str | None:
        if not values:
            return None
        counts: dict[str, int] = {}
        for v in values:
            counts[v] = counts.get(v, 0) + 1
        # deterministic tie-breaker
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
                text = re.sub(r'<\?xml.*?\?>', '', text, 1)
                return ET.fromstring(text.strip())
            except Exception:
                return None

    try:
        with zipfile.ZipFile(input_path) as zf:
            # responses (language per session)
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

            # structure (survey language + version)
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

