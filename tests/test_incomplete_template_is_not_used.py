"""A template must be complete to be used: converting or exporting with one that lacks required fields is refused,
and the message names what is missing and where."""

import json
from pathlib import Path

import pandas as pd
import pytest

from src.converters.survey import convert_survey_file_to_prism_dataset
from src.template_save import TemplateIncomplete, TemplateInvalid, require_complete_template
from tests.template_fixtures import project_template

APP = Path(__file__).resolve().parents[1] / "app"
SOURCE = "code/library/survey/survey-x.json"


def _without_creator():
    template = project_template()
    template["Metadata"].pop("Creator")
    return template


def test_a_complete_project_template_passes():
    require_complete_template(project_template(), source=SOURCE, app_root=APP)


def test_the_category_is_only_the_official_librarys_requirement():
    template = project_template()
    template["Study"].pop("Category")
    require_complete_template(template, source=SOURCE, app_root=APP)


def test_a_missing_field_is_named_with_its_source():
    template = project_template()
    template["Technical"]["Respondent"] = ""
    with pytest.raises(TemplateIncomplete) as error:
        require_complete_template(template, source=SOURCE, app_root=APP)
    assert f"Technical/Respondent is missing in {SOURCE}" in str(error.value)
    assert "set who answered the questionnaire" in str(error.value)
    assert isinstance(error.value, TemplateInvalid)


def test_every_missing_field_is_listed():
    template = _without_creator()
    template["Technical"]["Respondent"] = ""
    with pytest.raises(TemplateIncomplete) as error:
        require_complete_template(template, source=SOURCE, app_root=APP)
    lines = str(error.value).splitlines()
    assert any("Metadata/Creator is missing in" in line for line in lines)
    assert any("Technical/Respondent is missing in" in line for line in lines)


def test_conversion_writes_nothing_with_an_incomplete_template(tmp_path):
    result = _convert(tmp_path, respondent="")
    assert isinstance(result, TemplateIncomplete)
    assert f"Technical/Respondent is missing in {tmp_path / 'lib' / 'survey-gad7.json'}" in str(result)
    assert not (tmp_path / "out").exists()


def test_conversion_runs_once_the_template_is_complete(tmp_path):
    assert _convert(tmp_path, respondent="self") is None
    assert (tmp_path / "out").exists()


def _convert(tmp_path, respondent):
    library = tmp_path / "lib"
    library.mkdir()
    template = project_template()
    template["Technical"]["Respondent"] = respondent
    (library / "survey-gad7.json").write_text(json.dumps(template), encoding="utf-8")
    csv = tmp_path / "s.csv"
    pd.DataFrame({"participant_id": ["001"], **{f"GAD70{i}": [1] for i in range(1, 8)}}).to_csv(csv, index=False)
    try:
        convert_survey_file_to_prism_dataset(
            input_path=csv, library_dir=library, output_root=tmp_path / "out",
            survey="gad7", id_column="participant_id", separator=",",
        )
    except TemplateIncomplete as error:
        return error
    return None


def _file(tmp_path, template):
    path = tmp_path / "survey-x.json"
    path.write_text(json.dumps(template), encoding="utf-8")
    return path


def test_the_limesurvey_quick_export_refuses_an_incomplete_template(tmp_path):
    from src.limesurvey_exporter import generate_lss

    with pytest.raises(TemplateIncomplete, match="Metadata/Creator is missing"):
        generate_lss([str(_file(tmp_path, _without_creator()))])


def test_the_customizer_export_refuses_an_incomplete_template(tmp_path):
    from src.limesurvey_exporter import generate_lss_from_customization
    from src.survey_customizer import build_customizer_groups

    path = _file(tmp_path, _without_creator())
    groups = build_customizer_groups([{"path": str(path), "includeQuestions": []}])
    assert groups
    with pytest.raises(TemplateIncomplete, match="Metadata/Creator is missing"):
        generate_lss_from_customization(groups)


def test_the_pavlovia_export_refuses_an_incomplete_template(tmp_path):
    from src.converters.pavlovia import export_to_pavlovia

    with pytest.raises(TemplateIncomplete, match="Metadata/Creator is missing"):
        export_to_pavlovia(_file(tmp_path, _without_creator()), output_dir=tmp_path / "px")


def test_the_word_export_refuses_an_incomplete_template():
    from src.questionnaire_renderer import render_questionnaire_docx

    with pytest.raises(TemplateIncomplete, match="Metadata/Creator is missing"):
        render_questionnaire_docx(_without_creator())
