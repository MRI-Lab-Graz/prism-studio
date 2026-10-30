"""Studio only triggers what the CLI runs: the same input must give the same files in both.

Each test runs the CLI command and Studio's adapter on identical copies of a project and compares
what they write. A difference is a bug in one of the two paths, never a feature.
"""

import json
import shutil
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

from src import config

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "app"))

import src.cli.commands.survey as survey_cli  # noqa: E402
from src.cli.commands.survey import cmd_survey_convert  # noqa: E402

TEMPLATE_I18N = {
    "I18n": {"DefaultLanguage": "de"},
    "Technical": {"StimulusType": "Questionnaire", "FileFormat": "tsv", "Language": "de"},
    "Study": {"TaskName": "pss", "OriginalName": "pss", "LicenseID": "Other", "License": ""},
    "Metadata": {"SchemaVersion": "1.1.1", "CreationDate": "2026-10-01", "Creator": "t"},
    "PSS1": {
        "Description": {"de": "Frage", "en": "Question"},
        "Levels": {"0": {"de": "nie", "en": "never"}, "1": {"de": "oft", "en": "often"}},
    },
}
READY_PROJECT = {
    "Basics": {"Name": "N", "Authors": ["A"], "Keywords": ["k"]},
    "StudyDesign": {"Timepoints": "single"},
}


@pytest.fixture
def world(tmp_path):
    project = tmp_path / "proj"
    library = project / "code" / "library" / "survey"
    library.mkdir(parents=True)
    (library / "survey-pss.json").write_text(json.dumps(TEMPLATE_I18N), encoding="utf-8")
    (project / "project.json").write_text(json.dumps(READY_PROJECT), encoding="utf-8")
    table = tmp_path / "pss.csv"
    table.write_text("ID,PSS1\nsub-001,0\nsub-002,1\n", encoding="utf-8")
    return project, table


def _cli_args(project, table, **overrides):
    args = dict(
        input=str(table), output=str(project), library=None, lang="en", survey=None, id_column="ID",
        session_column=None, run_column=None, sheet=None, unknown="ignore", dry_run=False, force=True,
        name=None, authors=None, alias=None, project=None, template_versions=None, value_offsets=None,
    )
    args.update(overrides)
    return SimpleNamespace(**args)


def _studio_convert(project, table, **overrides):
    """What Studio's Convert button runs (its adapter around the same backend converter)."""
    from src.converters.survey import convert_survey_file_to_prism_dataset
    from src.web.blueprints.conversion_survey_handlers import _run_survey_with_official_fallback

    kwargs = dict(
        input_path=table, output_root=project, survey=None, id_column="ID", session_column=None, session=None,
        unknown="ignore", dry_run=False, force=True, language="en", skip_participants=True,
    )
    kwargs.update(overrides)
    return _run_survey_with_official_fallback(
        convert_survey_file_to_prism_dataset,
        library_dir=str(project / "code" / "library" / "survey"),
        fallback_project_path=str(project),
        **kwargs,
    )


def _written(project: Path) -> dict[str, str]:
    """Every file a conversion leaves in the project: name -> content."""
    wanted = ["task-*_survey.json", "code/library/survey/*.json", "sub-*/ses-*/survey/*.tsv", "participants.*"]
    return {
        str(p.relative_to(project)): p.read_text(encoding="utf-8")
        for pattern in wanted
        for p in sorted(project.glob(pattern))
    }


def test_the_cli_leaves_language_maps_to_the_converter(world, monkeypatch, capsys):
    """One place turns a multilingual template into one language: the converter, for CLI and Studio alike."""
    project, table = world

    def forbidden(*args, **kwargs):
        raise AssertionError("the CLI compiled the language maps itself")

    monkeypatch.setattr(survey_cli, "compile_survey_template", forbidden)
    cmd_survey_convert(_cli_args(project, table))

    assert "Survey conversion complete" in capsys.readouterr().out
    sidecar = json.loads((project / "task-pss_survey.json").read_text(encoding="utf-8"))
    assert sidecar["PSS1"]["Description"] == "Question"  # English was asked for
    assert sidecar["Technical"]["Language"] == "en"  # and the sidecar says so


def test_the_cli_and_studio_write_the_same_files(world, tmp_path, capsys):
    project, table = world
    twin = tmp_path / "twin"
    shutil.copytree(project, twin)

    cmd_survey_convert(_cli_args(project, table))
    _studio_convert(twin, table)

    cli_files, studio_files = _written(project), _written(twin)
    assert cli_files.keys() == studio_files.keys()
    assert cli_files == studio_files


def test_a_dry_run_leaves_the_same_files_in_the_cli_and_in_studio(world, tmp_path, monkeypatch, capsys):
    """Studio's preview puts the templates it used into the project (its template check reads them there);
    the CLI's dry-run does the same, and neither writes data."""
    project, table = world
    mine = tmp_path / "mine"
    (mine / "survey").mkdir(parents=True)
    shutil.move(str(project / "code" / "library" / "survey" / "survey-pss.json"), str(mine / "survey" / "survey-pss.json"))
    monkeypatch.setattr(config, "load_app_settings", lambda app_root=None: config.AppSettings(personal_library_path=str(mine)))
    twin = tmp_path / "twin"
    shutil.copytree(project, twin)

    cmd_survey_convert(_cli_args(project, table, dry_run=True))
    _studio_convert(twin, table, dry_run=True)

    cli_files, studio_files = _written(project), _written(twin)
    assert list(cli_files) == ["code/library/survey/survey-pss.json"]  # the copy, and no data
    assert cli_files == studio_files


def test_saving_a_template_writes_the_same_file_in_the_cli_and_in_studio(tmp_path):
    import importlib
    import os

    from flask import Flask, session
    from template_fixtures import project_template

    from src.cli.commands.library import cmd_library_template_save

    app_dir = Path(__file__).resolve().parents[1] / "app"
    handlers = importlib.import_module("src.web.blueprints.tools_template_editor_blueprint")
    app = Flask(__name__, root_path=str(app_dir))
    app.secret_key = os.urandom(32)
    template = project_template("mood")
    source = tmp_path / "mood.json"
    source.write_text(json.dumps(template), encoding="utf-8")
    cli_project, studio_project = tmp_path / "cli", tmp_path / "studio"
    cli_project.mkdir()
    studio_project.mkdir()

    cmd_library_template_save(SimpleNamespace(
        project=str(cli_project), to="project", modality="survey", filename="survey-mood.json", template=str(source),
        schema_version="stable", is_global=False, force=False,
    ))
    with app.test_request_context(
        "/api/template-editor/save", method="POST",
        json={"modality": "survey", "schema_version": "stable", "filename": "survey-mood.json", "template": template},
    ):
        session["current_project_path"] = str(studio_project)
        _response, status = handlers.api_template_editor_save()

    assert status == 200
    name = "code/library/survey/survey-mood.json"
    # parsed, not bytes: Flask's test client sorts the keys of the JSON it sends
    assert json.loads((cli_project / name).read_text(encoding="utf-8")) == json.loads((studio_project / name).read_text(encoding="utf-8"))


def test_saving_strips_and_warns_the_same_in_the_cli_and_in_studio(tmp_path, capsys):
    import importlib
    import os

    from flask import Flask, session
    from template_fixtures import project_template

    from src.cli.commands.library import cmd_library_template_save

    app_dir = Path(__file__).resolve().parents[1] / "app"
    handlers = importlib.import_module("src.web.blueprints.tools_template_editor_blueprint")
    app = Flask(__name__, root_path=str(app_dir))
    app.secret_key = os.urandom(32)
    template = project_template("mood")
    template["Technical"]["Respondent"] = ""
    item = next(k for k, v in template.items() if isinstance(v, dict) and "Description" in v)
    template[item]["LimeSurvey"] = {"questionType": "L", "inputWidth": "30", "columnName": "q1"}
    source = tmp_path / "mood.json"
    source.write_text(json.dumps(template), encoding="utf-8")
    cli_project, studio_project = tmp_path / "cli", tmp_path / "studio"
    cli_project.mkdir()
    studio_project.mkdir()

    cmd_library_template_save(SimpleNamespace(
        project=str(cli_project), to="project", modality="survey", filename="survey-mood.json", template=str(source),
        schema_version="stable", is_global=False, force=False,
    ))
    printed = capsys.readouterr().out
    with app.test_request_context(
        "/api/template-editor/save", method="POST",
        json={"modality": "survey", "schema_version": "stable", "filename": "survey-mood.json", "template": template},
    ):
        session["current_project_path"] = str(studio_project)
        response, status = handlers.api_template_editor_save()

    assert status == 200
    body = response.get_json()
    name = "code/library/survey/survey-mood.json"
    cli_saved = json.loads((cli_project / name).read_text(encoding="utf-8"))
    assert cli_saved == json.loads((studio_project / name).read_text(encoding="utf-8"))
    assert cli_saved[item]["LimeSurvey"] == {"columnName": "q1"}
    assert body["removed"] == [f"{item}: inputWidth, questionType"]
    assert {"path": "Technical/Respondent", "message": "Technical/Respondent is missing", "severity": "error"} in body["missing"]
    for field in body["missing"]:
        assert f"warning: {field['message']}" in printed
    assert "removed LimeSurvey export settings from 1 items" in printed
