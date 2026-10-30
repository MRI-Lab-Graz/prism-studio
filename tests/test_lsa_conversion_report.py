"""Found converting a real LimeSurvey 6 archive of a survey exported from PRISM:
- the "missing items" count ignored aliases, so PHQ-9 (LimeSurvey `PHQ01`, template `PHQ901`) was
  reported as 9 missing items although every answer had been converted;
- numbers came out as LimeSurvey stores them (`55.0000000000`) for integer items;
- a generic formula of a calculated item was written as `{a.NAOK}*2`, which LimeSurvey stores as
  the text `55*2` (only what is inside the braces is evaluated)."""

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "app"))

from test_limesurvey_roundtrip_codes import _answers_for_every_item, _export_phq9, _write_lsa  # noqa: E402

from tests.template_fixtures import completed_official_library, dump_complete  # noqa: E402

OFFICIAL_SURVEY_LIBRARY = completed_official_library()  # a conversion needs complete project templates


@pytest.fixture(autouse=True)
def _official_global_library(monkeypatch):
    import src.converters.survey as survey
    import src.converters.survey_templates as st

    monkeypatch.setattr(st, "_load_global_library_path", lambda: OFFICIAL_SURVEY_LIBRARY)
    monkeypatch.setattr(survey, "_load_global_library_path", lambda: OFFICIAL_SURVEY_LIBRARY)


# ── missing items ────────────────────────────────────────────────────────


def test_an_item_whose_column_has_an_alias_is_not_missing():
    from src.converters.survey import _compute_missing_items_report

    schema = {
        "PHQ901": {}, "PHQ902": {}, "PHQ903": {},
        "_aliases": {"PHQ01": "PHQ901", "PHQ02": "PHQ902"},
        "_reverse_aliases": {"PHQ901": ["PHQ01"], "PHQ902": ["PHQ02"]},
    }
    report = _compute_missing_items_report({"phq9"}, {"phq9": {"json": schema}}, {"PHQ01": "phq9", "PHQ02": "phq9"})
    assert report == {"phq9": 1}


def test_an_item_read_by_its_column_name_is_not_missing_even_when_the_column_is_not_mapped():
    """age/sex columns are skipped as participant columns in the mapping but converted by item name."""
    from src.converters.survey import _compute_missing_items_report

    schema = {"age": {}, "sex": {}, "details": {}}
    report = _compute_missing_items_report({"t"}, {"t": {"json": schema}}, {}, df_columns=["id", "age", "sex"])
    assert report == {"t": 1}


def test_a_survey_exported_from_prism_reports_no_missing_items(tmp_path):
    from src.converters.survey import convert_survey_lsa_to_prism_dataset

    codes, xml = _export_phq9("customizer")
    fields, values = _answers_for_every_item(xml)
    lsa = _write_lsa(tmp_path / "survey_archive_1.lsa", xml.encode(), fields, [values])
    result = convert_survey_lsa_to_prism_dataset(
        input_path=lsa, library_dir=OFFICIAL_SURVEY_LIBRARY, output_root=tmp_path / "ds", id_column="id", unknown="warn",
    )
    assert result.missing_items_by_task == {"phq9": 0}


# ── numbers LimeSurvey pads with zeros ───────────────────────────────────


@pytest.mark.parametrize(
    "value, expected",
    [("23.0000000000", "23"), ("44.50", "44.5"), ("-3.500", "-3.5"), (" 55.00 ", "55"), ("0.0", "0"), ("100.00", "100"),
     ("10", "10"), ("3.14", "3.14"), ("abc", "abc"), ("1.0.0", "1.0.0"), ("", ""), (None, None), (7, 7)],
)
def test_trim_trailing_decimal_zeros(value, expected):
    from src.text_sanitizer import trim_trailing_decimal_zeros

    assert trim_trailing_decimal_zeros(value) == expected


MINI_LSS = """<?xml version="1.0" encoding="UTF-8"?>
<document><LimeSurveyDocType>Survey</LimeSurveyDocType><DBVersion>636</DBVersion>
 <languages><language>en</language></languages>
 <surveys><rows><row><sid>1</sid><language>en</language></row></rows></surveys>
 <groups><rows><row><gid>1</gid><group_order>1</group_order></row></rows></groups>
 <group_l10ns><rows><row><gid>1</gid><group_name>Mini</group_name><language>en</language></row></rows></group_l10ns>
 <questions><rows>
  <row><qid>10</qid><parent_qid>0</parent_qid><gid>1</gid><type>N</type><title>age</title><question_order>1</question_order></row>
  <row><qid>20</qid><parent_qid>0</parent_qid><gid>1</gid><type>S</type><title>note</title><question_order>2</question_order></row>
  <row><qid>30</qid><parent_qid>0</parent_qid><gid>1</gid><type>N</type><title>weight</title><question_order>3</question_order></row>
 </rows></questions>
 <question_l10ns><rows>
  <row><qid>10</qid><question>Age?</question><language>en</language></row>
  <row><qid>20</qid><question>Note</question><language>en</language></row>
  <row><qid>30</qid><question>Weight?</question><language>en</language></row>
 </rows></question_l10ns>
</document>""".encode()


def _convert_mini(tmp_path):
    from src.converters.survey import convert_survey_lsa_to_prism_dataset

    library = tmp_path / "library"
    library.mkdir()
    (library / "survey-mini.json").write_text(dump_complete({
        "Technical": {"StimulusType": "Questionnaire", "FileFormat": "tsv", "SoftwarePlatform": "LimeSurvey",
                      "Language": "en", "Respondent": "self"},
        "Study": {"TaskName": "mini", "OriginalName": "Mini", "Version": "1.0"},
        "age": {"Description": {"en": "Age?"}, "DataType": "integer"},
        "note": {"Description": {"en": "Note"}, "DataType": "string"},
        "weight": {"Description": {"en": "Weight?"}, "DataType": "float"},
    }), encoding="utf-8")
    fields = ["id", "1X1X10", "1X1X20", "1X1X30"]
    lsa = _write_lsa(tmp_path / "survey_archive_1.lsa", MINI_LSS, fields,
                     [["1", "55.0000000000", "3.50", "70.5000000000"], ["2", "23.0000000000", "n/a", "61.0000000000"]])
    result = convert_survey_lsa_to_prism_dataset(
        input_path=lsa, library_dir=library, output_root=tmp_path / "ds", id_column="id", unknown="warn",
    )
    tsv = {}
    for path in (tmp_path / "ds").rglob("*task-mini_survey.tsv"):
        header, row = path.read_text(encoding="utf-8").splitlines()[:2]
        tsv[path.name.split("_")[0]] = dict(zip(header.split("\t"), row.split("\t")))
    return result, tsv


def test_numeric_items_are_written_without_padded_zeros(tmp_path):
    _result, tsv = _convert_mini(tmp_path)
    assert (tsv["sub-1"]["age"], tsv["sub-1"]["weight"]) == ("55", "70.5")
    assert (tsv["sub-2"]["age"], tsv["sub-2"]["weight"]) == ("23", "61")


def test_text_items_keep_their_value(tmp_path):
    _result, tsv = _convert_mini(tmp_path)
    assert tsv["sub-1"]["note"] == "3.50"


def test_the_trimming_is_reported(tmp_path):
    result, _tsv = _convert_mini(tmp_path)
    [note] = [w for w in result.conversion_warnings if "decimal zeros" in w]
    assert "4 value(s)" in note and "mini" in note and "55.0000000000" in note


# ── calculated items ─────────────────────────────────────────────────────


def _equation(calculation):
    from src.limesurvey_exporter import _determine_ls_question_type

    q_type, attributes = _determine_ls_question_type({"InputType": "calculated", "Calculation": calculation}, False)
    assert q_type == "*"
    return attributes["equation"]


def test_a_generic_formula_is_one_expression_in_one_pair_of_braces():
    assert _equation({"formula": "a + b * 2", "dependsOn": ["a", "b"]}) == "{a.NAOK + b.NAOK * 2}"


def test_exponentiation_and_codes_with_underscores():
    assert _equation({"formula": "(total_score + b) ** 2", "dependsOn": ["total_score", "b"]}) == \
        "{pow(totalscore.NAOK + b.NAOK, 2)}"


def test_a_limesurvey_formula_is_used_as_written():
    assert _equation({"lsFormula": "{sum(a.NAOK, b.NAOK)}", "formula": "a + b", "dependsOn": ["a", "b"]}) == \
        "{sum(a.NAOK, b.NAOK)}"


# ── matching a survey exported from PRISM ────────────────────────────────


@pytest.mark.parametrize("exporter", ["customizer", "quick"])
def test_a_prism_export_matches_its_template_by_the_original_item_codes(exporter):
    """LimeSurvey codes are shortened (PHQ901 -> PHQ01); the CodeMap in the export says which is which."""
    from src.converters.limesurvey import parse_lss_xml_by_groups
    from src.converters.survey_templates import match_against_library

    _codes, xml = _export_phq9(exporter)
    [(name, group)] = parse_lss_xml_by_groups(xml.encode()).items()
    match = match_against_library(group, group_name=name)
    assert match.template_key == "phq9" and match.overlap_count == 9 and match.confidence in ("exact", "high")


def test_converting_a_prism_export_raises_no_match_warning(tmp_path):
    from src.converters.survey import convert_survey_lsa_to_prism_dataset

    _codes, xml = _export_phq9("customizer")
    fields, values = _answers_for_every_item(xml)
    lsa = _write_lsa(tmp_path / "survey_archive_1.lsa", xml.encode(), fields, [values])
    result = convert_survey_lsa_to_prism_dataset(
        input_path=lsa, library_dir=OFFICIAL_SURVEY_LIBRARY, output_root=tmp_path / "ds", id_column="id", unknown="warn",
    )
    assert not [w for w in result.conversion_warnings if "confidence" in w]
