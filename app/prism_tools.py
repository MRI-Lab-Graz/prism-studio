#!/usr/bin/env python3
import argparse
import sys
import os
import shutil
import json
from pathlib import Path

# Enforce running from the repo-local virtual environment (skip for frozen/packaged apps)
# Since this script moved to app/, venv is one level up
current_dir = os.path.dirname(os.path.abspath(__file__))
venv_path = os.path.join(os.path.dirname(current_dir), ".venv")
if not getattr(sys, "frozen", False) and not sys.prefix.startswith(venv_path):
    print("❌ Error: You are not running inside the prism virtual environment!")
    print("   Please activate the venv first:")
    if os.name == "nt":
        print(f"     {venv_path}\\Scripts\\activate")
    else:
        print(f"     source {venv_path}/bin/activate")
    print("   Then run this script again.")
    sys.exit(1)

# Add project root to path to import helpers
project_root = Path(__file__).resolve().parent
sys.path.append(str(project_root))

from src.utils.io import (
    ensure_dir as _ensure_dir,
    read_json as _read_json,
    write_json as _write_json,
)  # noqa: E402

from src.library_i18n import (
    compile_survey_template,
)  # noqa: E402
from src.cli.commands.dataset import (  # noqa: E402
    cmd_dataset_build_biometrics_smoketest as _cmd_dataset_build_biometrics_smoketest,
)
from src.cli.commands.library import (  # noqa: E402
    cmd_library_generate_methods_text as _cmd_library_generate_methods_text,
    cmd_library_sync as _cmd_library_sync,
    cmd_library_catalog as _cmd_library_catalog,
    cmd_library_fill as _cmd_library_fill,
)
from src.cli.commands.convert import (  # noqa: E402
    sanitize_id as _sanitize_id,
    get_json_hash as _get_json_hash,
    consolidate_sidecars as _consolidate_sidecars,
    cmd_convert_physio as _cmd_convert_physio,
)
from src.cli.commands.anonymize import (  # noqa: E402
    cmd_anonymize as _cmd_anonymize,
)
from src.cli.commands.biometrics import (  # noqa: E402
    cmd_biometrics_import_excel as _cmd_biometrics_import_excel,
)
from src.cli.commands.survey import (  # noqa: E402
    cmd_survey_import_excel as _cmd_survey_import_excel,
    cmd_survey_convert as _cmd_survey_convert,
    cmd_survey_validate as _cmd_survey_validate,
    cmd_survey_import_limesurvey as _cmd_survey_import_limesurvey,
    parse_session_map as _parse_session_map,
    cmd_survey_import_limesurvey_batch as _cmd_survey_import_limesurvey_batch,
    cmd_survey_i18n_migrate as _cmd_survey_i18n_migrate,
    cmd_survey_i18n_build as _cmd_survey_i18n_build,
)
from src.cli.commands.recipes import (  # noqa: E402
    cmd_recipes_surveys as _cmd_recipes_surveys,
    cmd_recipes_biometrics as _cmd_recipes_biometrics,
)
from src.cli.dispatch import dispatch_prism_tools  # noqa: E402


def _normalize_survey_key(raw: str) -> str:
    s = str(raw or "").strip().lower()
    if not s:
        return s
    for prefix in ("survey-", "task-"):
        if s.startswith(prefix):
            s = s[len(prefix) :]
    return s


def _extract_task_from_survey_filename(path: Path) -> str | None:
    stem = path.stem
    # Examples:
    # sub-001_ses-1_task-ads_beh.tsv
    # sub-001_ses-1_survey-ads_beh.tsv
    for token in stem.split("_"):
        if token.startswith("task-"):
            return token.replace("task-", "", 1).strip().lower() or None
        if token.startswith("survey-"):
            return token.replace("survey-", "", 1).strip().lower() or None
    return None


def _infer_sub_ses_from_path(path: Path) -> tuple[str | None, str | None]:
    sub_id = None
    ses_id = None
    for part in path.parts:
        if sub_id is None and part.startswith("sub-"):
            sub_id = part
        if ses_id is None and part.startswith("ses-"):
            ses_id = part
    return sub_id, ses_id


def _parse_numeric_cell(val: str | None) -> float | None:
    if val is None:
        return None
    s = str(val).strip()
    if not s or s.lower() == "n/a":
        _cmd_recipes_surveys(args)
        print(f"Error: {e}")
        sys.exit(1)


def cmd_recipes_biometrics(args):
    _cmd_recipes_biometrics(args)


def sanitize_id(id_str):
    return _sanitize_id(id_str)


def get_json_hash(json_path):
    return _get_json_hash(json_path)


def consolidate_sidecars(output_dir, task, suffix):
    return _consolidate_sidecars(output_dir, task, suffix)


def cmd_convert_physio(args):
    _cmd_convert_physio(args)


def cmd_demo_create(args):
    """
    Creates a demo dataset.
    """
    output_path = Path(args.output)
    demo_source = project_root / "demo" / "prism_demo"

    if output_path.exists():
        print(f"Error: Output path '{output_path}' already exists.")
        sys.exit(1)

    print(f"Creating demo dataset at {output_path}...")
    try:
        shutil.copytree(demo_source, output_path)
        print("✅ Demo dataset created successfully.")
    except Exception as e:
        print(f"Error creating demo dataset: {e}")
        sys.exit(1)


def cmd_survey_import_excel(args):
    _cmd_survey_import_excel(args)


def cmd_survey_convert(args):
    _cmd_survey_convert(args)


def cmd_biometrics_import_excel(args):
    _cmd_biometrics_import_excel(args)


def cmd_dataset_build_biometrics_smoketest(args):
    _cmd_dataset_build_biometrics_smoketest(args)


def cmd_survey_validate(args):
    _cmd_survey_validate(args)


def cmd_survey_import_limesurvey(args):
    _cmd_survey_import_limesurvey(args)


def parse_session_map(map_str):
    return _parse_session_map(map_str)


def cmd_survey_import_limesurvey_batch(args):
    _cmd_survey_import_limesurvey_batch(args)


def cmd_survey_i18n_migrate(args):
    _cmd_survey_i18n_migrate(args)


def cmd_survey_i18n_build(args):
    _cmd_survey_i18n_build(args)


def cmd_library_generate_methods_text(args):
    _cmd_library_generate_methods_text(args)


def cmd_library_sync(args):
    _cmd_library_sync(args)


def cmd_library_catalog(args):
    _cmd_library_catalog(args)


def cmd_library_fill(args):
    _cmd_library_fill(args)


def cmd_anonymize(args):
    _cmd_anonymize(args)


def main():
    parser = argparse.ArgumentParser(
        description="Prism Tools: Utilities for PRISM/BIDS datasets"
    )
    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # Command: convert
    parser_convert = subparsers.add_parser(
        "convert", help="Convert raw data to BIDS format"
    )
    convert_subparsers = parser_convert.add_subparsers(
        dest="modality", help="Modality to convert"
    )

    # Subcommand: convert physio
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

    # Command: demo
    parser_demo = subparsers.add_parser("demo", help="Demo dataset operations")
    demo_subparsers = parser_demo.add_subparsers(dest="action", help="Action")

    # Subcommand: demo create
    parser_demo_create = demo_subparsers.add_parser(
        "create", help="Create a demo dataset"
    )
    parser_demo_create.add_argument(
        "--output",
        default="archive/prism_demo_copy",
        help="Output path for the demo dataset",
    )

    # Command: survey
    parser_survey = subparsers.add_parser("survey", help="Survey library operations")
    survey_subparsers = parser_survey.add_subparsers(dest="action", help="Action")

    # Subcommand: survey import-excel
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

    # Subcommand: survey convert
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
        "--sheet",
        default=0,
        help="Excel sheet name or index (default: 0)",
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
        "--name",
        help="Dataset name written to dataset_description.json (if created)",
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

    # Command: biometrics
    parser_biometrics = subparsers.add_parser(
        "biometrics", help="Biometrics library operations"
    )
    biometrics_subparsers = parser_biometrics.add_subparsers(
        dest="action", help="Action"
    )

    # Command: recipes
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
        choices=["prism", "flat", "csv", "xlsx", "save", "r"],
        help="Output format: 'flat' (default), 'prism', 'csv', 'xlsx', 'sav' (SPSS), 'r' (feather)",
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
        choices=["prism", "flat", "csv", "xlsx", "save", "r"],
        help="Output format: 'flat' (default), 'prism', 'csv', 'xlsx', 'sav' (SPSS), 'r' (feather)",
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

    # Subcommand: biometrics import-excel
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

    # Command: dataset
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
        help="Authors for dataset_description.json (default: 'PRISM smoketest')",
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

    # Command: anonymize
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

    # Subcommand: survey validate
    parser_survey_validate = survey_subparsers.add_parser(
        "validate", help="Validate survey library"
    )
    parser_survey_validate.add_argument(
        "--library", default="survey_library", help="Path to survey library"
    )

    # Subcommand: survey import-limesurvey
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

    # Subcommand: survey i18n-migrate
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

    # Subcommand: survey i18n-build
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

    # --- Library Command ---
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

    # library sync
    parser_lib_sync = subparsers_library.add_parser(
        "sync", help="Synchronize keys across library files"
    )
    parser_lib_sync.add_argument(
        "--modality", choices=["survey", "biometrics"], required=True
    )
    parser_lib_sync.add_argument("--path", help="Path to library directory")

    # library catalog
    parser_lib_catalog = subparsers_library.add_parser(
        "catalog", help="Generate a CSV catalog of the survey library"
    )
    parser_lib_catalog.add_argument("--input", required=True, help="Path to library")
    parser_lib_catalog.add_argument("--output", required=True, help="Output CSV path")

    # library fill
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

    args = parser.parse_args()
    dispatch_prism_tools(
        args,
        parsers={
            "root": parser,
            "survey": parser_survey,
            "biometrics": parser_biometrics,
            "library": parser_library,
            "dataset": parser_dataset,
            "recipes": parser_recipes,
        },
        handlers={
            "anonymize": cmd_anonymize,
            "convert_physio": cmd_convert_physio,
            "demo_create": cmd_demo_create,
            "survey_import_excel": cmd_survey_import_excel,
            "survey_convert": cmd_survey_convert,
            "survey_validate": cmd_survey_validate,
            "survey_import_limesurvey": cmd_survey_import_limesurvey,
            "survey_import_limesurvey_batch": cmd_survey_import_limesurvey_batch,
            "survey_i18n_migrate": cmd_survey_i18n_migrate,
            "survey_i18n_build": cmd_survey_i18n_build,
            "biometrics_import_excel": cmd_biometrics_import_excel,
            "library_generate_methods_text": cmd_library_generate_methods_text,
            "library_sync": cmd_library_sync,
            "library_catalog": cmd_library_catalog,
            "library_fill": cmd_library_fill,
            "dataset_build_biometrics_smoketest": cmd_dataset_build_biometrics_smoketest,
            "recipes_surveys": cmd_recipes_surveys,
            "recipes_biometrics": cmd_recipes_biometrics,
        },
    )


if __name__ == "__main__":
    main()
