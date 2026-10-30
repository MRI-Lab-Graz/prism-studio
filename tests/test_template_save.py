"""One function saves a template, for `library template-save` and for the template editor's Save."""

import json
from pathlib import Path

import pytest

from src import config
from src.template_save import TemplateExists, TemplateInvalid, save_template

APP = Path(__file__).resolve().parents[1] / "app"
GAD7 = Path(__file__).resolve().parents[1] / "official" / "library" / "survey" / "survey-gad7.json"
pytestmark = pytest.mark.skipif(not GAD7.exists(), reason="official library not available")


def _gad7(*, project_copy=False):
    """The official GAD-7 with a task name (a library template needs one); a project copy also names how it was run."""
    template = json.loads(GAD7.read_text(encoding="utf-8"))
    template["Study"]["TaskName"] = "gad7"
    if project_copy:
        template["Technical"].update(SoftwarePlatform="Other", SoftwareVersion="1", AdministrationMethod="paper")
    return template


def test_a_valid_template_is_saved_into_the_project_library(tmp_path):
    path = save_template("survey", "survey-gad7", _gad7(project_copy=True), target="project", project_root=tmp_path, app_root=APP)
    assert path == tmp_path / "code" / "library" / "survey" / "survey-gad7.json"
    assert json.loads(path.read_text(encoding="utf-8"))["Study"]["TaskName"]


def test_an_invalid_template_is_not_saved_and_says_why(tmp_path):
    with pytest.raises(TemplateInvalid) as error:
        save_template("survey", "survey-x.json", {"Study": {}}, target="project", project_root=tmp_path, app_root=APP)
    assert error.value.errors
    assert not (tmp_path / "code").exists()


def test_an_existing_template_is_only_replaced_when_asked(tmp_path):
    template = _gad7(project_copy=True)
    save_template("survey", "survey-gad7.json", template, target="project", project_root=tmp_path, app_root=APP)
    with pytest.raises(TemplateExists):
        save_template("survey", "survey-gad7.json", template, target="project", project_root=tmp_path, app_root=APP)
    save_template("survey", "survey-gad7.json", template, target="project", project_root=tmp_path, app_root=APP, allow_overwrite=True)


def test_a_library_template_still_needs_a_task_name(tmp_path):
    """The library relaxation drops the project-only fields, not the task name: for the global flag and for personal."""
    nameless = _gad7()
    nameless["Study"].pop("TaskName")
    with pytest.raises(TemplateInvalid, match="task name"):
        save_template("survey", "survey-x.json", nameless, target="project", project_root=tmp_path, app_root=APP, relaxed=True)


def test_the_personal_target_uses_the_personal_library_and_checks_the_task_name(tmp_path, monkeypatch):
    mine = tmp_path / "mine"
    mine.mkdir()
    monkeypatch.setattr(config, "load_app_settings", lambda app_root=None: config.AppSettings(personal_library_path=str(mine)))
    path = save_template("survey", "survey-gad7.json", _gad7(), target="personal", project_root=None, app_root=APP)
    assert path == mine / "survey" / "survey-gad7.json"

    nameless = _gad7()
    nameless["Study"].pop("TaskName")
    with pytest.raises(TemplateInvalid, match="task name"):
        save_template("survey", "survey-y.json", nameless, target="personal", project_root=None, app_root=APP)


def test_personal_without_a_personal_library_and_project_without_a_project_say_what_is_missing(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "load_app_settings", lambda app_root=None: config.AppSettings())
    with pytest.raises(RuntimeError, match="Personal Template Library"):
        save_template("survey", "survey-gad7.json", _gad7(), target="personal", project_root=None, app_root=APP)
    with pytest.raises(RuntimeError, match="project"):
        save_template("survey", "survey-gad7.json", _gad7(project_copy=True), target="project", project_root=None, app_root=APP)


@pytest.mark.parametrize("bad", ["", "a/b.json", "a\\b.json"])
def test_the_filename_must_be_a_bare_name(tmp_path, bad):
    with pytest.raises(ValueError, match="filename"):
        save_template("survey", bad, _gad7(), target="project", project_root=tmp_path, app_root=APP)
