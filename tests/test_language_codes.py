"""Language codes in templates are ISO 639-1 (en) with an optional region (en-US)."""

from src.language_codes import is_language_code
from src.template_validator import TemplateValidator

CHECK = TemplateValidator.validate_item_rules_from_data


def test_known_codes_with_and_without_region():
    for code in ("en", "de", "fr", "en-US", "pt-BR", "de-AT"):
        assert is_language_code(code), code


def test_unknown_or_malformed_codes():
    for code in ("xx", "EN", "english", "en-us", "en_US", "", " en", "e", "zz-ZZ"):
        assert not is_language_code(code), code


def _template(**extra):
    return {"Study": {"TaskName": "t"}, "Q1": {"Description": {"en": "q", "de": "f"}, "Levels": {"1": {"en": "a"}}}, **extra}


def test_valid_languages_give_no_finding():
    assert CHECK(_template()) == []


def test_unknown_language_keys_are_errors_naming_where():
    template = _template()
    template["Q1"]["Description"]["xx"] = "?"
    template["Q1"]["Levels"]["1"]["english"] = "?"
    template["Study"]["Description"] = {"zz": "?"}
    template["Technical"] = {"Language": "klingon"}
    template["I18n"] = {"DefaultLanguage": "yy"}
    errors = [f for f in CHECK(template) if f["severity"] == "error"]
    where = sorted(f["path"] for f in errors)
    assert where == ["I18n/DefaultLanguage", "Q1/Description", "Q1/Levels/1", "Study/Description", "Technical/Language"]
    assert all("language" in f["message"].lower() for f in errors)


def test_empty_technical_language_is_not_a_finding():
    assert CHECK(_template(Technical={"Language": ""})) == []


def test_task_name_is_taken_from_the_file_name_when_the_template_has_none():
    from src.prism_template_validation import with_default_task_name

    template = {"Study": {"TaskName": ""}}
    assert with_default_task_name(template, "survey-aai.json", "survey")["Study"]["TaskName"] == "aai"
    assert with_default_task_name({"Study": {"TaskName": "kept"}}, "survey-aai.json", "survey")["Study"]["TaskName"] == "kept"
    assert with_default_task_name({}, "biometrics-grip.json", "biometrics")["Study"]["TaskName"] == "grip"
    assert with_default_task_name({"Study": {}}, "weird name!.json", "survey")["Study"].get("TaskName", "") == ""


def test_a_template_without_a_task_name_is_reported_even_when_it_comes_from_the_library():
    from src.prism_template_validation import missing_task_name_error

    assert missing_task_name_error({"Study": {"TaskName": "aai"}}) is None
    for template in ({}, {"Study": {}}, {"Study": {"TaskName": "  "}}):
        error = missing_task_name_error(template)
        assert error["path"] == "Study/TaskName" and "task name" in error["message"]


def test_the_language_list_comes_from_the_backend(monkeypatch):
    import sys
    from pathlib import Path

    from flask import Flask

    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "app"))
    from src.web.blueprints.tools_template_editor_blueprint import tools_template_editor_bp

    app = Flask(__name__)
    app.register_blueprint(tools_template_editor_bp)
    codes = app.test_client().get("/api/template-editor/language-codes").get_json()["codes"]
    assert "en" in codes and "de" in codes and "xx" not in codes
