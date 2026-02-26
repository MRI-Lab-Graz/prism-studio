#!/usr/bin/env python3
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
from src.cli.parser import build_prism_tools_parsers  # noqa: E402


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
    parser, parsers = build_prism_tools_parsers(project_root)
    args = parser.parse_args()
    dispatch_prism_tools(
        args,
        parsers=parsers,
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
