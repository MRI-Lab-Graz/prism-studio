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
from datetime import datetime, timezone
from pathlib import Path
import csv
import zipfile
import defusedxml.ElementTree as ET
import re
from typing import cast

try:
    import pandas as pd
except ImportError:
    pd = None

from ..cross_platform import describe_case_insensitive_id_collisions
from ..utils.io import (
    ensure_dir as _ensure_dir,
    read_json as _read_json,
    write_json as _write_json,
)
from ..utils.naming import sanitize_id
from ..bids_integration import check_and_update_bidsignore
from ..constants import DEFAULT_BIDS_VERSION
from .survey_processing import (
    _RUN_SUFFIX_PATTERNS,
    LIMESURVEY_SYSTEM_COLUMNS,
    _LS_TIMING_PATTERN,
    _is_limesurvey_system_column,
    _extract_limesurvey_columns,
    _parse_run_from_column,
    _group_columns_by_run,
)
from .survey_core import (
    _NON_ITEM_TOPLEVEL_KEYS,
    _STYLING_KEYS,
    _extract_template_structure,
    _compare_template_structures,
    _build_bids_survey_filename,
    _determine_task_runs,
    _resolve_existing_project_root,
    _read_alias_rows,
    _build_alias_map,
    _build_canonical_aliases,
    _apply_alias_file_to_dataframe,
    _apply_alias_map_to_dataframe,
    _canonicalize_template_items,
    _inject_missing_token,
    _apply_technical_overrides,
)
from .survey_participants_logic import (
    _load_participants_mapping,
    _get_mapped_columns,
    _load_participants_template,
    _is_participant_template,
    _normalize_participant_template_dict,
    _participants_json_from_template,
)
from .survey_templates import (
    _LANGUAGE_KEY_RE,
    _apply_template_version_selection,
    _normalize_language,
    _default_language_from_template,
    _is_language_dict,
    _pick_language_value,
    _localize_survey_template,
)
from .wide_to_long import detect_wide_session_prefixes

from .file_reader import read_tabular_file as _read_tabular_file  # type: ignore[attr-defined]
from . import survey_lsa as _survey_lsa  # type: ignore[attr-defined]
from . import survey_io as _survey_io  # type: ignore[attr-defined]
from . import survey_templates as _survey_templates
from . import survey_processing as _survey_processing
from . import survey_core as _survey_core
from . import survey_participants_logic as _survey_participants_logic
from . import survey_column_mapping as _survey_column_mapping

SurveyValueOutOfBoundsError = _survey_processing.SurveyValueOutOfBoundsError

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
    _survey_lsa._infer_lsa_language_and_tech,
    _survey_lsa.infer_lsa_metadata,
)


def _load_global_library_path() -> Path | None:
    """Find the global library path from config."""
    return _survey_templates._load_global_library_path()


def _load_global_templates() -> dict[str, dict]:
    """Load all templates from the global library."""
    return _survey_templates._load_global_templates()


def _load_global_participants_template() -> dict | None:
    """Load the global participants.json template."""
    return _survey_templates._load_global_participants_template()


def _compare_participants_templates(
    project_template: dict | None,
    global_template: dict | None,
) -> tuple[bool, set[str], set[str], list[str]]:
    """Compare project participants template against global template."""
    return _survey_templates._compare_participants_templates(
        project_template=project_template,
        global_template=global_template,
    )


def _find_matching_global_template(
    project_template: dict,
    global_templates: dict[str, dict],
) -> tuple[str | None, bool, set[str], set[str]]:
    """Find if a project template matches any global template."""
    return _survey_templates._find_matching_global_template(
        project_template=project_template,
        global_templates=global_templates,
    )


_MISSING_TOKEN = "n/a"  # noqa: S105 - placeholder value for missing survey answers, not a credential


def _normalize_run_id(value: object) -> str | None:
    text = sanitize_id(str(value).strip())
    if not text or text.lower() == "nan":
        return None
    label = text[4:] if text[:4].lower() == "run-" else text
    label = re.sub(r"[^A-Za-z0-9]+", "", label)
    if not label:
        return None
    return f"run-{label}"


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


def _summarize_labels(values: list[str], limit: int = 10) -> str:
    if len(values) <= limit:
        return ", ".join(values)
    remaining = len(values) - limit
    return f"{', '.join(values[:limit])}, +{remaining} more"


def _format_participant_registry_warning_message(warning: dict[str, object]) -> str:
    parts = [
        str(warning.get("message") or "").strip(),
        str(warning.get("details") or "").strip(),
        str(warning.get("next_step") or "").strip(),
    ]
    return " ".join(part for part in parts if part)


def _build_participant_registry_warning(
    *,
    df,
    res_id_col: str,
    normalize_sub_fn,
    project_path: str | Path | None,
) -> dict[str, object] | None:
    project_root = _resolve_existing_project_root(project_path)
    if project_root is None:
        return None

    participants_tsv = project_root / "participants.tsv"
    if not participants_tsv.exists() or not participants_tsv.is_file():
        return None

    imported_ids = sorted(
        {
            normalized
            for raw_value in df[res_id_col].tolist()
            if (normalized := normalize_sub_fn(raw_value))
        }
    )
    if not imported_ids:
        return None

    try:
        from ..participants_converter import (
            ParticipantsConverter as DatasetParticipantsConverter,
        )
    except Exception:
        return None

    existing_ids: set[str] = set()
    try:
        with participants_tsv.open("r", encoding="utf-8", newline="") as handle:
            reader = csv.DictReader(handle, delimiter="\t")
            headers = [str(field) for field in (reader.fieldnames or []) if field]
            if not headers:
                return None

            id_column = (
                "participant_id"
                if "participant_id" in headers
                else DatasetParticipantsConverter._find_participant_id_source_column(
                    headers
                )
            )
            if not id_column:
                return None

            for row in reader:
                normalized = DatasetParticipantsConverter._normalize_participant_id(
                    (row or {}).get(id_column)
                )
                if normalized:
                    existing_ids.add(normalized)
    except Exception:
        return None

    missing_ids = sorted(
        participant_id
        for participant_id in imported_ids
        if participant_id not in existing_ids
    )
    if not missing_ids:
        return None

    participant_label = "participant" if len(missing_ids) == 1 else "participants"
    verb = "is" if len(missing_ids) == 1 else "are"
    return {
        "type": "missing_from_participants_tsv",
        "severity": "warning",
        "message": (
            f"{len(missing_ids)} imported {participant_label} {verb} missing from participants.tsv."
        ),
        "details": f"Missing IDs: {_summarize_labels(missing_ids)}",
        "next_step": "Open Sociodemographics to import or add the missing participants.",
        "missing_count": len(missing_ids),
        "missing_participants": missing_ids,
        "participants_tsv": str(participants_tsv),
        "action": {
            "type": "open_converter_tab",
            "target": "participants",
            "label": "Open Sociodemographics",
        },
    }


@dataclass(frozen=True)
class SurveyConvertResult:
    tasks_included: list[str]
    unknown_columns: list[str]
    missing_items_by_task: dict[str, int]
    id_column: str
    session_column: str | None
    run_column: str | None = None
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
    participant_registry_warning: dict | None = None
    near_match_candidates: list[dict[str, object]] = field(default_factory=list)
    near_match_applied: bool = False
    applied_value_offsets: dict[str, float] = field(default_factory=dict)
    value_offset_application_counts: dict[str, int] = field(default_factory=dict)


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
        missing_token: str,
        lsa_col_renames: dict[str, str] | None = None,
    ) -> None:
        _survey_participants_logic._write_survey_participants(
            df=df,
            output_root=output_root,
            id_col=id_col,
            ses_col=ses_col,
            participant_template=participant_template,
            normalize_sub_fn=normalize_sub_fn,
            is_missing_fn=is_missing_fn,
            missing_token=missing_token,
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
        run_column: str | None = None,
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
        separator: str | None = None,
        duplicate_handling: str = "error",
        skip_participants: bool = True,
        project_path: str | Path | None = None,
        template_version_overrides: dict[str, str] | None = None,
        task_value_offsets: dict[str, float] | None = None,
        allow_near_item_match: bool = False,
        near_match_tasks: set[str] | None = None,
    ) -> SurveyConvertResult:
        return _convert_survey_xlsx_to_prism_dataset_impl(
            input_path=input_path,
            library_dir=library_dir,
            output_root=output_root,
            survey=survey,
            id_column=id_column,
            session_column=session_column,
            run_column=run_column,
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
            separator=separator,
            duplicate_handling=duplicate_handling,
            skip_participants=skip_participants,
            project_path=project_path,
            template_version_overrides=template_version_overrides,
            task_value_offsets=task_value_offsets,
            allow_near_item_match=allow_near_item_match,
            near_match_tasks=near_match_tasks,
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
        run_column: str | None = None,
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
        template_version_overrides: dict[str, str] | None = None,
        task_value_offsets: dict[str, float] | None = None,
        allow_near_item_match: bool = False,
        near_match_tasks: set[str] | None = None,
    ) -> SurveyConvertResult:
        return _convert_survey_lsa_to_prism_dataset_impl(
            input_path=input_path,
            library_dir=library_dir,
            output_root=output_root,
            survey=survey,
            id_column=id_column,
            session_column=session_column,
            run_column=run_column,
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
            template_version_overrides=template_version_overrides,
            task_value_offsets=task_value_offsets,
            allow_near_item_match=allow_near_item_match,
            near_match_tasks=near_match_tasks,
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
    return _survey_templates._copy_templates_to_project(
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
    run_column: str | None = None,
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
    separator: str | None = None,
    duplicate_handling: str = "error",
    skip_participants: bool = True,
    project_path: str | Path | None = None,
    template_version_overrides: dict[str, str] | None = None,
    task_value_offsets: dict[str, float] | None = None,
    allow_near_item_match: bool = False,
    near_match_tasks: set[str] | None = None,
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
    df = _read_table_as_dataframe(
        input_path=input_path,
        kind=kind,
        sheet=sheet_arg,
        separator=separator,
    )

    return _convert_survey_dataframe_to_prism_dataset(
        df=df,
        library_dir=library_dir,
        output_root=output_root,
        survey=survey,
        id_column=id_column,
        session_column=session_column,
        run_column=run_column,
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
        project_path=project_path,
        template_version_overrides=template_version_overrides,
        task_value_offsets=task_value_offsets,
        allow_near_item_match=allow_near_item_match,
        near_match_tasks=near_match_tasks,
    )


def _analyze_lsa_structure(
    input_path: Path,
    project_path: str | Path | None = None,
) -> dict | None:
    """Parse .lss structure from .lsa and match groups against template library."""
    return _survey_lsa._analyze_lsa_structure(
        input_path=input_path,
        project_path=project_path,
    )


def _add_ls_code_aliases(sidecar: dict, imported_codes: list[str]) -> None:
    """Register LS-mangled item codes as aliases in a library template."""
    return _survey_templates._add_ls_code_aliases(
        sidecar=sidecar,
        imported_codes=imported_codes,
        non_item_keys=_NON_ITEM_TOPLEVEL_KEYS,
    )


def _add_matched_template(
    templates: dict[str, dict],
    item_to_task: dict[str, str],
    match,
    group_info: dict,
) -> None:
    """Add a library-matched template to the templates and item_to_task dicts."""
    return _survey_templates._add_matched_template(
        templates=templates,
        item_to_task=item_to_task,
        match=match,
        group_info=group_info,
        read_json_fn=_read_json,
        non_item_keys=_NON_ITEM_TOPLEVEL_KEYS,
    )


def _add_generated_template(
    templates: dict[str, dict],
    item_to_task: dict[str, str],
    group_name: str,
    group_info: dict,
) -> None:
    """Add a generated (unmatched) template from .lss parsing."""
    from ..utils.naming import sanitize_task_name

    return _survey_templates._add_generated_template(
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
    run_column: str | None = None,
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
    template_version_overrides: dict[str, str] | None = None,
    task_value_offsets: dict[str, float] | None = None,
    allow_near_item_match: bool = False,
    near_match_tasks: set[str] | None = None,
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
    df, lsa_questions_map = _survey_lsa._unpack_lsa_read_result(result)

    effective_language, inferred_tech, effective_strict_levels = (
        _survey_lsa._resolve_lsa_language_and_strict(
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
        run_column=run_column,
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
        project_path=project_path,
        template_version_overrides=template_version_overrides,
        task_value_offsets=task_value_offsets,
        allow_near_item_match=allow_near_item_match,
        near_match_tasks=near_match_tasks,
    )


def convert_survey_xlsx_to_prism_dataset(
    *,
    input_path: str | Path,
    library_dir: str | Path,
    output_root: str | Path,
    survey: str | None = None,
    id_column: str | None = None,
    session_column: str | None = None,
    run_column: str | None = None,
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
    separator: str | None = None,
    duplicate_handling: str = "error",
    skip_participants: bool = True,
    project_path: str | Path | None = None,
    template_version_overrides: dict[str, str] | None = None,
    task_value_offsets: dict[str, float] | None = None,
    allow_near_item_match: bool = False,
    near_match_tasks: set[str] | None = None,
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
        run_column=run_column,
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
        separator=separator,
        duplicate_handling=duplicate_handling,
        skip_participants=skip_participants,
        project_path=project_path,
        template_version_overrides=template_version_overrides,
        task_value_offsets=task_value_offsets,
        allow_near_item_match=allow_near_item_match,
        near_match_tasks=near_match_tasks,
    )


def convert_survey_lsa_to_prism_dataset(
    *,
    input_path: str | Path,
    library_dir: str | Path,
    output_root: str | Path,
    survey: str | None = None,
    id_column: str | None = None,
    session_column: str | None = None,
    run_column: str | None = None,
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
    template_version_overrides: dict[str, str] | None = None,
    task_value_offsets: dict[str, float] | None = None,
    allow_near_item_match: bool = False,
    near_match_tasks: set[str] | None = None,
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
        run_column=run_column,
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
        template_version_overrides=template_version_overrides,
        task_value_offsets=task_value_offsets,
        allow_near_item_match=allow_near_item_match,
        near_match_tasks=near_match_tasks,
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
        df = pd.read_csv(p, sep=sep, engine="python", encoding="utf-8-sig", dtype=str)
    except Exception:
        # Last attempt: sniff delimiter, then manual parse to avoid pandas edge cases on small files
        try:
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


def _read_table_as_dataframe(
    *, input_path: Path, kind: str, sheet: str | int = 0, separator: str | None = None
):
    # Print head for visibility in terminal
    _debug_print_file_head(input_path)

    if kind in ("xlsx", "csv", "tsv"):
        result = _read_tabular_file(
            input_path, kind=kind, sheet=sheet, separator=separator
        )
        for w in result.warnings:
            import logging

            logging.getLogger(__name__).warning(w)
        return result.df

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
    run_column: str | None = None,
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
    project_path: str | Path | None = None,
    template_version_overrides: dict[str, str] | None = None,
    task_value_offsets: dict[str, float] | None = None,
    allow_near_item_match: bool = False,
    near_match_tasks: set[str] | None = None,
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

    normalized_task_value_offsets: dict[str, float] | None = None
    if isinstance(task_value_offsets, dict) and task_value_offsets:
        normalized_task_value_offsets = {}
        for raw_task, raw_offset in task_value_offsets.items():
            task_name = str(raw_task or "").strip().lower()
            if not task_name:
                continue
            try:
                normalized_task_value_offsets[task_name] = float(raw_offset)
            except (TypeError, ValueError) as error:
                raise ValueError(
                    f"Invalid task value offset for '{raw_task}': {raw_offset!r}"
                ) from error
        if not normalized_task_value_offsets:
            normalized_task_value_offsets = None

    try:
        import pandas  # noqa: F401 -- import-only fail-fast guard, see except below
    except Exception as e:  # pragma: no cover
        raise RuntimeError(
            "pandas is required for survey conversion. Ensure dependencies are installed via setup.sh"
        ) from e

    id_normalizers = _survey_core.build_survey_id_normalizers(project_path)
    _normalize_sub_id = id_normalizers.normalize_sub
    _normalize_ses_id = id_normalizers.normalize_ses
    _normalize_run_id = id_normalizers.normalize_run
    _is_missing_value = id_normalizers.is_missing

    # --- Load Aliases and Templates ---
    participants_converter = ParticipantsConverter()
    loaded = _survey_core._load_survey_aliases_and_templates(
        participants_converter=participants_converter,
        library_dir=library_dir,
        alias_file=alias_file,
        load_and_preprocess_templates_fn=_load_and_preprocess_templates,
    )
    alias_map = loaded.alias_map
    participant_template = loaded.participant_template
    participant_columns_lower = loaded.participant_columns_lower
    templates = loaded.templates
    item_to_task = loaded.item_to_task
    template_warnings_by_task = loaded.template_warnings_by_task
    conversion_warnings: list[str] = list(loaded.warnings)

    conversion_warnings.extend(
        _survey_lsa._apply_lsa_structural_matching(
            templates=templates,
            item_to_task=item_to_task,
            participant_columns_lower=participant_columns_lower,
            lsa_analysis=lsa_analysis,
            survey_filter=survey,
            add_matched_template_fn=_add_matched_template,
            unmatched_groups_error_cls=UnmatchedGroupsError,
        )
    )

    # --- LSA Participant Column Renames ---
    # When converting .lsa files, LimeSurvey mangles question codes (strips
    # underscores, truncates long names with MD5 hash suffix). Build a reverse
    # mapping so _write_survey_participants() can match mangled DF columns
    # back to standard PRISM participant field names.
    lsa_participant_renames = _survey_lsa._derive_lsa_participant_renames(
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
    selected_tasks = _survey_core._resolve_selected_tasks(
        survey_filter=survey,
        templates=templates,
    )

    # --- Determine Columns ---
    from .id_detection import has_prismmeta_columns as _has_pm

    _prismmeta = _has_pm(list(df.columns))
    res_id_col, res_ses_col, res_run_col = _resolve_id_and_session_cols(
        df,
        id_column,
        session_column,
        participants_template=participant_template,
        source_format=source_format,
        has_prismmeta=_prismmeta,
        run_column=run_column,
    )
    if res_run_col:
        print(f"[PRISM INFO] Run column detected: '{res_run_col}'")

    # --- Apply subject ID mapping if provided ---
    id_map: dict[str, str] | None = _load_id_mapping(id_map_file)
    df, res_id_col, id_map_warnings = (
        _survey_participants_logic._apply_subject_id_mapping(
            df=df,
            res_id_col=res_id_col,
            id_map=id_map,
            id_map_file=id_map_file,
            suggest_id_matches_fn=_suggest_id_matches,
            missing_id_mapping_error_cls=MissingIdMappingError,
        )
    )
    conversion_warnings.extend(id_map_warnings)

    if alias_map:
        df = _apply_alias_map_to_dataframe(df=df, alias_map=alias_map)

    # PRISM survey conversion currently accepts long-format tables only.
    # If wide session-coded columns are detected without a session column,
    # direct users to the dedicated File Management conversion tool.
    if res_ses_col is None:
        detected_prefixes = detect_wide_session_prefixes(list(df.columns), min_count=2)
        if detected_prefixes:
            raise ValueError(
                "Wide-format session-coded columns detected "
                f"({', '.join(detected_prefixes)}). "
                "Survey conversion accepts long format only. "
                "Use File Management -> Wide to Long first."
            )

    # --- Detect Available Sessions ---
    detected_sessions = _survey_core._detect_sessions(
        df=df,
        res_ses_col=res_ses_col,
    )

    # --- Filter Rows by Selected Session ---
    # If both session column exists and a specific session is selected,
    # filter to only rows matching that session.
    # This MUST happen before duplicate checking so that legitimate duplicates
    # (same subject in different sessions) can be filtered to a single session.
    df = _survey_core._filter_rows_by_selected_session(
        df=df,
        res_ses_col=res_ses_col,
        session=session,
        duplicate_handling=duplicate_handling,
        detected_sessions=detected_sessions,
    )

    # --- Extract LimeSurvey System Columns ---
    # Only native LimeSurvey sources should emit tool-limesurvey sidecars.
    # Generic CSV/XLSX/TSV imports may contain similarly named columns, but
    # those must remain in the primary survey flow and not produce
    # tool-limesurvey artifacts.
    source_format_normalized = str(source_format or "").strip().lower()
    ls_system_cols: list[str] = []
    if source_format_normalized in {"lsa", "lss"}:
        detected_ls_system_cols, _ = _extract_limesurvey_columns(list(df.columns))
        if detected_ls_system_cols:
            shown = ", ".join(detected_ls_system_cols[:8])
            more = (
                ""
                if len(detected_ls_system_cols) <= 8
                else f" (+{len(detected_ls_system_cols) - 8} more)"
            )
            conversion_warnings.append(
                f"LimeSurvey system columns detected ({len(detected_ls_system_cols)}): {shown}{more}"
            )
        ls_system_cols = detected_ls_system_cols

    # Handle duplicate IDs based on duplicate_handling parameter
    df, _res_ses_override, duplicate_warnings = _survey_core._handle_duplicate_ids(
        df=df,
        res_id_col=res_id_col,
        duplicate_handling=duplicate_handling,
        normalize_sub_fn=_normalize_sub_id,
        res_ses_col=res_ses_col,
        res_run_col=res_run_col,
    )
    if _res_ses_override:
        res_ses_col = _res_ses_override
    conversion_warnings.extend(duplicate_warnings)

    # Two participant ids differing only by case (e.g. 'sub-Ab'/'sub-ab')
    # resolve to the identical on-disk directory on a case-insensitive
    # filesystem (default macOS/Windows): the second one written would
    # silently overwrite the first's survey files with no error. Fail
    # fast, before any output is written, rather than allow that.
    normalized_ids_for_collision_check = (
        df[res_id_col].astype(str).map(_normalize_sub_id)
    )
    collision_message = describe_case_insensitive_id_collisions(
        [sid for sid in normalized_ids_for_collision_check if sid]
    )
    if collision_message:
        raise ValueError(collision_message)

    participant_registry_warning = None
    if skip_participants:
        participant_registry_warning = _build_participant_registry_warning(
            df=df,
            res_id_col=res_id_col,
            normalize_sub_fn=_normalize_sub_id,
            project_path=project_path,
        )
        if participant_registry_warning:
            conversion_warnings.append(
                _format_participant_registry_warning_message(
                    participant_registry_warning
                )
            )

    (
        col_to_mapping,
        unknown_cols,
        map_warnings,
        task_runs,
        near_match_candidates,
        near_match_applied,
    ) = _survey_column_mapping._map_survey_columns(
        df=df,
        item_to_task=item_to_task,
        participant_columns_lower=participant_columns_lower,
        id_col=res_id_col,
        ses_col=res_ses_col,
        run_col=res_run_col,
        unknown_mode=unknown,
        templates=templates,
        selected_tasks=selected_tasks,
        allow_near_item_match=allow_near_item_match,
        near_match_tasks=near_match_tasks,
    )
    conversion_warnings.extend(map_warnings)

    tasks_with_data, task_template_warnings = _survey_core._resolve_tasks_with_warnings(
        col_to_mapping=col_to_mapping,
        selected_tasks=selected_tasks,
        template_warnings_by_task=template_warnings_by_task,
        templates=templates,
        library_dir=library_dir,
        unknown_cols=unknown_cols,
    )
    conversion_warnings.extend(task_template_warnings)

    col_to_task, task_run_columns = _survey_core._build_col_to_task_and_task_runs(
        col_to_mapping=col_to_mapping,
    )
    if res_run_col and res_run_col in df.columns:
        detected_run_numbers = sorted(
            int(run_label[4:])
            for value in df[res_run_col].dropna().tolist()
            if (run_label := _normalize_run_id(value)) is not None
            and run_label.startswith("run-")
            and run_label[4:].isdigit()
        )
        if detected_run_numbers:
            max_detected_run = max(detected_run_numbers)
            for task in tasks_with_data:
                existing_run_count = task_runs.get(task)
                if isinstance(existing_run_count, int):
                    task_runs[task] = max(existing_run_count, max_detected_run)
                else:
                    task_runs[task] = max_detected_run if max_detected_run > 1 else None

    task_context_templates, task_context_acq_map = _build_task_context_maps(
        tasks_with_data=tasks_with_data,
        df=df,
        res_ses_col=res_ses_col,
        session=session,
        res_run_col=res_run_col,
        task_run_columns=task_run_columns,
        templates=templates,
        template_version_overrides=template_version_overrides,
        normalize_ses_fn=_normalize_ses_id,
    )

    # --- Results Preparation ---
    missing_items_by_task = _compute_missing_items_report(
        tasks_with_data, templates, col_to_task
    )

    # Build template_matches from lsa_analysis for API responses
    _template_matches = _survey_core._build_template_matches_payload(
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
            task_context_templates=task_context_templates,
            res_id_col=res_id_col,
            res_ses_col=res_ses_col,
            res_run_col=res_run_col,
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
            task_runs=task_runs,
            task_context_acq_map=task_context_acq_map,
        )
        if participant_registry_warning:
            dry_run_preview["participant_registry_warning"] = (
                participant_registry_warning
            )
            dry_run_preview.setdefault("data_issues", []).append(
                participant_registry_warning
            )

        return SurveyConvertResult(
            tasks_included=sorted(tasks_with_data),
            unknown_columns=unknown_cols,
            missing_items_by_task=missing_items_by_task,
            id_column=res_id_col,
            session_column=res_ses_col,
            run_column=res_run_col,
            detected_sessions=detected_sessions,
            conversion_warnings=conversion_warnings,
            task_runs=task_runs,
            dry_run_preview=dry_run_preview,
            template_matches=_template_matches,
            tool_columns=ls_system_cols or [],
            participant_registry_warning=participant_registry_warning,
            near_match_candidates=near_match_candidates,
            near_match_applied=near_match_applied,
        )

    # --- Write Output ---
    _ensure_dir(output_root)
    dataset_root = _resolve_dataset_root(output_root)
    _ensure_dir(dataset_root)
    _write_survey_description(dataset_root, name, authors)

    if not skip_participants:
        participants_converter.write_participants(
            df=df,
            output_root=dataset_root,
            id_col=res_id_col,
            ses_col=res_ses_col,
            participant_template=participant_template,
            normalize_sub_fn=_normalize_sub_id,
            is_missing_fn=_is_missing_value,
            missing_token=_MISSING_TOKEN,
            lsa_col_renames=lsa_participant_renames,
        )

    _survey_io._write_task_sidecars(
        dataset_root=dataset_root,
        task_context_templates=task_context_templates,
        task_context_acq_map=task_context_acq_map,
        language=language,
        force=force,
        technical_overrides=technical_overrides,
        missing_token=_MISSING_TOKEN,
        localize_survey_template_fn=_localize_survey_template,
        inject_missing_token_fn=_inject_missing_token,
        apply_technical_overrides_fn=_apply_technical_overrides,
        strip_internal_keys_fn=_strip_internal_keys,
        write_json_fn=_write_json,
        load_global_library_path_fn=_load_global_library_path,
    )

    # --- Process and Write Responses ---
    (
        missing_cells_by_subject,
        items_using_tolerance,
        value_offset_application_counts,
    ) = _survey_io._process_and_write_responses(
        df=df,
        res_id_col=res_id_col,
        res_ses_col=res_ses_col,
        res_run_col=res_run_col,
        session=session,
        output_root=output_root,
        task_run_columns=task_run_columns,
        selected_tasks=selected_tasks,
        templates=templates,
        task_context_templates=task_context_templates,
        col_to_mapping=col_to_mapping,
        strict_levels=strict_levels,
        task_runs=task_runs,
        task_context_acq_map=task_context_acq_map,
        non_item_toplevel_keys=_NON_ITEM_TOPLEVEL_KEYS,
        normalize_sub_fn=_normalize_sub_id,
        normalize_ses_fn=_normalize_ses_id,
        normalize_item_fn=_normalize_item_value,
        is_missing_fn=_is_missing_value,
        ensure_dir_fn=_ensure_dir,
        process_survey_row_with_run_fn=_process_survey_row_with_run,
        build_bids_survey_filename_fn=_build_bids_survey_filename,
        task_value_offsets=normalized_task_value_offsets,
    )

    applied_value_offsets: dict[str, float] = {}
    if normalized_task_value_offsets:
        wildcard_offset = normalized_task_value_offsets.get("*")
        for task_name, applications in value_offset_application_counts.items():
            if applications <= 0:
                continue
            offset_value = normalized_task_value_offsets.get(task_name, wildcard_offset)
            if offset_value is None:
                continue
            applied_value_offsets[task_name] = float(offset_value)

    # Add summary for items using numeric range tolerance
    conversion_warnings.extend(
        _survey_io._build_tolerance_warnings(
            items_using_tolerance=items_using_tolerance,
        )
    )

    # --- Write LimeSurvey System Variables ---
    if ls_system_cols:
        # Extract LS metadata from the .lsa analysis if available
        _ls_meta: dict = {}
        if lsa_analysis and isinstance(lsa_analysis, dict):
            _ls_meta["survey_id"] = lsa_analysis.get("survey_id", "")
            _ls_meta["survey_title"] = lsa_analysis.get("survey_title", "")
            _ls_meta["tool_version"] = lsa_analysis.get("software_version", "")

        ls_files_written = _survey_io._write_tool_limesurvey_files(
            df=df,
            ls_system_cols=ls_system_cols,
            res_id_col=res_id_col,
            res_ses_col=res_ses_col,
            session=session,
            output_root=output_root,
            normalize_sub_fn=_normalize_sub_id,
            normalize_ses_fn=_normalize_ses_id,
            ensure_dir_fn=_ensure_dir,
            build_bids_survey_filename_fn=_build_bids_survey_filename,
            ls_metadata=_ls_meta,
        )
        if ls_files_written:
            conversion_warnings.append(
                f"Wrote {ls_files_written} tool-limesurvey file(s) with JSON sidecar"
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
        run_column=res_run_col,
        detected_sessions=detected_sessions,
        missing_cells_by_subject=missing_cells_by_subject,
        missing_value_token=_MISSING_TOKEN,
        conversion_warnings=conversion_warnings,
        task_runs=task_runs,
        template_matches=_template_matches,
        tool_columns=ls_system_cols or [],
        participant_registry_warning=participant_registry_warning,
        near_match_candidates=near_match_candidates,
        near_match_applied=near_match_applied,
        applied_value_offsets=applied_value_offsets,
        value_offset_application_counts=value_offset_application_counts,
    )


def _normalize_item_value(val) -> str:
    return _survey_processing._normalize_item_value(
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
    run_column: str | None = None,
) -> tuple[str, str | None, str | None]:
    return _survey_participants_logic._resolve_id_and_session_cols(
        df=df,
        id_column=id_column,
        session_column=session_column,
        participants_template=participants_template,
        source_format=source_format,
        has_prismmeta=has_prismmeta,
        run_column=run_column,
    )


def _write_survey_description(
    output_root: Path, name: str | None, authors: list[str] | None
):
    """Write dataset_description.json if it doesn't exist."""
    ds_desc = output_root / "dataset_description.json"
    if ds_desc.exists():
        return

    from src import __version__ as prism_version

    dataset_description = {
        "Name": name or "PRISM Survey Dataset",
        "BIDSVersion": DEFAULT_BIDS_VERSION,
        "DatasetType": "raw",
        "Authors": authors or ["prism-studio"],
        "Acknowledgements": "This dataset was created using the PRISM framework.",
        "HowToAcknowledge": "Please cite the original survey publication and the PRISM framework.",
        "Keywords": ["psychology", "survey", "PRISM"],
        "GeneratedBy": [
            {
                "Name": "PRISM Survey Converter",
                "Version": prism_version,
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


def _load_and_preprocess_templates(
    library_dir: Path,
    canonical_aliases: dict[str, list[str]] | None,
    compare_with_global: bool = True,
    template_version_overrides: dict[str, str] | None = None,
) -> tuple[
    dict[str, dict],
    dict[str, str],
    dict[str, set[str]],
    dict[str, list[str]],
]:
    """Load and prepare survey templates from library."""
    return _survey_templates._load_and_preprocess_templates(
        library_dir=library_dir,
        canonical_aliases=canonical_aliases,
        compare_with_global=compare_with_global,
        template_version_overrides=template_version_overrides,
        load_global_library_path_fn=_load_global_library_path,
        load_global_templates_fn=_load_global_templates,
        is_participant_template_fn=_is_participant_template,
        read_json_fn=_read_json,
        canonicalize_template_items_fn=_canonicalize_template_items,
        non_item_keys=_NON_ITEM_TOPLEVEL_KEYS,
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


def _coerce_study_version_value(raw_value) -> str | None:
    """Coerce Study.Version values to a single string value."""
    if isinstance(raw_value, str):
        value = raw_value.strip()
        return value or None
    if isinstance(raw_value, dict):
        if "version" in raw_value:
            nested_value = _coerce_study_version_value(raw_value.get("version"))
            if nested_value:
                return nested_value
        for lang in ("en", "de"):
            candidate = raw_value.get(lang)
            if isinstance(candidate, str) and candidate.strip():
                return candidate.strip()
        for candidate in raw_value.values():
            if isinstance(candidate, str) and candidate.strip():
                return candidate.strip()
    return None


def _normalize_acq_value(raw_value: str | None) -> str | None:
    if not raw_value:
        return None
    normalized = re.sub(r"[^a-zA-Z0-9-]+", "-", str(raw_value).strip().lower())
    normalized = normalized.strip("-")
    return normalized or None


def _normalize_template_version_overrides(
    raw_overrides: object,
) -> list[dict[str, object]]:
    if not raw_overrides:
        return []

    normalized: list[dict[str, object]] = []
    if isinstance(raw_overrides, dict):
        for task, version in raw_overrides.items():
            task_name = str(task or "").strip().lower()
            session_name = None
            run_number = None
            if isinstance(version, dict):
                version_name = _coerce_study_version_value(version)
                session_name = str(version.get("session") or "").strip() or None
                run_value = version.get("run")
                if run_value not in {None, ""}:
                    run_number = _normalize_run_id(run_value)
                    if run_number is None:
                        continue
            else:
                version_name = _coerce_study_version_value(version)
            if task_name and version_name:
                normalized.append(
                    {
                        "task": task_name,
                        "version": version_name,
                        "session": session_name,
                        "run": run_number,
                    }
                )
        return normalized

    if not isinstance(raw_overrides, list):
        return normalized

    for entry in raw_overrides:
        if not isinstance(entry, dict):
            continue
        task_name = str(entry.get("task") or "").strip().lower()
        version_name = _coerce_study_version_value(entry.get("version"))
        if not task_name or not version_name:
            continue
        session_name = str(entry.get("session") or "").strip() or None
        run_value = entry.get("run")
        run_number = None
        if run_value not in {None, ""}:
            run_number = _normalize_run_id(run_value)
            if run_number is None:
                continue
        normalized.append(
            {
                "task": task_name,
                "version": version_name,
                "session": session_name,
                "run": run_number,
            }
        )
    return normalized


def _template_version_override_key(
    entry: dict[str, object],
) -> tuple[str, str | None, str | None]:
    task = str(entry.get("task") or "").strip().lower()
    session = str(entry.get("session") or "").strip() or None
    run = str(entry.get("run") or "").strip() or None
    return task, session, run


def _merge_template_version_overrides(
    *,
    primary_overrides: object,
    fallback_overrides: object,
) -> list[dict[str, object]]:
    """Merge override lists, preferring primary entries for matching contexts."""

    primary = _normalize_template_version_overrides(primary_overrides)
    fallback = _normalize_template_version_overrides(fallback_overrides)

    merged: list[dict[str, object]] = list(primary)
    seen = {_template_version_override_key(entry) for entry in primary}
    for entry in fallback:
        key = _template_version_override_key(entry)
        if key in seen:
            continue
        merged.append(entry)
    return merged


def _load_project_template_version_overrides(
    dataset_root: Path,
) -> list[dict[str, object]]:
    """Load normalized TemplateVersionSelections from project.json."""

    project_json_path = Path(dataset_root) / "project.json"
    if not project_json_path.exists():
        return []

    try:
        payload = _read_json(project_json_path)
    except Exception:
        return []

    return _normalize_template_version_overrides(
        payload.get("TemplateVersionSelections")
    )


def _persist_project_template_version_overrides(
    *,
    dataset_root: Path,
    task_context_templates: dict[tuple[str, str | None, str | int | None], dict],
) -> None:
    """Persist selected Study.Version values for multi-version task contexts."""

    project_json_path = Path(dataset_root) / "project.json"
    existing_payload: dict = {}
    if project_json_path.exists():
        try:
            existing_payload = _read_json(project_json_path)
        except Exception:
            existing_payload = {}

    generated_overrides: list[dict[str, object]] = []
    for (task, session_name, run_name), template_json in sorted(
        task_context_templates.items(),
        key=lambda item: (item[0][0], item[0][1] or "", str(item[0][2] or "")),
    ):
        if not isinstance(template_json, dict):
            continue
        study = template_json.get("Study")
        if not isinstance(study, dict):
            continue

        versions_raw = study.get("Versions")
        versions = (
            [str(v).strip() for v in versions_raw if str(v).strip()]
            if isinstance(versions_raw, list)
            else []
        )
        if len(versions) <= 1:
            continue

        selected_version = _coerce_study_version_value(study.get("Version"))
        if not selected_version:
            continue

        entry: dict[str, object] = {
            "task": str(task or "").strip().lower(),
            "version": selected_version,
        }
        if session_name not in {None, ""}:
            entry["session"] = str(session_name).strip()
        if run_name not in {None, ""}:
            normalized_run = _normalize_run_id(run_name)
            if normalized_run:
                entry["run"] = normalized_run
        generated_overrides.append(entry)

    merged_overrides = _merge_template_version_overrides(
        primary_overrides=generated_overrides,
        fallback_overrides=existing_payload.get("TemplateVersionSelections"),
    )

    if merged_overrides:
        existing_payload["TemplateVersionSelections"] = merged_overrides
    else:
        existing_payload.pop("TemplateVersionSelections", None)

    _write_json(project_json_path, existing_payload)


def _resolve_requested_template_version(
    *,
    task: str,
    session: str | None,
    run: str | int | None,
    template_version_overrides: object,
    normalize_ses_fn,
) -> str | None:
    best_version: str | None = None
    best_score = -1
    for entry in _normalize_template_version_overrides(template_version_overrides):
        if entry.get("task") != task:
            continue
        entry_session = entry.get("session")
        if entry_session not in {None, ""}:
            entry_session = normalize_ses_fn(entry_session)
        else:
            entry_session = None
        if entry_session is not None and entry_session != session:
            continue
        entry_run = entry.get("run")
        if entry_run is not None and entry_run != run:
            continue
        score = 1
        if entry_session is not None:
            score += 1
        if entry_run is not None:
            score += 1
        if score > best_score:
            best_score = score
            best_version = _coerce_study_version_value(entry.get("version"))
    return best_version


def _derive_template_acq_value(*, task: str, template_json: dict) -> str | None:
    study = template_json.get("Study")
    if not isinstance(study, dict):
        return None

    versions = []
    versions_raw = study.get("Versions")
    if isinstance(versions_raw, list):
        versions = [str(v).strip() for v in versions_raw if str(v).strip()]

    active_version = _coerce_study_version_value(study.get("Version"))

    if len(versions) > 1 and active_version and active_version not in versions:
        raise ValueError(
            f"Template version mismatch for task '{task}': "
            f"Study.Version '{active_version}' is not in Study.Versions "
            f"({', '.join(versions)})."
        )

    if len(versions) > 1 and not active_version:
        raise ValueError(
            f"Template 'survey-{task}.json' defines multiple Study.Versions "
            "but no active Study.Version. Set Study.Version in the template."
        )

    if len(versions) > 1:
        return _normalize_acq_value(active_version)
    return None


def _build_task_context_maps(
    *,
    tasks_with_data: set[str],
    df,
    res_ses_col: str | None,
    session: str | None,
    res_run_col: str | None,
    task_run_columns: dict[tuple[str, int | None], list[str]],
    templates: dict[str, dict],
    template_version_overrides: object,
    normalize_ses_fn,
) -> tuple[
    dict[tuple[str, str | None, str | int | None], dict],
    dict[tuple[str, str | None, str | int | None], str | None],
]:
    """Build per task/run template variants and their acq labels."""
    task_contexts: set[tuple[str, str | None, str | int | None]] = set()
    normalized_template_overrides = _normalize_template_version_overrides(
        template_version_overrides
    )
    template_override_contexts_by_task: dict[str, list[dict[str, object]]] = {}
    for override_entry in normalized_template_overrides:
        override_task = str(override_entry.get("task") or "").strip().lower()
        if not override_task:
            continue
        template_override_contexts_by_task.setdefault(override_task, []).append(
            override_entry
        )

    detected_session_values: list[str] = []
    if res_ses_col and res_ses_col in df.columns:
        detected_session_values = sorted(
            {
                normalize_ses_fn(value)
                for value in df[res_ses_col].dropna().tolist()
                if str(value).strip()
            }
        )
    elif session and session != "all":
        detected_session_values = [normalize_ses_fn(session)]

    detected_run_values: list[str] = []
    if res_run_col and res_run_col in df.columns:
        detected_run_values = sorted(
            run_label
            for value in df[res_run_col].dropna().tolist()
            if (run_label := _normalize_run_id(value)) is not None
        )

    observed_contexts_from_rows: set[tuple[str | None, str | None]] = set()
    has_session_rows = bool(res_ses_col and res_ses_col in df.columns)
    has_run_rows = bool(res_run_col and res_run_col in df.columns)
    if has_session_rows or has_run_rows:
        for _, row in df.iterrows():
            row_session: str | None = None
            row_run: str | None = None
            if has_session_rows and str(row.get(res_ses_col) or "").strip():
                row_session = normalize_ses_fn(row[res_ses_col])
            if has_run_rows:
                row_run = _normalize_run_id(row[res_run_col])
            observed_contexts_from_rows.add((row_session, row_run))

    for task in sorted(tasks_with_data):
        template_json = (templates.get(task) or {}).get("json")
        if not isinstance(template_json, dict):
            continue

        study = template_json.get("Study")
        versions: list[str] = []
        if isinstance(study, dict) and isinstance(study.get("Versions"), list):
            versions = [
                str(value).strip()
                for value in study.get("Versions", [])
                if str(value).strip()
            ]
        is_multiversion = len(versions) > 1

        if not is_multiversion:
            task_contexts.add((task, None, None))
            continue

        task_override_entries = template_override_contexts_by_task.get(task, [])
        task_override_sessions = sorted(
            {
                normalize_ses_fn(raw_session)
                for raw_session in (
                    entry.get("session") for entry in task_override_entries
                )
                if raw_session not in {None, ""}
            }
        )
        task_override_runs = sorted(
            {
                normalized_run
                for normalized_run in (
                    _normalize_run_id(entry.get("run"))
                    for entry in task_override_entries
                )
                if normalized_run is not None
            }
        )

        task_specific_runs = sorted(
            {
                run
                for (task_name, run) in task_run_columns.keys()
                if task_name == task and run is not None
            }
        )
        contextual_sessions: list[str] = []
        if len(detected_session_values) > 1:
            contextual_sessions = detected_session_values
        elif len(detected_session_values) == 1:
            single_detected_session = detected_session_values[0]
            has_explicit_session_filter = bool(
                str(session or "").strip() and str(session).strip().lower() != "all"
            )
            if has_explicit_session_filter or single_detected_session in {
                str(session_name or "").strip()
                for session_name in task_override_sessions
            }:
                contextual_sessions = [single_detected_session]
        if not contextual_sessions and task_override_sessions:
            contextual_sessions = task_override_sessions

        contextual_runs = (
            task_specific_runs
            if len(task_specific_runs) > 1
            else (detected_run_values if len(detected_run_values) > 1 else [])
        )
        if not contextual_runs and task_override_runs:
            contextual_runs = task_override_runs

        if not contextual_sessions and not contextual_runs:
            task_contexts.add((task, None, None))
            continue

        task_observed_contexts: set[tuple[str | None, str | None]] = set()
        for row_session, row_run in observed_contexts_from_rows:
            effective_session = row_session if contextual_sessions else None
            effective_run = row_run if contextual_runs else None
            if (
                effective_run is not None
                and task_specific_runs
                and effective_run not in task_specific_runs
            ):
                continue
            if effective_session is None and effective_run is None:
                continue
            task_observed_contexts.add((effective_session, effective_run))

        if task_observed_contexts:
            for context_session, context_run in sorted(
                task_observed_contexts,
                key=lambda item: (item[0] or "", item[1] or ""),
            ):
                task_contexts.add((task, context_session, context_run))
            continue

        fallback_sessions = (
            [cast(str | None, session_name) for session_name in contextual_sessions]
            if contextual_sessions
            else [None]
        )
        fallback_runs = (
            [cast(str | None, run_number) for run_number in contextual_runs]
            if contextual_runs
            else [None]
        )
        for context_session in fallback_sessions:
            for context_run in fallback_runs:
                task_contexts.add((task, context_session, context_run))

    task_context_templates: dict[tuple[str, str | None, str | int | None], dict] = {}
    task_context_acq_map: dict[
        tuple[str, str | None, str | int | None], str | None
    ] = {}

    for task, context_session, run in sorted(
        task_contexts, key=lambda item: (item[0], item[1] or "", str(item[2] or ""))
    ):
        template_json = (templates.get(task) or {}).get("json")
        if not isinstance(template_json, dict):
            continue
        requested_version = _resolve_requested_template_version(
            task=task,
            session=context_session,
            run=run,
            template_version_overrides=normalized_template_overrides,
            normalize_ses_fn=normalize_ses_fn,
        )
        variant_template = _apply_template_version_selection(
            template_json,
            task=task,
            requested_version=requested_version,
            non_item_keys=_NON_ITEM_TOPLEVEL_KEYS,
        )
        task_context_templates[(task, context_session, run)] = variant_template
        task_context_acq_map[(task, context_session, run)] = _derive_template_acq_value(
            task=task,
            template_json=variant_template,
        )

    return task_context_templates, task_context_acq_map


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
    return _survey_io._generate_participants_preview(
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
    task_context_templates: dict[tuple[str, str | None, str | int | None], dict],
    res_id_col: str,
    res_ses_col: str | None,
    res_run_col: str | None = None,
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
    task_runs: dict[str, int | None] | None = None,
    task_context_acq_map: (
        dict[tuple[str, str | None, str | int | None], str | None] | None
    ) = None,
    task_acq_map: dict[str, str | None] | None = None,
) -> dict:
    """Generate a detailed preview of what will be created during conversion."""
    return _survey_io._generate_dry_run_preview(
        df=df,
        tasks_with_data=tasks_with_data,
        task_run_columns=task_run_columns,
        col_to_mapping=col_to_mapping,
        templates=templates,
        task_context_templates=task_context_templates,
        res_id_col=res_id_col,
        res_ses_col=res_ses_col,
        res_run_col=res_run_col,
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
        task_runs=task_runs,
        task_context_acq_map=task_context_acq_map,
        task_acq_map=task_acq_map,
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
    task_value_offsets: dict[str, float] | None = None,
    offset_application_counts: dict[str, int] | None = None,
) -> tuple[dict[str, str], int]:
    """Process a single task's data for one subject/session."""
    return _survey_processing._process_survey_row(
        row=row,
        df_cols=df_cols,
        task=task,
        schema=schema,
        sub_id=sub_id,
        strict_levels=strict_levels,
        items_using_tolerance=items_using_tolerance,
        is_missing_fn=is_missing_fn,
        normalize_val_fn=normalize_val_fn,
        task_value_offsets=task_value_offsets,
        offset_application_counts=offset_application_counts,
        non_item_keys=_NON_ITEM_TOPLEVEL_KEYS,
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
    task_value_offsets: dict[str, float] | None = None,
    offset_application_counts: dict[str, int] | None = None,
) -> tuple[dict[str, str], int]:
    """Process a single task/run's data for one subject/session."""
    return _survey_processing._process_survey_row_with_run(
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
        task_value_offsets=task_value_offsets,
        offset_application_counts=offset_application_counts,
        non_item_keys=_NON_ITEM_TOPLEVEL_KEYS,
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
    task_value_offsets: dict[str, float] | None = None,
    offset_application_counts: dict[str, int] | None = None,
):
    """Internal validation for a single survey item value."""
    return _survey_processing._validate_survey_item_value(
        item_id=item_id,
        val=val,
        item_schema=item_schema,
        sub_id=sub_id,
        task=task,
        strict_levels=strict_levels,
        items_using_tolerance=items_using_tolerance,
        normalize_fn=normalize_fn,
        is_missing_fn=is_missing_fn,
        task_value_offsets=task_value_offsets,
        offset_application_counts=offset_application_counts,
        find_matching_level_key_fn=_survey_participants_logic._find_matching_level_key,
        missing_token=_MISSING_TOKEN,
    )


def _infer_lsa_language_and_tech(*, input_path: Path, df) -> tuple[str | None, dict]:
    """Compatibility wrapper delegating to extracted LSA metadata module."""
    return _survey_lsa._infer_lsa_language_and_tech(input_path=input_path, df=df)


def _read_lsa_as_dataframe(input_path: str | Path):
    """Compatibility wrapper that returns only the LSA response DataFrame."""
    result = _read_table_as_dataframe(input_path=Path(input_path).resolve(), kind="lsa")
    df, _questions_map = _survey_lsa._unpack_lsa_read_result(result)
    return df


def infer_lsa_metadata(input_path: str | Path) -> dict:
    """Compatibility wrapper delegating to extracted LSA metadata module."""
    return _survey_lsa.infer_lsa_metadata(input_path)


def _resolve_effective_template_version_overrides(
    *,
    project_path: str | Path | None,
    template_version_overrides: object,
) -> object:
    """Resolve request + project template-version selections.

    Request-level selections take precedence over `project.json`
    `TemplateVersionSelections` entries for the same task/session/run context.
    """

    project_path_value = "" if project_path is None else str(project_path).strip()
    if not project_path_value:
        return template_version_overrides

    try:
        project_overrides = _load_project_template_version_overrides(
            Path(project_path_value)
        )
    except Exception:
        project_overrides = []

    if not project_overrides:
        return template_version_overrides

    primary_overrides = _normalize_template_version_overrides(
        template_version_overrides
    )

    return _merge_template_version_overrides(
        primary_overrides=primary_overrides,
        fallback_overrides=project_overrides,
    )


def sync_project_survey_recipe_offsets(
    *,
    project_root: str | Path,
    task_value_offsets: dict[str, float] | None,
    offset_application_counts: dict[str, int] | None = None,
) -> dict[str, list[str]]:
    """Persist applied survey import offsets into project survey recipes.

    Updates `project_root/code/recipes/survey/recipe-<task>.json` in-place by
    writing:
    - `Survey.ImportValueOffset`
    - `Survey.ImportValueOffsetSource`
    - appending to `Survey.ImportValueOffsetHistory`
    """

    summary: dict[str, list[str]] = {
        "updated_tasks": [],
        "missing_tasks": [],
        "errors": [],
    }

    normalized_offsets: dict[str, float] = {}
    for raw_task, raw_offset in (task_value_offsets or {}).items():
        task_name = str(raw_task or "").strip().lower()
        if not task_name:
            continue
        try:
            normalized_offsets[task_name] = float(raw_offset)
        except (TypeError, ValueError):
            summary["errors"].append(
                f"{task_name}: invalid offset value {raw_offset!r}"
            )

    if not normalized_offsets:
        return summary

    project_root_path = Path(project_root)
    recipes_root = project_root_path / "code" / "recipes" / "survey"

    for task_name in sorted(normalized_offsets):
        recipe_path = recipes_root / f"recipe-{task_name}.json"
        if not recipe_path.exists():
            summary["missing_tasks"].append(task_name)
            continue

        try:
            recipe_payload = _read_json(recipe_path)
            if not isinstance(recipe_payload, dict):
                recipe_payload = {}

            survey_section = recipe_payload.get("Survey")
            if not isinstance(survey_section, dict):
                survey_section = {}

            offset_value = normalized_offsets[task_name]
            survey_section["ImportValueOffset"] = offset_value
            survey_section["ImportValueOffsetSource"] = "survey-import"

            history = survey_section.get("ImportValueOffsetHistory")
            if not isinstance(history, list):
                history = []

            history_entry: dict[str, object] = {
                "offset": offset_value,
                "source": "survey-import",
                "updated_at": datetime.now(timezone.utc).isoformat(),
            }

            application_count = (offset_application_counts or {}).get(task_name)
            if isinstance(application_count, int):
                history_entry["applications"] = application_count

            history.append(history_entry)
            survey_section["ImportValueOffsetHistory"] = history

            recipe_payload["Survey"] = survey_section
            _write_json(recipe_path, recipe_payload)
            summary["updated_tasks"].append(task_name)
        except Exception as exc:
            summary["errors"].append(f"{task_name}: {exc}")

    return summary
