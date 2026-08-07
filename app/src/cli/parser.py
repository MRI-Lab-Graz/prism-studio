"""Parser construction helpers for prism_tools CLI."""

from __future__ import annotations

import argparse
from pathlib import Path

from src.entity_rules import load_entity_rules


def build_parser() -> argparse.ArgumentParser:
    """Create a base parser for prism_tools."""
    return argparse.ArgumentParser(
        description="Prism Tools: Utilities for PRISM/BIDS datasets"
    )


def build_prism_tools_parsers(
    project_root: Path,
) -> tuple[argparse.ArgumentParser, dict[str, argparse.ArgumentParser]]:
    """Build full prism_tools parser tree and return key parser handles for dispatch."""
    parser = build_parser()
    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    parser_convert = subparsers.add_parser(
        "convert", help="Convert raw data to BIDS format"
    )
    convert_subparsers = parser_convert.add_subparsers(
        dest="modality", help="Modality to convert"
    )

    _rules = load_entity_rules()
    _physio_suffix = _rules.primary_suffix("physio")
    _default_recording = dict(_rules.modalities["physio"].optional_entity_values)[
        "recording"
    ].enum[0]

    parser_physio = convert_subparsers.add_parser(
        "physio", help="Convert physiological data (Varioport)"
    )
    parser_physio.add_argument(
        "--input",
        required=True,
        help="Path to a sourcedata directory or a single .raw/.vpd file",
    )
    parser_physio.add_argument(
        "--output", required=True, help="Path to output directory"
    )
    parser_physio.add_argument(
        "--task", default="rest", help="Task name (default: rest)"
    )
    parser_physio.add_argument(
        "--suffix",
        default=_physio_suffix,
        help=(
            f"Output suffix. '{_physio_suffix}' is normalized to "
            f"'recording-{_default_recording}_{_physio_suffix}' for BIDS-like naming."
        ),
    )
    parser_physio.add_argument(
        "--sampling-rate", type=float, help="Override sampling rate (e.g. 256)"
    )

    parser_wide_to_long = subparsers.add_parser(
        "wide-to-long",
        help="Convert a wide table with session-coded columns into long format",
    )
    parser_wide_to_long.add_argument(
        "--input",
        required=True,
        help="Path to the input table (.csv, .tsv, or .xlsx)",
    )
    parser_wide_to_long.add_argument(
        "--output",
        help="Optional output path (.csv, .tsv, .xlsx). Default: <input>_long.csv",
    )
    parser_wide_to_long.add_argument(
        "--session-column",
        default="session",
        help="Output column name for the session label (default: session)",
    )
    parser_wide_to_long.add_argument(
        "--id-column",
        help=(
            "Column used for early uniqueness checks before conversion. "
            "If omitted, participant_id is preferred and other IDs require manual selection."
        ),
    )
    parser_wide_to_long.add_argument(
        "--session-indicators",
        default="",
        help="Comma-separated exact indicators to match anywhere in a column name, e.g. T1_,T2_,T3_ or _pre,_post",
    )
    parser_wide_to_long.add_argument(
        "--session-map",
        default="",
        help="Optional indicator-to-session mapping like T1_:pre,T2_:post",
    )
    parser_wide_to_long.add_argument(
        "--sheet",
        default="0",
        help="Sheet name or index for Excel input (default: 0)",
    )
    parser_wide_to_long.add_argument(
        "--preview-limit",
        type=int,
        default=12,
        help="How many rename or ambiguity preview lines to print (default: 12)",
    )
    parser_wide_to_long.add_argument(
        "--inspect-only",
        action="store_true",
        help="Inspect matches and rename preview without writing an output file",
    )
    parser_wide_to_long.add_argument(
        "--json",
        action="store_true",
        help="Emit machine-readable JSON output for backend integrations",
    )
    parser_wide_to_long.add_argument(
        "--force",
        action="store_true",
        help="Overwrite an existing output file",
    )
    parser_wide_to_long.add_argument(
        "--drop-empty-rows",
        action="store_true",
        help=(
            "Exclude participants whose session-coded columns are all empty "
            "(e.g. a dropout row with only an ID/group) from the long output. "
            "Without this flag, such rows are kept but reported as a warning."
        ),
    )

    parser_participants = subparsers.add_parser(
        "participants",
        help="Participants conversion utilities (detect ID, preview, convert)",
    )
    participants_subparsers = parser_participants.add_subparsers(
        dest="action", help="Action"
    )

    parser_participants_detect = participants_subparsers.add_parser(
        "detect-id", help="Detect participant ID column in a table"
    )
    parser_participants_detect.add_argument(
        "--input", required=True, help="Path to input file (.xlsx/.csv/.tsv/.lsa)"
    )
    parser_participants_detect.add_argument(
        "--sheet", default="0", help="Sheet name/index for Excel input (default: 0)"
    )
    parser_participants_detect.add_argument(
        "--separator",
        default="auto",
        choices=["auto", "comma", "semicolon", "tab", "pipe"],
        help="Delimiter override for CSV/TSV (default: auto)",
    )
    parser_participants_detect.add_argument(
        "--json", action="store_true", help="Emit machine-readable JSON"
    )

    parser_participants_preview = participants_subparsers.add_parser(
        "preview",
        help="Preview participant-relevant columns and rows from an input file",
    )
    parser_participants_preview.add_argument(
        "--mode",
        choices=["file", "dataset"],
        default="file",
        help="Preview from an uploaded file or from an existing dataset (default: file)",
    )
    parser_participants_preview.add_argument(
        "--input",
        help="Path to input file (.xlsx/.csv/.tsv/.lsa); required for --mode file",
    )
    parser_participants_preview.add_argument(
        "--project",
        help="Project root or project.json path used to resolve mappings or scan an existing dataset",
    )
    parser_participants_preview.add_argument(
        "--sheet", default="0", help="Sheet name/index for Excel input (default: 0)"
    )
    parser_participants_preview.add_argument(
        "--id-column", help="Explicit participant ID column (default: auto-detect)"
    )
    parser_participants_preview.add_argument(
        "--separator",
        default="auto",
        choices=["auto", "comma", "semicolon", "tab", "pipe"],
        help="Delimiter override for CSV/TSV (default: auto)",
    )
    parser_participants_preview.add_argument(
        "--preview-limit", type=int, default=20, help="Number of rows to preview"
    )
    parser_participants_preview.add_argument(
        "--extract-from-survey",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Include participant IDs discovered from survey files in dataset mode",
    )
    parser_participants_preview.add_argument(
        "--extract-from-biometrics",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Include participant IDs discovered from biometrics files in dataset mode",
    )
    parser_participants_preview.add_argument(
        "--json", action="store_true", help="Emit machine-readable JSON"
    )

    parser_participants_convert = participants_subparsers.add_parser(
        "convert", help="Convert participant table to participants.tsv"
    )
    parser_participants_convert.add_argument(
        "--mode",
        choices=["file", "dataset"],
        default="file",
        help="Convert from an uploaded file or derive participants from an existing dataset (default: file)",
    )
    parser_participants_convert.add_argument(
        "--input",
        help="Path to input file (.xlsx/.csv/.tsv/.lsa); required for --mode file",
    )
    parser_participants_convert.add_argument(
        "--project",
        help="Project root or project.json path; output is <project>/participants.tsv",
    )
    parser_participants_convert.add_argument(
        "--sheet", default="0", help="Sheet name/index for Excel input (default: 0)"
    )
    parser_participants_convert.add_argument(
        "--id-column", help="Explicit participant ID column for auto-mapping"
    )
    parser_participants_convert.add_argument(
        "--separator",
        default="auto",
        choices=["auto", "comma", "semicolon", "tab", "pipe"],
        help="Delimiter override for CSV/TSV (default: auto)",
    )
    parser_participants_convert.add_argument(
        "--force", action="store_true", help="Overwrite existing participants.tsv"
    )
    parser_participants_convert.add_argument(
        "--extract-from-survey",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Include participant IDs discovered from survey files in dataset mode",
    )
    parser_participants_convert.add_argument(
        "--extract-from-biometrics",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Include participant IDs discovered from biometrics files in dataset mode",
    )
    parser_participants_convert.add_argument(
        "--neurobagel-schema",
        help="Optional NeuroBagel schema JSON string to merge into participants.json",
    )
    parser_participants_convert.add_argument(
        "--json", action="store_true", help="Emit machine-readable JSON"
    )

    parser_participants_merge = participants_subparsers.add_parser(
        "merge",
        help="Preview or apply a safe merge into an existing participants.tsv",
    )
    parser_participants_merge.add_argument(
        "--input",
        required=True,
        help="Path to input file (.xlsx/.csv/.tsv/.lsa) that should be merged",
    )
    parser_participants_merge.add_argument(
        "--project",
        required=True,
        help="Project root or project.json path containing the existing participants.tsv",
    )
    parser_participants_merge.add_argument(
        "--sheet", default="0", help="Sheet name/index for Excel input (default: 0)"
    )
    parser_participants_merge.add_argument(
        "--id-column", help="Explicit participant ID column for auto-mapping"
    )
    parser_participants_merge.add_argument(
        "--separator",
        default="auto",
        choices=["auto", "comma", "semicolon", "tab", "pipe"],
        help="Delimiter override for CSV/TSV (default: auto)",
    )
    parser_participants_merge.add_argument(
        "--preview-limit",
        type=int,
        default=20,
        help="How many conflicts/fill actions/rows to include in preview output",
    )
    parser_participants_merge.add_argument(
        "--apply",
        action="store_true",
        help="Write the merged participants.tsv/json if the preview has no conflicts",
    )
    parser_participants_merge.add_argument(
        "--conflicts-csv",
        action="store_true",
        help="Emit the full merge conflict report as CSV to stdout",
    )
    parser_participants_merge.add_argument(
        "--neurobagel-schema",
        help="Optional NeuroBagel schema JSON string to merge into participants.json",
    )
    parser_participants_merge.add_argument(
        "--json", action="store_true", help="Emit machine-readable JSON"
    )

    parser_participants_save_mapping = participants_subparsers.add_parser(
        "save-mapping",
        help="Save participants_mapping.json into the project or a library directory",
    )
    parser_participants_save_mapping.add_argument(
        "--mapping-json",
        required=True,
        help="Mapping JSON object to save",
    )
    parser_participants_save_mapping.add_argument(
        "--project",
        help="Project root or project.json path; preferred target is <project>/code/library",
    )
    parser_participants_save_mapping.add_argument(
        "--library-path",
        help="Fallback library directory when no project is loaded",
    )
    parser_participants_save_mapping.add_argument(
        "--json", action="store_true", help="Emit machine-readable JSON"
    )

    parser_participants_neurobagel_schema = participants_subparsers.add_parser(
        "neurobagel-schema",
        help="Fetch the Neurobagel controlled vocabulary and sample local "
        "participants.tsv columns, to inform building a --neurobagel-schema "
        "payload. Matches the value the Studio GUI's Neurobagel widget adds "
        "beyond a raw --neurobagel-schema passthrough.",
    )
    parser_participants_neurobagel_schema.add_argument(
        "--project", required=True, help="Project root containing participants.tsv"
    )
    parser_participants_neurobagel_schema.add_argument(
        "--output", default=None, help="Path to write the combined JSON (optional)"
    )
    parser_participants_neurobagel_schema.add_argument(
        "--json", action="store_true", help="Emit machine-readable JSON"
    )

    parser_participants_save_schema = participants_subparsers.add_parser(
        "save-schema",
        help="Save a participants.json schema into a project, canonicalizing "
        "participant-ID-like fields into one 'participant_id' key. Matches the "
        "Studio GUI's Neurobagel widget 'Save Annotations' action.",
    )
    parser_participants_save_schema.add_argument(
        "--project", required=True, help="Project root (participants.json target)"
    )
    parser_participants_save_schema.add_argument(
        "--schema-json",
        default=None,
        help="Path to the full schema JSON to save (mutually exclusive with "
        "--survey-selected-schema)",
    )
    parser_participants_save_schema.add_argument(
        "--survey-selected-schema",
        default=None,
        help="Path to a survey-selected-fields schema JSON to merge into the "
        "existing participants.json (mutually exclusive with --schema-json)",
    )
    parser_participants_save_schema.add_argument(
        "--json", action="store_true", help="Emit machine-readable JSON"
    )

    parser_environment = subparsers.add_parser(
        "environment",
        help="Environment conversion utilities (preview)",
    )
    environment_subparsers = parser_environment.add_subparsers(
        dest="action", help="Action"
    )

    parser_environment_scan_mri = environment_subparsers.add_parser(
        "scan-mri",
        help="Scan a project's rawdata for MRI acquisition timestamps/location and "
        "write a TSV usable with 'environment convert --input'. Matches the Studio "
        "GUI's Environment/MRI tab 'Scan Project MRI Data' action.",
    )
    parser_environment_scan_mri.add_argument(
        "--project", required=True, help="Project root folder"
    )
    parser_environment_scan_mri.add_argument(
        "--output", required=True, help="Path to write the scanned TSV"
    )
    parser_environment_scan_mri.add_argument(
        "--json", action="store_true", help="Emit machine-readable JSON"
    )

    parser_environment_preview = environment_subparsers.add_parser(
        "preview",
        help="Preview environment-compatible columns and sample rows from an input file",
    )
    parser_environment_preview.add_argument(
        "--input", required=True, help="Path to input file (.xlsx/.csv/.tsv)"
    )
    parser_environment_preview.add_argument(
        "--separator",
        default="auto",
        choices=["auto", "comma", "semicolon", "tab", "pipe"],
        help="Delimiter override for CSV/TSV (default: auto)",
    )
    parser_environment_preview.add_argument(
        "--json", action="store_true", help="Emit machine-readable JSON"
    )

    parser_environment_convert = environment_subparsers.add_parser(
        "convert",
        help="Convert an environment source table into project environment outputs",
    )
    parser_environment_convert.add_argument(
        "--input", required=True, help="Path to input file (.xlsx/.csv/.tsv)"
    )
    parser_environment_convert.add_argument(
        "--project",
        required=True,
        help="Project root or project.json path receiving environment outputs",
    )
    parser_environment_convert.add_argument(
        "--separator",
        default="auto",
        choices=["auto", "comma", "semicolon", "tab", "pipe"],
        help="Delimiter override for CSV/TSV (default: auto)",
    )
    parser_environment_convert.add_argument(
        "--timestamp-col", required=True, help="Timestamp column name"
    )
    parser_environment_convert.add_argument(
        "--participant-col", help="Participant ID column name"
    )
    parser_environment_convert.add_argument(
        "--participant-override", help="Manual participant ID fallback"
    )
    parser_environment_convert.add_argument("--session-col", help="Session column name")
    parser_environment_convert.add_argument(
        "--session-override", help="Manual session fallback"
    )
    parser_environment_convert.add_argument(
        "--location-col", help="Location label column name"
    )
    parser_environment_convert.add_argument("--lat-col", help="Latitude column name")
    parser_environment_convert.add_argument("--lon-col", help="Longitude column name")
    parser_environment_convert.add_argument(
        "--location-label", help="Manual location label fallback"
    )
    parser_environment_convert.add_argument("--lat", help="Global fallback latitude")
    parser_environment_convert.add_argument("--lon", help="Global fallback longitude")
    parser_environment_convert.add_argument(
        "--pilot-random-subject",
        action="store_true",
        help="Run pilot conversion for one random subject and estimate full runtime",
    )
    parser_environment_convert.add_argument(
        "--json", action="store_true", help="Emit machine-readable JSON"
    )
    parser_environment_convert.add_argument("--log-file", help=argparse.SUPPRESS)
    parser_environment_convert.add_argument("--result-file", help=argparse.SUPPRESS)
    parser_environment_convert.add_argument("--cancel-file", help=argparse.SUPPRESS)

    parser_demo = subparsers.add_parser("demo", help="Demo dataset operations")
    demo_subparsers = parser_demo.add_subparsers(dest="action", help="Action")

    parser_demo_create = demo_subparsers.add_parser(
        "create", help="Create a demo dataset"
    )
    parser_demo_create.add_argument(
        "--output",
        default="archive/prism_demo_copy",
        help="Output path for the demo dataset",
    )

    parser_survey = subparsers.add_parser("survey", help="Survey library operations")
    survey_subparsers = parser_survey.add_subparsers(dest="action", help="Action")

    parser_survey_excel = survey_subparsers.add_parser(
        "import-excel", help="Import survey library from Excel"
    )
    parser_survey_excel.add_argument(
        "--excel", required=True, help="Path to Excel file"
    )
    parser_survey_excel.add_argument(
        "--output", default="survey_library", help="Output directory"
    )
    parser_survey_excel.add_argument(
        "--library-root",
        dest="library_root",
        help="If set, writes to <library-root>/survey instead of --output.",
    )

    parser_survey_convert = survey_subparsers.add_parser(
        "convert",
        help="Convert a wide survey data file (.xlsx or .lsa) into a PRISM/BIDS survey dataset",
    )
    parser_survey_convert.add_argument(
        "--input",
        required=True,
        help="Path to the survey data file (.xlsx or LimeSurvey .lsa)",
    )
    parser_survey_convert.add_argument(
        "--library",
        default=argparse.SUPPRESS,
        help=(
            "Path to survey template library folder (contains survey-*.json). "
            "If omitted, auto-selects library/survey_<lang>, then library/survey_i18n (compiled), then library/survey."
        ),
    )
    parser_survey_convert.add_argument(
        "--lang",
        default="de",
        help="Language for templates when using i18n libraries (default: de; use 'auto' to infer for .lsa)",
    )
    parser_survey_convert.add_argument(
        "--output",
        required=True,
        help="Output dataset root folder (will be created if missing)",
    )
    parser_survey_convert.add_argument(
        "--survey",
        help="Comma-separated list of surveys to include (e.g., 'ads,psqi'). Default: auto-detect from headers.",
    )
    parser_survey_convert.add_argument(
        "--id-column",
        dest="id_column",
        help="Column name containing participant IDs (default: auto-detect)",
    )
    parser_survey_convert.add_argument(
        "--session-column",
        dest="session_column",
        help="Optional column name for session labels (default: auto-detect; otherwise ses-1)",
    )
    parser_survey_convert.add_argument(
        "--run-column",
        dest="run_column",
        default=None,
        help="Optional column name for run labels (default: auto-detect column named 'run' or similar)",
    )
    parser_survey_convert.add_argument(
        "--sheet", default=0, help="Excel sheet name or index (default: 0)"
    )
    parser_survey_convert.add_argument(
        "--unknown",
        choices=["error", "warn", "ignore"],
        default="warn",
        help="How to handle unmapped columns not found in any survey template (default: warn)",
    )
    parser_survey_convert.add_argument(
        "--dry-run",
        action="store_true",
        help="Only print mapping report; do not write files",
    )
    parser_survey_convert.add_argument(
        "--force",
        action="store_true",
        help="Allow writing into a non-empty output dir and overwrite inherited sidecars",
    )
    parser_survey_convert.add_argument(
        "--name", help="Dataset name written to dataset_description.json (if created)"
    )
    parser_survey_convert.add_argument(
        "--authors",
        nargs="+",
        default=None,
        help="Authors written to dataset_description.json (if created)",
    )
    parser_survey_convert.add_argument(
        "--alias",
        dest="alias",
        default=None,
        help=(
            "Optional TSV/whitespace alias file: each line is '<canonical_id> <alias1> <alias2> ...'. "
            "Used to map changing item IDs onto stable canonical IDs before template matching."
        ),
    )
    parser_survey_convert.add_argument(
        "--project",
        dest="project",
        default=None,
        help=(
            "Path to project.json or project root folder. "
            "When provided, project defaults are applied for conversion. "
            "Multi-variant versioning is derived from template Study.Version and filename acq labels."
        ),
    )
    parser_survey_convert.add_argument(
        "--template-version",
        dest="template_versions",
        action="append",
        default=None,
        metavar="TASK=VERSION",
        help=(
            "Override the selected version for a multi-version survey template. "
            "Repeat for multiple tasks, e.g. --template-version wellbeing=10-likert "
            "or --template-version wellbeing;session=ses-02;run=2=10-vas"
        ),
    )
    parser_survey_convert.add_argument(
        "--value-offset",
        dest="value_offsets",
        action="append",
        default=None,
        metavar="TASK=OFFSET",
        help=(
            "Apply a numeric value offset before level/range validation for the given task. "
            "Repeat for multiple tasks, e.g. --value-offset pss=-1. "
            "Use --value-offset *=-1 as a global fallback."
        ),
    )

    parser_biometrics = subparsers.add_parser(
        "biometrics", help="Biometrics library operations"
    )
    biometrics_subparsers = parser_biometrics.add_subparsers(
        dest="action", help="Action"
    )

    parser_biometrics_detect = biometrics_subparsers.add_parser(
        "detect", help="Detect which biometric tasks are present in a spreadsheet"
    )
    parser_biometrics_detect.add_argument(
        "--input", required=True, help="Path to input file (.xlsx, .csv, .tsv)"
    )
    parser_biometrics_detect.add_argument(
        "--library",
        required=True,
        dest="library_dir",
        help="Path to biometrics library directory (containing biometrics-*.json templates)",
    )
    parser_biometrics_detect.add_argument(
        "--sheet", default="0", help="Sheet name or index for Excel input (default: 0)"
    )
    parser_biometrics_detect.add_argument(
        "--json", action="store_true", help="Emit machine-readable JSON output"
    )

    parser_biometrics_convert = biometrics_subparsers.add_parser(
        "convert", help="Convert a biometrics spreadsheet to a PRISM dataset"
    )
    parser_biometrics_convert.add_argument(
        "--input", required=True, help="Path to input file (.xlsx, .csv, .tsv)"
    )
    parser_biometrics_convert.add_argument(
        "--library",
        required=True,
        dest="library_dir",
        help="Path to biometrics library directory (containing biometrics-*.json templates)",
    )
    parser_biometrics_convert.add_argument(
        "--output", required=True, help="Output directory for the PRISM dataset"
    )
    parser_biometrics_convert.add_argument(
        "--id-column", dest="id_column", help="Column name for participant ID"
    )
    parser_biometrics_convert.add_argument(
        "--session-column", dest="session_column", help="Column name for session"
    )
    parser_biometrics_convert.add_argument(
        "--session", help="Override session label (e.g. ses-1)"
    )
    parser_biometrics_convert.add_argument(
        "--sheet", default="0", help="Sheet name or index for Excel input (default: 0)"
    )
    parser_biometrics_convert.add_argument(
        "--unknown",
        default="warn",
        choices=["warn", "error", "ignore"],
        help="How to handle unknown columns (default: warn)",
    )
    parser_biometrics_convert.add_argument(
        "--tasks",
        default="",
        help="Comma-separated task names to export (default: all detected)",
    )
    parser_biometrics_convert.add_argument("--name", help="Dataset name")
    parser_biometrics_convert.add_argument(
        "--force", action="store_true", help="Overwrite existing output directory"
    )

    parser_physio = subparsers.add_parser(
        "physio", help="Physiological data operations"
    )
    physio_subparsers = parser_physio.add_subparsers(dest="action", help="Action")

    parser_physio_batch = physio_subparsers.add_parser(
        "batch-convert",
        help="Batch convert physio/eyetracking files in a flat source folder",
    )
    parser_physio_batch.add_argument(
        "--input", required=True, help="Path to source folder containing raw files"
    )
    parser_physio_batch.add_argument(
        "--output", required=True, help="Path to output PRISM dataset folder"
    )
    parser_physio_batch.add_argument(
        "--modality",
        default="all",
        choices=["all", "physio", "eyetracking"],
        help="Modality filter (default: all)",
    )
    parser_physio_batch.add_argument(
        "--sampling-rate",
        type=float,
        dest="sampling_rate",
        help="Override physio sampling rate in Hz",
    )
    parser_physio_batch.add_argument(
        "--dry-run",
        action="store_true",
        dest="dry_run",
        help="Preview without writing files",
    )

    parser_recipes = subparsers.add_parser(
        "recipes",
        help="Compute scores/recipes from an already-valid PRISM dataset using recipes",
    )
    recipes_subparsers = parser_recipes.add_subparsers(dest="kind", help="Recipe kind")

    parser_deriv_surveys = recipes_subparsers.add_parser(
        "surveys",
        aliases=["survey", "surves"],
        help="Compute survey scores (e.g., reverse coding, subscales) from TSVs",
    )
    parser_deriv_surveys.add_argument(
        "--prism",
        "--dataset",
        required=True,
        help="Path to the PRISM dataset root (input + output target)",
    )
    parser_deriv_surveys.add_argument(
        "--repo",
        default=(
            str(project_root.parent)
            if project_root.name == "app"
            else str(project_root)
        ),
        help=(
            "Path to the PRISM tools repository root (used to locate recipe JSONs under "
            "recipe/survey/*.json). Default: this script's folder."
        ),
    )
    parser_deriv_surveys.add_argument(
        "--recipes",
        help="Optional path to a custom folder containing recipe JSONs. Overrides default repository folder.",
    )
    parser_deriv_surveys.add_argument(
        "--survey",
        "--task",
        help="Optional comma-separated recipe selection (e.g., 'ADS'). Default: run all matching recipes.",
    )
    parser_deriv_surveys.add_argument(
        "--sessions",
        help="Optional comma-separated session list (e.g., 'ses-1,ses-2' or '1,2'). Default: all sessions.",
    )
    parser_deriv_surveys.add_argument(
        "--format",
        default="flat",
        choices=["prism", "flat", "csv", "xlsx", "sav", "save"],
        help="Output format: 'flat' (default), 'prism', 'csv', 'xlsx', 'sav' (SPSS; 'save' is legacy alias)",
    )
    parser_deriv_surveys.add_argument(
        "--lang",
        default="en",
        choices=["en", "de"],
        help="Language for metadata labels in export formats (default: en)",
    )
    parser_deriv_surveys.add_argument(
        "--layout",
        default="long",
        choices=["long", "wide"],
        help="Layout for repeated measures: 'long' (one row per session) or 'wide' (one row per participant)",
    )
    parser_deriv_surveys.add_argument(
        "--include-raw",
        action="store_true",
        help="Include original raw data columns in the output",
    )
    parser_deriv_surveys.add_argument(
        "--merge-all",
        action="store_true",
        help="Combine all matched recipes into one output file",
    )
    parser_deriv_surveys.add_argument(
        "--no-recipe-prefix",
        dest="include_recipe_prefix",
        action="store_false",
        default=True,
        help="In combined exports, keep raw item variables bare where possible; score columns remain recipe-prefixed",
    )
    parser_deriv_surveys.add_argument(
        "--boilerplate",
        action="store_true",
        help="Generate a scientific methods boilerplate describing the scoring logic",
    )
    parser_deriv_surveys.add_argument(
        "--anonymized",
        "-a",
        action="store_true",
        help=(
            "Anonymize participant IDs in the output (pseudonymized via "
            "participants.tsv) and append '_anon' to the output subfolder. "
            "Matches the Studio GUI's Recipes page 'Anonymize' option."
        ),
    )
    parser_deriv_surveys.add_argument(
        "--mask-questions",
        action="store_true",
        help="With --anonymized, also replace question/item text columns with '[MASKED]'",
    )
    parser_deriv_surveys.add_argument(
        "--id-length",
        type=int,
        default=8,
        help="With --anonymized, length of the random portion of generated pseudonyms (default: 8)",
    )
    parser_deriv_surveys.add_argument(
        "--random-ids",
        action="store_true",
        help="With --anonymized, use non-deterministic random pseudonyms instead of deterministic ones",
    )
    parser_deriv_surveys.add_argument(
        "--missing-policy",
        default="system-missing",
        choices=["system-missing", "text-na", "text-nan", "numeric-sentinel"],
        help="Missing-value export policy for csv/xlsx/sav outputs",
    )
    parser_deriv_surveys.add_argument(
        "--missing-numeric-value",
        type=float,
        help="Numeric sentinel used when --missing-policy is numeric-sentinel (e.g., -99)",
    )

    parser_deriv_biometrics = recipes_subparsers.add_parser(
        "biometrics",
        aliases=["biometric"],
        help="Compute biometric scores (e.g., best of trials, composite scores) from TSVs",
    )
    parser_deriv_biometrics.add_argument(
        "--prism",
        "--dataset",
        required=True,
        help="Path to the PRISM dataset root (input + output target)",
    )
    parser_deriv_biometrics.add_argument(
        "--repo",
        default=(
            str(project_root.parent)
            if project_root.name == "app"
            else str(project_root)
        ),
        help=(
            "Path to the PRISM tools repository root (used to locate recipe JSONs under "
            "recipe/biometrics/*.json). Default: this script's folder."
        ),
    )
    parser_deriv_biometrics.add_argument(
        "--recipes",
        help="Optional path to a custom folder containing recipe JSONs. Overrides default repository folder.",
    )
    parser_deriv_biometrics.add_argument(
        "--biometric",
        "--task",
        help="Optional comma-separated recipe selection (e.g., 'y_balance'). Default: run all matching recipes.",
    )
    parser_deriv_biometrics.add_argument(
        "--sessions",
        help="Optional comma-separated session list (e.g., 'ses-1,ses-2' or '1,2'). Default: all sessions.",
    )
    parser_deriv_biometrics.add_argument(
        "--format",
        default="flat",
        choices=["prism", "flat", "csv", "xlsx", "sav", "save"],
        help="Output format: 'flat' (default), 'prism', 'csv', 'xlsx', 'sav' (SPSS; 'save' is legacy alias)",
    )
    parser_deriv_biometrics.add_argument(
        "--lang",
        default="en",
        choices=["en", "de"],
        help="Language for metadata labels in export formats (default: en)",
    )
    parser_deriv_biometrics.add_argument(
        "--layout",
        default="long",
        choices=["long", "wide"],
        help="Layout for repeated measures: 'long' (one row per session) or 'wide' (one row per participant)",
    )
    parser_deriv_biometrics.add_argument(
        "--merge-all",
        action="store_true",
        help="Combine all matched recipes into one output file",
    )
    parser_deriv_biometrics.add_argument(
        "--no-recipe-prefix",
        dest="include_recipe_prefix",
        action="store_false",
        default=True,
        help="In combined exports, keep raw item variables bare where possible; score columns remain recipe-prefixed",
    )
    parser_deriv_biometrics.add_argument(
        "--missing-policy",
        default="system-missing",
        choices=["system-missing", "text-na", "text-nan", "numeric-sentinel"],
        help="Missing-value export policy for csv/xlsx/sav outputs",
    )
    parser_deriv_biometrics.add_argument(
        "--missing-numeric-value",
        type=float,
        help="Numeric sentinel used when --missing-policy is numeric-sentinel (e.g., -99)",
    )
    parser_deriv_biometrics.add_argument(
        "--anonymized",
        "-a",
        action="store_true",
        help=(
            "Anonymize participant IDs in the output (pseudonymized via "
            "participants.tsv) and append '_anon' to the output subfolder. "
            "Matches the Studio GUI's Recipes page 'Anonymize' option."
        ),
    )
    parser_deriv_biometrics.add_argument(
        "--mask-questions",
        action="store_true",
        help="With --anonymized, also replace question/item text columns with '[MASKED]'",
    )
    parser_deriv_biometrics.add_argument(
        "--id-length",
        type=int,
        default=8,
        help="With --anonymized, length of the random portion of generated pseudonyms (default: 8)",
    )
    parser_deriv_biometrics.add_argument(
        "--random-ids",
        action="store_true",
        help="With --anonymized, use non-deterministic random pseudonyms instead of deterministic ones",
    )

    parser_recipes_validate_file = recipes_subparsers.add_parser(
        "validate-file",
        help="Validate a recipe JSON file's structure without running a scoring job. "
        "Matches the validation the Studio GUI's Recipe Builder 'Save' action uses.",
    )
    parser_recipes_validate_file.add_argument(
        "recipe", help="Path to the recipe JSON file to validate"
    )
    parser_recipes_validate_file.add_argument(
        "--known-items-from",
        default=None,
        help="Optional path to the matched survey/biometrics template JSON, so item "
        "IDs referenced by the recipe (Scores/Transforms) are checked for typos",
    )
    parser_recipes_validate_file.add_argument(
        "--recipe-id",
        default=None,
        help="Label used in error messages (default: the recipe filename)",
    )
    parser_recipes_validate_file.add_argument(
        "--json", action="store_true", help="Emit machine-readable JSON instead of progress lines"
    )

    parser_biometrics_excel = biometrics_subparsers.add_parser(
        "import-excel", help="Import biometrics templates/library from Excel"
    )
    parser_biometrics_excel.add_argument(
        "--excel", required=True, help="Path to Excel file"
    )
    parser_biometrics_excel.add_argument(
        "--output", default="biometrics_library", help="Output directory"
    )
    parser_biometrics_excel.add_argument(
        "--library-root",
        dest="library_root",
        help="If set, writes to <library-root>/biometrics instead of --output.",
    )
    parser_biometrics_excel.add_argument(
        "--sheet",
        default=0,
        help="Sheet name or index containing the data dictionary (e.g., 'Description').",
    )
    parser_biometrics_excel.add_argument(
        "--equipment",
        default="Legacy/Imported",
        help="Default Technical.Equipment value written to biometrics JSON (required by schema).",
    )
    parser_biometrics_excel.add_argument(
        "--supervisor",
        default="investigator",
        choices=["investigator", "physician", "trainer", "self"],
        help="Default Technical.Supervisor value written to biometrics JSON.",
    )

    parser_dataset = subparsers.add_parser("dataset", help="Dataset helper commands")
    dataset_subparsers = parser_dataset.add_subparsers(dest="action", help="Action")

    parser_ds_bio = dataset_subparsers.add_parser(
        "build-biometrics-smoketest",
        help="Build a small PRISM-valid biometrics dataset from a codebook and dummy CSV",
    )
    parser_ds_bio.add_argument(
        "--codebook",
        default="test_dataset/Biometrics_variables.xlsx",
        help="Path to Biometrics codebook Excel (default: test_dataset/Biometrics_variables.xlsx)",
    )
    parser_ds_bio.add_argument(
        "--sheet",
        default="biometrics_codebook",
        help="Sheet name or index for the codebook (default: biometrics_codebook)",
    )
    parser_ds_bio.add_argument(
        "--data",
        default="test_dataset/Biometrics_dummy_data.csv",
        help="Path to dummy biometrics data CSV with participant_id column",
    )
    parser_ds_bio.add_argument(
        "--output",
        default="test_dataset/_tmp_prism_biometrics_dataset",
        help="Output dataset directory (must be empty or non-existent)",
    )
    parser_ds_bio.add_argument(
        "--library-root",
        default="library",
        help="Library root directory to write templates into (creates <library-root>/biometrics)",
    )
    parser_ds_bio.add_argument(
        "--name",
        default="PRISM Biometrics Smoketest",
        help="Dataset name for dataset_description.json",
    )
    parser_ds_bio.add_argument(
        "--authors",
        nargs="+",
        default=None,
        help="Authors for dataset_description.json (default: empty list)",
    )
    parser_ds_bio.add_argument(
        "--session",
        default="ses-01",
        help="Session folder label to use (default: ses-01)",
    )
    parser_ds_bio.add_argument(
        "--equipment",
        default="Legacy/Imported",
        help="Default Technical.Equipment value for generated biometrics templates",
    )

    parser_ds_hostile = dataset_subparsers.add_parser(
        "build-hostile-demo",
        help="Build an adversarial PRISM dataset exercising edge cases across "
        "sociodemographics, biometrics, environment/MRI, and subject/session ids",
    )
    parser_ds_hostile.add_argument(
        "--output",
        default="examples/hostile_demo",
        help="Output dataset directory (must be empty or non-existent)",
    )
    parser_ds_hostile.add_argument(
        "--seed",
        type=int,
        default=20260620,
        help="Deterministic RNG seed (default: 20260620)",
    )
    parser_ds_hostile.add_argument(
        "--domains",
        default="all",
        help="Comma-separated domains to include: sociodemo,biometrics,"
        "environment_mri,subject_session,all (default: all)",
    )
    parser_ds_hostile.add_argument(
        "--use-datalad",
        action="store_true",
        help="Create the project as a DataLad dataset (default: off)",
    )
    parser_ds_hostile.add_argument(
        "--name",
        default="hostile_demo",
        help="Dataset name for dataset_description.json (letters/numbers/_/- only)",
    )
    parser_ds_hostile.add_argument(
        "--guide",
        action="store_true",
        help="Also write DEMO_GUIDE.md enumerating injected cases and expected outcomes",
    )
    parser_ds_hostile.add_argument(
        "--json", action="store_true", help="Emit machine-readable JSON"
    )

    parser_dataset_cleanup = dataset_subparsers.add_parser(
        "cleanup-project-metadata",
        help="Remove legacy converter-written session metadata from project.json",
    )
    parser_dataset_cleanup.add_argument(
        "--project",
        required=True,
        help="Project root folder or direct path to project.json",
    )
    parser_dataset_cleanup.add_argument(
        "--dry-run",
        action="store_true",
        help="Report what would be removed without writing changes",
    )
    parser_dataset_cleanup.add_argument(
        "--recursive",
        action="store_true",
        help="Treat --project as a folder and clean every project.json beneath it",
    )
    parser_dataset_cleanup.add_argument(
        "--drop-task-definitions",
        action="store_true",
        help="Also remove TaskDefinitions for a stricter project-page-only cleanup",
    )
    parser_dataset_cleanup.add_argument(
        "--json", action="store_true", help="Emit machine-readable JSON"
    )

    parser_dataset_rename_subjects = dataset_subparsers.add_parser(
        "rename-subjects",
        help="Rename subject IDs across a PRISM/BIDS dataset (DataLad-aware, one commit per subject)",
    )
    parser_dataset_rename_subjects.add_argument(
        "--project",
        required=True,
        help="Dataset/project root folder",
    )
    parser_dataset_rename_subjects.add_argument(
        "--mode",
        default="last3",
        choices=["last3", "example_keep"],
        help="Rewrite rule: 'last3' keeps the last 3 characters of each subject ID, "
        "'example_keep' keeps the part of --example-subject matching --keep-fragment "
        "(default: last3)",
    )
    parser_dataset_rename_subjects.add_argument(
        "--example-subject",
        default=None,
        help="Required for --mode example_keep: one current subject ID to define the rule from "
        "(e.g. sub-1291003)",
    )
    parser_dataset_rename_subjects.add_argument(
        "--keep-fragment",
        default=None,
        help="Required for --mode example_keep: the part of --example-subject that should stay "
        "(e.g. 003)",
    )
    parser_dataset_rename_subjects.add_argument(
        "--allow-many-to-one",
        action="store_true",
        help="Allow multiple source subject IDs to map to one target ID (safe merge only)",
    )
    parser_dataset_rename_subjects.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview the mapping and report conflicts without renaming anything",
    )
    parser_dataset_rename_subjects.add_argument(
        "--yes",
        "-y",
        action="store_true",
        help="Apply without an interactive confirmation prompt",
    )
    parser_dataset_rename_subjects.add_argument(
        "--json", action="store_true", help="Emit machine-readable JSON instead of progress lines"
    )

    parser_dataset_rewrite_entities = dataset_subparsers.add_parser(
        "rewrite-entities",
        help=(
            "Rename or delete a non-subject BIDS entity (task/acq/run/ses/etc.) across a "
            "dataset's filenames (DataLad-aware). Matches the Studio GUI's File Management "
            "-> 'Edit BIDS Filename Parts' action. Use 'rename-subjects' for the sub- entity."
        ),
    )
    parser_dataset_rewrite_entities.add_argument(
        "--project",
        required=True,
        help="Dataset/project root folder",
    )
    parser_dataset_rewrite_entities.add_argument(
        "--modality",
        default=None,
        help="Modality to rewrite within (e.g. beh, physio, eeg). Required unless "
        "--list-modalities is used.",
    )
    parser_dataset_rewrite_entities.add_argument(
        "--entity",
        default=None,
        help="BIDS entity/part to rewrite, with or without a leading underscore "
        "(e.g. task, acq, run, ses). The sub entity is not supported here — use "
        "'dataset rename-subjects'.",
    )
    parser_dataset_rewrite_entities.add_argument(
        "--operation",
        default="rename",
        choices=["rename", "delete"],
        help="'rename' replaces the entity's value; 'delete' removes the entity entirely "
        "(default: rename)",
    )
    parser_dataset_rewrite_entities.add_argument(
        "--current-value",
        default=None,
        help="Only rewrite files where the entity currently has this value "
        "(default: match all values)",
    )
    parser_dataset_rewrite_entities.add_argument(
        "--replacement",
        default=None,
        help="New value for the entity. Required when --operation is 'rename'.",
    )
    parser_dataset_rewrite_entities.add_argument(
        "--list-modalities",
        action="store_true",
        help="List available modalities for --project and exit",
    )
    parser_dataset_rewrite_entities.add_argument(
        "--list-entities",
        action="store_true",
        help="List available entities/values for --project and --modality, and exit",
    )
    parser_dataset_rewrite_entities.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview the rewrite and report conflicts without renaming anything",
    )
    parser_dataset_rewrite_entities.add_argument(
        "--yes",
        "-y",
        action="store_true",
        help="Apply without an interactive confirmation prompt",
    )
    parser_dataset_rewrite_entities.add_argument(
        "--json", action="store_true", help="Emit machine-readable JSON instead of progress lines"
    )

    parser_ds_bio.add_argument(
        "--supervisor",
        default="investigator",
        choices=["investigator", "physician", "trainer", "self"],
        help="Default Technical.Supervisor value for generated biometrics templates",
    )

    parser_anonymize = subparsers.add_parser(
        "anonymize",
        help="Anonymize a dataset for sharing (randomize participant IDs, mask copyrighted questions)",
    )
    parser_anonymize.add_argument(
        "--dataset", required=True, help="Path to the PRISM dataset to anonymize"
    )
    parser_anonymize.add_argument(
        "--output",
        help="Path for the anonymized output dataset (default: <dataset>_anonymized)",
    )
    parser_anonymize.add_argument(
        "--mapping",
        help="Path to save/load the ID mapping file (default: <output>/code/anonymization_map.json)",
    )
    parser_anonymize.add_argument(
        "--id-length",
        type=int,
        default=6,
        help="Length of randomized ID codes (default: 6)",
    )
    parser_anonymize.add_argument(
        "--random",
        action="store_true",
        help="Use truly random IDs (default: deterministic based on original IDs)",
    )
    parser_anonymize.add_argument(
        "--force",
        action="store_true",
        help="Force creation of new mapping even if one exists",
    )
    parser_anonymize.add_argument(
        "--mask-questions",
        action="store_true",
        help="Mask copyrighted question text (e.g., 'ADS Question 1' instead of full text)",
    )

    parser_template_export = subparsers.add_parser(
        "template-export",
        help="Export a reusable project template ZIP without subject folders",
    )
    parser_template_export.add_argument(
        "--project",
        required=True,
        help="Project root folder to export as template",
    )
    parser_template_export.add_argument(
        "--output",
        required=True,
        help="Output ZIP path for the template export",
    )
    parser_template_export.add_argument(
        "--json", action="store_true", help="Emit machine-readable JSON"
    )

    parser_survey_validate = survey_subparsers.add_parser(
        "validate", help="Validate survey library"
    )
    parser_survey_validate.add_argument(
        "--library", default="survey_library", help="Path to survey library"
    )

    parser_survey_export_lss = survey_subparsers.add_parser(
        "export-lss",
        help="Export PRISM survey template JSON file(s) to a LimeSurvey .lss file. "
        "Matches the Studio GUI's Survey Generator 'Quick Export' action.",
    )
    parser_survey_export_lss.add_argument(
        "files", nargs="+", help="One or more PRISM survey template JSON files"
    )
    parser_survey_export_lss.add_argument(
        "--output", required=True, help="Path to write the .lss file"
    )
    parser_survey_export_lss.add_argument(
        "--language", default="en", help="Primary export language (default: en)"
    )
    parser_survey_export_lss.add_argument(
        "--languages",
        default=None,
        help="Comma-separated language codes to include (default: --language only)",
    )
    parser_survey_export_lss.add_argument(
        "--base-language",
        default=None,
        help="Base language code (default: --language)",
    )
    parser_survey_export_lss.add_argument(
        "--ls-version",
        default="3",
        choices=["3", "6"],
        help="Target LimeSurvey version (default: 3)",
    )

    parser_survey_export_lss_customized = survey_subparsers.add_parser(
        "export-lss-customized",
        help="Export a Survey Customizer-style customization JSON to a LimeSurvey "
        ".lss file. Matches the Studio GUI's Survey Customizer 'Export' action.",
    )
    parser_survey_export_lss_customized.add_argument(
        "--customization-json",
        required=True,
        help="Path to a customization JSON file (the 'groups' structure produced by "
        "the Survey Customizer's own 'Preview/Copy JSON' action)",
    )
    parser_survey_export_lss_customized.add_argument(
        "--output", required=True, help="Path to write the .lss file"
    )
    parser_survey_export_lss_customized.add_argument(
        "--language", default="en", help="Primary export language (default: en)"
    )
    parser_survey_export_lss_customized.add_argument(
        "--languages",
        default=None,
        help="Comma-separated language codes to include (default: --language only)",
    )
    parser_survey_export_lss_customized.add_argument(
        "--base-language",
        default=None,
        help="Base language code (default: --language)",
    )
    parser_survey_export_lss_customized.add_argument(
        "--ls-version",
        default="6",
        choices=["3", "6"],
        help="Target LimeSurvey version (default: 6)",
    )
    parser_survey_export_lss_customized.add_argument(
        "--survey-title",
        default=None,
        help="Override survey title (default: from customization JSON, if present)",
    )
    parser_survey_export_lss_customized.add_argument(
        "--no-matrix",
        action="store_true",
        help="Disable grouping identical-option questions into matrices",
    )
    parser_survey_export_lss_customized.add_argument(
        "--no-matrix-global",
        action="store_true",
        help="Only matrix-group consecutive questions, not all identical-option ones",
    )

    parser_survey_export_questionnaire_docx = survey_subparsers.add_parser(
        "export-questionnaire-docx",
        help="Render a PRISM survey template as a paper-pencil Word (.docx) "
        "questionnaire. Matches the 'Export Word' action shared by the Studio "
        "GUI's Template Editor and Survey Customizer pages.",
    )
    parser_survey_export_questionnaire_docx.add_argument(
        "--template", required=True, help="Path to a PRISM survey template JSON file"
    )
    parser_survey_export_questionnaire_docx.add_argument(
        "--output", required=True, help="Path to write the .docx file"
    )
    parser_survey_export_questionnaire_docx.add_argument(
        "--language", default="en", help="Export language (default: en)"
    )
    parser_survey_export_questionnaire_docx.add_argument(
        "--variant-id", default=None, help="Optional VariantID to render (default: all)"
    )
    parser_survey_export_questionnaire_docx.add_argument(
        "--options-json",
        default=None,
        help="Rendering options as a JSON file path or inline JSON string (e.g. "
        '\'{"show_item_codes": true, "font_size": 11}\'). See '
        "render_questionnaire_docx's docstring for available keys.",
    )

    parser_survey_limesurvey = survey_subparsers.add_parser(
        "import-limesurvey", help="Import LimeSurvey structure"
    )
    parser_survey_limesurvey.add_argument(
        "--input", required=True, help="Path to .lsa/.lss file"
    )
    parser_survey_limesurvey.add_argument("--output", help="Path to output .json file")
    parser_survey_limesurvey.add_argument(
        "--task", help="Optional task name override (defaults from file name)"
    )

    parser_survey_limesurvey_batch = survey_subparsers.add_parser(
        "import-limesurvey-batch",
        help="Batch import LimeSurvey files with session mapping",
    )
    parser_survey_limesurvey_batch.add_argument(
        "--input-dir", required=True, help="Root directory containing .lsa/.lss files"
    )
    parser_survey_limesurvey_batch.add_argument(
        "--output-dir", required=True, help="Output root for generated PRISM dataset"
    )
    parser_survey_limesurvey_batch.add_argument(
        "--session-map",
        default="t1:ses-1,t2:ses-2,t3:ses-3",
        help="Comma-separated mapping, e.g. t1:ses-1,t2:ses-2,t3:ses-3",
    )
    parser_survey_limesurvey_batch.add_argument(
        "--task",
        help="Optional task name fallback (otherwise derived from file name)",
    )
    parser_survey_limesurvey_batch.add_argument(
        "--library",
        default="survey_library",
        help="Path to survey library (survey-*.json and optional participants.json)",
    )
    parser_survey_limesurvey_batch.add_argument(
        "--subject-id-col",
        dest="subject_id_col",
        help="Preferred column name to use for participant ID (e.g., ID, code, token)",
    )
    parser_survey_limesurvey_batch.add_argument(
        "--id-map",
        dest="id_map",
        help="Path to TSV/CSV file mapping LimeSurvey IDs to BIDS participant IDs (cols: limesurvey_id, participant_id)",
    )

    parser_survey_i18n_migrate = survey_subparsers.add_parser(
        "i18n-migrate",
        help="Create i18n-capable source templates from single-language survey-*.json templates (no translation)",
    )
    parser_survey_i18n_migrate.add_argument(
        "--src",
        default="library/survey",
        help="Source folder containing single-language survey-*.json (default: library/survey)",
    )
    parser_survey_i18n_migrate.add_argument(
        "--dst",
        default="library/survey_i18n",
        help="Destination folder for i18n source templates (default: library/survey_i18n)",
    )
    parser_survey_i18n_migrate.add_argument(
        "--languages",
        default="de,en",
        help="Comma-separated language codes to include (default: de,en)",
    )

    parser_survey_i18n_build = survey_subparsers.add_parser(
        "i18n-build",
        help="Compile i18n survey templates into PRISM schema-compatible survey-*.json for one language",
    )
    parser_survey_i18n_build.add_argument(
        "--src",
        default="library/survey_i18n",
        help="Source folder containing i18n survey-*.json (default: library/survey_i18n)",
    )
    parser_survey_i18n_build.add_argument(
        "--out",
        required=True,
        help="Output folder to write compiled survey-*.json",
    )
    parser_survey_i18n_build.add_argument(
        "--lang",
        required=True,
        help="Target language code to compile (e.g., de, en)",
    )
    parser_survey_i18n_build.add_argument(
        "--fallback",
        default="de",
        help="Fallback language if a translation is missing (default: de)",
    )

    parser_survey_i18n_autotranslate = survey_subparsers.add_parser(
        "i18n-autotranslate",
        help="Auto-translate survey localized text from one language into another using an external translation provider",
    )
    parser_survey_i18n_autotranslate.add_argument(
        "--src",
        default="library/survey",
        help="Source folder containing survey-*.json templates (default: library/survey)",
    )
    parser_survey_i18n_autotranslate.add_argument(
        "--out",
        help="Output folder for translated survey templates; required unless --in-place is used",
    )
    parser_survey_i18n_autotranslate.add_argument(
        "--in-place",
        action="store_true",
        help="Overwrite files in --src instead of writing to --out",
    )
    parser_survey_i18n_autotranslate.add_argument(
        "--provider",
        default="deepl",
        choices=["deepl", "libretranslate"],
        help="Translation provider to use (default: deepl)",
    )
    parser_survey_i18n_autotranslate.add_argument(
        "--api-key",
        help="Provider API key; can also be supplied via provider-specific environment variables",
    )
    parser_survey_i18n_autotranslate.add_argument(
        "--api-url",
        help="Provider API URL override; required for libretranslate if LIBRETRANSLATE_URL is not set",
    )
    parser_survey_i18n_autotranslate.add_argument(
        "--source-lang",
        default="en",
        help="Source language code to translate from (default: en)",
    )
    parser_survey_i18n_autotranslate.add_argument(
        "--target-lang",
        default="de",
        help="Target language code to translate into (default: de)",
    )
    parser_survey_i18n_autotranslate.add_argument(
        "--overwrite-existing",
        action="store_true",
        help="Replace existing target-language values instead of only filling missing translations",
    )
    parser_survey_i18n_autotranslate.add_argument(
        "--batch-size",
        type=int,
        default=50,
        help="Maximum number of unique strings per provider request batch (default: 50)",
    )

    parser_library = subparsers.add_parser(
        "library", help="Manage PRISM library templates"
    )
    subparsers_library = parser_library.add_subparsers(
        dest="action", help="Library actions"
    )

    parser_lib_methods = subparsers_library.add_parser(
        "generate-methods-text",
        help="Generate a scientific methods section boilerplate from library templates",
    )
    parser_lib_methods.add_argument(
        "--survey-lib", default="library/survey", help="Path to survey library"
    )
    parser_lib_methods.add_argument(
        "--biometrics-lib",
        default="library/biometrics",
        help="Path to biometrics library",
    )
    parser_lib_methods.add_argument(
        "--output", default="methods_boilerplate.md", help="Output markdown file"
    )
    parser_lib_methods.add_argument(
        "--lang", default="en", choices=["en", "de"], help="Language for the text"
    )

    parser_lib_sync = subparsers_library.add_parser(
        "sync", help="Synchronize keys across library files"
    )
    parser_lib_sync.add_argument(
        "--modality", choices=["survey", "biometrics"], required=True
    )
    parser_lib_sync.add_argument("--path", help="Path to library directory")

    parser_lib_catalog = subparsers_library.add_parser(
        "catalog", help="Generate a CSV catalog of the survey library"
    )
    parser_lib_catalog.add_argument("--input", required=True, help="Path to library")
    parser_lib_catalog.add_argument("--output", required=True, help="Output CSV path")

    parser_lib_fill = subparsers_library.add_parser(
        "fill", help="Fill missing metadata keys based on schema"
    )
    parser_lib_fill.add_argument(
        "--modality", choices=["survey", "biometrics"], required=True
    )
    parser_lib_fill.add_argument(
        "--path", required=True, help="Path to file or directory"
    )
    parser_lib_fill.add_argument("--version", default="stable", help="Schema version")

    parser_lib_template_save = subparsers_library.add_parser(
        "template-save",
        help="Validate and save a single template into a project's library. "
        "Matches the Studio GUI's Template Editor Save action.",
    )
    parser_lib_template_save.add_argument(
        "--project", required=True, help="Project root folder"
    )
    parser_lib_template_save.add_argument(
        "--modality", choices=["survey", "biometrics"], required=True
    )
    parser_lib_template_save.add_argument(
        "--filename", required=True, help="Target filename (e.g. survey-mytask.json)"
    )
    parser_lib_template_save.add_argument(
        "--template", required=True, help="Path to the template JSON file to save"
    )
    parser_lib_template_save.add_argument(
        "--schema-version", default="stable", help="Schema version to validate against"
    )
    parser_lib_template_save.add_argument(
        "--is-global",
        action="store_true",
        help="Validate as a global/library template (relaxes project-copy-only "
        "required fields like TaskName)",
    )
    parser_lib_template_save.add_argument(
        "--force",
        action="store_true",
        help="Overwrite an existing template with the same filename",
    )

    parser_lib_template_delete = subparsers_library.add_parser(
        "template-delete",
        help="Delete a single project-library template. Matches the Studio GUI's "
        "Template Editor Delete action.",
    )
    parser_lib_template_delete.add_argument(
        "--project", required=True, help="Project root folder"
    )
    parser_lib_template_delete.add_argument(
        "--modality", choices=["survey", "biometrics"], required=True
    )
    parser_lib_template_delete.add_argument(
        "--filename", required=True, help="Filename to delete (e.g. survey-mytask.json)"
    )
    parser_lib_template_delete.add_argument(
        "--yes",
        "-y",
        action="store_true",
        help="Delete without an interactive confirmation prompt",
    )

    parser_file_management = subparsers.add_parser(
        "file-management",
        help="Studio File Management page actions (delete files, etc.)",
    )
    file_management_subparsers = parser_file_management.add_subparsers(
        dest="action", help="Action"
    )

    parser_file_management_delete = file_management_subparsers.add_parser(
        "delete-files",
        help="Preview or delete project files matching BIDS entity filters "
        "(DataLad-aware). Matches the Studio GUI's File Management -> Delete Files action.",
    )
    parser_file_management_delete.add_argument(
        "--project",
        required=True,
        help="Dataset/project root folder",
    )
    parser_file_management_delete.add_argument(
        "--modality",
        default=None,
        help="Only match files under this modality folder (e.g. func, beh)",
    )
    parser_file_management_delete.add_argument(
        "--entity-filter",
        action="append",
        metavar="KEY=VALUE",
        help="Only match files where BIDS entity KEY has VALUE (e.g. task=RS). "
        "Repeatable for multiple filters (all must match).",
    )
    parser_file_management_delete.add_argument(
        "--subjects",
        default=None,
        help="Comma-separated subject IDs to restrict deletion to (e.g. 001,002 or sub-001,sub-002)",
    )
    parser_file_management_delete.add_argument(
        "--apply",
        action="store_true",
        help="Actually delete the matched files (default: preview only)",
    )
    parser_file_management_delete.add_argument(
        "--yes",
        "-y",
        action="store_true",
        help="Apply without an interactive confirmation prompt",
    )
    parser_file_management_delete.add_argument(
        "--json", action="store_true", help="Emit machine-readable JSON instead of progress lines"
    )

    parser_file_management_remove_scans_tsv = file_management_subparsers.add_parser(
        "remove-scans-tsv",
        help="Delete every *_scans.tsv file across a project (superdataset + nested "
        "subdatasets), committing the removal. Matches the Studio GUI's File "
        "Management -> 'Delete all scans.tsv' action.",
    )
    parser_file_management_remove_scans_tsv.add_argument(
        "--project",
        required=True,
        help="Dataset/project root folder",
    )
    parser_file_management_remove_scans_tsv.add_argument(
        "--yes",
        "-y",
        action="store_true",
        help="Apply without an interactive confirmation prompt (required with --json)",
    )
    parser_file_management_remove_scans_tsv.add_argument(
        "--json", action="store_true", help="Emit machine-readable JSON instead of progress lines"
    )

    parser_file_management_rename_physio = file_management_subparsers.add_parser(
        "rename-physio",
        help="Preview or apply a regex-based batch rename of physio/eyetracking files. "
        "Matches the Studio GUI's Converter -> Physio Renamer action.",
    )
    parser_file_management_rename_physio.add_argument(
        "--input",
        required=True,
        help="Folder to scan for files to rename (recursive, skips dotfiles)",
    )
    parser_file_management_rename_physio.add_argument(
        "--output",
        default=None,
        help="Folder to write renamed copies into. Required with --apply.",
    )
    parser_file_management_rename_physio.add_argument(
        "--pattern",
        required=True,
        help="Regex pattern matched against each filename (e.g. '^VP_')",
    )
    parser_file_management_rename_physio.add_argument(
        "--replacement",
        required=True,
        help="Replacement text. May include {subject}/{session} placeholders when "
        "--id-source is 'folder'.",
    )
    parser_file_management_rename_physio.add_argument(
        "--id-source",
        default="filename",
        choices=["filename", "folder"],
        help="'filename' renames using only regex substitution; 'folder' also resolves "
        "{subject}/{session} placeholders from each file's folder path (default: filename)",
    )
    parser_file_management_rename_physio.add_argument(
        "--folder-subject-level",
        type=int,
        default=2,
        help="With --id-source folder: folder depth (from the end) containing the subject "
        "label (default: 2)",
    )
    parser_file_management_rename_physio.add_argument(
        "--folder-session-level",
        type=int,
        default=1,
        help="With --id-source folder: folder depth (from the end) containing the session "
        "label (default: 1)",
    )
    parser_file_management_rename_physio.add_argument(
        "--folder-example-path",
        default=None,
        help="With --id-source folder: an example source path illustrating where the "
        "subject/session values appear (used with --folder-subject-value/"
        "--folder-session-value)",
    )
    parser_file_management_rename_physio.add_argument(
        "--folder-subject-value",
        default=None,
        help="With --folder-example-path: the substring in the example path that is the "
        "subject value",
    )
    parser_file_management_rename_physio.add_argument(
        "--folder-session-value",
        default=None,
        help="With --folder-example-path: the substring in the example path that is the "
        "session value",
    )
    parser_file_management_rename_physio.add_argument(
        "--modality",
        default="physio",
        help="Modality label used when --organize is set (default: physio)",
    )
    parser_file_management_rename_physio.add_argument(
        "--organize",
        action="store_true",
        help="Write output under sub-XXX/ses-XXX/<modality>/ instead of flat, when the "
        "renamed filename parses as BIDS",
    )
    parser_file_management_rename_physio.add_argument(
        "--apply",
        action="store_true",
        help="Actually copy renamed files to --output (default: preview only)",
    )
    parser_file_management_rename_physio.add_argument(
        "--json", action="store_true", help="Emit machine-readable JSON instead of progress lines"
    )

    parser_json_editor = subparsers.add_parser(
        "json-editor",
        help="Studio JSON Editor page actions (save BIDS sidecar JSON files)",
    )
    json_editor_subparsers = parser_json_editor.add_subparsers(
        dest="action", help="Action"
    )

    parser_json_editor_save = json_editor_subparsers.add_parser(
        "save",
        help="Save a BIDS sidecar JSON file into a project, with post-save "
        "validation. Matches the Studio GUI's JSON Editor 'Save to Project' action.",
    )
    parser_json_editor_save.add_argument(
        "--project", required=True, help="Project/BIDS root folder"
    )
    parser_json_editor_save.add_argument(
        "--type",
        required=True,
        help="JSON type: 'dataset_description', 'participants', 'samples', or "
        "'task-<name>' (e.g. task-rest)",
    )
    parser_json_editor_save.add_argument(
        "--file", required=True, help="Path to the JSON file content to save"
    )
    parser_json_editor_save.add_argument(
        "--json", action="store_true", help="Emit machine-readable JSON"
    )

    return parser, {
        "root": parser,
        "survey": parser_survey,
        "participants": parser_participants,
        "environment": parser_environment,
        "biometrics": parser_biometrics,
        "physio": parser_physio,
        "library": parser_library,
        "dataset": parser_dataset,
        "recipes": parser_recipes,
        "file_management": parser_file_management,
        "json_editor": parser_json_editor,
    }
