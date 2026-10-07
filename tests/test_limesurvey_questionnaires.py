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


def test_prism_template_survives_limesurvey_round_trip(tmp_path):
    import json

    from src.limesurvey_exporter import generate_lss

    original = {
        "Technical": {"StimulusType": "Questionnaire", "FileFormat": "tsv",
                      "SoftwarePlatform": "LimeSurvey", "Language": "de",
                      "Respondent": "self", "AdministrationMethod": "online"},
        "Study": {"TaskName": "rts", "OriginalName": "Round Trip Scale", "ShortName": "RTS",
                  "Citation": "Doe 2020", "Authors": ["Doe J"], "LicenseID": "CC-BY-4.0",
                  "Category": "other", "Description": "A test scale",
                  "Instructions": "Bitte antworten Sie."},
        "RTS01": {"Description": "erstes Item", "Levels": {"1": "nie", "2": "oft"}},
        "RTS02": {"Description": "zweites Item", "Levels": {"1": "nie", "2": "oft"}},
    }
    source = tmp_path / "survey-rts.json"
    source.write_text(json.dumps(original), encoding="utf-8")
    lss = tmp_path / "rts.lss"
    generate_lss([str(source)], output_path=str(lss), language="de")
    xml = lss.read_bytes()

    [found] = list_limesurvey_questionnaires(xml)
    template = limesurvey_questionnaire_template(xml, found["key"])

    assert [k for k in template if k.startswith("RTS")] == ["RTS01", "RTS02"]
    assert not [k for k in template if k.upper().startswith("PRISMMETA")]
    assert template["RTS01"]["Levels"] == {"1": {"de": "nie"}, "2": {"de": "oft"}}
    study = template["Study"]
    assert study["OriginalName"] == "Round Trip Scale"
    assert study["ShortName"] == "RTS"
    assert study["Citation"] == "Doe 2020"
    assert study["Authors"] == ["Doe J"]
    assert study["Description"] == "A test scale"
    assert study["Instructions"] == {"de": "Bitte antworten Sie."}


def test_description_without_group_description_names_own_group():
    for key, name in (("g30", "ADS"), ("g40", "Händigkeit")):
        desc = limesurvey_questionnaire_template(XML, key)["Study"]["Description"]
        assert name in desc
        assert "catch the submitted ID" not in desc


def _row(**fields):
    return "<row>" + "".join(f"<{k}>{v}</{k}>" for k, v in fields.items()) + "</row>"


def _ls3_bilingual_xml(base="de"):
    rows = lambda *r: "<rows>" + "".join(r) + "</rows>"
    q = lambda lang, text: _row(qid=1, parent_qid=0, gid=1, type="F", title="WHO",
                                question=text, question_order=1, language=lang)
    sq = lambda qid, code, lang, text: _row(qid=qid, parent_qid=1, gid=1, type="T", title=code,
                                            question=text, question_order=qid, scale_id=0,
                                            language=lang)
    ans = lambda lang, text: _row(qid=1, code="1", answer=text, sortorder=1, scale_id=0,
                                  language=lang)
    return (
        "<document><DBVersion>260</DBVersion>"
        f"<surveys>{rows(_row(sid=1, language=base))}</surveys>"
        "<groups>" + rows(_row(gid=1, group_name="Wohl", group_order=1, language="de"),
                          _row(gid=1, group_name="Well", group_order=1, language="en")) + "</groups>"
        "<questions>" + rows(q("de", "Stamm"), q("en", "Stem")) + "</questions>"
        "<subquestions>" + rows(sq(2, "WHO1", "de", "Frage eins"), sq(2, "WHO1", "en", "Question one"),
                                sq(3, "WHO2", "de", "Frage zwei"), sq(3, "WHO2", "en", "Question two"))
        + "</subquestions>"
        "<answers>" + rows(ans("de", "nie"), ans("en", "never")) + "</answers>"
        "</document>"
    ).encode()


def test_ls3_multilanguage_rows_are_not_duplicated():
    xml = _ls3_bilingual_xml()
    [found] = list_limesurvey_questionnaires(xml)
    template = limesurvey_questionnaire_template(xml, found["key"])

    items = [k for k in template if k not in ("Technical", "Study", "Metadata", "I18n")]
    assert items == ["WHO1", "WHO2"]
    assert template["WHO1"]["Description"] == {"de": "Frage eins"}
    assert template["WHO1"]["Levels"] == {"1": {"de": "nie"}}
    assert found["name"] == "Wohl"


def test_colliding_task_names_are_deduped_in_listing_and_templates():
    import json
    import re

    schema = json.loads(Path("app/schemas/stable/survey.schema.json").read_text())
    pattern = schema["properties"]["Study"]["properties"]["TaskName"]["pattern"]
    text = FIXTURE.read_text(encoding="utf-8")
    text = text.replace("<group_name>WHO-5</group_name>", "<group_name>Stress 1</group_name>")
    text = text.replace("<group_name>ADS</group_name>", "<group_name>Stress-1</group_name>")
    xml = text.encode()

    keys = [q["key"] for q in list_limesurvey_questionnaires(xml)]
    names = [limesurvey_questionnaire_template(xml, k)["Study"]["TaskName"] for k in keys]

    assert names[1:3] == ["stress1", "stress1-2"]
    assert len(set(names)) == len(names)
    assert all(re.fullmatch(pattern, n) for n in names)
