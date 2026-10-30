"""Question types that are several response columns become several template items, and
their answers reach them (checkbox lists M/P, ranking R, text/number arrays ;/: and the
dual-scale array 1). The columns are LimeSurvey's: multiple choice {qid}{row} = Y or empty,
with comments {qid}{row}comment, ranking {qid}{position}, the two-dimensional arrays
{qid}{row}_{column}, dual scale {qid}{row}-0 and -1 (LimeSurvey 6; older versions wrote #0 and #1)."""

import sys
import zipfile
from pathlib import Path

import pytest
from tests.template_fixtures import complete, dump_complete

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "app"))


def _row(**fields):
    return "<row>" + "".join(f"<{k}><![CDATA[{v}]]></{k}>" for k, v in fields.items()) + "</row>"


def _sub(qid, parent, code, text, scale=0, order=1):
    return _row(qid=qid, parent_qid=parent, gid=1, type="T", title=code, question_order=order, scale_id=scale), \
        _row(qid=qid, question=text, language="de")


SUBS = [
    _sub(11, 10, "M1", "Musik", order=1), _sub(12, 10, "M2", "Sport", order=2),
    _sub(21, 20, "P1", "Lesen"),
    _sub(41, 40, "T1", "Zeile eins", 0, 1), _sub(42, 40, "T2", "Zeile zwei", 0, 2),
    _sub(43, 40, "K1", "Spalte A", 1, 1), _sub(44, 40, "K2", "Spalte B", 1, 2),
    _sub(51, 50, "N1", "Gewicht", 0, 1), _sub(52, 50, "K1", "morgens", 1, 1), _sub(53, 50, "K2", "abends", 1, 2),
    _sub(61, 60, "D1", "Stimmung"),
]
QUESTIONS = [(10, "M", "boxes"), (20, "P", "boxcom"), (30, "R", "rank"), (40, ";", "textarr"),
             (50, ":", "numarr"), (60, "1", "dual")]

LSS = f"""<?xml version="1.0" encoding="UTF-8"?>
<document><LimeSurveyDocType>Survey</LimeSurveyDocType><DBVersion>636</DBVersion>
 <languages><language>de</language></languages>
 <surveys><rows>{_row(sid=1, language="de")}</rows></surveys>
 <groups><rows>{_row(gid=1, group_order=1)}</rows></groups>
 <group_l10ns><rows>{_row(gid=1, group_name="Types", language="de")}</rows></group_l10ns>
 <questions><rows>{"".join(_row(qid=q, parent_qid=0, gid=1, type=t, title=title, question_order=i) for i, (q, t, title) in enumerate(QUESTIONS))}</rows></questions>
 <subquestions><rows>{"".join(row for row, _ in SUBS)}</rows></subquestions>
 <question_l10ns><rows>{"".join(_row(qid=q, question=f"Stamm {title}", language="de") for q, _t, title in QUESTIONS)}{"".join(l10n for _, l10n in SUBS)}</rows></question_l10ns>
 <answers><rows>
  {_row(aid=1, qid=30, code="A1", sortorder=1, scale_id=0)}{_row(aid=2, qid=30, code="A2", sortorder=2, scale_id=0)}{_row(aid=3, qid=30, code="A3", sortorder=3, scale_id=0)}
  {_row(aid=4, qid=60, code="1", sortorder=1, scale_id=0)}{_row(aid=5, qid=60, code="2", sortorder=2, scale_id=0)}
  {_row(aid=6, qid=60, code="1", sortorder=1, scale_id=1)}{_row(aid=7, qid=60, code="2", sortorder=2, scale_id=1)}
 </rows></answers>
 <answer_l10ns><rows>
  {_row(aid=1, answer="eins", language="de")}{_row(aid=2, answer="zwei", language="de")}{_row(aid=3, answer="drei", language="de")}
  {_row(aid=4, answer="gut", language="de")}{_row(aid=5, answer="schlecht", language="de")}
  {_row(aid=6, answer="oft", language="de")}{_row(aid=7, answer="selten", language="de")}
 </rows></answer_l10ns>
</document>""".encode()

FIELDS = ["id", "1X1X10M1", "1X1X10M2", "1X1X20P1", "1X1X20P1comment", "1X1X301", "1X1X302", "1X1X303",
          "1X1X40T1_K1", "1X1X40T2_K2", "1X1X50N1_K1", "1X1X60D1-0", "1X1X60D1-1"]
EXPECTED = ["id", "M1", "M2", "P1", "P1_comment", "rank_1", "rank_2", "rank_3",
            "T1_K1", "T2_K2", "N1_K1", "D1_scale1", "D1_scale2"]


@pytest.fixture(scope="module")
def template():
    from src.converters.limesurvey import limesurvey_questionnaire

    return limesurvey_questionnaire(LSS, "g1")[0]


def test_checkbox_rows_are_items_with_a_checked_level(template):
    assert template["M1"]["Description"] == {"de": "Musik"}
    assert template["M1"]["Levels"] == {"Y": {"de": "Ja"}}
    assert template["M1"]["LimeSurvey"]["columnName"] == "boxes[M1]"
    assert "M2" in template and "boxes" not in template


def test_checkbox_with_comments_gets_a_comment_item_per_row(template):
    assert template["P1"]["Levels"] == {"Y": {"de": "Ja"}}
    assert template["P1_comment"]["DataType"] == "string"
    assert template["P1_comment"]["Description"] == {"de": "Lesen (comment)"}
    assert template["P1_comment"]["LimeSurvey"]["columnName"] == "boxcom[P1comment]"


def test_ranking_is_one_item_per_position_with_the_options_as_levels(template):
    assert [k for k in template if k.startswith("rank_")] == ["rank_1", "rank_2", "rank_3"]
    assert template["rank_2"]["Description"] == {"de": "Stamm rank (2)"}
    assert template["rank_2"]["Levels"] == {"A1": {"de": "eins"}, "A2": {"de": "zwei"}, "A3": {"de": "drei"}}
    assert template["rank_2"]["LimeSurvey"]["columnName"] == "rank[2]"


def test_two_dimensional_arrays_are_one_item_per_row_and_column(template):
    assert [k for k in template if k.startswith("T") and "_K" in k] == ["T1_K1", "T1_K2", "T2_K1", "T2_K2"]
    assert template["T1_K2"]["Description"] == {"de": "Zeile eins / Spalte B"}
    assert template["T1_K2"]["DataType"] == "string" and "Levels" not in template["T1_K2"]
    assert template["N1_K1"]["DataType"] == "float"
    assert template["N1_K1"]["LimeSurvey"]["columnName"] == "numarr[N1_K1]"


def test_dual_scale_array_is_one_item_per_row_and_scale_with_their_own_levels(template):
    assert template["D1_scale1"]["Levels"] == {"1": {"de": "gut"}, "2": {"de": "schlecht"}}
    assert template["D1_scale2"]["Levels"] == {"1": {"de": "oft"}, "2": {"de": "selten"}}
    assert template["D1_scale2"]["LimeSurvey"]["columnName"] == "dual[D1-1]"


def test_response_columns_land_on_these_items():
    from src.converters.limesurvey import lsa_column_names

    assert lsa_column_names(FIELDS, LSS) == EXPECTED


def test_every_column_of_the_archive_is_an_item_of_the_template(template):
    from src.converters.template_import import TEMPLATE_SECTIONS

    items = {k for k in template if k not in TEMPLATE_SECTIONS}
    assert set(EXPECTED[1:3]) | set(EXPECTED[3:]) <= items


def test_notes_say_that_unchecked_boxes_import_as_missing():
    from src.converters.limesurvey import limesurvey_questionnaire

    _template, notes = limesurvey_questionnaire(LSS, "g1")
    assert any(" / boxes:" in n and "unchecked" in n for n in notes)
    assert any(" / boxcom:" in n and "unchecked" in n for n in notes)
    assert not [n for n in notes if "not numbers" not in n and any(f" / {t}:" in n for t in ("rank", "textarr", "numarr", "dual"))]


def test_checkbox_answers_convert_checked_boxes_and_leave_unchecked_missing(tmp_path):
    """End to end: the .lsa converts with a project-local template made from the import."""
    import json

    from src.converters.limesurvey import limesurvey_questionnaire
    from src.converters.survey import convert_survey_lsa_to_prism_dataset

    template, _notes = limesurvey_questionnaire(LSS, "g1")
    library = tmp_path / "library"
    library.mkdir()
    (library / "survey-types.json").write_text(dump_complete(template), encoding="utf-8")
    fields = ["id", "1X1X10M1", "1X1X10M2", "1X1X301", "1X1X302", "1X1X303", "1X1X40T1_K1"]
    body = "<row>" + "".join(
        f"<{('_' + f) if f[0].isdigit() else f}>{v}</{('_' + f) if f[0].isdigit() else f}>"
        for f, v in zip(fields, ["7", "Y", "", "A2", "A1", "A3", "text"])
    ) + "</row>"
    lsr = ("<document><responses><fields>" + "".join(f"<fieldname>{f}</fieldname>" for f in fields)
           + f"</fields><rows>{body}</rows></responses></document>")
    lsa = tmp_path / "survey_archive_1.lsa"
    with zipfile.ZipFile(lsa, "w") as archive:
        archive.writestr("survey.lss", LSS)
        archive.writestr("survey_1_responses.lsr", lsr)

    convert_survey_lsa_to_prism_dataset(
        input_path=lsa, library_dir=library, output_root=tmp_path / "ds", id_column="id", unknown="warn",
    )
    header, row = next((tmp_path / "ds").rglob("*task-types_survey.tsv")).read_text(encoding="utf-8").splitlines()[:2]
    answered = dict(zip(header.split("\t"), row.split("\t")))
    assert answered["M1"] == "Y" and answered["M2"] == "n/a"
    assert [answered["rank_1"], answered["rank_2"], answered["rank_3"]] == ["A2", "A1", "A3"]
    assert answered["T1_K1"] == "text"


# ── Export of the imported items ─────────────────────────────────────────


@pytest.mark.parametrize("exporter", ["quick", "customizer"])
def test_exported_single_items_are_never_row_types_without_rows(tmp_path, template, exporter):
    """Each imported item is exported on its own; a lone array/checkbox/ranking question would be
    broken in LimeSurvey, so it becomes a list with its options (or a text/number question)."""
    import json

    import defusedxml.ElementTree as DET
    from src.limesurvey_attributes import LS_ROW_TYPES
    from src.limesurvey_exporter import generate_lss, generate_lss_from_customization
    from src.survey_customizer import build_customizer_groups

    path = tmp_path / "survey-types.json"
    path.write_text(dump_complete({**template, "I18n": {"Languages": ["de"], "DefaultLanguage": "de"}}), encoding="utf-8")
    if exporter == "quick":
        xml = generate_lss([str(path)], language="de", matrix_mode=False)
    else:
        xml = generate_lss_from_customization(
            build_customizer_groups([{"path": str(path)}], "de"), language="de", matrix_mode=False)
    root = DET.fromstring(xml)
    questions = {q.findtext("qid"): q for q in root.findall("questions/rows/row")}
    with_answers = {a.findtext("qid") for a in root.findall("answers/rows/row")}
    types = {q.findtext("title"): q.findtext("type") for q in questions.values()}
    assert not [t for t, ty in types.items() if ty in LS_ROW_TYPES], types
    # LimeSurvey codes have no underscores: P1_comment is exported as P1comment. Derived from DataType:
    # a text cell (string, no answer options) is a long text question, a number cell (float) numerical.
    assert types["P1comment"] == "T" and types["T1K1"] == "T" and types["N1K1"] == "N"
    for title in ("M1", "rank2", "D1scale2"):
        [qid] = [i for i, q in questions.items() if q.findtext("title") == title]
        assert qid in with_answers, title


def test_the_older_hash_notation_of_dual_scale_columns_maps_to_the_same_items():
    from src.converters.limesurvey import lsa_column_names

    assert lsa_column_names(["1X1X60D1#0", "1X1X60D1#1"], LSS) == ["D1_scale1", "D1_scale2"]


# ── the structure and column names of a real LimeSurvey 6 export (default codes SQ001, AO01) ──


def _real_ls6_survey():
    """Question types M, P, ;, : and 1 as LimeSurvey 6 numbers them, every row coded SQ001."""
    questions = [(748, "M", "G01Q02"), (752, "P", "G01Q03"), (755, ";", "G01Q04"), (758, ":", "G01Q05"), (761, "1", "G01Q06")]
    subs = [  # (qid, parent, code, scale)
        (1, 748, "SQ001", 0), (2, 748, "SQ002", 0), (3, 748, "SQ003", 0), (4, 752, "SQ001", 0), (5, 752, "SQ002", 0),
        (6, 755, "SQ001", 0), (7, 755, "SQ001", 1), (8, 758, "SQ001", 0), (9, 758, "SQ001", 1), (10, 761, "SQ001", 0),
    ]
    xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<document><LimeSurveyDocType>Survey</LimeSurveyDocType><DBVersion>636</DBVersion>
 <languages><language>de</language></languages>
 <surveys><rows>{_row(sid=1, language="de")}</rows></surveys>
 <groups><rows>{_row(gid=1, group_order=1)}</rows></groups>
 <group_l10ns><rows>{_row(gid=1, group_name="Meine erste Fragengruppe", language="de")}</rows></group_l10ns>
 <questions><rows>{"".join(_row(qid=q, parent_qid=0, gid=1, type=t, title=title, question_order=i) for i, (q, t, title) in enumerate(questions))}</rows></questions>
 <subquestions><rows>{"".join(_row(qid=q, parent_qid=p, gid=1, type="T", title=c, question_order=q, scale_id=s) for q, p, c, s in subs)}</rows></subquestions>
 <question_l10ns><rows>{"".join(_row(qid=q, question="q", language="de") for q, _t, _n in questions)}{"".join(_row(qid=q, question="s", language="de") for q, *_ in subs)}</rows></question_l10ns>
 <answers><rows>{_row(aid=1, qid=761, code="AO01", sortorder=1, scale_id=0)}{_row(aid=2, qid=761, code="AO01", sortorder=1, scale_id=1)}</rows></answers>
 <answer_l10ns><rows>{_row(aid=1, answer="gut", language="de")}{_row(aid=2, answer="oft", language="de")}</rows></answer_l10ns>
</document>""".encode()
    fields = ["id", "656971X1X748SQ001", "656971X1X748SQ002", "656971X1X748SQ003", "656971X1X752SQ001", "656971X1X752SQ001comment",
              "656971X1X752SQ002", "656971X1X752SQ002comment", "656971X1X755SQ001_SQ001", "656971X1X758SQ001_SQ001",
              "656971X1X761SQ001-0", "656971X1X761SQ001-1"]
    return xml, fields


def test_every_column_of_a_real_limesurvey6_survey_with_default_codes_is_an_item():
    from src.converters.limesurvey import limesurvey_questionnaire, lsa_column_names
    from src.converters.template_import import TEMPLATE_SECTIONS

    xml, fields = _real_ls6_survey()
    template, _notes = limesurvey_questionnaire(xml, "g1")
    items = {k for k in template if k not in TEMPLATE_SECTIONS}
    columns = lsa_column_names(fields, xml)[1:]
    assert [c for c in columns if c not in items] == [], columns
    assert len(set(columns)) == len(columns), "no two columns share an item"
