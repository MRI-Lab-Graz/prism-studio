"""Survey conversion utilities.

This module provides a programmatic API for converting wide survey tables (e.g. .xlsx)
into a PRISM/BIDS-style survey dataset.

Architecture note:
- Prefer class-based entry points for new integrations:
    ``SurveyResponsesConverter`` (response conversion) and
    ``ParticipantsConverter`` (participant-level handling).
- Keep top-level ``convert_survey_*`` functions for backward compatibility.

It is extracted from the CLI implementation in `prism_tools.py` so the Web UI and
GUI can call the same logic without invoking subprocesses or relying on `sys.exit`.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
import csv
import zipfile
import defusedxml.ElementTree as ET
import re

try:
    import pandas as pd
except ImportError:
    pd = None

from ..utils.io import (
    ensure_dir as _ensure_dir,
    read_json as _read_json,
    write_json as _write_json,
)
from ..utils.naming import sanitize_id
from ..bids_integration import check_and_update_bidsignore
from .survey_columns import (
    _RUN_SUFFIX_PATTERNS,
    LIMESURVEY_SYSTEM_COLUMNS,
    _LS_TIMING_PATTERN,
    _is_limesurvey_system_column,
    _extract_limesurvey_columns,
    _parse_run_from_column,
    _group_columns_by_run,
)
from .survey_helpers import (
    _NON_ITEM_TOPLEVEL_KEYS,
    _STYLING_KEYS,
    _extract_template_structure,
    _compare_template_structures,
    _build_bids_survey_filename,
    _determine_task_runs,
)
from .survey_participants import (
    _load_participants_mapping,
    _get_mapped_columns,
    _load_participants_template,
    _is_participant_template,
    _normalize_participant_template_dict,
    _participants_json_from_template,
)
from .survey_i18n import (
    _LANGUAGE_KEY_RE,
    _normalize_language,
    _default_language_from_template,
    _is_language_dict,
    _pick_language_value,
    _localize_survey_template,
)
from .survey_aliases import (
    _read_alias_rows,
    _build_alias_map,
    _build_canonical_aliases,
    _apply_alias_file_to_dataframe,
    _apply_alias_map_to_dataframe,
    _canonicalize_template_items,
)
from .survey_technical import (
    _inject_missing_token,
    _apply_technical_overrides,
)
from . import survey_lsa_metadata as _survey_lsa_metadata
from . import survey_preview as _survey_preview
from . import survey_row_processing as _survey_row_processing
from . import survey_template_loading as _survey_template_loading
from . import survey_global_templates as _survey_global_templates
from . import survey_template_assignment as _survey_template_assignment
from .survey_lsa_metadata import (
    _infer_lsa_language_and_tech,
    infer_lsa_metadata,
)

# Compatibility re-exports for external imports that still reference helpers
# from this module during the incremental decomposition phase.
_COMPAT_SURVEY_HELPER_EXPORTS = (
    _RUN_SUFFIX_PATTERNS,
    LIMESURVEY_SYSTEM_COLUMNS,
    _LS_TIMING_PATTERN,
    _is_limesurvey_system_column,
    _extract_limesurvey_columns,
    _parse_run_from_column,
    _group_columns_by_run,
    _NON_ITEM_TOPLEVEL_KEYS,
    _STYLING_KEYS,
    _extract_template_structure,
    _compare_template_structures,
    _build_bids_survey_filename,
    _determine_task_runs,
    _load_participants_mapping,
    _get_mapped_columns,
    _load_participants_template,
    _is_participant_template,
    _normalize_participant_template_dict,
    _participants_json_from_template,
    _LANGUAGE_KEY_RE,
    _normalize_language,
    _default_language_from_template,
    _is_language_dict,
    _pick_language_value,
    _localize_survey_template,
    _read_alias_rows,
    _build_alias_map,
    _build_canonical_aliases,
    _apply_alias_file_to_dataframe,
    _apply_alias_map_to_dataframe,
    _canonicalize_template_items,
    _inject_missing_token,
    _apply_technical_overrides,
    _infer_lsa_language_and_tech,
    infer_lsa_metadata,
)


def _load_global_library_path() -> Path | None:
    """Find the global library path from config."""
    return _survey_global_templates._load_global_library_path()


def _load_global_templates() -> dict[str, dict]:
    """Load all templates from the global library."""
    return _survey_global_templates._load_global_templates()


def _load_global_participants_template() -> dict | None:
    """Load the global participants.json template."""
    return _survey_global_templates._load_global_participants_template()


def _compare_participants_templates(
    project_template: dict | None,
    global_template: dict | None,
) -> tuple[bool, set[str], set[str], list[str]]:
    """Compare project participants template against global template."""
    return _survey_global_templates._compare_participants_templates(
        project_template=project_template,
        global_template=global_template,
    )


def _find_matching_global_template(
    project_template: dict,
    global_templates: dict[str, dict],
) -> tuple[str | None, bool, set[str], set[str]]:
    """Find if a project template matches any global template."""
    return _survey_global_templates._find_matching_global_template(
        project_template=project_template,
        global_templates=global_templates,
    )


_MISSING_TOKEN = "n/a"
# LimeSurvey answer code max length (used for reverse lookup)
_LS_ANSWER_CODE_MAX_LENGTH = 5


def _sanitize_answer_code_for_ls(code: str) -> str:
    """Apply LimeSurvey answer code sanitization (for reverse lookup).

    This mirrors the logic in limesurvey_exporter._sanitize_answer_code()
    to allow matching truncated codes back to original level keys.

    LimeSurvey truncates answer codes to 5 chars using: first 3 + last 2 chars
    after removing non-alphanumeric characters.
    """
    # Handle n/a specially
    if code.lower() in ("n/a", "na"):
        return "na"

    # Remove non-alphanumeric characters
    sanitized = re.sub(r"[^a-zA-Z0-9]", "", code)

    if len(sanitized) <= _LS_ANSWER_CODE_MAX_LENGTH:
        return sanitized.lower()

    # For long codes: first 3 chars + last 2 chars
    prefix_len = _LS_ANSWER_CODE_MAX_LENGTH - 2  # 3
    suffix_len = 2
    abbreviated = sanitized[:prefix_len] + sanitized[-suffix_len:]
    return abbreviated.lower()


def _find_matching_level_key(value: str, levels: dict) -> str | None:
    """Try to find the original level key for a potentially sanitized value.

    Handles:
    - Direct matches (case-insensitive)
    - LimeSurvey truncated codes (e.g., 'cohng' -> 'cohabiting')
    - Common missing value formats (e.g., 'na' -> 'n/a')

    Returns:
        Original level key if found, None otherwise
    """
    v_lower = value.lower().strip()

    # Direct match (case-insensitive)
    for key in levels:
        if key.lower() == v_lower:
            return key

    # Handle common missing value variations
    if v_lower == "na":
        if "n/a" in levels:
            return "n/a"
        if "N/A" in levels:
            return "N/A"

    # Try reverse LimeSurvey sanitization lookup
    # For each level key, compute what LimeSurvey would truncate it to
    # and see if it matches the input value
    for key in levels:
        sanitized = _sanitize_answer_code_for_ls(key)
        if sanitized == v_lower:
            return key

    return None


def _safe_eval_formula(formula: str) -> float | None:
    """Safely evaluate a simple arithmetic formula (e.g., BMI calculation).

    Only allows: numbers, basic arithmetic (+, -, *, /), round(), parentheses.
    Returns None if evaluation fails or formula is unsafe.

    Examples:
        'round(56 / ((145 / 100) * (145 / 100)), 1)' -> 26.6
        '123 + 456' -> 579
    """
    import ast
    import operator

    if not isinstance(formula, str):
        return None

    formula = formula.strip()
    if not formula:
        return None

    # Quick check: must contain at least one digit and an operator
    if not any(c.isdigit() for c in formula):
        return None
    if not any(c in formula for c in "+-*/()"):
        return None

    # Whitelist of safe operations
    safe_operators = {
        ast.Add: operator.add,
        ast.Sub: operator.sub,
        ast.Mult: operator.mul,
        ast.Div: operator.truediv,
        ast.USub: operator.neg,
        ast.UAdd: operator.pos,
    }

    def _eval_node(node):
        if isinstance(node, ast.Constant):
            if isinstance(node.value, (int, float)):
                return node.value
            raise ValueError("Non-numeric constant")
        elif isinstance(node, ast.Num):  # Python 3.7 compatibility
            return node.n
        elif isinstance(node, ast.BinOp):
            if type(node.op) not in safe_operators:
                raise ValueError(f"Unsafe operator: {type(node.op)}")
            left = _eval_node(node.left)
            right = _eval_node(node.right)
            return safe_operators[type(node.op)](left, right)
        elif isinstance(node, ast.UnaryOp):
            if type(node.op) not in safe_operators:
                raise ValueError(f"Unsafe unary operator: {type(node.op)}")
            operand = _eval_node(node.operand)
            return safe_operators[type(node.op)](operand)
        elif isinstance(node, ast.Call):
            # Only allow round() function
            if isinstance(node.func, ast.Name) and node.func.id == "round":
                args = [_eval_node(arg) for arg in node.args]
                return round(*args)
            raise ValueError("Unsafe function call")
        elif isinstance(node, ast.Expression):
            return _eval_node(node.body)
        else:
            raise ValueError(f"Unsafe node type: {type(node)}")

    try:
        tree = ast.parse(formula, mode="eval")
        result = _eval_node(tree)
        if isinstance(result, (int, float)) and not (result != result):  # not NaN
            return result
        return None
    except Exception:
        return None


def _auto_correct_participant_value(value, col_name: str, template: dict | None) -> str:
    """Auto-correct a participant data value based on template Levels.

    Handles:
    - LimeSurvey truncated codes -> original level keys
    - 'na' -> 'n/a' for missing values
    - Formula strings -> evaluated numeric values

    Returns the corrected value, or original if no correction needed/possible.
    """
    if template is None:
        return value

    # Get column schema from template
    col_schema = template.get(col_name)
    if not isinstance(col_schema, dict):
        return value

    v_str = str(value).strip() if value is not None else ""

    # Skip empty/missing values
    if not v_str or v_str.lower() in ("", "nan", "none"):
        return _MISSING_TOKEN

    # Check for Levels - try to find matching key
    levels = col_schema.get("Levels")
    if isinstance(levels, dict) and levels:
        # Direct match
        if v_str in levels:
            return v_str

        # Try reverse lookup
        matched_key = _find_matching_level_key(v_str, levels)
        if matched_key is not None:
            return matched_key

    # Check for numeric DataType - try to evaluate formulas
    data_type = col_schema.get("DataType", "").lower()
    if data_type in ("number", "integer", "float"):
        # If it's already a valid number, return as-is
        try:
            float(v_str)
            return v_str
        except (ValueError, TypeError):
            pass

        # Try to evaluate as formula
        result = _safe_eval_formula(v_str)
        if result is not None:
            if data_type == "integer":
                return str(int(round(result)))
            else:
                # Round to reasonable precision
                return str(round(result, 2))

    return value


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
    detected_sessions: list[str] = field(default_factory=list)  # Sessions found in file
    missing_cells_by_subject: dict[str, int] = field(default_factory=dict)
    missing_value_token: str = _MISSING_TOKEN
    conversion_warnings: list[str] = field(default_factory=list)
    task_runs: dict[str, int | None] = field(
        default_factory=dict
    )  # task -> max run number (None if single occurrence)
    # Enhanced dry-run information
    dry_run_preview: dict | None = None  # Detailed preview of what will be created
    template_matches: dict | None = (
        None  # Structural match results per group (LSA only)
    )
    tool_columns: list[str] = field(default_factory=list)  # LimeSurvey system columns


class ParticipantsConverter:
    """Participant-focused conversion helpers.

    This class centralizes participant template loading/comparison and
    participants.tsv writing so participant-level concerns stay separate from
    response-level conversion logic.
    """

    def load_template(self, library_dir: str | Path) -> dict | None:
        return _load_participants_template(Path(library_dir))

    def load_global_template(self) -> dict | None:
        return _load_global_participants_template()

    def compare_with_global(
        self,
        project_template: dict | None,
    ) -> tuple[bool, set[str], set[str], list[str]]:
        return _compare_participants_templates(
            project_template=project_template,
            global_template=self.load_global_template(),
        )

    def normalize_template(self, template: dict | None) -> dict | None:
        return _normalize_participant_template_dict(template)

    def write_participants(
        self,
        *,
        df,
        output_root: Path,
        id_col: str,
        ses_col: str | None,
        participant_template: dict | None,
        normalize_sub_fn,
        is_missing_fn,
        lsa_col_renames: dict[str, str] | None = None,
    ) -> None:
        _write_survey_participants(
            df=df,
            output_root=output_root,
            id_col=id_col,
            ses_col=ses_col,
            participant_template=participant_template,
            normalize_sub_fn=normalize_sub_fn,
            is_missing_fn=is_missing_fn,
            lsa_col_renames=lsa_col_renames,
        )


class SurveyResponsesConverter:
    """Response-focused survey conversion facade.

    This class owns conversion of survey response tables/archives and delegates
    participant-specific operations to ``ParticipantsConverter``.

    This is the preferred integration API for new callers.
    """

    def __init__(self, participants: ParticipantsConverter | None = None) -> None:
        self.participants = participants or ParticipantsConverter()

    def convert_xlsx(
        self,
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
        skip_participants: bool = True,
    ) -> SurveyConvertResult:
        return _convert_survey_xlsx_to_prism_dataset_impl(
            input_path=input_path,
            library_dir=library_dir,
            output_root=output_root,
            survey=survey,
            id_column=id_column,
            session_column=session_column,
            session=session,
            sheet=sheet,
            unknown=unknown,
            dry_run=dry_run,
            force=force,
            name=name,
            authors=authors,
            language=language,
            alias_file=alias_file,
            id_map_file=id_map_file,
            duplicate_handling=duplicate_handling,
            skip_participants=skip_participants,
        )

    def convert_lsa(
        self,
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
        skip_participants: bool = True,
        project_path: str | Path | None = None,
    ) -> SurveyConvertResult:
        return _convert_survey_lsa_to_prism_dataset_impl(
            input_path=input_path,
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
            strict_levels=strict_levels,
            duplicate_handling=duplicate_handling,
            skip_participants=skip_participants,
            project_path=project_path,
        )


def _copy_templates_to_project(
    *,
    templates: dict,
    tasks_with_data: set[str],
    dataset_root: Path,
    language: str | None,
    technical_overrides: dict | None,
) -> None:
    """Copy used templates to project's code/library/survey/ for reproducibility."""
    return _survey_template_assignment._copy_templates_to_project(
        templates=templates,
        tasks_with_data=tasks_with_data,
        dataset_root=dataset_root,
        language=language,
        technical_overrides=technical_overrides,
        missing_token=_MISSING_TOKEN,
        localize_survey_template_fn=_localize_survey_template,
        inject_missing_token_fn=_inject_missing_token,
        apply_technical_overrides_fn=_apply_technical_overrides,
        write_json_fn=_write_json,
    )


def _convert_survey_xlsx_to_prism_dataset_impl(
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
    skip_participants: bool = True,
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
        skip_participants=skip_participants,
        source_format=kind,
    )


def _analyze_lsa_structure(
    input_path: Path,
    project_path: str | Path | None = None,
) -> dict | None:
    """Parse .lss structure from .lsa and match groups against template library.

    Extracts the .lss XML embedded in a LimeSurvey .lsa archive, parses it
    into per-group PRISM templates, and matches each group against both
    global and project template libraries.

    Args:
        input_path: Path to the .lsa archive file.
        project_path: Optional project root to also check project templates.

    Returns:
        Dict with:
          - groups: dict[group_name -> {prism_json, match, item_codes}]
          - column_to_group: dict[column_name -> group_name]
        Or None if .lss extraction or parsing fails.
    """
    from .limesurvey import parse_lss_xml_by_groups
    from .template_matcher import match_groups_against_library

    # Extract .lss XML from the .lsa archive
    try:
        with zipfile.ZipFile(str(input_path), "r") as z:
            lss_names = [n for n in z.namelist() if n.endswith(".lss")]
            if not lss_names:
                return None
            xml_lss = z.read(lss_names[0])
    except Exception:
        return None

    # Parse .lss into per-group PRISM templates
    parsed_groups = parse_lss_xml_by_groups(xml_lss, use_standard_format=True)
    if not parsed_groups:
        return None

    # Match each group against global + project libraries
    matches = match_groups_against_library(parsed_groups, project_path=project_path)

    # Build structured result
    groups: dict[str, dict] = {}
    column_to_group: dict[str, str] = {}

    for group_name, prism_json in parsed_groups.items():
        # Collect item codes (keys that are not metadata sections)
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

        # Map each item code to the group it belongs to
        for code in item_codes:
            column_to_group[code] = group_name

    return {
        "groups": groups,
        "column_to_group": column_to_group,
    }


def _add_ls_code_aliases(sidecar: dict, imported_codes: list[str]) -> None:
    """Register LS-mangled item codes as aliases in a library template."""
    return _survey_template_assignment._add_ls_code_aliases(
        sidecar=sidecar,
        imported_codes=imported_codes,
        non_item_toplevel_keys=_NON_ITEM_TOPLEVEL_KEYS,
    )


def _add_matched_template(
    templates: dict[str, dict],
    item_to_task: dict[str, str],
    match,
    group_info: dict,
) -> None:
    """Add a library-matched template to the templates and item_to_task dicts."""
    return _survey_template_assignment._add_matched_template(
        templates=templates,
        item_to_task=item_to_task,
        match=match,
        group_info=group_info,
        add_ls_code_aliases_fn=_add_ls_code_aliases,
        load_global_templates_fn=_load_global_templates,
        read_json_fn=_read_json,
        non_item_toplevel_keys=_NON_ITEM_TOPLEVEL_KEYS,
    )


def _add_generated_template(
    templates: dict[str, dict],
    item_to_task: dict[str, str],
    group_name: str,
    group_info: dict,
) -> None:
    """Add a generated (unmatched) template from .lss parsing."""
    from ..utils.naming import sanitize_task_name

    return _survey_template_assignment._add_generated_template(
        templates=templates,
        item_to_task=item_to_task,
        group_name=group_name,
        group_info=group_info,
        sanitize_task_name_fn=sanitize_task_name,
    )


def _convert_survey_lsa_to_prism_dataset_impl(
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
    skip_participants: bool = True,
    project_path: str | Path | None = None,
) -> SurveyConvertResult:
    """Convert a LimeSurvey response archive (.lsa) into a PRISM dataset.

    The .lsa file is a zip archive. We extract the embedded *_responses.lsr XML and
    treat it as a wide table where each column is a survey item / variable.

    Args:
        project_path: Optional project root path. When provided, the .lss
            structure is analyzed and matched against global + project
            template libraries for automatic template recognition.
    """

    input_path = Path(input_path).resolve()
    if input_path.suffix.lower() not in {".lsa"}:
        raise ValueError("Currently only .lsa input is supported.")

    # Analyze .lss structure for template matching (before reading responses)
    lsa_analysis = _analyze_lsa_structure(input_path, project_path=project_path)

    result = _read_table_as_dataframe(input_path=input_path, kind="lsa")
    # LSA returns (df, questions_map); other formats return just df
    if isinstance(result, tuple):
        df, lsa_questions_map = result
    else:
        df = result
        lsa_questions_map = None

    # If language was not explicitly specified, try to infer it from the LSA.
    inferred_lang, inferred_tech = _infer_lsa_language_and_tech(
        input_path=input_path, df=df
    )
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
        skip_participants=skip_participants,
        lsa_analysis=lsa_analysis,
        source_format="lsa",
    )


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
    skip_participants: bool = True,
) -> SurveyConvertResult:
    """Backward-compatible wrapper around ``SurveyResponsesConverter``.

    New integrations should prefer ``SurveyResponsesConverter.convert_xlsx``.
    """
    return SurveyResponsesConverter().convert_xlsx(
        input_path=input_path,
        library_dir=library_dir,
        output_root=output_root,
        survey=survey,
        id_column=id_column,
        session_column=session_column,
        session=session,
        sheet=sheet,
        unknown=unknown,
        dry_run=dry_run,
        force=force,
        name=name,
        authors=authors,
        language=language,
        alias_file=alias_file,
        id_map_file=id_map_file,
        duplicate_handling=duplicate_handling,
        skip_participants=skip_participants,
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
    skip_participants: bool = True,
    project_path: str | Path | None = None,
) -> SurveyConvertResult:
    """Backward-compatible wrapper around ``SurveyResponsesConverter``.

    New integrations should prefer ``SurveyResponsesConverter.convert_lsa``.
    """
    return SurveyResponsesConverter().convert_lsa(
        input_path=input_path,
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
        strict_levels=strict_levels,
        duplicate_handling=duplicate_handling,
        skip_participants=skip_participants,
        project_path=project_path,
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
                print(f"L{i + 1}: {line.rstrip()}")
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
    except Exception:
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
                    raise ValueError(
                        f"ID map must have at least two columns, got {len(rows[0])}"
                    )
                print(f"[PRISM DEBUG] Manually parsed {len(rows)} rows")
                # Use first row as header, rest as data
                if len(rows) > 1:
                    df = pd.DataFrame(rows[1:], columns=rows[0])
                else:
                    raise ValueError("ID map file contains only a header row, no data")
        except Exception as inner:
            raise ValueError(
                f"Error loading ID map {p}: {inner}. Try saving as UTF-8 TSV with a tab delimiter or CSV with commas."
            ) from inner

    if df is None or df.empty:
        raise ValueError(f"ID map file is empty: {p}")

    if df.shape[1] < 2:
        raise ValueError(
            f"ID map file {p} must have at least two columns (source_id, participant_id)"
        )

    # Debug: Log current state
    print(f"[PRISM DEBUG] DataFrame shape before processing: {df.shape}")
    print(f"[PRISM DEBUG] DataFrame columns before processing: {list(df.columns)}")
    print(f"[PRISM DEBUG] First 3 rows:\n{df.head(3)}")

    try:
        df = df.iloc[:, :2].copy()
        df.columns = ["source_id", "participant_id"]
        print(f"[PRISM DEBUG] After column rename: {list(df.columns)}")

        df["source_id"] = df["source_id"].astype(str).str.strip()
        df["participant_id"] = df["participant_id"].astype(str).str.strip()
        print(f"[PRISM DEBUG] After string conversion - dtypes: {df.dtypes.to_dict()}")

        mapping = {
            str(row["source_id"]).strip(): str(row["participant_id"]).strip()
            for _, row in df.iterrows()
            if row["source_id"] and row["participant_id"]
        }
    except KeyError as ke:
        raise ValueError(
            f"Error accessing column in ID map file {p}: {ke}. "
            f"Available columns: {list(df.columns)}. "
            f"DataFrame shape: {df.shape}"
        ) from ke

    if not mapping:
        raise ValueError(f"ID map file {p} contains no valid mappings")

    print(f"[PRISM DEBUG] Loaded ID map with {len(mapping)} entries")
    return mapping


class MissingIdMappingError(ValueError):
    """Raised when IDs in data are missing from the mapping, with suggestions."""

    def __init__(
        self, missing_ids: list[str], suggestions: dict[str, list[dict]], message: str
    ):
        super().__init__(message)
        self.missing_ids = missing_ids
        self.suggestions = suggestions


class UnmatchedGroupsError(ValueError):
    """Raised when LSA groups have no matching library template."""

    def __init__(self, unmatched: list[dict], message: str):
        super().__init__(message)
        self.unmatched = unmatched
        # Each dict: {"group_name": str, "task_key": str, "item_codes": [...], "prism_json": {...}}


def _damerau_levenshtein(a: str, b: str, limit: int = 2) -> int | None:
    """Compute Damerau-Levenshtein distance with an optional early-exit limit."""

    a = a or ""
    b = b or ""
    if a == b:
        return 0
    if abs(len(a) - len(b)) > limit:
        return None

    len_a, len_b = len(a), len(b)
    max_dist = limit if limit is not None else max(len_a, len_b)

    # Use two-row DP with transposition check
    prev_row = list(range(len_b + 1))
    curr_row = [0] * (len_b + 1)
    last_row = [0] * (len_b + 1)

    for i in range(1, len_a + 1):
        curr_row[0] = i
        min_in_row = curr_row[0]
        for j in range(1, len_b + 1):
            cost = 0 if a[i - 1] == b[j - 1] else 1
            deletion = prev_row[j] + 1
            insertion = curr_row[j - 1] + 1
            substitution = prev_row[j - 1] + cost
            curr_row[j] = min(deletion, insertion, substitution)

            if i > 1 and j > 1 and a[i - 1] == b[j - 2] and a[i - 2] == b[j - 1]:
                curr_row[j] = min(curr_row[j], last_row[j - 2] + 1)

            if curr_row[j] < min_in_row:
                min_in_row = curr_row[j]

        if min_in_row > max_dist:
            return None
        last_row, prev_row, curr_row = prev_row, curr_row, [0] * (len_b + 1)

    return prev_row[-1]


def _suggest_id_matches(
    missing_ids: list[str], map_keys: list[str]
) -> dict[str, list[dict]]:
    """Return top candidate matches for each missing ID based on small edit distance."""

    suggestions: dict[str, list[dict]] = {}
    map_keys_lower = [(k, str(k).strip().lower()) for k in map_keys]

    for miss in missing_ids:
        miss_clean = str(miss).strip()
        miss_lower = miss_clean.lower()
        scored: list[tuple[int, str]] = []
        for orig, lower in map_keys_lower:
            dist = _damerau_levenshtein(miss_lower, lower, limit=2)
            if dist is None:
                continue
            scored.append((dist, orig))

        scored.sort(key=lambda x: (x[0], x[1]))
        top = [s for s in scored[:3]]
        suggestions[miss_clean] = [
            {"candidate": cand, "distance": dist} for dist, cand in top
        ]

    return suggestions


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
                    text = re.sub(r"<\?xml.*?\?>", "", text, 1)
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
                                "question": clean_question,
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
            # Parse tokenization errors to provide user-friendly messages
            error_msg = str(e)

            # Detect "Expected X fields in line Y, saw Z" errors
            token_match = re.search(
                r"Expected (\d+) fields in line (\d+), saw (\d+)", error_msg
            )
            if token_match:
                expected, line_num, got = token_match.groups()
                return_msg = (
                    f"CSV format error in row {line_num}: Expected {expected} columns but found {got}. "
                    f"This usually indicates:\n"
                    f"  • Extra commas or quotes within a cell\n"
                    f"  • Inconsistent number of columns across rows\n"
                    f"  • Unescaped quotes or embedded newlines in data\n"
                    f"Please check the file structure and ensure all rows have the same number of columns."
                )
                raise ValueError(return_msg) from e

            raise ValueError(f"Failed to read CSV: {error_msg}") from e

        if df is None or df.empty:
            raise ValueError("Input CSV is empty (no content in file).")

        return df.rename(columns={c: str(c).strip() for c in df.columns})

    if kind == "tsv":
        try:
            df = pd.read_csv(input_path, sep="\t")
        except EmptyDataError:
            raise ValueError("Input TSV is empty (no content in file).")
        except Exception as e:
            # Parse tokenization errors to provide user-friendly messages
            error_msg = str(e)

            # Detect "Expected X fields in line Y, saw Z" errors
            token_match = re.search(
                r"Expected (\d+) fields in line (\d+), saw (\d+)", error_msg
            )
            if token_match:
                expected, line_num, got = token_match.groups()
                return_msg = (
                    f"TSV format error in row {line_num}: Expected {expected} columns but found {got}. "
                    f"This usually indicates:\n"
                    f"  • Extra tabs or newlines within a cell\n"
                    f"  • Inconsistent number of columns across rows\n"
                    f"  • Trailing tabs at the end of a line\n"
                    f"Please check the file structure and ensure all rows have the same number of columns."
                )
                raise ValueError(return_msg) from e

            raise ValueError(f"Failed to read TSV: {error_msg}") from e

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

        def _normalize_lsa_columns(
            cols: list[str], questions_map: dict | None = None
        ) -> list[str]:
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
                qid_to_title = {
                    qid: info["title"] for qid, info in questions_map.items()
                }

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
            matches = [
                name for name in zf.namelist() if name.endswith("_responses.lsr")
            ]
            if not matches:
                # Some LSA exports use different naming or case
                matches = [
                    name for name in zf.namelist() if "_responses" in name.lower()
                ]
            if not matches:
                raise ValueError(
                    "No survey response file (e.g. *_responses.lsr) found inside the .lsa archive"
                )
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
                    text = re.sub(r"<\?xml.*?\?>", "", text, 1)
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
        df = df.dropna(axis=1, how="all")

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
    skip_participants: bool = True,
    lsa_analysis: dict | None = None,
    source_format: str = "xlsx",
) -> SurveyConvertResult:
    if unknown not in {"error", "warn", "ignore"}:
        raise ValueError("unknown must be one of: error, warn, ignore")
    if duplicate_handling not in {"error", "keep_first", "keep_last", "sessions"}:
        raise ValueError(
            "duplicate_handling must be one of: error, keep_first, keep_last, sessions"
        )

    library_dir = Path(library_dir).resolve()
    output_root = Path(output_root).resolve()

    if not library_dir.exists() or not library_dir.is_dir():
        raise ValueError(
            f"Library folder does not exist or is not a directory: {library_dir}"
        )

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
            return "ses-01"
        # Strip ses- prefix if present, then re-add with zero-padding
        num_part = s[4:] if s.startswith("ses-") else s
        try:
            n = int(num_part)
            return f"ses-{n:02d}"
        except ValueError:
            # Non-numeric labels (e.g., "baseline") pass through as-is
            return f"ses-{num_part}"

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

    # Participants converter: participant-template loading, normalization, and writing
    participants_converter = ParticipantsConverter()

    # Load participant template and compare with global
    raw_participant_template = participants_converter.load_template(library_dir)
    participant_template = participants_converter.normalize_template(
        raw_participant_template
    )
    participant_columns_lower: set[str] = set()
    if participant_template:
        participant_columns_lower = {
            str(k).strip().lower()
            for k in participant_template.keys()
            if isinstance(k, str)
        }

    # Compare participants.json with global
    if raw_participant_template:
        _, _, _, part_warnings = participants_converter.compare_with_global(
            raw_participant_template
        )
        conversion_warnings.extend(part_warnings)

    templates, item_to_task, duplicates, template_warnings_by_task = (
        _load_and_preprocess_templates(
            library_dir, canonical_aliases, compare_with_global=True
        )
    )
    if duplicates:
        msg_lines = [
            "Duplicate item IDs found across survey templates (ambiguous mapping):"
        ]
        for it_id, tsks in sorted(duplicates.items()):
            msg_lines.append(f"- {it_id}: {', '.join(sorted(tsks))}")
        raise ValueError("\n".join(msg_lines))

    # --- LSA Structural Matching ---
    # When converting .lsa files without an explicit survey= filter,
    # use the .lss structure analysis to auto-detect and register templates.
    unmatched_groups: list[dict] = []
    if lsa_analysis and not survey:
        for group_name, group_info in lsa_analysis["groups"].items():
            match = group_info.get("match")
            if match and match.is_participants:
                # Participant/sociodemographic data: register item codes
                # as participant columns so they get written to participants.tsv
                # instead of being treated as unmapped survey items.
                # Always register the actual LS-mangled item_codes (DataFrame
                # column names) so they are recognized during column mapping.
                # Also register PRISMMETA variable names as standard aliases.
                for code in group_info["item_codes"]:
                    if not code.upper().startswith("PRISMMETA"):
                        participant_columns_lower.add(code.lower())
                prismmeta = group_info["prism_json"].get("_prismmeta")
                if prismmeta and prismmeta.get("variables"):
                    for var_code in prismmeta["variables"]:
                        if not var_code.upper().startswith("PRISMMETA"):
                            participant_columns_lower.add(var_code.lower())
            elif match and match.confidence in ("exact", "high"):
                # Use the matched library template
                _add_matched_template(templates, item_to_task, match, group_info)
            elif match and match.confidence == "medium":
                # Medium confidence — still use it, but warn
                _add_matched_template(templates, item_to_task, match, group_info)
                conversion_warnings.append(
                    f"Group '{group_name}' matched template '{match.template_key}' "
                    f"with medium confidence ({match.overlap_count}/{match.template_items} items). "
                    f"Review the match to ensure correctness."
                )
            else:
                # No match or low confidence — collect as unmatched.
                # Deduplicate run groups: if "resiliencebrsrun1" and
                # "resiliencebrsrun2" both fail, collapse them into a
                # single "resiliencebrs" entry so the user saves ONE
                # base template that matches all runs.
                from ..utils.naming import sanitize_task_name
                from .template_matcher import (
                    _strip_run_from_group_name,
                    _normalize_item_codes,
                )

                task_key = sanitize_task_name(group_name).lower()
                if not task_key:
                    task_key = group_name.lower().replace(" ", "")

                # Strip run suffix from task_key to get the base name
                base_key = _strip_run_from_group_name(task_key)
                if not base_key:
                    base_key = task_key

                # Strip run suffixes from item codes in prism_json so
                # the saved template uses base codes (BRS01 not BRS01run02)
                raw_codes = group_info["item_codes"]
                base_codes, _ = _normalize_item_codes(
                    raw_codes if isinstance(raw_codes, set) else set(raw_codes)
                )
                base_prism = {}
                for k, v in group_info["prism_json"].items():
                    if k in _NON_ITEM_TOPLEVEL_KEYS or not isinstance(v, dict):
                        base_prism[k] = v
                    else:
                        from .template_matcher import _strip_run_suffix

                        stripped, _ = _strip_run_suffix(k)
                        if stripped not in base_prism:
                            base_prism[stripped] = v

                # Check if we already collected a group with this base key
                existing = next(
                    (g for g in unmatched_groups if g["task_key"] == base_key),
                    None,
                )
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
                    # Merge: add any new base codes from this run group
                    existing["item_codes"] = existing["item_codes"] | base_codes

                if match:
                    conversion_warnings.append(
                        f"Group '{group_name}' had low-confidence match to "
                        f"'{match.template_key}'. No suitable template found."
                    )

    if unmatched_groups:
        names = [g["group_name"] for g in unmatched_groups]
        raise UnmatchedGroupsError(
            unmatched=unmatched_groups,
            message=(
                f"No library template found for {len(unmatched_groups)} group(s): "
                f"{', '.join(names)}. Save templates to project library first, "
                f"then re-run conversion."
            ),
        )

    # --- LSA Participant Column Renames ---
    # When converting .lsa files, LimeSurvey mangles question codes (strips
    # underscores, truncates long names with MD5 hash suffix). Build a reverse
    # mapping so _write_survey_participants() can match mangled DF columns
    # back to standard PRISM participant field names.
    lsa_participant_renames: dict[str, str] = {}
    if lsa_analysis and not survey:
        for group_name, group_info in lsa_analysis["groups"].items():
            match = group_info.get("match")
            if match and match.is_participants:
                lsa_participant_renames = _build_participant_col_renames(
                    item_codes=group_info["item_codes"],
                    participant_template=participant_template,
                )
                if lsa_participant_renames:
                    print(
                        f"[INFO] LSA participant column renames: "
                        f"{len(lsa_participant_renames)} fields will be remapped"
                    )
                break

    # --- Survey Filtering ---
    selected_tasks: set[str] | None = None
    if survey:
        parts = [p.strip() for p in str(survey).replace(";", ",").split(",")]
        parts = [p for p in parts if p]
        selected = {p.lower().replace("survey-", "") for p in parts}
        unknown_surveys = sorted([t for t in selected if t not in templates])
        if unknown_surveys:
            raise ValueError(
                "Unknown surveys: "
                + ", ".join(unknown_surveys)
                + ". Available: "
                + ", ".join(sorted(templates.keys()))
            )
        selected_tasks = selected

    # --- Determine Columns ---
    from .id_detection import has_prismmeta_columns as _has_pm

    _prismmeta = _has_pm(list(df.columns))
    res_id_col, res_ses_col = _resolve_id_and_session_cols(
        df,
        id_column,
        session_column,
        participants_template=participant_template,
        source_format=source_format,
        has_prismmeta=_prismmeta,
    )

    # --- Apply subject ID mapping if provided ---
    id_map: dict[str, str] | None = _load_id_mapping(id_map_file)
    if id_map:
        df = df.copy()

        # Heuristic: pick the column whose values best match the ID map keys.
        # Order candidates with likely user-provided codes before tokens.
        all_cols_lower = {str(c).strip().lower(): str(c) for c in df.columns}
        preferred_order = [
            res_id_col,
            "participant_id",
            "code",
            "token",
            "id",
            "subject",
            "sub_id",
            "participant",
        ]
        candidate_cols: list[str] = []
        seen = set()
        for name in preferred_order:
            if not name:
                continue
            # exact first
            if name in df.columns and name not in seen:
                candidate_cols.append(name)
                seen.add(name)
                continue
            # case-insensitive
            lower = str(name).strip().lower()
            if lower in all_cols_lower:
                actual = all_cols_lower[lower]
                if actual not in seen:
                    candidate_cols.append(actual)
                    seen.add(actual)

        # Normalize id_map keys to lowercase for case-insensitive matching
        id_map_lower = {str(k).strip().lower(): v for k, v in id_map.items()}

        def _score_column(col: str) -> tuple[int, float]:
            col_values = df[col].astype(str).str.strip()
            unique_vals = set(col_values.unique())
            matches = len(
                [v for v in unique_vals if str(v).strip().lower() in id_map_lower]
            )
            total = len(unique_vals) if unique_vals else 1
            ratio = matches / total if total else 0.0
            return matches, ratio

        print(f"[PRISM DEBUG] ID map keys sample: {list(id_map_lower.keys())[:5]} ...")
        print(f"[PRISM DEBUG] Dataframe columns: {list(df.columns)}")
        print(f"[PRISM DEBUG] Candidate ID columns: {candidate_cols}")

        best_col = res_id_col
        best_matches, best_ratio = _score_column(res_id_col)
        print(
            f"[PRISM DEBUG] Score {res_id_col}: matches={best_matches}, ratio={best_ratio:.3f}"
        )
        for c in candidate_cols:
            matches, ratio = _score_column(c)
            print(f"[PRISM DEBUG] Score {c}: matches={matches}, ratio={ratio:.3f}")
            if (matches > best_matches) or (
                matches == best_matches and ratio > best_ratio
            ):
                best_col = c
                best_matches, best_ratio = matches, ratio

        # If no matches at all, prefer 'code' if available
        if best_matches == 0 and "code" in candidate_cols:
            best_col = "code"
            print("[PRISM DEBUG] No matches; falling back to 'code' column")

        if best_col != res_id_col:
            conversion_warnings.append(
                f"Selected id_column '{best_col}' based on ID map overlap ({best_matches} matches)."
            )
            res_id_col = best_col

        print(
            f"[PRISM DEBUG] Selected ID column: {res_id_col}; unique sample: {df[res_id_col].astype(str).unique()[:10]}"
        )

        df[res_id_col] = df[res_id_col].astype(str).str.strip()
        ids_in_data = set(df[res_id_col].unique())
        missing = sorted(
            [i for i in ids_in_data if str(i).strip().lower() not in id_map_lower]
        )
        if missing:
            sample = ", ".join(missing[:20])
            more = "" if len(missing) <= 20 else f" (+{len(missing) - 20} more)"
            map_keys = list(id_map.keys())
            suggestions = _suggest_id_matches(missing, map_keys)
            raise MissingIdMappingError(
                missing,
                suggestions,
                f"ID mapping incomplete: {len(missing)} IDs from data are missing in the mapping: {sample}{more}.",
            )

        df[res_id_col] = df[res_id_col].map(
            lambda x: id_map_lower.get(
                str(x).strip().lower(), id_map.get(str(x).strip(), x)
            )
        )
        conversion_warnings.append(
            f"Applied subject ID mapping from {Path(id_map_file).name} ({len(id_map)} entries)."
        )

    if alias_map:
        df = _apply_alias_map_to_dataframe(df=df, alias_map=alias_map)

    # --- Detect Available Sessions ---
    detected_sessions: list[str] = []
    if res_ses_col:
        # Get unique session values from the file
        detected_sessions = sorted(
            [
                str(v).strip()
                for v in df[res_ses_col].dropna().unique()
                if str(v).strip()
            ]
        )
        print(f"[PRISM INFO] Sessions detected in {res_ses_col}: {detected_sessions}")
    else:
        print(
            f"[PRISM DEBUG] No session column detected (res_ses_col is None). Available columns: {list(df.columns)[:20]}"
        )

    # --- Filter Rows by Selected Session ---
    # If both session column exists and a specific session is selected,
    # filter to only rows matching that session.
    # This MUST happen before duplicate checking so that legitimate duplicates
    # (same subject in different sessions) can be filtered to a single session.
    rows_before_filter = len(df)
    if res_ses_col and session and session != "all":
        # Normalize the session value for comparison
        session_normalized = str(session).strip()
        df_filtered = df[df[res_ses_col].astype(str).str.strip() == session_normalized]
        if len(df_filtered) == 0:
            raise ValueError(
                f"No rows found with session '{session}' in column '{res_ses_col}'. "
                f"Available values: {', '.join(detected_sessions if detected_sessions else ['none'])}"
            )
        df = df_filtered
        print(
            f"[PRISM INFO] Filtered {rows_before_filter} rows → {len(df)} rows for session '{session}'"
        )
    elif (
        res_ses_col
        and not session
        and detected_sessions
        and duplicate_handling == "error"
    ):
        # PREVIEW MODE: If session column exists but user hasn't selected a session,
        # and no custom duplicate handling, auto-select first session for preview
        # to avoid blocking on duplicate IDs (which are legitimate across sessions)
        first_session = detected_sessions[0]
        df_filtered = df[df[res_ses_col].astype(str).str.strip() == first_session]
        if len(df_filtered) > 0:
            df = df_filtered
            print(
                f"[PRISM INFO] Auto-filtering to first session '{first_session}' for preview ({rows_before_filter} rows → {len(df)} rows)"
            )
    elif session == "all" and res_ses_col:
        print(f"[PRISM INFO] Processing all sessions from '{res_ses_col}'")

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
            raise ValueError(
                f"Duplicate participant_id values after normalization: {', '.join(dup_ids[:5])}"
            )
        elif duplicate_handling == "keep_first":
            # Keep first occurrence, drop subsequent duplicates
            df = df[~normalized_ids.duplicated(keep="first")].copy()
            normalized_ids = df[res_id_col].astype(str).map(_normalize_sub_id)
            conversion_warnings.append(
                f"Duplicate IDs found ({dup_count} duplicates). Kept first occurrence for: {', '.join(dup_ids[:5])}"
            )
        elif duplicate_handling == "keep_last":
            # Keep last occurrence, drop earlier duplicates
            df = df[~normalized_ids.duplicated(keep="last")].copy()
            normalized_ids = df[res_id_col].astype(str).map(_normalize_sub_id)
            conversion_warnings.append(
                f"Duplicate IDs found ({dup_count} duplicates). Kept last occurrence for: {', '.join(dup_ids[:5])}"
            )
        elif duplicate_handling == "sessions":
            # Create multiple sessions for duplicates (ses-1, ses-2, etc.)
            # Add a session counter column based on occurrence order
            df = df.copy()
            df["_dup_session_num"] = df.groupby(normalized_ids.values).cumcount() + 1
            # Override session column with the computed session numbers
            res_ses_col = "_dup_session_num"
            conversion_warnings.append(
                f"Duplicate IDs found ({dup_count} duplicates). Created multiple sessions for: {', '.join(dup_ids[:5])}"
            )

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

    # Add template warnings only for templates that are used in this conversion
    for task_name in sorted(tasks_with_data):
        conversion_warnings.extend(template_warnings_by_task.get(task_name, []))

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
    missing_items_by_task = _compute_missing_items_report(
        tasks_with_data, templates, col_to_task
    )

    # Build template_matches from lsa_analysis for API responses
    _template_matches: dict | None = None
    if lsa_analysis:
        _template_matches = {}
        for group_name, group_info in lsa_analysis["groups"].items():
            match = group_info.get("match")
            _template_matches[group_name] = match.to_dict() if match else None

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
            skip_participants=skip_participants,
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
            detected_sessions=detected_sessions,
            conversion_warnings=conversion_warnings,
            task_runs=task_runs,
            dry_run_preview=dry_run_preview,
            template_matches=_template_matches,
            tool_columns=ls_system_cols or [],
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
            ls_version=(
                technical_overrides.get("SoftwareVersion")
                if technical_overrides
                else None
            ),
            force=force,
        )

    if not skip_participants:
        participants_converter.write_participants(
            df=df,
            output_root=dataset_root,
            id_col=res_id_col,
            ses_col=res_ses_col,
            participant_template=participant_template,
            normalize_sub_fn=_normalize_sub_id,
            is_missing_fn=_is_missing_value,
            lsa_col_renames=lsa_participant_renames,
        )

    # Write task sidecars
    for task in sorted(tasks_with_data):
        sidecar_path = dataset_root / f"task-{task}_survey.json"
        if not sidecar_path.exists() or force:
            localized = _localize_survey_template(
                templates[task]["json"], language=language
            )
            localized = _inject_missing_token(localized, token=_MISSING_TOKEN)
            if technical_overrides:
                localized = _apply_technical_overrides(localized, technical_overrides)
            # Ensure Metadata section exists (required by PRISM schema)
            if "Metadata" not in localized:
                from datetime import datetime

                localized["Metadata"] = {
                    "SchemaVersion": "1.1.1",
                    "CreationDate": datetime.utcnow().strftime("%Y-%m-%d"),
                    "Creator": "prism-studio",
                }
            # Ensure required Technical fields exist (required by PRISM schema)
            if "Technical" not in localized or not isinstance(
                localized.get("Technical"), dict
            ):
                localized["Technical"] = {}
            tech = localized["Technical"]
            if "StimulusType" not in tech:
                tech["StimulusType"] = "Questionnaire"
            if "FileFormat" not in tech:
                tech["FileFormat"] = "tsv"
            if "Language" not in tech:
                tech["Language"] = language or ""
            if "Respondent" not in tech:
                tech["Respondent"] = "self"
            # Ensure required Study fields exist (required by PRISM schema)
            if "Study" not in localized or not isinstance(localized.get("Study"), dict):
                localized["Study"] = {}
            study = localized["Study"]
            if "TaskName" not in study:
                study["TaskName"] = task
            if "OriginalName" not in study:
                study["OriginalName"] = study.get("TaskName", task)
            if "LicenseID" not in study:
                study["LicenseID"] = "Other"
            if "License" not in study:
                study["License"] = ""
            # Remove internal keys before writing to avoid schema validation errors
            cleaned = _strip_internal_keys(localized)
            _write_json(sidecar_path, cleaned)

    # --- Process and Write Responses ---
    missing_cells_by_subject: dict[str, int] = {}
    items_using_tolerance: dict[str, set[str]] = {}

    for _, row in df.iterrows():
        sub_id = _normalize_sub_id(row[res_id_col])
        # Determine session: if session="all", treat as if no override (use file values)
        ses_id = (
            _normalize_ses_id(session)
            if session and session != "all"
            else (_normalize_ses_id(row[res_ses_col]) if res_ses_col else "ses-1")
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
        for (task, run), columns in sorted(
            task_run_columns.items(), key=lambda x: (x[0][0], x[0][1] or 0)
        ):
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
            missing_cells_by_subject[sub_id] = (
                missing_cells_by_subject.get(sub_id, 0) + missing_count
            )

            # Write TSV with run number if needed
            expected_cols = [
                k
                for k in schema.keys()
                if k not in _NON_ITEM_TOPLEVEL_KEYS
                and k not in schema.get("_aliases", {})
            ]

            # Determine if run number should be in filename
            # Only include run if this task has multiple runs detected
            include_run = task_runs.get(task) is not None
            effective_run = run if include_run else None

            filename = _build_bids_survey_filename(
                sub_id, ses_id, task, effective_run, "tsv"
            )
            res_file = modality_dir / filename

            with open(res_file, "w", encoding="utf-8", newline="") as f:
                writer = csv.DictWriter(
                    f, fieldnames=expected_cols, delimiter="\t", lineterminator="\n"
                )
                writer.writeheader()
                writer.writerow(out_row)

    # Add summary for items using numeric range tolerance
    if items_using_tolerance:
        for task, item_ids in sorted(items_using_tolerance.items()):
            sorted_items = sorted(list(item_ids))
            shown = ", ".join(sorted_items[:10])
            more = (
                "" if len(sorted_items) <= 10 else f" (+{len(sorted_items) - 10} more)"
            )
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
        detected_sessions=detected_sessions,
        missing_cells_by_subject=missing_cells_by_subject,
        missing_value_token=_MISSING_TOKEN,
        conversion_warnings=conversion_warnings,
        task_runs=task_runs,
        template_matches=_template_matches,
        tool_columns=ls_system_cols or [],
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
    df,
    id_column: str | None,
    session_column: str | None,
    participants_template: dict | None = None,
    source_format: str = "xlsx",
    has_prismmeta: bool = False,
) -> tuple[str, str | None]:
    """Helper to determine participant ID and session columns from dataframe.

    Delegates ID detection to the central id_detection module.

    Auto-detect priority:
    1. Explicit id_column parameter
    2. participant_id / participantid (PRISM primary, handles LS code mangling)
    3. prism_participant_id / prismparticipantid (PRISM alternative)
    4. token / id (LSA + PRISMMETA only)
    5. None found → IdColumnNotDetectedError (manual selection required)
    """
    from .id_detection import detect_id_column, IdColumnNotDetectedError

    resolved_id = detect_id_column(
        df_columns=list(df.columns),
        source_format=source_format,
        explicit_id_column=id_column,
        has_prismmeta=has_prismmeta,
    )
    if not resolved_id:
        raise IdColumnNotDetectedError(list(df.columns), source_format)

    def _find_col(candidates: set[str]) -> str | None:
        lower_map = {str(c).strip().lower(): str(c).strip() for c in df.columns}
        for c in candidates:
            if c in lower_map:
                return lower_map[c]
        return None

    resolved_ses: str | None
    if session_column:
        if session_column not in df.columns:
            raise ValueError(
                f"session_column '{session_column}' not found in input columns"
            )
        resolved_ses = session_column
    else:
        resolved_ses = _find_col({"session", "ses", "visit", "timepoint"})

    return str(resolved_id), resolved_ses


@dataclass
class ColumnMapping:
    """Mapping information for a single column."""

    task: str
    run: int | None  # None if single occurrence, 1/2/3... if multiple runs
    base_item: str  # Item name without run suffix (for template lookup)


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
                task=matched_task, run=run_num, base_item=matched_base
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
        "id",
        "submitdate",
        "lastpage",
        "startlanguage",
        "seed",
        "startdate",
        "datestamp",
        "token",
        "refurl",
        "ipaddr",
        "googleid",
        "session_id",
        "participant_id",
        "attribute_1",
        "attribute_2",
        "attribute_3",
    }
    # Also filter out LimeSurvey "Other" text columns (other, other_1, other_2, ...),
    # PRISM metadata questions, and menstrual cycle columns with LS-mangled names
    _other_pattern = re.compile(r"^other(_\d+)?$", re.IGNORECASE)
    _prismmeta_pattern = re.compile(r"^prismmeta", re.IGNORECASE)
    filtered_unknown = [
        c
        for c in unknown_cols
        if str(c).lower() not in bookkeeping
        and not _other_pattern.match(str(c).strip())
        and not _prismmeta_pattern.match(str(c).strip())
    ]

    if filtered_unknown:
        if unknown_mode == "error":
            raise ValueError("Unmapped columns: " + ", ".join(filtered_unknown))
        if unknown_mode == "warn":
            shown = ", ".join(filtered_unknown[:10])
            more = (
                ""
                if len(filtered_unknown) <= 10
                else f" (+{len(filtered_unknown) - 10} more)"
            )
            warnings.append(
                f"Unmapped columns (not in any survey template): {shown}{more}"
            )

    return col_to_mapping, filtered_unknown, warnings, task_runs


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
            "SchemaVersion": "1.1.1",
            "CreationDate": today,
            "Tool": "LimeSurvey",
        },
        "Technical": {
            "StimulusType": "Questionnaire",
            "FileFormat": "tsv",
            "Language": "",
            "Respondent": "self",
            "SoftwarePlatform": "LimeSurvey",
        },
        "Study": {
            "TaskName": "limesurvey",
            "OriginalName": "LimeSurvey System Data",
            "LicenseID": "Other",
            "License": "System metadata generated by LimeSurvey",
        },
    }

    if ls_version:
        sidecar["Metadata"]["ToolVersion"] = ls_version
        sidecar["Technical"]["SoftwareVersion"] = ls_version

    # Field descriptions for common LimeSurvey system columns.
    # Each column is a top-level item with Description (conforms to PRISM schema).
    field_descriptions = {
        "id": {"Description": "LimeSurvey response ID"},
        "submitdate": {"Description": "Survey completion timestamp"},
        "startdate": {"Description": "Survey start timestamp"},
        "datestamp": {"Description": "Date stamp of response"},
        "lastpage": {"Description": "Last page number viewed by participant"},
        "startlanguage": {"Description": "Language code at survey start"},
        "seed": {"Description": "Randomization seed for question/answer order"},
        "token": {"Description": "Participant access token"},
        "ipaddr": {"Description": "IP address of respondent"},
        "refurl": {"Description": "Referrer URL"},
        "interviewtime": {"Description": "Total time spent on survey (seconds)"},
        "optout": {"Description": "Opt-out status"},
        "emailstatus": {"Description": "Email delivery status"},
    }

    # Add each system column as a top-level item
    for col in ls_columns:
        col_lower = col.lower()
        if col_lower in field_descriptions:
            sidecar[col] = field_descriptions[col_lower]
        elif col_lower.startswith("grouptime"):
            sidecar[col] = {"Description": "Time spent on question group (seconds)"}
        elif col_lower.startswith("duration_"):
            group_name = col[9:]  # Remove "Duration_" prefix
            sidecar[col] = {
                "Description": f"Time spent on group: {group_name} (seconds)"
            }
        elif col_lower.startswith("attribute_"):
            sidecar[col] = {"Description": "Custom participant attribute"}
        else:
            sidecar[col] = {"Description": f"LimeSurvey system field: {col}"}

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
        writer = csv.DictWriter(
            f, fieldnames=present_cols, delimiter="\t", lineterminator="\n"
        )
        writer.writeheader()
        writer.writerow(out_row)

    return res_file


def _write_survey_description(
    output_root: Path, name: str | None, authors: list[str] | None
):
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
                "Description": "Manual survey template mapping and TSV conversion.",
            }
        ],
        "HEDVersion": "8.2.0",
    }
    _write_json(ds_desc, dataset_description)


def _build_participant_col_renames(
    item_codes: set[str],
    participant_template: dict | None,
) -> dict[str, str]:
    """Build a rename map from LS-mangled column names to standard PRISM participant field names.

    When LimeSurvey exports data, question codes are sanitized:
    - Underscores/hyphens stripped: native_language -> nativelanguage
    - Long codes truncated to 13 chars + 2-char MD5 hash: country_of_residence -> countryofresi54

    This function reverses that process by:
    1. Taking each standard field name from the participant template
    2. Applying the same sanitization logic used by _sanitize_question_code()
    3. Checking if the sanitized name exists in the actual DataFrame columns (item_codes)
    4. Building a mangled_name -> standard_name mapping

    Returns:
        dict mapping LS column names (lowercased) to standard PRISM field names
    """
    import re
    import hashlib

    if not participant_template:
        return {}

    LS_MAX = 15
    non_column_keys = {
        "@context",
        "Technical",
        "I18n",
        "Study",
        "Metadata",
        "_aliases",
        "_reverse_aliases",
        "participant_id",
    }

    # Build a lowercase lookup of actual item codes
    codes_lower = {c.lower() for c in item_codes}

    renames: dict[str, str] = {}
    for field_name in participant_template:
        if field_name in non_column_keys:
            continue

        # Apply the same sanitization as _sanitize_question_code()
        sanitized = re.sub(r"[^a-zA-Z0-9]", "", field_name)
        if sanitized and not sanitized[0].isalpha():
            sanitized = "Q" + sanitized
        if not sanitized:
            continue
        if len(sanitized) > LS_MAX:
            # Hash used for generating short suffixes, not for security
            hash_suffix = hashlib.md5(
                field_name.encode(), usedforsecurity=False
            ).hexdigest()[:2]
            sanitized = sanitized[: LS_MAX - 2] + hash_suffix

        sanitized_lower = sanitized.lower()

        # Only map if the sanitized name differs from the original
        if sanitized_lower != field_name.lower() and sanitized_lower in codes_lower:
            renames[sanitized_lower] = field_name

    return renames


def _write_survey_participants(
    *,
    df,
    output_root: Path,
    id_col: str,
    ses_col: str | None,
    participant_template: dict | None,
    normalize_sub_fn,
    is_missing_fn,
    lsa_col_renames: dict[str, str] | None = None,
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
    participants_mapping = _load_participants_mapping(output_root)
    mapped_cols, col_renames, value_mappings = _get_mapped_columns(participants_mapping)

    # Log what was found
    if participants_mapping:
        print(
            f"[INFO] Using participants_mapping.json from project ({len(mapped_cols)} mapped columns)"
        )
        if col_renames:
            print(f"[INFO]   Column renames: {col_renames}")
        if value_mappings:
            print(f"[INFO]   Value transformations for: {list(value_mappings.keys())}")
    else:
        print("[INFO] No participants_mapping.json found (using template columns only)")

    # Start with participant_id column
    df_part = pd.DataFrame(
        {"participant_id": df[id_col].astype(str).map(normalize_sub_fn)}
    )

    # Normalize template to get column definitions
    template_norm = _normalize_participant_template_dict(participant_template)
    template_cols = set(template_norm.keys()) if template_norm else set()
    # Remove non-column keys from template
    non_column_keys = {
        "@context",
        "Technical",
        "I18n",
        "Study",
        "Metadata",
        "_aliases",
        "_reverse_aliases",
    }
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
                # Direct match: template field name found as-is in DataFrame
                actual_col = lower_to_col[col]
                if actual_col not in {id_col, ses_col}:
                    extra_cols.append(actual_col)
                    col_output_names[actual_col] = col
            elif lsa_col_renames:
                # Fallback: look up the LS-mangled column name for this field
                mangled = None
                for mangled_name, standard_name in lsa_col_renames.items():
                    if standard_name == col:
                        mangled = mangled_name
                        break
                if mangled and mangled in lower_to_col:
                    actual_col = lower_to_col[mangled]
                    if actual_col not in {id_col, ses_col}:
                        extra_cols.append(actual_col)
                        col_output_names[actual_col] = col  # Output uses standard name

    if extra_cols:
        extra_cols = list(dict.fromkeys(extra_cols))
        df_extra = df[[id_col] + extra_cols].copy()

        # Apply value mappings and missing value handling
        for c in extra_cols:
            output_name = col_output_names.get(c, c)

            # Apply value mapping if specified
            if output_name in value_mappings:
                val_map = value_mappings[output_name]
                df_extra[c] = (
                    df_extra[c]
                    .astype(str)
                    .map(
                        lambda v, vm=val_map: (
                            vm.get(v, v)
                            if v not in ("nan", "None", "")
                            else _MISSING_TOKEN
                        )
                    )
                )
            else:
                df_extra[c] = df_extra[c].apply(
                    lambda v: _MISSING_TOKEN if is_missing_fn(v) else v
                )

        # Normalize ID column and rename to participant_id
        df_extra[id_col] = df_extra[id_col].astype(str).map(normalize_sub_fn)
        df_extra = df_extra.rename(columns={id_col: "participant_id"})
        df_extra = (
            df_extra.groupby("participant_id", dropna=False)[extra_cols]
            .first()
            .reset_index()
        )

        # Rename columns to standard variable names
        rename_map = {c: col_output_names.get(c, c) for c in extra_cols}
        df_extra = df_extra.rename(columns=rename_map)

        # Auto-correct values: truncated LS codes -> original level keys, formulas -> numbers
        if template_norm:
            for col in df_extra.columns:
                if col == "participant_id":
                    continue
                df_extra[col] = df_extra[col].apply(
                    lambda v, c=col, t=template_norm: _auto_correct_participant_value(
                        v, c, t
                    )
                )

        df_part = df_part.merge(df_extra, on="participant_id", how="left")

    df_part = df_part.drop_duplicates(subset=["participant_id"]).reset_index(drop=True)

    # Merge with existing participants.tsv if it exists
    participants_tsv_path = output_root / "participants.tsv"
    if participants_tsv_path.exists():
        try:
            existing_df = pd.read_csv(participants_tsv_path, sep="\t", dtype=str)
            if "participant_id" in existing_df.columns:
                # Merge new data with existing, preferring new values for overlapping participants
                # but keeping all existing participants and columns
                df_part = pd.merge(
                    existing_df,
                    df_part,
                    on="participant_id",
                    how="outer",
                    suffixes=("_old", "_new"),
                )

                # For each column that exists in both, prefer new value if not n/a
                for col in df_part.columns:
                    if col.endswith("_new"):
                        base_col = col[:-4]  # Remove "_new"
                        old_col = base_col + "_old"
                        if old_col in df_part.columns:
                            # Prefer new value, fall back to old if new is n/a
                            df_part[base_col] = df_part.apply(
                                lambda row: (
                                    row[col]
                                    if pd.notna(row[col])
                                    and str(row[col]) not in ("n/a", "nan", "")
                                    else (
                                        row[old_col]
                                        if pd.notna(row[old_col])
                                        else "n/a"
                                    )
                                ),
                                axis=1,
                            )
                            # Drop the _old and _new columns
                            df_part = df_part.drop(columns=[old_col, col])
                        else:
                            # No old column, just rename new column
                            df_part = df_part.rename(columns={col: base_col})

                # Sort by participant_id
                df_part = df_part.sort_values("participant_id").reset_index(drop=True)
                print(
                    f"[INFO] Merged with existing participants.tsv ({len(existing_df)} existing → {len(df_part)} total)"
                )
        except Exception as e:
            print(f"[WARNING] Could not merge with existing participants.tsv: {e}")

    df_part.to_csv(participants_tsv_path, sep="\t", index=False)

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
) -> tuple[
    dict[str, dict],
    dict[str, str],
    dict[str, set[str]],
    dict[str, list[str]],
]:
    """Load and prepare survey templates from library."""
    return _survey_template_loading._load_and_preprocess_templates(
        library_dir=library_dir,
        canonical_aliases=canonical_aliases,
        compare_with_global=compare_with_global,
        load_global_library_path_fn=_load_global_library_path,
        load_global_templates_fn=_load_global_templates,
        is_participant_template_fn=_is_participant_template,
        read_json_fn=_read_json,
        canonicalize_template_items_fn=_canonicalize_template_items,
        non_item_toplevel_keys=_NON_ITEM_TOPLEVEL_KEYS,
        find_matching_global_template_fn=_find_matching_global_template,
    )


def _compute_missing_items_report(
    tasks: set[str], templates: dict, col_to_task: dict
) -> dict[str, int]:
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
    """Generate a preview of what will be written to participants.tsv."""
    return _survey_preview._generate_participants_preview(
        df=df,
        res_id_col=res_id_col,
        res_ses_col=res_ses_col,
        session=session,
        normalize_sub_fn=normalize_sub_fn,
        normalize_ses_fn=normalize_ses_fn,
        is_missing_fn=is_missing_fn,
        participant_template=participant_template,
        output_root=output_root,
        survey_columns=survey_columns,
        ls_system_columns=ls_system_columns,
        lsa_questions_map=lsa_questions_map,
        missing_token=_MISSING_TOKEN,
    )


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
    skip_participants: bool = True,
    output_root: Path,
    dataset_root: Path,
    lsa_questions_map: dict | None = None,
) -> dict:
    """Generate a detailed preview of what will be created during conversion."""
    return _survey_preview._generate_dry_run_preview(
        df=df,
        tasks_with_data=tasks_with_data,
        task_run_columns=task_run_columns,
        col_to_mapping=col_to_mapping,
        templates=templates,
        res_id_col=res_id_col,
        res_ses_col=res_ses_col,
        session=session,
        selected_tasks=selected_tasks,
        normalize_sub_fn=normalize_sub_fn,
        normalize_ses_fn=normalize_ses_fn,
        is_missing_fn=is_missing_fn,
        ls_system_cols=ls_system_cols,
        participant_template=participant_template,
        skip_participants=skip_participants,
        output_root=output_root,
        dataset_root=dataset_root,
        lsa_questions_map=lsa_questions_map,
        missing_token=_MISSING_TOKEN,
    )


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
    return _survey_row_processing._process_survey_row(
        row=row,
        df_cols=df_cols,
        task=task,
        schema=schema,
        sub_id=sub_id,
        strict_levels=strict_levels,
        items_using_tolerance=items_using_tolerance,
        is_missing_fn=is_missing_fn,
        normalize_val_fn=normalize_val_fn,
        non_item_toplevel_keys=_NON_ITEM_TOPLEVEL_KEYS,
        missing_token=_MISSING_TOKEN,
        validate_item_fn=_validate_survey_item_value,
    )


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
    """Process a single task/run's data for one subject/session."""
    return _survey_row_processing._process_survey_row_with_run(
        row=row,
        df_cols=df_cols,
        task=task,
        run=run,
        schema=schema,
        run_col_mapping=run_col_mapping,
        sub_id=sub_id,
        strict_levels=strict_levels,
        items_using_tolerance=items_using_tolerance,
        is_missing_fn=is_missing_fn,
        normalize_val_fn=normalize_val_fn,
        non_item_toplevel_keys=_NON_ITEM_TOPLEVEL_KEYS,
        missing_token=_MISSING_TOKEN,
        validate_item_fn=_validate_survey_item_value,
    )


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
    return _survey_row_processing._validate_survey_item_value(
        item_id=item_id,
        val=val,
        item_schema=item_schema,
        sub_id=sub_id,
        task=task,
        strict_levels=strict_levels,
        items_using_tolerance=items_using_tolerance,
        normalize_fn=normalize_fn,
        is_missing_fn=is_missing_fn,
        find_matching_level_key_fn=_find_matching_level_key,
        missing_token=_MISSING_TOKEN,
    )


def _infer_lsa_language_and_tech(*, input_path: Path, df) -> tuple[str | None, dict]:
    """Compatibility wrapper delegating to extracted LSA metadata module."""
    return _survey_lsa_metadata._infer_lsa_language_and_tech(input_path=input_path, df=df)


def infer_lsa_metadata(input_path: str | Path) -> dict:
    """Compatibility wrapper delegating to extracted LSA metadata module."""
    return _survey_lsa_metadata.infer_lsa_metadata(input_path)
