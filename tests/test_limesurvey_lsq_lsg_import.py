"""Regression tests for parse_lsq_xml/parse_lsg_xml.

These two functions back the Template Editor's "Import .lsq/.lsg" button
(app/src/web/blueprints/tools_template_editor_blueprint.py). They were added
to app/src/converters/limesurvey.py in commit 8c8b96ee, then lost when that
file was collapsed into a compat shim over the canonical src/converters/
limesurvey.py in commit ab5f22a2 — the canonical file never had them, so the
button 500'd on every click (see docs/_archive/GUI_BACKEND_AUDIT_2026-08-07.md).
"""

import xml.etree.ElementTree as ET

from src.converters.limesurvey import (
    _build_prism_template_from_parsed,
    _detect_languages,
    _parse_answers_into_questions,
    _parse_lss_structure,
    parse_lsg_xml,
    parse_lsq_xml,
)


def _get_text(element, tag):
    child = element.find(tag)
    val = child.text if child is not None else ""
    return val or ""


# A .lsq export: single question, no <groups>/<surveys> sections.
_MINIMAL_LSQ = """<?xml version="1.0" encoding="UTF-8"?>
<document>
  <questions><rows>
    <row>
      <qid>10</qid>
      <gid>1</gid>
      <type>L</type>
      <title>MOOD</title>
      <question>How do you feel today?</question>
      <question_order>1</question_order>
      <mandatory>Y</mandatory>
      <parent_qid>0</parent_qid>
      <other>N</other>
      <preg></preg>
    </row>
  </rows></questions>
  <answers><rows>
    <row>
      <qid>10</qid>
      <code>1</code>
      <answer>Good</answer>
      <language>en</language>
    </row>
    <row>
      <qid>10</qid>
      <code>2</code>
      <answer>Bad</answer>
      <language>en</language>
    </row>
  </rows></answers>
  <question_attributes><rows></rows></question_attributes>
  <subquestions><rows></rows></subquestions>
</document>
"""

# A .lsg export: one group with a matrix (array) question and subquestions.
_MINIMAL_LSG = """<?xml version="1.0" encoding="UTF-8"?>
<document>
  <groups><rows>
    <row>
      <gid>1</gid>
      <group_name>Wellbeing</group_name>
      <group_order>1</group_order>
      <description></description>
    </row>
  </rows></groups>
  <questions><rows>
    <row>
      <qid>100</qid>
      <gid>1</gid>
      <type>F</type>
      <title>WB</title>
      <question>Rate the following</question>
      <question_order>1</question_order>
      <mandatory>N</mandatory>
      <parent_qid>0</parent_qid>
      <other>N</other>
      <preg></preg>
    </row>
  </rows></questions>
  <subquestions><rows>
    <row>
      <qid>101</qid>
      <parent_qid>100</parent_qid>
      <title>SQ001</title>
      <question>Sleep quality</question>
      <question_order>1</question_order>
      <scale_id>0</scale_id>
    </row>
    <row>
      <qid>102</qid>
      <parent_qid>100</parent_qid>
      <title>SQ002</title>
      <question>Energy level</question>
      <question_order>2</question_order>
      <scale_id>0</scale_id>
    </row>
  </rows></subquestions>
  <answers><rows>
    <row>
      <qid>100</qid>
      <code>1</code>
      <answer>Low</answer>
    </row>
    <row>
      <qid>100</qid>
      <code>2</code>
      <answer>High</answer>
    </row>
  </rows></answers>
  <question_attributes><rows></rows></question_attributes>
</document>
"""


class TestParseLsqXml:
    def test_returns_none_for_invalid_xml(self):
        assert parse_lsq_xml(b"NOT XML") is None

    def test_parses_minimal_lsq(self):
        result = parse_lsq_xml(_MINIMAL_LSQ.encode("utf-8"))
        assert result is not None
        assert isinstance(result, dict)

    def test_item_present_with_levels(self):
        result = parse_lsq_xml(_MINIMAL_LSQ.encode("utf-8"))
        assert "MOOD" in result
        levels = result["MOOD"].get("Levels") or {}
        assert "1" in levels
        assert levels["1"]["en"] == "Good"

    def test_limesurvey_props_preserved(self):
        result = parse_lsq_xml(_MINIMAL_LSQ.encode("utf-8"))
        ls_props = result["MOOD"]["LimeSurvey"]
        assert ls_props["questionType"] == "L"
        assert ls_props["mandatory"] is True

    def test_study_metadata_present(self):
        result = parse_lsq_xml(_MINIMAL_LSQ.encode("utf-8"))
        study = result.get("Study") or {}
        assert study.get("ItemCount") == 1
        assert "lsq" in (study.get("Description") or "")


class TestParseLsgXml:
    def test_returns_none_for_invalid_xml(self):
        assert parse_lsg_xml(b"NOT XML") is None

    def test_parses_minimal_lsg(self):
        result = parse_lsg_xml(_MINIMAL_LSG.encode("utf-8"))
        assert result is not None
        assert isinstance(result, dict)

    def test_matrix_flattened_to_subquestion_items(self):
        result = parse_lsg_xml(_MINIMAL_LSG.encode("utf-8"))
        assert "SQ001" in result
        assert "SQ002" in result
        assert "WB" not in result  # parent matrix code itself isn't emitted

    def test_subquestion_items_share_matrix_levels(self):
        result = parse_lsg_xml(_MINIMAL_LSG.encode("utf-8"))
        levels = result["SQ001"].get("Levels") or {}
        assert "1" in levels and "2" in levels

    def test_task_name_from_group(self):
        result = parse_lsg_xml(_MINIMAL_LSG.encode("utf-8"))
        study = result.get("Study") or {}
        assert study.get("OriginalName") == "Wellbeing"


class TestParseAnswersIntoQuestions:
    def test_simple_mode_maps_code_to_answer(self):
        root = ET.fromstring(_MINIMAL_LSQ)
        questions_map, _ = _parse_lss_structure(root, _get_text)
        _parse_answers_into_questions(root, questions_map, _get_text)
        assert questions_map["10"]["levels"]["1"] == {"en": "Good"}

    def test_track_scales_populates_levels_by_scale(self):
        xml = """<root>
          <questions><rows>
            <row><qid>1</qid><gid>1</gid><type>1</type><title>Q1</title>
              <question>Q</question><question_order>1</question_order>
              <mandatory>N</mandatory><parent_qid>0</parent_qid><other>N</other>
            </row>
          </rows></questions>
          <answers><rows>
            <row><qid>1</qid><code>A</code><answer>Alpha</answer><scale_id>0</scale_id></row>
            <row><qid>1</qid><code>B</code><answer>Beta</answer><scale_id>1</scale_id></row>
          </rows></answers>
        </root>"""
        root = ET.fromstring(xml)
        questions_map, _ = _parse_lss_structure(root, _get_text)
        _parse_answers_into_questions(root, questions_map, _get_text, track_scales=True)
        assert questions_map["1"]["levels_by_scale"]["0"]["A"] == "Alpha"
        assert questions_map["1"]["levels_by_scale"]["1"]["B"] == "Beta"

    def test_unknown_qid_is_skipped_without_error(self):
        root = ET.fromstring(_MINIMAL_LSQ)
        questions_map, _ = _parse_lss_structure(root, _get_text)
        # Answers for a qid that isn't in questions_map shouldn't raise.
        extra = ET.fromstring(
            "<root><answers><rows><row><qid>999</qid><code>1</code>"
            "<answer>x</answer></row></rows></answers></root>"
        )
        _parse_answers_into_questions(extra, questions_map, _get_text)


class TestDetectLanguages:
    def test_defaults_to_english_when_nothing_found(self):
        root = ET.fromstring("<root/>")
        languages, default_language = _detect_languages(root, _get_text)
        assert languages == ["en"]
        assert default_language == "en"

    def test_detects_additional_languages(self):
        xml = """<root>
          <surveys><rows>
            <row><language>en</language><additional_languages>de fr</additional_languages></row>
          </rows></surveys>
        </root>"""
        root = ET.fromstring(xml)
        languages, default_language = _detect_languages(root, _get_text)
        assert default_language == "en"
        assert set(languages) == {"en", "de", "fr"}


class TestBuildPrismTemplateFromParsed:
    def test_empty_input_yields_metadata_only_template(self):
        template = _build_prism_template_from_parsed({}, {}, ["en"], "en", "lsq")
        assert template["Technical"]["SoftwarePlatform"] == "LimeSurvey"
        assert template["Study"]["ItemCount"] == 0

    def test_multilingual_adds_i18n_section(self):
        template = _build_prism_template_from_parsed(
            {}, {}, ["en", "de"], "en", "lsg"
        )
        assert template["I18n"]["Languages"] == ["en", "de"]
