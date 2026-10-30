"""Defacing for export: report, preflight and the run are backend functions; the commands and Studio's routes return the same."""

import importlib
import json
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "app"))

from flask import Flask  # noqa: E402

from src import export_defacing as ed  # noqa: E402

REPORT = [{"path": "sub-01/anat/a.nii.gz", "status": "not_defaced"}, {"path": "sub-02/anat/a.nii.gz", "status": "defaced"}, {"path": "x", "status": "weird"}]


@pytest.fixture
def project(tmp_path):
    root = tmp_path / "study"
    root.mkdir()
    return root


def test_the_report_counts_each_status_and_files_unknown_ones_under_unknown(project):
    seen = {}
    with patch("src.mri_json_scrubber.build_defacing_report", lambda path, **kw: seen.update(kw) or REPORT):
        result = ed.defacing_report(project, {"selected_variants": ["T1w "], "exclude_subjects": ["sub-09"]})
    assert result["counts"] == {"defaced": 1, "not_defaced": 1, "unknown": 0, "weird": 1}
    assert seen["selected_variants"] == {"t1w"} and seen["excluded_subjects"] == {"sub-09"} and seen["excluded_sessions"] is None


def test_the_run_always_defaces_a_copy_and_never_the_project(project, tmp_path):
    calls = {}

    def prepare(source, output_root, **kw):
        calls["prepare"] = (source, output_root, kw)
        return {"success": True, "target_path": str(tmp_path / "copy")}

    def deface(target, **kw):
        calls["deface"] = (target, kw)
        return {"success": True, "message": "Defaced 1", "counts": {"defaced": 1}, "items": []}

    manager = SimpleNamespace(get_datalad_status=lambda path: {"enabled": False, "executable": ""})
    with patch("src.mri_json_scrubber.prepare_defacing_export_copy", prepare), patch("src.mri_json_scrubber.deface_anatomical_scans", deface), \
            patch("src.mri_json_scrubber.build_defacing_report", lambda *a, **k: REPORT), patch("src.project_manager.ProjectManager", lambda: manager):
        payload, ok = ed.run_defacing(project, {"force": True})

    assert ok and calls["deface"][0] == (tmp_path / "copy").resolve() and calls["deface"][1]["force"] is True
    assert calls["prepare"][0] == project and calls["prepare"][1] == project.parent  # next to the project by default
    assert payload["source_project_path"] == str(project) and "Source project was not modified" in payload["message"]
    assert payload["report_counts"] == {"defaced": 1, "not_defaced": 1, "unknown": 1}


def test_a_failed_copy_is_reported_without_defacing_anything(project):
    with patch("src.mri_json_scrubber.prepare_defacing_export_copy", lambda *a, **k: {"success": False, "error": "disk full"}), \
            patch("src.mri_json_scrubber.deface_anatomical_scans", lambda *a, **k: pytest.fail("defaced")), \
            patch("src.project_manager.ProjectManager", lambda: SimpleNamespace(get_datalad_status=lambda p: {})):
        payload, ok = ed.run_defacing(project, {})
    assert not ok and payload["error"] == "disk full" and payload["target_mode"] == "export_copy"


def test_the_datalad_preserving_copy_is_only_used_when_the_project_is_a_datalad_dataset(project):
    seen = []
    for enabled, mode, expected in ((True, "datalad_preserving", True), (True, "datalad_free", False), (False, "datalad_preserving", False), (True, "", True)):
        with patch("src.mri_json_scrubber.prepare_defacing_export_copy", lambda *a, **k: seen.append(k["preserve_datalad_metadata"]) or {"success": False}), \
                patch("src.project_manager.ProjectManager", lambda: SimpleNamespace(get_datalad_status=lambda p, e=enabled: {"enabled": e})):
            ed.run_defacing(project, {"repository_mode": mode} if mode else {})
    assert seen == [True, False, False, True]


@pytest.mark.parametrize("command, route, backend, patched", [
    ("cmd_export_deface_report", "/api/projects/export/defacing-report", "build_defacing_report", lambda *a, **k: REPORT),
    ("cmd_export_deface_preflight", "/api/projects/export/defacing-preflight", "get_defacing_preflight", lambda *a, **k: {"ready": True, "tools": ["pydeface"]}),
])
def test_the_command_prints_what_studios_route_returns(project, capsys, command, route, backend, patched):
    import src.cli.commands.export as export_commands

    args = SimpleNamespace(project=str(project), selected_variant=None, exclude_subject=None, exclude_session=None, json=True)
    with patch(f"src.mri_json_scrubber.{backend}", patched):
        getattr(export_commands, command)(args)
        cli_payload = json.loads(capsys.readouterr().out)
        blueprint = importlib.import_module("src.web.blueprints.projects_export_blueprint")
        app = Flask(__name__, root_path=str(Path(__file__).resolve().parents[1] / "app"))
        app.register_blueprint(blueprint.projects_export_bp)
        studio_payload = app.test_client().post(route, json={"project_path": str(project)}).get_json()
    assert cli_payload == studio_payload
