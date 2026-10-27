"""LimeSurvey response columns must land on the right template items.

Two ways answers used to be lost or misrouted:
- a response field is ``{sid}X{gid}X{qid}{row code}``; with a numeric row code the
  question id and the row code run together (``X38486`` + ``1`` -> ``384861``), and a
  row code used by two arrays (``SQ001``) was read as the same column for both;
- PRISM's own export shortens matrix row codes to 5 characters (``PHQ901`` ->
  ``PHQ01``) but its CodeMap recorded the unshortened code, so a survey exported
  from PRISM converted back with every answer ``n/a``.
"""

import json
import sys
import zipfile
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "app"))

import defusedxml.ElementTree as DET  # noqa: E402

OFFICIAL_SURVEY_LIBRARY = (
    Path(__file__).resolve().parent.parent / "official" / "library" / "survey"
)


@pytest.fixture(autouse=True)
def _official_global_library(monkeypatch):
    import src.converters.survey_templates as st

    monkeypatch.setattr(st, "_load_global_library_path", lambda: OFFICIAL_SURVEY_LIBRARY)


def _row(**fields):
    return "<row>" + "".join(f"<{k}>{v}</{k}>" for k, v in fields.items()) + "</row>"


def _question(qid, gid, qtype, title, order, other="N"):
    return _row(qid=qid, parent_qid=0, gid=gid, type=qtype, title=title,
                question_order=order, other=other, mandatory="N")


def _sub(qid, parent, gid, code, order):
    return _row(qid=qid, parent_qid=parent, gid=gid, type="T", title=code,
                question_order=order, scale_id=0)


# LimeSurvey 6 shape (text in *_l10ns), as in a real export:
# group 10: array ADS1 with numeric row codes 1, 2 (qid 38486, like the real ADS export)
# group 20: array WHO with row SQ001; group 30: array PSS with row SQ001 as well
# group 40: list question edu with an "Other" field
LSS = f"""<?xml version="1.0" encoding="UTF-8"?>
<document>
 <LimeSurveyDocType>Survey</LimeSurveyDocType>
 <DBVersion>636</DBVersion>
 <surveys><rows>{_row(sid=1, language="de", additional_languages="")}</rows></surveys>
 <groups><rows>{_row(gid=10, group_order=1)}{_row(gid=20, group_order=2)}{_row(gid=30, group_order=3)}{_row(gid=40, group_order=4)}</rows></groups>
 <group_l10ns><rows>
  {_row(gid=10, group_name="ADS", language="de")}{_row(gid=20, group_name="WHO", language="de")}
  {_row(gid=30, group_name="PSS", language="de")}{_row(gid=40, group_name="Demo", language="de")}
 </rows></group_l10ns>
 <questions><rows>
  {_question(38486, 10, "F", "ADS1", 1)}{_question(200, 20, "F", "WHO", 1)}
  {_question(300, 30, "F", "PSS", 1)}{_question(400, 40, "L", "edu", 1, other="Y")}
 </rows></questions>
 <subquestions><rows>
  {_sub(901, 38486, 10, "1", 1)}{_sub(902, 38486, 10, "2", 2)}
  {_sub(903, 200, 20, "SQ001", 1)}{_sub(904, 300, 30, "SQ001", 1)}
 </rows></subquestions>
 <question_l10ns><rows>
  {_row(qid=38486, question="Stem", language="de")}{_row(qid=901, question="eins", language="de")}
  {_row(qid=902, question="zwei", language="de")}{_row(qid=200, question="Stem", language="de")}
  {_row(qid=903, question="who eins", language="de")}{_row(qid=300, question="Stem", language="de")}
  {_row(qid=904, question="pss eins", language="de")}{_row(qid=400, question="Bildung", language="de")}
 </rows></question_l10ns>
 <answers><rows>
  {_row(aid=1, qid=38486, code="A1", sortorder=1, scale_id=0)}{_row(aid=2, qid=200, code="A1", sortorder=1, scale_id=0)}
  {_row(aid=3, qid=300, code="A1", sortorder=1, scale_id=0)}{_row(aid=4, qid=400, code="A1", sortorder=1, scale_id=0)}
 </rows></answers>
 <answer_l10ns><rows>
  {_row(aid=1, answer="ja", language="de")}{_row(aid=2, answer="ja", language="de")}
  {_row(aid=3, answer="ja", language="de")}{_row(aid=4, answer="ja", language="de")}
 </rows></answer_l10ns>
</document>""".encode()

FIELDS = ["id", "submitdate", "1X10X384861", "1X10X384862", "1X20X200SQ001",
          "1X30X300SQ001", "1X40X400", "1X40X400other"]
# Item IDs stay what the template import makes (ADS1_1, edu, ...). WHO and PSS both
# import their row as item "SQ001"; one column name cannot feed both, so those two
# keep LimeSurvey's own names and are reported as unconverted, never misrouted.
EXPECTED_COLUMNS = ["id", "submitdate", "ADS1_1", "ADS1_2", "WHO[SQ001]",
                    "PSS[SQ001]", "edu", "edu[other]"]


def _write_lsa(path, lss_bytes, fields, rows):
    """A .lsa holding the .lss and a responses .lsr (XML tags start with '_' like LimeSurvey's)."""
    tag = lambda f: f"_{f}" if f[0].isdigit() else f  # noqa: E731
    body = "".join(
        "<row>" + "".join(f"<{tag(f)}>{v}</{tag(f)}>" for f, v in zip(fields, row)) + "</row>"
        for row in rows
    )
    lsr = (
        "<?xml version='1.0' encoding='UTF-8'?><document><LimeSurveyDocType>Responses"
        "</LimeSurveyDocType><responses><fields>"
        + "".join(f"<fieldname>{f}</fieldname>" for f in fields)
        + f"</fields><rows>{body}</rows></responses></document>"
    )
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("survey_archive_1.lss", lss_bytes)
        archive.writestr("survey_1_responses.lsr", lsr)
    return path


def test_response_columns_split_by_the_question_ids_of_the_survey():
    from src.converters.limesurvey import lsa_column_names

    assert lsa_column_names(FIELDS, LSS) == EXPECTED_COLUMNS


def test_response_columns_are_the_template_item_ids():
    """Item IDs are unchanged; every item gets its own column except the two clashing rows."""
    from src.converters.limesurvey import _build_questionnaires
    from src.converters.template_import import TEMPLATE_SECTIONS

    _parsed, results = _build_questionnaires(LSS, "group")
    items = {key for _info, template in results for key in template if key not in TEMPLATE_SECTIONS}
    assert items == {"ADS1_1", "ADS1_2", "SQ001", "edu"}
    assert {c for c in EXPECTED_COLUMNS if c in items} == items - {"SQ001"}


def test_survey_converter_reads_lsa_columns_by_question_id(tmp_path):
    from src.converters import survey

    lsa = _write_lsa(tmp_path / "survey_archive_1.lsa", LSS, FIELDS,
                     [["1", "2026-01-01 10:00:00", "A1", "A1", "A1", "A1", "A1", "Musik"]])
    df, _questions = survey._read_table_as_dataframe(input_path=lsa, kind="lsa")
    assert list(df.columns) == EXPECTED_COLUMNS


def test_parse_lsa_responses_reads_columns_by_question_id(tmp_path):
    from src.converters.limesurvey import parse_lsa_responses

    lsa = _write_lsa(tmp_path / "survey_archive_1.lsa", LSS, FIELDS,
                     [["1", "2026-01-01 10:00:00", "A1", "A1", "A1", "A1", "A1", "Musik"]])
    df, _questions, _groups = parse_lsa_responses(str(lsa))
    assert list(df.columns) == EXPECTED_COLUMNS


# ── PRISM export -> LimeSurvey -> PRISM ─────────────────────────────────


def _phq9_customization_groups():
    path = OFFICIAL_SURVEY_LIBRARY / "survey-phq9.json"
    template = json.loads(path.read_text(encoding="utf-8"))
    codes = [k for k, v in template.items() if isinstance(v, dict) and "Levels" in v]
    return codes, [{
        "name": "PHQ-9", "order": 0,
        "questions": [
            {"sourceFile": str(path), "questionCode": code, "displayOrder": i,
             "enabled": True, "levels": template[code]["Levels"],
             "originalData": template[code]}
            for i, code in enumerate(codes)
        ],
    }]


def _export_phq9(exporter):
    from src.limesurvey_exporter import generate_lss, generate_lss_from_customization

    codes, groups = _phq9_customization_groups()
    if exporter == "customizer":
        xml = generate_lss_from_customization(groups, language="en", matrix_mode=True)
    else:
        xml = generate_lss([str(OFFICIAL_SURVEY_LIBRARY / "survey-phq9.json")], matrix_mode=True)
    return codes, xml


def _answers_for_every_item(xml):
    """Response fields LimeSurvey creates for the export, each answered with the second answer code."""
    root = DET.fromstring(xml)
    questions = {r.findtext("qid"): r for r in root.findall("questions/rows/row")}
    second_code = {}
    for answer in root.findall("answers/rows/row"):
        second_code.setdefault(answer.findtext("qid"), []).append(answer.findtext("code"))
    fields, values = ["id", "token"], ["1", "tok1"]
    for sub in root.findall("subquestions/rows/row"):
        parent = questions[sub.findtext("parent_qid")]
        fields.append(f"123456X{parent.findtext('gid')}X{parent.findtext('qid')}{sub.findtext('title')}")
        values.append(second_code[parent.findtext("qid")][1])
    return fields, values


@pytest.mark.parametrize("exporter", ["customizer", "quick"])
def test_prism_export_converts_back_with_every_answer(tmp_path, exporter):
    from src.converters.survey import convert_survey_lsa_to_prism_dataset

    codes, xml = _export_phq9(exporter)
    fields, values = _answers_for_every_item(xml)
    assert len(fields) - 2 == len(codes), "every PHQ-9 item is a matrix row"
    lsa = _write_lsa(tmp_path / "survey_archive_123456.lsa", xml.encode(), fields, [values])

    out = tmp_path / "ds"
    convert_survey_lsa_to_prism_dataset(
        input_path=lsa, library_dir=OFFICIAL_SURVEY_LIBRARY, output_root=out,
        id_column="id", unknown="warn",
    )
    tsv = next(out.rglob("*task-phq9_survey.tsv")).read_text(encoding="utf-8").splitlines()
    header, row = tsv[0].split("\t"), tsv[1].split("\t")
    answered = dict(zip(header, row))
    assert {code: answered.get(code) for code in codes} == {code: "1" for code in codes}


@pytest.mark.parametrize("exporter", ["customizer", "quick"])
def test_template_import_of_prism_export_restores_item_ids(exporter):
    from src.converters.limesurvey import limesurvey_questionnaire_template

    codes, xml = _export_phq9(exporter)
    template = limesurvey_questionnaire_template(xml.encode(), "g10")
    assert [k for k in template if k.startswith("PHQ")] == codes
