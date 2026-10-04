"""Pins which terminal-command builder each endpoint routes to."""

import sys
from functools import partial
from pathlib import Path

import pytest
from flask import Flask, request

APP_PATH = Path(__file__).resolve().parent.parent / "app"
if str(APP_PATH) not in sys.path:
    sys.path.insert(0, str(APP_PATH))

import src.web.backend_monitoring as bm  # noqa: E402

EXPECTED = {
    "validation.validate_folder": ("validate_folder", {}),
    "conversion.api_biometrics_detect": ("biometrics_detect", {}),
    "conversion.api_biometrics_convert": ("biometrics_convert", {}),
    "conversion.api_physio_convert": ("physio_convert", {}),
    "conversion.api_batch_convert": ("batch_convert", {"start_async": False}),
    "conversion.api_batch_convert_start": ("batch_convert", {"start_async": True}),
    "conversion.api_physio_rename": ("physio_rename", {}),
    "conversion_survey.api_survey_convert": ("survey_convert", {"dry_run": False}),
    "conversion_survey.api_survey_convert_preview": (
        "survey_convert",
        {"dry_run": True},
    ),
    "conversion_survey.api_survey_convert_validate": (
        "survey_convert",
        {"dry_run": True},
    ),
    "conversion_survey.api_survey_prepare_workflow": (
        "survey_convert",
        {"dry_run": True},
    ),
    "conversion_survey.api_survey_detect_version_context": (
        "survey_convert",
        {"dry_run": True},
    ),
    "conversion_survey.api_survey_check_project_templates": (
        "survey_check_templates",
        {},
    ),
    "tools.detect_columns": ("detect_columns", {}),
    "tools.api_recipes_surveys": ("tools_recipes_surveys", {}),
    "tools.api_file_management_wide_to_long_preview": (
        "wide_to_long",
        {"inspect_only": True},
    ),
    "tools.api_file_management_wide_to_long": ("wide_to_long", {"inspect_only": False}),
    "tools.api_file_management_delete": ("file_management_delete", {}),
    "tools.api_file_management_entity_rewrite": ("file_management_entity_rewrite", {}),
    "tools.api_file_management_entity_rewrite_start": (
        "file_management_entity_rewrite",
        {"start_async": True},
    ),
    "tools.api_file_management_subject_rewrite": (
        "file_management_subject_rewrite",
        {},
    ),
    "tools.api_file_management_subject_rewrite_start": (
        "file_management_subject_rewrite",
        {"start_async": True},
    ),
    "conversion.api_environment_preview": ("environment_preview", {}),
    "conversion.api_environment_convert": ("environment_convert", {}),
    "conversion.api_environment_convert_start": ("environment_convert", {}),
    "conversion.api_environment_scan_mri_acquisition": ("environment_scan_mri", {}),
    "conversion.api_environment_rescan_mri": ("environment_scan_mri", {"rescan": True}),
    "conversion_participants.api_participants_detect_id": (
        "participants_detect_id",
        {},
    ),
    "conversion_participants.api_participants_preview": ("participants_preview", {}),
    "conversion_participants.api_participants_convert_start": (
        "participants_convert",
        {},
    ),
    "conversion_participants.api_participants_merge": ("participants_merge", {}),
    "conversion_participants.api_participants_merge_conflicts": (
        "participants_merge",
        {"conflicts_csv": True},
    ),
    "conversion_participants.save_participant_mapping": (
        "save_participant_mapping",
        {},
    ),
    "projects.set_current": ("projects_set_current", {}),
    "projects.save_datalad_snapshot": ("projects_datalad_save", {}),
    "projects.enable_datalad_for_project": ("projects_datalad_enable", {}),
    "projects_export.export_project_structure": ("projects_export_structure", {}),
    "projects_export.export_project_folder": ("projects_folder_export", {}),
    "projects_export.export_defacing_report": (
        "projects_defacing",
        {"run_defacing": False},
    ),
    "projects_export.project_deface_anatomical_scans": (
        "projects_defacing",
        {"run_defacing": True},
    ),
    "projects_export.export_deface_anatomical_scans": (
        "projects_defacing",
        {"run_defacing": True},
    ),
    "projects_export.template_export_project": ("projects_template_export", {}),
}


def _route(endpoint):
    entry = bm._TERMINAL_COMMAND_BUILDERS[endpoint]
    func, kwargs = (
        (entry.func, entry.keywords) if isinstance(entry, partial) else (entry, {})
    )
    return (
        func.__name__.removeprefix("_build_").removesuffix("_terminal_command"),
        kwargs,
    )


@pytest.mark.parametrize("endpoint", sorted(EXPECTED))
def test_endpoint_routes_to_builder(endpoint):
    assert _route(endpoint) == EXPECTED[endpoint]


def test_no_unpinned_endpoints():
    special = {"conversion_survey.api_survey_workflow_command"}
    assert set(bm._TERMINAL_COMMAND_BUILDERS) - special == set(EXPECTED)


def _dispatch(monkeypatch, endpoint, data=None):
    monkeypatch.setattr(bm, "_resolve_request_endpoint", lambda req: endpoint)
    monkeypatch.setattr(
        bm, "_build_survey_convert_terminal_command", lambda req, **kw: kw
    )
    with Flask(__name__).test_request_context("/", method="POST", data=data or {}):
        return bm._build_terminal_command(request)


@pytest.mark.parametrize(
    "form, dry_run",
    [({"workflow_command": "convert"}, False), ({"mode": "Preview"}, True), ({}, True)],
)
def test_survey_workflow_command_dry_run(monkeypatch, form, dry_run):
    got = _dispatch(monkeypatch, "conversion_survey.api_survey_workflow_command", form)
    assert got == {"dry_run": dry_run}


def test_unknown_endpoint_has_no_command(monkeypatch):
    assert _dispatch(monkeypatch, "projects.nope") == ""
