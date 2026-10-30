"""How complete a template is: the numbers the template editor's rings show and `library template-score` prints."""

from src.template_completeness import RECOMMENDED, template_completeness
from tests.template_fixtures import library_template, project_template

SOURCE = "code/library/survey/survey-x.json"


def test_a_complete_project_template_has_every_required_field_filled():
    result = template_completeness(project_template(), source=SOURCE)

    assert result["required"]["missing"] == []
    assert result["required"]["filled"] == result["required"]["total"] > 0
    assert result["complete"] is True
    assert result["percent"]["required"] == 100


def test_an_empty_required_field_is_counted_and_named():
    template = project_template()
    template["Technical"]["Respondent"] = ""

    result = template_completeness(template, source=SOURCE)

    assert result["required"]["missing"] == ["Technical/Respondent"]
    assert result["required"]["filled"] == result["required"]["total"] - 1
    assert result["complete"] is False
    assert result["percent"]["required"] < 100


def test_a_library_template_does_not_need_the_project_fields():
    template = project_template()
    for field in ("Respondent", "AdministrationMethod", "SoftwarePlatform"):
        template["Technical"].pop(field)

    as_project = template_completeness(template, source=SOURCE, project=True)
    as_library = template_completeness(template, source=SOURCE, project=False)

    assert as_project["complete"] is False and len(as_project["required"]["missing"]) == 3
    assert as_library["complete"] is True
    assert as_library["required"]["total"] == as_project["required"]["total"] - 3


def test_the_file_name_is_the_task_name():
    template = library_template()
    template["Study"].pop("TaskName")

    result = template_completeness(template, source="official/library/survey/survey-gad7.json", project=False)

    assert "Study/TaskName" not in result["required"]["missing"]


def test_recommended_fields_are_counted_apart_and_never_block():
    template = project_template()
    for path in RECOMMENDED:
        section, field = path.split("/")
        template[section].pop(field, None)

    empty = template_completeness(template, source=SOURCE)

    assert empty["complete"] is True  # recommended fields never decide whether a template can be used
    assert empty["recommended"]["filled"] == 0
    assert empty["recommended"]["missing"] == list(RECOMMENDED)
    assert empty["percent"]["recommended"] == 0

    template["Study"]["DOI"] = "10.1000/182"
    one = template_completeness(template, source=SOURCE)

    assert one["recommended"]["filled"] == 1
    assert "Study/DOI" not in one["recommended"]["missing"]


def test_a_language_the_template_does_not_declare_is_a_problem_and_blocks():
    template = project_template()
    template["I18n"]["Languages"] = ["en"]
    item = next(k for k, v in template.items() if k not in ("Technical", "Study", "Metadata", "I18n") and isinstance(v, dict))
    template[item]["Description"] = {"en": "a", "de": "b"}

    result = template_completeness(template, source=SOURCE)

    assert result["complete"] is False
    assert any("de" in problem for problem in result["problems"])
