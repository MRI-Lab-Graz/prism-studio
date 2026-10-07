"""LimeSurvey import: one PRISM template per questionnaire (spec 2026-10-07)."""

from __future__ import annotations

from pathlib import Path

import defusedxml.ElementTree as ET

from src.converters.limesurvey import _parse_answers_into_questions

FIXTURE = Path(__file__).parent / "data" / "limesurvey_four_questionnaires.lss"


def _get_text(element, tag):
    child = element.find(tag)
    return (child.text if child is not None else "") or ""


def test_ls6_answer_labels_come_from_answer_l10ns():
    root = ET.fromstring(
        """<document>
          <answers><rows><row><aid>7</aid><qid>1</qid><code>A1</code></row></rows></answers>
          <answer_l10ns><rows>
            <row><aid>7</aid><answer>selten</answer><language>de</language></row>
            <row><aid>7</aid><answer>rarely</answer><language>en</language></row>
          </rows></answer_l10ns>
        </document>"""
    )
    questions_map = {"1": {"levels": {}}}

    _parse_answers_into_questions(root, questions_map, _get_text)

    assert questions_map["1"]["levels"] == {"A1": {"de": "selten", "en": "rarely"}}


from src.converters.limesurvey import parse_lsg_xml


def test_numeric_row_codes_are_prefixed_with_the_array_code():
    template = parse_lsg_xml(FIXTURE.read_bytes())

    assert "ADS1_1" in template and "ADS1_2" in template
    assert "1" not in template
    assert template["ADS1_1"]["LimeSurvey"]["columnName"] == "ADS1[1]"


def test_identifier_row_codes_are_kept():
    template = parse_lsg_xml(FIXTURE.read_bytes())

    assert "WHO1" in template and "WHO2" in template


import io
import zipfile

import pytest

from src.converters.limesurvey import (
    limesurvey_questionnaire_template,
    list_limesurvey_questionnaires,
    read_lss_xml,
)

XML = FIXTURE.read_bytes()


def test_split_by_group_lists_each_questionnaire(capsys):
    found = list_limesurvey_questionnaires(XML, "group", source_name="survey.lss")

    assert [(q["key"], q["name"], q["item_count"], q["helper"]) for q in found] == [
        ("g10", "catch the submitted ID", 1, True),
        ("g20", "WHO-5", 2, False),
        ("g30", "ADS", 2, False),
        ("g40", "Händigkeit", 1, False),
    ]
    out = capsys.readouterr().out
    assert "[PRISM] LimeSurvey import: survey.lss (DBVersion 636, languages: de)" in out
    assert "[PRISM] Split by group -> 4 questionnaire(s):" in out
    assert "ADS" in out and "(array ADS1)" in out


def test_split_by_question_and_whole_survey():
    by_question = list_limesurvey_questionnaires(XML, "question")
    whole = list_limesurvey_questionnaires(XML, "survey")

    assert [q["name"] for q in by_question] == ["catchsubmittedID", "WHO5", "ADS1", "Hand"]
    assert [(q["key"], q["item_count"]) for q in whole] == [("survey", 6)]


def test_questionnaire_template_has_real_items_and_instructions(capsys):
    template = limesurvey_questionnaire_template(XML, "g30", "group")

    items = [k for k in template if k not in ("Technical", "Study", "Metadata", "I18n")]
    assert items == ["ADS1_1", "ADS1_2"]
    assert template["ADS1_1"]["Description"] == {"de": "war ich bedrückt"}
    assert template["ADS1_1"]["Levels"] == {"0": {"de": "selten"}, "1": {"de": "meistens"}}
    assert template["Study"]["Instructions"] == {"de": "Während der letzten Woche..."}
    assert template["Study"]["OriginalName"] == "ADS"
    assert template["Study"]["TaskName"] == "ads"
    assert template["Technical"]["AdministrationMethod"] == "online"
    assert "[PRISM] Loading g30 'ADS': 2 item(s)" in capsys.readouterr().out


def test_group_description_and_umlaut_task_name():
    who = limesurvey_questionnaire_template(XML, "g20")
    hand = limesurvey_questionnaire_template(XML, "g40")

    assert who["Study"]["Description"] == "Wohlbefinden"
    assert who["Study"]["TaskName"] == "who5"
    assert hand["Study"]["TaskName"] == "handigkeit"
    assert hand["Hand"]["Levels"] == {"L": {"de": "links"}, "R": {"de": "rechts"}}


def test_unknown_key_lists_valid_keys():
    with pytest.raises(ValueError, match="Valid keys: g10, g20, g30, g40"):
        limesurvey_questionnaire_template(XML, "g99")


def test_unknown_split_mode_is_rejected():
    with pytest.raises(ValueError, match="Unknown split mode"):
        list_limesurvey_questionnaires(XML, "pages")


def _zip(**members):
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        for name, content in members.items():
            archive.writestr(name, content)
    return buffer.getvalue()


def test_read_lss_xml_unpacks_lsa_and_rejects_garbage():
    assert read_lss_xml(XML, "x.lss") == XML
    assert read_lss_xml(_zip(**{"survey_1.lss": XML, "survey_1_responses.lsr": b""}), "x.lsa") == XML
    with pytest.raises(ValueError, match="not a valid .lsa archive"):
        read_lss_xml(b"not a zip", "x.lsa")
    with pytest.raises(ValueError, match="No .lss file found"):
        read_lss_xml(_zip(**{"readme.txt": b"hi"}), "x.lsa")
    with pytest.raises(ValueError, match="Unsupported file type"):
        read_lss_xml(XML, "x.txt")
    with pytest.raises(ValueError, match="Invalid LimeSurvey XML"):
        list_limesurvey_questionnaires(b"<not xml")
