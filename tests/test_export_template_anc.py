"""Template export and the ANC export: one backend function each for Studio's routes and the commands (THE RULE, CLAUDE.md)."""

import importlib
import json
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "app"))

from flask import Flask  # noqa: E402

from src import export_options as eo  # noqa: E402


@pytest.fixture
def project(tmp_path):
    root = tmp_path / "study"
    root.mkdir()
    (root / "project.json").write_text("{}", encoding="utf-8")
    return root


def _client():
    blueprint = importlib.import_module("src.web.blueprints.projects_export_blueprint")
    app = Flask(__name__, root_path=str(Path(__file__).resolve().parents[1] / "app"))
    app.register_blueprint(blueprint.projects_export_bp)
    return app.test_client()


def _fake_template_zip(project_path, output_zip):
    Path(output_zip).write_bytes(b"PK")
    return {"output_zip": str(output_zip), "files_written": 1, "files_skipped": 0, "subject_dirs_skipped": 0, "root_subject_dirs_skipped": 0}


def test_the_template_export_is_blocked_by_validation_errors_and_names_its_zip_next_to_the_project(project):
    with patch.object(eo, "run_pre_export_validation", lambda *a: "Export blocked: 1 error"):
        with pytest.raises(eo.ExportBlocked):
            eo.run_template_export(project, {})
    with patch("src.project_template_export.export_project_template_zip", _fake_template_zip):
        stats = eo.run_template_export(project, {"validation_mode": "ignore"})
    assert stats["output_zip"] == str(project.parent / "study_template_export.zip")


def test_the_template_command_and_studios_route_give_the_same_result(project, capsys, tmp_path):
    from src.cli.commands.template_export import cmd_template_export

    out = tmp_path / "exports"
    with patch("src.project_template_export.export_project_template_zip", _fake_template_zip):
        cmd_template_export(SimpleNamespace(project=str(project), output=None, output_folder=str(out), validation_mode="ignore", json=True))
        cli = json.loads(capsys.readouterr().out)
        studio = _client().post("/api/projects/template-export", json={"project_path": str(project), "output_folder": str(out), "validation_mode": "ignore"}).get_json()
    assert cli["output_zip"] == studio["stats"]["output_zip"] == str(out / "study_template_export.zip")


def test_the_template_command_validates_first_like_studio(project, capsys):
    from src.cli.commands.template_export import cmd_template_export

    with patch.object(eo, "run_pre_export_validation", lambda *a: "Export blocked: 2 errors"), \
            patch("src.project_template_export.export_project_template_zip", lambda *a: pytest.fail("exported")):
        with pytest.raises(SystemExit):
            cmd_template_export(SimpleNamespace(project=str(project), output=None, output_folder=None, validation_mode="both", json=False))
    assert "Export blocked" in capsys.readouterr().out


class _FakeANC:
    calls = []

    def __init__(self, project_path, output_path):
        self.output_path = Path(output_path)
        _FakeANC.calls.append(("init", Path(project_path).name, self.output_path.name))

    def export(self, **kwargs):
        _FakeANC.calls.append(("export", kwargs))
        return self.output_path


def test_the_anc_command_and_studios_route_run_the_same_export(project, capsys):
    import src.cli.commands.export as export_commands

    args = SimpleNamespace(project=str(project), convert_to_git_lfs=True, include_ci_examples=False, metadata=["DATASET_NAME=My Study", "CONTACT_EMAIL=a@b.c"], json=True)
    with patch("src.converters.anc_export.ANCExporter", _FakeANC):
        export_commands.cmd_export_anc(args)
        cli = json.loads(capsys.readouterr().out)
        studio = _client().post("/api/projects/anc-export", json={
            "project_path": str(project), "convert_to_git_lfs": True, "include_ci_examples": False,
            "metadata": {"DATASET_NAME": "My Study", "CONTACT_EMAIL": "a@b.c"},
        }).get_json()
    first, second = _FakeANC.calls[:2], _FakeANC.calls[2:4]
    assert first == second and first[1][1]["metadata"] == {"DATASET_NAME": "My Study", "CONTACT_EMAIL": "a@b.c"}
    assert first[1][1]["convert_to_git_lfs"] is True and first[1][1]["copy_data"] is True
    assert cli == studio and cli["output_path"].endswith("study_anc_export")
