"""Parser construction helpers for prism_tools CLI."""

from __future__ import annotations

import argparse
from pathlib import Path


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

    parser_physio = convert_subparsers.add_parser(
        "physio", help="Convert physiological data (Varioport)"
    )
    parser_physio.add_argument(
        "--input", required=True, help="Path to sourcedata directory"
    )
    parser_physio.add_argument(
        "--output", required=True, help="Path to output rawdata directory"
    )
    parser_physio.add_argument(
        "--task", default="rest", help="Task name (default: rest)"
    )
    parser_physio.add_argument(
        "--suffix", default="physio", help="Output suffix (default: physio)"
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
        "--input", required=True, help="Path to input file (.xlsx/.csv/.tsv/.lsa)"
    )
    parser_participants_preview.add_argument(
        "--project",
        help="Project root or project.json path used to resolve participants_mapping.json",
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
        "--json", action="store_true", help="Emit machine-readable JSON"
    )

    parser_participants_convert = participants_subparsers.add_parser(
        "convert", help="Convert participant table to participants.tsv"
    )
    parser_participants_convert.add_argument(
        "--input", required=True, help="Path to input file (.xlsx/.csv/.tsv/.lsa)"
    )
    parser_participants_convert.add_argument(
        "--project",
        required=True,
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
        "--json", action="store_true", help="Emit machine-readable JSON"
    )

    parser_environment = subparsers.add_parser(
        "environment",
        help="Environment conversion utilities (preview)",
    )
    environment_subparsers = parser_environment.add_subparsers(
        dest="action", help="Action"
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
    parser_environment_convert.add_argument(
        "--session-col", help="Session column name"
    )
    parser_environment_convert.add_argument(
        "--session-override", help="Manual session fallback"
    )
    parser_environment_convert.add_argument(
        "--location-col", help="Location label column name"
    )
    parser_environment_convert.add_argument(
        "--lat-col", help="Latitude column name"
    )
    parser_environment_convert.add_argument(
        "--lon-col", help="Longitude column name"
    )
    parser_environment_convert.add_argument(
        "--location-label", help="Manual location label fallback"
    )
    parser_environment_convert.add_argument(
        "--lat", help="Global fallback latitude"
    )
    parser_environment_convert.add_argument(
        "--lon", help="Global fallback longitude"
    )
    parser_environment_convert.add_argument(
        "--pilot-random-subject",
        action="store_true",
        help="Run pilot conversion for one random subject and estimate full runtime",
    )
    parser_environment_convert.add_argument(
        "--json", action="store_true", help="Emit machine-readable JSON"
    )
    parser_environment_convert.add_argument(
        "--log-file", help=argparse.SUPPRESS
    )
    parser_environment_convert.add_argument(
        "--result-file", help=argparse.SUPPRESS
    )
    parser_environment_convert.add_argument(
        "--cancel-file", help=argparse.SUPPRESS
    )

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

    parser_biometrics = subparsers.add_parser(
        "biometrics", help="Biometrics library operations"
    )
    biometrics_subparsers = parser_biometrics.add_subparsers(
        dest="action", help="Action"
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
        choices=["prism", "flat", "csv", "xlsx", "save"],
        help="Output format: 'flat' (default), 'prism', 'csv', 'xlsx', 'sav' (SPSS)",
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
        "--boilerplate",
        action="store_true",
        help="Generate a scientific methods boilerplate describing the scoring logic",
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
        choices=["prism", "flat", "csv", "xlsx", "save"],
        help="Output format: 'flat' (default), 'prism', 'csv', 'xlsx', 'sav' (SPSS)",
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

    parser_survey_validate = survey_subparsers.add_parser(
        "validate", help="Validate survey library"
    )
    parser_survey_validate.add_argument(
        "--library", default="survey_library", help="Path to survey library"
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

    return parser, {
        "root": parser,
        "survey": parser_survey,
        "participants": parser_participants,
        "environment": parser_environment,
        "biometrics": parser_biometrics,
        "library": parser_library,
        "dataset": parser_dataset,
        "recipes": parser_recipes,
    }
