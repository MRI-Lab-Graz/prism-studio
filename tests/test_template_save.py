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
        template["Technical"].update(SoftwarePlatform="Other", SoftwareVersion="1", AdministrationMethod="paper", Respondent="self")
    return template


def test_a_valid_template_is_saved_into_the_project_library(tmp_path):
    saved = save_template("survey", "survey-gad7", _gad7(project_copy=True), target="project", project_root=tmp_path, app_root=APP)
    path = saved.path
    assert saved.missing == [] and saved.removed == []
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
    path = save_template("survey", "survey-gad7.json", _gad7(), target="personal", project_root=None, app_root=APP).path
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


def _technical_required(schema):
    return schema["properties"]["Technical"]["required"]


def test_library_template_may_leave_respondent_out():
    from src.prism_template_validation import relax_schema_for_library_template
    from src.schema_manager import load_schema

    assert "Respondent" not in _technical_required(relax_schema_for_library_template(load_schema("survey")))


def test_project_template_needs_respondent():
    from src.schema_manager import load_schema

    assert "Respondent" in _technical_required(load_schema("survey"))


def _project_save(tmp_path, template, **kwargs):
    return save_template("survey", "survey-gad7.json", template, target="project", project_root=tmp_path, app_root=APP, **kwargs)


def test_saving_with_an_empty_respondent_writes_and_warns(tmp_path):
    template = _gad7(project_copy=True)
    template["Technical"]["Respondent"] = ""
    saved = _project_save(tmp_path, template)
    assert saved.path.exists()
    assert {"path": "Technical/Respondent", "message": "Technical/Respondent is missing"} in saved.missing


def test_saving_strips_export_settings(tmp_path):
    template = _gad7(project_copy=True)
    item = next(k for k, v in template.items() if isinstance(v, dict) and "Description" in v)
    template[item]["LimeSurvey"] = {"questionType": "L", "columnName": "q1"}
    saved = _project_save(tmp_path, template)
    written = json.loads(saved.path.read_text(encoding="utf-8"))
    assert written[item]["LimeSurvey"] == {"columnName": "q1"}
    assert saved.removed == [f"{item}: questionType"]


def test_other_schema_errors_still_refuse(tmp_path):
    template = _gad7(project_copy=True)
    template["Technical"]["Respondent"] = "robot"
    with pytest.raises(TemplateInvalid):
        _project_save(tmp_path, template)
    assert not (tmp_path / "code").exists()


def test_a_template_without_a_whole_section_still_refuses(tmp_path):
    template = _gad7(project_copy=True)
    del template["Technical"]
    with pytest.raises(TemplateInvalid):
        _project_save(tmp_path, template)


def _survey_schema():
    from src.schema_manager import load_schema

    return load_schema("survey")


def test_missing_required_fields_without_sections():
    from src.prism_template_validation import missing_required_fields

    paths = {m["path"] for m in missing_required_fields({}, _survey_schema())}
    assert {"Study/TaskName", "Technical/Respondent", "Metadata/Creator", "I18n/Languages"} <= paths
    assert missing_required_fields({"Technical": "x", "Study": None, "I18n": []}, _survey_schema())  # no crash


def test_missing_english():
    from src.prism_template_validation import missing_required_fields

    template = _gad7(project_copy=True)
    template["Study"]["OriginalName"] = {"en": "", "de": "x"}
    assert {"path": "Study/OriginalName", "message": "Study/OriginalName is missing"} in missing_required_fields(template, _survey_schema())


def test_a_complete_template_misses_nothing():
    from src.prism_template_validation import missing_required_fields

    assert missing_required_fields(_gad7(project_copy=True), _survey_schema()) == []


def test_language_consistency_findings_are_warnings_on_save(tmp_path):
    template = _gad7(project_copy=True)
    template["I18n"]["Languages"] = ["en", "de", "fr"]
    saved = _project_save(tmp_path, template)
    assert any("'fr'" in m["message"] for m in saved.missing)
