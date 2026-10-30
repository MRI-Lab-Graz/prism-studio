"""Studio's pre-conversion template check asks the backend gate; it has no rules of its own."""

import json

from src.web.blueprints.conversion_survey_template_helpers import validate_project_templates_for_tasks
from tests.template_fixtures import project_template


def _project_with(tmp_path, template):
    folder = tmp_path / "code" / "library" / "survey"
    folder.mkdir(parents=True)
    (folder / "survey-x.json").write_text(json.dumps(template), encoding="utf-8")
    return str(tmp_path)


def test_a_complete_project_template_has_no_issues(tmp_path):
    assert validate_project_templates_for_tasks(tasks=["x"], project_path=_project_with(tmp_path, project_template())) == []


def test_a_missing_project_field_is_reported_as_the_gate_words_it(tmp_path):
    template = project_template()
    template["Technical"].pop("Respondent")

    issues = validate_project_templates_for_tasks(tasks=["x"], project_path=_project_with(tmp_path, template))

    assert [i["message"] for i in issues if "Respondent" in i["message"]] == [
        f"Technical/Respondent is missing in {tmp_path / 'code/library/survey/survey-x.json'}"
        " – set who answered the questionnaire (self, parent, clinician, …)"
    ]
    assert all(i["file"].endswith("survey-x.json") for i in issues)


def test_a_language_the_template_does_not_declare_is_reported(tmp_path):
    template = project_template()
    template["I18n"]["Languages"] = ["en"]
    for key, item in template.items():
        if key.startswith("Q") and isinstance(item, dict):
            item["Description"] = {"en": "a", "de": "b"}
            break

    issues = validate_project_templates_for_tasks(tasks=["x"], project_path=_project_with(tmp_path, template))

    assert any("de" in i["message"] for i in issues)
