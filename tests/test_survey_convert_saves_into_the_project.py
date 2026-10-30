"""`survey convert` into a project saves like Studio's Convert with "save to project" (THE RULE, CLAUDE.md)."""

import io
import json
import os
import shutil
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "app"))

from flask import Flask  # noqa: E402

from src import conversion_to_project as ctp  # noqa: E402
from src.cli.commands.survey import cmd_survey_convert  # noqa: E402
from template_fixtures import project_template  # noqa: E402

READY_PROJECT = {
    "Basics": {"Name": "N", "Authors": ["A"], "Keywords": ["k"]},
    "StudyDesign": {"Timepoints": "multiple"},
}


@pytest.fixture
def world(tmp_path):
    template = project_template("gad7")  # a complete project template: Studio refuses to convert with an incomplete one
    item = next(k for k, v in template.items() if isinstance(v, dict) and "Levels" in v)
    project = tmp_path / "proj"
    library = project / "code" / "library" / "survey"
    library.mkdir(parents=True)
    (library / "survey-gad7.json").write_text(json.dumps(template), encoding="utf-8")
    (project / "project.json").write_text(json.dumps(READY_PROJECT), encoding="utf-8")
    (project / "code" / "session_map.json").write_text(json.dumps({"1": "1"}), encoding="utf-8")
    table = tmp_path / "gad7.csv"
    table.write_text(f"ID,{item}\nsub-001,0\nsub-002,1\n", encoding="utf-8")
    return project, table


def _cli_args(project_dir, table, **overrides):
    args = dict(
        input=str(table), output=str(project_dir), library=None, lang="en", survey=None, id_column="ID",
        session_column=None, run_column=None, session="1", sheet=None, unknown="ignore", dry_run=False, force=None,
        name=None, authors=None, alias=None, project=None, template_versions=["gad7=10-likert"], value_offsets=None,
        archive_sourcedata=False,
    )
    args.update(overrides)
    return SimpleNamespace(**args)


def _files(project: Path) -> dict[str, str]:
    skip = {"survey_imports.json"}  # the import ledger holds timestamps
    return {
        p.relative_to(project).as_posix(): p.read_text(encoding="utf-8")
        for p in sorted(project.rglob("*")) if p.is_file() and p.name not in skip and ".git" not in p.parts
    }


def test_the_cli_saves_into_the_project_through_the_datalad_aware_copy(world, monkeypatch, capsys):
    project, table = world
    seen = []
    real = ctp.copy_files_into_project
    monkeypatch.setattr(ctp, "copy_files_into_project", lambda **kw: seen.append(kw["run_message"]) or real(**kw))

    cmd_survey_convert(_cli_args(project, table, archive_sourcedata=True))

    assert seen == ["PRISM: Copy converted survey files into project"]
    assert (project / "sourcedata" / "gad7.csv").exists()
    assert json.loads((project / "project.json").read_text(encoding="utf-8"))["TemplateVersionSelections"]
    assert list(project.glob("sub-*/ses-*/survey/*.tsv"))


def test_a_dry_run_does_not_save_into_the_project(world, monkeypatch):
    project, table = world
    monkeypatch.setattr(ctp, "copy_files_into_project", lambda **kw: pytest.fail("a dry-run saved into the project"))
    cmd_survey_convert(_cli_args(project, table, dry_run=True))
    assert not list(project.glob("sub-*"))


def test_an_output_that_is_not_the_project_is_written_directly(world, tmp_path, monkeypatch):
    project, table = world
    out = tmp_path / "elsewhere"
    monkeypatch.setattr(ctp, "copy_files_into_project", lambda **kw: pytest.fail("saved into a project that is not the output"))
    cmd_survey_convert(_cli_args(project, table, output=str(out), project=str(project)))
    assert list(out.glob("sub-*/ses-*/survey/*.tsv"))


def test_skip_existing_still_sees_what_the_project_already_holds(world, capsys):
    project, table = world
    cmd_survey_convert(_cli_args(project, table))
    capsys.readouterr()
    cmd_survey_convert(_cli_args(project, table, skip_existing=True))
    assert "Already in project" in capsys.readouterr().out


def test_the_cli_and_studios_convert_route_leave_the_same_project(world, tmp_path):
    """Studio's real Convert route with "save to project" and the command, on identical copies."""
    import importlib

    from flask import session as flask_session

    project, table = world
    twin = tmp_path / "twin"
    shutil.copytree(project, twin)
    handlers = importlib.import_module("src.web.blueprints.conversion_survey_handlers")
    app = Flask(__name__, root_path=str(Path(__file__).resolve().parents[1] / "app"))
    app.secret_key = os.urandom(32)
    app.add_url_rule("/api/survey-convert", view_func=handlers.api_survey_convert, methods=["POST"])

    cmd_survey_convert(_cli_args(project, table, archive_sourcedata=True))

    from unittest.mock import patch

    with patch.object(handlers, "_resolve_effective_library_path", return_value=twin / "code" / "library"):
        with app.test_client() as client:
            with client.session_transaction() as sess:
                sess["current_project_path"] = str(twin)
            response = client.post(
                "/api/survey-convert",
                data={
                    "file": (io.BytesIO(table.read_bytes()), "gad7.csv"), "id_column": "ID", "session": "1", "language": "en",
                    "save_to_project": "true", "archive_sourcedata": "true", "template_versions": json.dumps({"gad7": "10-likert"}),
                    "unknown": "ignore",
                },
                content_type="multipart/form-data",
            )

    assert response.status_code == 200, response.get_data(as_text=True)[:300]
    assert _files(project) == _files(twin)
