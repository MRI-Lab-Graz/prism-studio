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
from . import survey_lsa_analysis as _survey_lsa_analysis
from . import survey_lsa_unmatched as _survey_lsa_unmatched
from . import survey_lsa_participants as _survey_lsa_participants
from . import survey_selection as _survey_selection
from . import survey_session_handling as _survey_session_handling
from . import survey_mapping_results as _survey_mapping_results
from . import survey_sidecars as _survey_sidecars
from . import survey_response_writing as _survey_response_writing
from . import survey_id_mapping as _survey_id_mapping
from . import survey_lsa_preprocess as _survey_lsa_preprocess
from . import survey_value_normalization as _survey_value_normalization
from . import survey_id_resolution as _survey_id_resolution
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
    """Parse .lss structure from .lsa and match groups against template library."""
    return _survey_lsa_analysis._analyze_lsa_structure(
        input_path=input_path,
        project_path=project_path,
    )


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
    df, lsa_questions_map = _survey_lsa_preprocess._unpack_lsa_read_result(result)

    effective_language, inferred_tech, effective_strict_levels = (
        _survey_lsa_preprocess._resolve_lsa_language_and_strict(
            input_path=input_path,
            df=df,
            language=language,
            strict_levels=strict_levels,
            infer_lsa_language_and_tech_fn=_infer_lsa_language_and_tech,
        )
    )

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
                _survey_lsa_participants._register_participant_columns_from_lsa_group(
                    group_info=group_info,
                    participant_columns_lower=participant_columns_lower,
                )
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
                _survey_lsa_unmatched._collect_unmatched_lsa_group(
                    group_name=group_name,
                    group_info=group_info,
                    unmatched_groups=unmatched_groups,
                    non_item_toplevel_keys=_NON_ITEM_TOPLEVEL_KEYS,
                    sanitize_task_name_fn=sanitize_task_name,
                )

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
    lsa_participant_renames = _survey_lsa_participants._derive_lsa_participant_renames(
        lsa_analysis=lsa_analysis,
        survey_filter=survey,
        participant_template=participant_template,
        build_participant_col_renames_fn=_build_participant_col_renames,
    )
    if lsa_participant_renames:
        print(
            f"[INFO] LSA participant column renames: "
            f"{len(lsa_participant_renames)} fields will be remapped"
        )

    # --- Survey Filtering ---
    selected_tasks = _survey_selection._resolve_selected_tasks(
        survey_filter=survey,
        templates=templates,
    )

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
    df, res_id_col, id_map_warnings = _survey_id_mapping._apply_subject_id_mapping(
        df=df,
        res_id_col=res_id_col,
        id_map=id_map,
        id_map_file=id_map_file,
        suggest_id_matches_fn=_suggest_id_matches,
        missing_id_mapping_error_cls=MissingIdMappingError,
    )
    conversion_warnings.extend(id_map_warnings)

    if alias_map:
        df = _apply_alias_map_to_dataframe(df=df, alias_map=alias_map)

    # --- Detect Available Sessions ---
    detected_sessions = _survey_session_handling._detect_sessions(
        df=df,
        res_ses_col=res_ses_col,
    )

    # --- Filter Rows by Selected Session ---
    # If both session column exists and a specific session is selected,
    # filter to only rows matching that session.
    # This MUST happen before duplicate checking so that legitimate duplicates
    # (same subject in different sessions) can be filtered to a single session.
    df = _survey_session_handling._filter_rows_by_selected_session(
        df=df,
        res_ses_col=res_ses_col,
        session=session,
        duplicate_handling=duplicate_handling,
        detected_sessions=detected_sessions,
    )

    # --- Extract LimeSurvey System Columns ---
    # These are platform metadata (timestamps, tokens, timings) that should be
    # written to a separate tool-limesurvey file, not mixed with questionnaire data
    ls_system_cols, _ = _extract_limesurvey_columns(list(df.columns))

    # Handle duplicate IDs based on duplicate_handling parameter
    df, _res_ses_override, duplicate_warnings = _survey_session_handling._handle_duplicate_ids(
        df=df,
        res_id_col=res_id_col,
        duplicate_handling=duplicate_handling,
        normalize_sub_fn=_normalize_sub_id,
    )
    if _res_ses_override:
        res_ses_col = _res_ses_override
    conversion_warnings.extend(duplicate_warnings)

    col_to_mapping, unknown_cols, map_warnings, task_runs = _map_survey_columns(
        df=df,
        item_to_task=item_to_task,
        participant_columns_lower=participant_columns_lower,
        id_col=res_id_col,
        ses_col=res_ses_col,
        unknown_mode=unknown,
    )
    conversion_warnings.extend(map_warnings)

    tasks_with_data, task_template_warnings = (
        _survey_mapping_results._resolve_tasks_with_warnings(
            col_to_mapping=col_to_mapping,
            selected_tasks=selected_tasks,
            template_warnings_by_task=template_warnings_by_task,
        )
    )
    conversion_warnings.extend(task_template_warnings)

    col_to_task, task_run_columns = (
        _survey_mapping_results._build_col_to_task_and_task_runs(
            col_to_mapping=col_to_mapping,
        )
    )

    # --- Results Preparation ---
    missing_items_by_task = _compute_missing_items_report(
        tasks_with_data, templates, col_to_task
    )

    # Build template_matches from lsa_analysis for API responses
    _template_matches = _survey_mapping_results._build_template_matches_payload(
        lsa_analysis=lsa_analysis,
    )

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

    _survey_sidecars._write_task_sidecars(
        tasks_with_data=tasks_with_data,
        dataset_root=dataset_root,
        templates=templates,
        language=language,
        force=force,
        technical_overrides=technical_overrides,
        missing_token=_MISSING_TOKEN,
        localize_survey_template_fn=_localize_survey_template,
        inject_missing_token_fn=_inject_missing_token,
        apply_technical_overrides_fn=_apply_technical_overrides,
        strip_internal_keys_fn=_strip_internal_keys,
        write_json_fn=_write_json,
    )

    # --- Process and Write Responses ---
    missing_cells_by_subject, items_using_tolerance = (
        _survey_response_writing._process_and_write_responses(
            df=df,
            res_id_col=res_id_col,
            res_ses_col=res_ses_col,
            session=session,
            output_root=output_root,
            task_run_columns=task_run_columns,
            selected_tasks=selected_tasks,
            templates=templates,
            col_to_mapping=col_to_mapping,
            strict_levels=strict_levels,
            task_runs=task_runs,
            ls_system_cols=ls_system_cols,
            non_item_toplevel_keys=_NON_ITEM_TOPLEVEL_KEYS,
            normalize_sub_fn=_normalize_sub_id,
            normalize_ses_fn=_normalize_ses_id,
            normalize_item_fn=_normalize_item_value,
            is_missing_fn=_is_missing_value,
            ensure_dir_fn=_ensure_dir,
            write_limesurvey_data_fn=_write_limesurvey_data,
            process_survey_row_with_run_fn=_process_survey_row_with_run,
            build_bids_survey_filename_fn=_build_bids_survey_filename,
        )
    )

    # Add summary for items using numeric range tolerance
    conversion_warnings.extend(
        _survey_response_writing._build_tolerance_warnings(
            items_using_tolerance=items_using_tolerance,
        )
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
    return _survey_value_normalization._normalize_item_value(
        val,
        missing_token=_MISSING_TOKEN,
    )


def _resolve_id_and_session_cols(
    df,
    id_column: str | None,
    session_column: str | None,
    participants_template: dict | None = None,
    source_format: str = "xlsx",
    has_prismmeta: bool = False,
) -> tuple[str, str | None]:
    return _survey_id_resolution._resolve_id_and_session_cols(
        df=df,
        id_column=id_column,
        session_column=session_column,
        participants_template=participants_template,
        source_format=source_format,
        has_prismmeta=has_prismmeta,
    )


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
