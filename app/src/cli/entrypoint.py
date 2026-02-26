"""Runtime entrypoint for prism_tools CLI.

Keeps command wiring separate from the compatibility launcher script.
"""

from __future__ import annotations

import shutil
import sys
from pathlib import Path

from src.cli.commands.anonymize import cmd_anonymize
from src.cli.commands.biometrics import cmd_biometrics_import_excel
from src.cli.commands.convert import cmd_convert_physio
from src.cli.commands.dataset import cmd_dataset_build_biometrics_smoketest
from src.cli.commands.library import (
    cmd_library_catalog,
    cmd_library_fill,
    cmd_library_generate_methods_text,
    cmd_library_sync,
)
from src.cli.commands.recipes import cmd_recipes_biometrics, cmd_recipes_surveys
from src.cli.commands.survey import (
    cmd_survey_convert,
    cmd_survey_i18n_build,
    cmd_survey_i18n_migrate,
    cmd_survey_import_excel,
    cmd_survey_import_limesurvey,
    cmd_survey_import_limesurvey_batch,
    cmd_survey_validate,
)
from src.cli.dispatch import dispatch_prism_tools
from src.cli.parser import build_prism_tools_parsers


APP_ROOT = Path(__file__).resolve().parents[2]


def cmd_demo_create(args) -> None:
    """Create a demo dataset."""
    output_path = Path(args.output)
    demo_source = APP_ROOT / "demo" / "prism_demo"

    if output_path.exists():
        print(f"Error: Output path '{output_path}' already exists.")
        sys.exit(1)

    print(f"Creating demo dataset at {output_path}...")
    try:
        shutil.copytree(demo_source, output_path)
        print("✅ Demo dataset created successfully.")
    except Exception as error:
        print(f"Error creating demo dataset: {error}")
        sys.exit(1)


def main() -> None:
    parser, parsers = build_prism_tools_parsers(APP_ROOT)
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
