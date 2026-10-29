"""`survey convert` finds templates in the personal library and leaves a copy in the project."""

import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "app"))

from src import config  # noqa: E402
from src.cli.commands.survey import cmd_survey_convert  # noqa: E402

TEMPLATE = {
    "Technical": {"StimulusType": "Questionnaire", "FileFormat": "tsv", "Language": "en"},
    "Study": {"TaskName": "pss", "OriginalName": "pss", "LicenseID": "Other", "License": ""},
    "Metadata": {"SchemaVersion": "1.1.1", "CreationDate": "2026-10-01", "Creator": "me"},
    "PSS1": {"Description": "Q1", "Levels": {"0": "never", "1": "often"}},
}
READY_PROJECT = {
    "Basics": {"Name": "N", "Authors": ["A"], "Keywords": ["k"]},
    "StudyDesign": {"Timepoints": "single"},
}


@pytest.fixture
def setup(tmp_path, monkeypatch):
    mine = tmp_path / "mine"
    (mine / "library" / "survey").mkdir(parents=True)
    (mine / "library" / "survey" / "survey-pss.json").write_text(json.dumps(TEMPLATE), encoding="utf-8")
    monkeypatch.setattr(config, "load_app_settings", lambda app_root=None: config.AppSettings(personal_library_path=str(mine)))

    project = tmp_path / "proj"
    project.mkdir()
    (project / "project.json").write_text(json.dumps(READY_PROJECT), encoding="utf-8")
    table = tmp_path / "pss.csv"
    table.write_text("ID,PSS1\nsub-001,0\nsub-002,1\n", encoding="utf-8")
    return project, table


def _args(project, table, **overrides):
    args = dict(
        input=str(table), output=str(project), library=None, lang="en", survey=None, id_column="ID",
        session_column=None, run_column=None, sheet=None, unknown="ignore", dry_run=False, force=True,
        name=None, authors=None, alias=None, project=None, template_versions=None, value_offsets=None,
    )
    args.update(overrides)
    return SimpleNamespace(**args)


def test_conversion_uses_the_personal_template_and_leaves_a_copy_in_the_project(setup, capsys):
    project, table = setup
    cmd_survey_convert(_args(project, table))

    out = capsys.readouterr().out
    assert "Survey conversion complete" in out
    assert "personal " in out  # the report names the library it used
    copied = project / "code" / "library" / "survey" / "survey-pss.json"
    assert json.loads(copied.read_text(encoding="utf-8"))["PSS1"]["Levels"] == {"0": "never", "1": "often"}


def test_a_dry_run_leaves_the_project_untouched(setup, capsys):
    project, table = setup
    cmd_survey_convert(_args(project, table, dry_run=True))

    assert "No files were created" in capsys.readouterr().out
    assert not (project / "code").exists()


GAD7 = Path(__file__).resolve().parents[1] / "official" / "library" / "survey" / "survey-gad7.json"


def _save_args(tmp_path, **overrides):
    args = dict(
        project=None, to="personal", modality="survey", filename="survey-gad7.json", template=str(GAD7),
        schema_version="stable", is_global=False, force=False,
    )
    args.update(overrides)
    return SimpleNamespace(**args)


@pytest.mark.skipif(not GAD7.exists(), reason="official library not available")
def test_template_save_to_the_personal_library(tmp_path, monkeypatch, capsys):
    from src.cli.commands.library import cmd_library_template_save

    mine = tmp_path / "mine"
    mine.mkdir()
    monkeypatch.setattr(config, "load_app_settings", lambda app_root=None: config.AppSettings(personal_library_path=str(mine)))

    cmd_library_template_save(_save_args(tmp_path))

    assert "Saved to" in capsys.readouterr().out
    assert (mine / "survey" / "survey-gad7.json").exists()


@pytest.mark.skipif(not GAD7.exists(), reason="official library not available")
def test_template_save_to_personal_without_a_personal_library_says_how_to_set_it(tmp_path, monkeypatch, capsys):
    from src.cli.commands.library import cmd_library_template_save

    monkeypatch.setattr(config, "load_app_settings", lambda app_root=None: config.AppSettings())

    with pytest.raises(SystemExit):
        cmd_library_template_save(_save_args(tmp_path))

    assert "Personal Template Library" in capsys.readouterr().out


def test_a_template_copied_from_the_personal_library_is_not_reported_as_changed(setup, capsys):
    """The copy is prepared (Technical/Study defaults) but its items equal the sidecar's: no PRISM710."""
    from src.survey_template_drift import check_survey_template_drift

    project, table = setup
    cmd_survey_convert(_args(project, table))

    assert (project / "task-pss_survey.json").exists()
    assert check_survey_template_drift(str(project), project_path=str(project)) == []
