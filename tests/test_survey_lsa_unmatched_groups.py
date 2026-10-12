"""LSA questionnaires without a template: reported on the result, never an error."""

import json
import zipfile
from pathlib import Path

from src.converters.survey import convert_survey_lsa_to_prism_dataset
from tests.test_limesurvey_e2e import LSS_XML
from tests.test_survey_cli_lsa import _library

# Second questionnaire ("Other", MOTHER) that the library has no template for.
SECOND_GROUP = {
    "<questions>\n    <rows>": "<questions>\n    <rows>"
    "<row><qid>202</qid><parent_qid>0</parent_qid><sid>999999</sid><gid>11</gid><type>F</type>"
    "<title>MOTHER</title><other>N</other><mandatory>Y</mandatory><question_order>2</question_order>"
    "<scale_id>0</scale_id><same_default>0</same_default><relevance>1</relevance></row>",
    "<groups>\n    <rows>": "<groups>\n    <rows><row><gid>11</gid><sid>999999</sid><group_order>2</group_order></row>",
    "<subquestions>\n    <rows>": "<subquestions>\n    <rows>"
    "<row><qid>304</qid><parent_qid>202</parent_qid><sid>999999</sid><gid>11</gid><type>T</type>"
    "<title>SQ001</title><question_order>1</question_order><scale_id>0</scale_id><same_default>0</same_default><relevance>1</relevance></row>",
    "<question_l10ns>\n    <rows>": "<question_l10ns>\n    <rows>"
    "<row><id>20</id><qid>202</qid><question>Other:</question><help /><language>en</language></row>"
    "<row><id>21</id><qid>304</qid><question>Something else</question><help /><language>en</language></row>",
    "<group_l10ns>\n    <rows>": "<group_l10ns>\n    <rows>"
    "<row><id>2</id><gid>11</gid><group_name>Other</group_name><description /><language>en</language></row>",
}


def _lsa_with_two_questionnaires(tmp_path: Path) -> Path:
    lss = LSS_XML
    for old, new in SECOND_GROUP.items():
        assert old in lss, old
        lss = lss.replace(old, new, 1)
    fields = ["id", "token", "MTESTSQ001", "MTESTSQ002", "MTESTSQ003", "MOTHERSQ001"]
    row = ["1", "a", "4", "3", "5", "x"]
    lsr = (
        '<?xml version="1.0" encoding="UTF-8"?><document><LimeSurveyDocType>Responses</LimeSurveyDocType>'
        "<DBVersion>636</DBVersion><languages><language>en</language></languages><responses><fields>"
        + "".join(f"<fieldname>{f}</fieldname>" for f in fields)
        + "</fields><rows><row>"
        + "".join(f"<{f}><![CDATA[{v}]]></{f}>" for f, v in zip(fields, row))
        + "</row></rows></responses></document>"
    )
    path = tmp_path / "two.lsa"
    with zipfile.ZipFile(path, "w") as z:
        z.writestr("survey_999999.lss", lss)
        z.writestr("survey_999999_responses.lsr", lsr)
    return path


def _convert(tmp_path):
    return convert_survey_lsa_to_prism_dataset(
        input_path=_lsa_with_two_questionnaires(tmp_path),
        library_dir=_library(tmp_path),
        output_root=tmp_path / "out",
        id_column="token",
        dry_run=True,
        force=True,
    )


def test_a_questionnaire_without_a_template_is_listed_and_the_rest_converts(tmp_path):
    result = _convert(tmp_path)

    assert result.tasks_included == ["wellbeing"]
    assert "other" in [g["group_name"] for g in result.unmatched_groups]
    assert any("other" in w and "not converted" in w for w in result.conversion_warnings)
