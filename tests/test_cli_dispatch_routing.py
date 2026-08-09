"""Routing coverage for src.cli.dispatch: dispatch_prism_tools."""

from __future__ import annotations

from argparse import Namespace
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from src.cli.dispatch import dispatch_prism_tools

# (command, extra kwargs, expected handler key) for every branch that calls a
# handler directly in dispatch_prism_tools.
DISPATCH_CASES = [
    (dict(command="anonymize"), "anonymize"),
    (dict(command="template-export"), "template_export"),
    (dict(command="convert", modality="physio"), "convert_physio"),
    (dict(command="wide-to-long"), "wide_to_long"),
    (dict(command="participants", action="detect-id"), "participants_detect_id"),
    (dict(command="participants", action="preview"), "participants_preview"),
    (dict(command="participants", action="convert"), "participants_convert"),
    (dict(command="participants", action="merge"), "participants_merge"),
    (dict(command="participants", action="save-mapping"), "participants_save_mapping"),
    (
        dict(command="participants", action="neurobagel-schema"),
        "participants_neurobagel_schema",
    ),
    (dict(command="participants", action="save-schema"), "participants_save_schema"),
    (dict(command="environment", action="preview"), "environment_preview"),
    (dict(command="environment", action="convert"), "environment_convert"),
    (dict(command="environment", action="scan-mri"), "environment_scan_mri"),
    (dict(command="demo", action="create"), "demo_create"),
    (dict(command="survey", action="import-excel"), "survey_import_excel"),
    (dict(command="survey", action="convert"), "survey_convert"),
    (dict(command="survey", action="validate"), "survey_validate"),
    (dict(command="survey", action="export-lss"), "survey_export_lss"),
    (
        dict(command="survey", action="export-lss-customized"),
        "survey_export_lss_customized",
    ),
    (
        dict(command="survey", action="export-questionnaire-docx"),
        "survey_export_questionnaire_docx",
    ),
    (dict(command="survey", action="import-limesurvey"), "survey_import_limesurvey"),
    (
        dict(command="survey", action="import-limesurvey-batch"),
        "survey_import_limesurvey_batch",
    ),
    (dict(command="survey", action="i18n-migrate"), "survey_i18n_migrate"),
    (dict(command="survey", action="i18n-build"), "survey_i18n_build"),
    (dict(command="survey", action="i18n-autotranslate"), "survey_i18n_autotranslate"),
    (dict(command="biometrics", action="detect"), "biometrics_detect"),
    (dict(command="biometrics", action="convert"), "biometrics_convert"),
    (dict(command="biometrics", action="import-excel"), "biometrics_import_excel"),
    (dict(command="physio", action="batch-convert"), "physio_batch_convert"),
    (
        dict(command="library", action="generate-methods-text"),
        "library_generate_methods_text",
    ),
    (dict(command="library", action="sync"), "library_sync"),
    (dict(command="library", action="catalog"), "library_catalog"),
    (dict(command="library", action="fill"), "library_fill"),
    (dict(command="library", action="template-save"), "library_template_save"),
    (dict(command="library", action="template-delete"), "library_template_delete"),
    (
        dict(command="dataset", action="build-biometrics-smoketest"),
        "dataset_build_biometrics_smoketest",
    ),
    (
        dict(command="dataset", action="cleanup-project-metadata"),
        "dataset_cleanup_project_metadata",
    ),
    (dict(command="dataset", action="rename-subjects"), "dataset_rename_subjects"),
    (dict(command="dataset", action="rewrite-entities"), "dataset_rewrite_entities"),
    (
        dict(command="dataset", action="build-hostile-demo"),
        "dataset_build_hostile_demo",
    ),
    (
        dict(command="file-management", action="delete-files"),
        "file_management_delete_files",
    ),
    (
        dict(command="file-management", action="remove-scans-tsv"),
        "file_management_remove_scans_tsv",
    ),
    (
        dict(command="file-management", action="rename-physio"),
        "file_management_rename_physio",
    ),
    (dict(command="json-editor", action="save"), "json_editor_save"),
    (dict(command="recipes", kind="surveys"), "recipes_surveys"),
    (dict(command="recipes", kind="survey"), "recipes_surveys"),
    (dict(command="recipes", kind="surves"), "recipes_surveys"),
    (dict(command="recipes", kind="biometrics"), "recipes_biometrics"),
    (dict(command="recipes", kind="biometric"), "recipes_biometrics"),
    (dict(command="recipes", kind="validate-file"), "recipes_validate_file"),
]

ALL_HANDLER_KEYS = sorted({key for _, key in DISPATCH_CASES})

# Fallback branches: (command, extra kwargs, parser key whose print_help() must fire)
FALLBACK_CASES = [
    (dict(command="participants", action="unknown"), "participants"),
    (dict(command="environment", action="unknown"), "environment"),
    (dict(command="survey", action="unknown"), "survey"),
    (dict(command="biometrics", action="unknown"), "biometrics"),
    (dict(command="physio", action="unknown"), "physio"),
    (dict(command="library", action="unknown"), "library"),
    (dict(command="dataset", action="unknown"), "dataset"),
    (dict(command="file-management", action="unknown"), "file_management"),
    (dict(command="json-editor", action="unknown"), "json_editor"),
    (dict(command="recipes", kind="unknown"), "recipes"),
    (dict(command="something-else"), "root"),
]

PARSER_KEYS = [
    "root",
    "participants",
    "environment",
    "survey",
    "biometrics",
    "physio",
    "library",
    "dataset",
    "file_management",
    "json_editor",
    "recipes",
]


def _make_parsers():
    return {key: MagicMock(name=f"parser:{key}") for key in PARSER_KEYS}


def _make_handlers():
    return {key: MagicMock(name=f"handler:{key}") for key in ALL_HANDLER_KEYS}


@pytest.mark.parametrize("extra_args,expected_key", DISPATCH_CASES)
def test_dispatch_prism_tools_routes_to_expected_handler(extra_args, expected_key):
    parsers = _make_parsers()
    handlers = _make_handlers()
    args = Namespace(**extra_args)

    dispatch_prism_tools(args, parsers=parsers, handlers=handlers)

    handlers[expected_key].assert_called_once_with(args)
    for key, handler in handlers.items():
        if key != expected_key:
            handler.assert_not_called()
    for parser in parsers.values():
        parser.print_help.assert_not_called()


@pytest.mark.parametrize("extra_args,expected_parser_key", FALLBACK_CASES)
def test_dispatch_prism_tools_falls_back_to_help(extra_args, expected_parser_key):
    parsers = _make_parsers()
    handlers = _make_handlers()
    args = Namespace(**extra_args)

    dispatch_prism_tools(args, parsers=parsers, handlers=handlers)

    parsers[expected_parser_key].print_help.assert_called_once()
    for handler in handlers.values():
        handler.assert_not_called()


