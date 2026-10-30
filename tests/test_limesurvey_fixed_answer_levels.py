"""Question types whose answer options LimeSurvey defines itself have no <answers> rows
in the .lss; the import must still give them Levels, with LimeSurvey's stored codes.

Codes as LimeSurvey's question renderers store them (application/core/QuestionTypes):
Y: Y/N, G: F/M, C: Y/U/N, E: I/S/D, 5 and A: 1-5, B: 1-10. Labels in LimeSurvey's own
wording (its German translation for "de"). "No answer" is stored empty: a missing value,
not a level.
"""

import sys
from pathlib import Path

import pytest
from tests.template_fixtures import complete, dump_complete

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "app"))


def _row(**fields):
    return "<row>" + "".join(f"<{k}><![CDATA[{v}]]></{k}>" for k, v in fields.items()) + "</row>"


def _lss(language):
    """LS 6 shape: one group with one question of each fixed-option type (A, C, E as arrays)."""
    questions = [(10, "Y", "consent"), (20, "G", "sex"), (30, "5", "mood"),
                 (40, "A", "arrA"), (50, "B", "arrB"), (60, "C", "arrC"), (70, "E", "arrE"),
                 (80, "L", "edu")]
    arrays = {"A", "B", "C", "E"}
    q_rows = "".join(_row(qid=q, parent_qid=0, gid=1, type=t, title=title, question_order=i)
                     for i, (q, t, title) in enumerate(questions))
    sub_rows = "".join(_row(qid=q + 1, parent_qid=q, gid=1, type="T", title=f"{title}1",
                            question_order=1, scale_id=0)
                       for q, t, title in questions if t in arrays)
    l10n = "".join(_row(qid=q, question=f"Text {title}", language=language) for q, _t, title in questions)
    l10n += "".join(_row(qid=q + 1, question=f"Row {title}", language=language)
                    for q, t, title in questions if t in arrays)
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<document>
 <LimeSurveyDocType>Survey</LimeSurveyDocType>
 <DBVersion>636</DBVersion>
 <surveys><rows>{_row(sid=1, language=language)}</rows></surveys>
 <groups><rows>{_row(gid=1, group_order=1)}</rows></groups>
 <group_l10ns><rows>{_row(gid=1, group_name="Fixed", language=language)}</rows></group_l10ns>
 <questions><rows>{q_rows}</rows></questions>
 <subquestions><rows>{sub_rows}</rows></subquestions>
 <question_l10ns><rows>{l10n}</rows></question_l10ns>
 <answers><rows>{_row(aid=1, qid=80, code="1", sortorder=1, scale_id=0)}</rows></answers>
 <answer_l10ns><rows>{_row(aid=1, answer="Matura", language=language)}</rows></answer_l10ns>
</document>""".encode()


def _template(language):
    from src.converters.limesurvey import _build_questionnaires

    _parsed, results = _build_questionnaires(_lss(language), "group")
    return results[0][1]


def _labels(levels):
    return {code: label for code, by_lang in levels.items() for label in by_lang.values()}


def _numbers(n):
    return {str(i): str(i) for i in range(1, n + 1)}


@pytest.mark.parametrize(
    "item, expected",
    [
        ("consent", {"Y": "Ja", "N": "Nein"}),
        ("sex", {"F": "weiblich", "M": "männlich"}),
        ("mood", _numbers(5)),
        ("arrA1", _numbers(5)),
        ("arrB1", _numbers(10)),
        ("arrC1", {"Y": "Ja", "U": "Unsicher", "N": "Nein"}),
        ("arrE1", {"I": "Zunahme", "S": "Unverändert", "D": "Abnahme"}),
    ],
)
def test_fixed_answer_types_get_levels_in_survey_language(item, expected):
    levels = _template("de")[item]["Levels"]
    assert set(lang for by_lang in levels.values() for lang in by_lang) == {"de"}
    assert _labels(levels) == expected
    assert list(levels) == list(expected), "LimeSurvey's order"


def test_english_survey_gets_limesurvey_english_labels():
    template = _template("en")
    assert template["consent"]["Levels"] == {"Y": {"en": "Yes"}, "N": {"en": "No"}}
    assert _labels(template["arrE1"]["Levels"]) == {"I": "Increase", "S": "Same", "D": "Decrease"}


def test_language_without_known_labels_gets_them_in_english():
    """Never an English word filed under another language's key."""
    assert _template("fr")["sex"]["Levels"] == {"F": {"en": "Female"}, "M": {"en": "Male"}}


def test_question_with_own_answers_is_unchanged():
    assert _template("de")["edu"]["Levels"] == {"1": {"de": "Matura"}}


def test_five_point_choice_is_a_known_integer_type():
    item = _template("de")["mood"]
    assert "questionTypeName" not in item.get("LimeSurvey", {})
    assert item["DataType"] == "integer"


def test_lsq_import_gets_fixed_levels():
    from src.converters.limesurvey import parse_lsq_xml

    lsq = f"""<?xml version="1.0" encoding="UTF-8"?>
<document><LimeSurveyDocType>Question</LimeSurveyDocType><DBVersion>366</DBVersion>
 <languages><language>en</language></languages>
 <questions><rows>{_row(qid=10, parent_qid=0, gid=1, type="Y", title="consent", question="Agree?", question_order=1, language="en")}</rows></questions>
</document>""".encode()
    assert parse_lsq_xml(lsq)["consent"]["Levels"] == {"Y": {"en": "Yes"}, "N": {"en": "No"}}


def test_single_sidecar_converter_gets_fixed_levels():
    from src.converters.limesurvey import parse_lss_xml

    sidecar = parse_lss_xml(_lss("de"), check_collisions=False)
    assert sidecar["consent"]["Levels"] == {"Y": {"de": "Ja"}, "N": {"de": "Nein"}}


# ── Export of an imported template back to LimeSurvey ───────────────────


def _export(tmp_path, exporter):
    import json

    import defusedxml.ElementTree as DET
    from src.limesurvey_exporter import generate_lss, generate_lss_from_customization

    template = _template("de")
    path = tmp_path / "survey-fixed.json"
    path.write_text(dump_complete(template), encoding="utf-8")
    if exporter == "quick":
        xml = generate_lss([str(path)], language="de", matrix_mode=False)
    else:
        codes = [k for k, v in template.items() if isinstance(v, dict) and "Description" in v]
        groups = [{"name": "Fixed", "order": 0, "questions": [
            {"sourceFile": str(path), "questionCode": c, "displayOrder": i, "enabled": True,
             "levels": template[c].get("Levels", {}), "originalData": template[c]}
            for i, c in enumerate(codes)]}]
        xml = generate_lss_from_customization(groups, language="de", matrix_mode=False)
    root = DET.fromstring(xml)
    questions = {q.findtext("qid"): q for q in root.findall("questions/rows/row")}
    by_title = {q.findtext("title"): q for q in questions.values()}
    answers = {}
    for a in root.findall("answers/rows/row"):
        answers.setdefault(questions[a.findtext("qid")].findtext("title"), []).append(a.findtext("code"))
    return by_title, answers


@pytest.mark.parametrize("exporter", ["quick", "customizer"])
def test_fixed_option_types_export_as_lists_with_limesurveys_codes(tmp_path, exporter):
    """The template keeps no question type: yes/no, gender and 5-point choice come back as lists
    whose options are the imported Levels, with LimeSurvey's own codes, so answers keep their values."""
    by_title, answers = _export(tmp_path, exporter)
    assert by_title["consent"].findtext("type") == "L" and answers["consent"] == ["Y", "N"]
    assert by_title["sex"].findtext("type") == "L" and answers["sex"] == ["F", "M"]
    assert by_title["mood"].findtext("type") == "L" and answers["mood"] == ["1", "2", "3", "4", "5"]


def test_a_fixed_option_type_chosen_for_one_export_writes_no_answer_rows(tmp_path):
    """LimeSurvey defines the options of Y/G/5 itself: an <answers> row would not be used."""
    import json

    import defusedxml.ElementTree as DET
    from src.limesurvey_exporter import generate_lss_from_customization
    from src.survey_customizer import build_customizer_groups

    path = tmp_path / "survey-fixed.json"
    path.write_text(dump_complete(_template("de")), encoding="utf-8")
    groups = build_customizer_groups([{"path": str(path)}], "de")
    chosen = {"consent": "Y", "sex": "G", "mood": "5"}
    for question in groups[0]["questions"]:
        if question["questionCode"] in chosen:
            question["toolOverrides"] = {"questionType": chosen[question["questionCode"]]}
    root = DET.fromstring(generate_lss_from_customization(groups, language="de", matrix_mode=False))
    questions = {q.findtext("qid"): q for q in root.findall("questions/rows/row")}
    types = {q.findtext("title"): q.findtext("type") for q in questions.values()}
    answered = {questions[a.findtext("qid")].findtext("title") for a in root.findall("answers/rows/row")}
    assert {code: types[code] for code in chosen} == chosen
    assert not answered & set(chosen)


@pytest.mark.parametrize("exporter", ["quick", "customizer"])
def test_array_row_exported_alone_is_a_list_with_its_options(tmp_path, exporter):
    """A lone row of an array type would be an array question without rows in LimeSurvey."""
    by_title, answers = _export(tmp_path, exporter)
    assert by_title["arrC1"].findtext("type") == "L"
    assert answers["arrC1"] == ["Y", "U", "N"]
    assert answers["arrB1"] == [str(i) for i in range(1, 11)]
