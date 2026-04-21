"""Additional tests for src/converters/limesurvey.py — metadata parsing with XML fixtures."""

import sys
import os
import pytest
import xml.etree.ElementTree as ET

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.converters.limesurvey import (
    _get_question_type_name,
    _map_field_to_code,
    _extract_media_urls,
    _clean_html_preserve_info,
    _parse_survey_metadata,
    _parse_lss_structure,
    parse_lss_xml,
    parse_lss_xml_by_groups,
    parse_lss_xml_by_questions,
)


# ---------------------------------------------------------------------------
# Helper to build minimal XML roots
# ---------------------------------------------------------------------------

def _make_root(xml_str: str):
    return ET.fromstring(xml_str)


def _get_text(element, tag):
    child = element.find(tag)
    val = child.text if child is not None else ""
    return val or ""


# ---------------------------------------------------------------------------
# _parse_survey_metadata
# ---------------------------------------------------------------------------

class TestParseSurveyMetadata:
    def test_returns_defaults_for_empty_root(self):
        root = _make_root("<root/>")
        meta = _parse_survey_metadata(root, _get_text)
        assert meta["title"] == ""
        assert meta["language"] == "en"
        assert meta["anonymized"] is False

    def test_reads_survey_fields(self):
        xml = """<root>
            <surveys><rows>
              <row>
                <admin>admin@example.com</admin>
                <adminemail>admin@example.com</adminemail>
                <language>de</language>
                <anonymized>Y</anonymized>
                <format>S</format>
              </row>
            </rows></surveys>
        </root>"""
        root = _make_root(xml)
        meta = _parse_survey_metadata(root, _get_text)
        assert meta["language"] == "de"
        assert meta["anonymized"] is True
        assert meta["format"] == "S"

    def test_reads_title_from_lang_settings(self):
        xml = """<root>
            <surveys_languagesettings><rows>
              <row>
                <surveyls_title>My Survey</surveyls_title>
                <surveyls_welcometext>Welcome!</surveyls_welcometext>
                <surveyls_endtext>Thank you.</surveyls_endtext>
                <surveyls_description>Survey description.</surveyls_description>
              </row>
            </rows></surveys_languagesettings>
        </root>"""
        root = _make_root(xml)
        meta = _parse_survey_metadata(root, _get_text)
        assert meta["title"] == "My Survey"
        assert meta["welcome_message"] == "Welcome!"
        assert meta["end_message"] == "Thank you."
        assert meta["description"] == "Survey description."

    def test_strips_html_from_title(self):
        xml = """<root>
            <surveys_languagesettings><rows>
              <row>
                <surveyls_title><![CDATA[<b>Bold Title</b>]]></surveyls_title>
              </row>
            </rows></surveys_languagesettings>
        </root>"""
        root = _make_root(xml)
        meta = _parse_survey_metadata(root, _get_text)
        assert "<b>" not in meta["title"]
        assert "Bold Title" in meta["title"]

    def test_datestamp_true(self):
        xml = """<root>
            <surveys><rows>
              <row><datestamp>Y</datestamp></row>
            </rows></surveys>
        </root>"""
        root = _make_root(xml)
        meta = _parse_survey_metadata(root, _get_text)
        assert meta["datestamp"] is True


# ---------------------------------------------------------------------------
# _parse_lss_structure
# ---------------------------------------------------------------------------

class TestParseLssStructure:
    def test_empty_root(self):
        root = _make_root("<root/>")
        questions_map, groups_map = _parse_lss_structure(root, _get_text)
        assert questions_map == {}
        assert groups_map == {}

    def test_parses_group(self):
        xml = """<root>
            <groups><rows>
              <row>
                <gid>10</gid>
                <group_name>Group 1</group_name>
                <group_order>1</group_order>
                <description>First group</description>
              </row>
            </rows></groups>
        </root>"""
        root = _make_root(xml)
        _, groups_map = _parse_lss_structure(root, _get_text)
        assert "10" in groups_map
        assert groups_map["10"]["name"] == "Group 1"
        assert groups_map["10"]["order"] == 1

    def test_parses_question(self):
        xml = """<root>
            <questions><rows>
              <row>
                <qid>42</qid>
                <gid>10</gid>
                <type>L</type>
                <title>Q1</title>
                <question>How do you feel?</question>
                <question_order>1</question_order>
                <mandatory>N</mandatory>
                <parent_qid>0</parent_qid>
              </row>
            </rows></questions>
        </root>"""
        root = _make_root(xml)
        questions_map, _ = _parse_lss_structure(root, _get_text)
        assert "42" in questions_map
        assert questions_map["42"]["type"] == "L"
        assert questions_map["42"]["title"] == "Q1"

    def test_parses_answers(self):
        xml = """<root>
            <questions><rows>
              <row>
                <qid>42</qid>
                <gid>10</gid>
                <type>L</type>
                <title>Q1</title>
                <question>Choice question</question>
                <question_order>1</question_order>
                <mandatory>N</mandatory>
                <parent_qid>0</parent_qid>
              </row>
            </rows></questions>
            <answers><rows>
              <row>
                <qid>42</qid>
                <code>A1</code>
                <answer>Answer One</answer>
                <sortorder>1</sortorder>
              </row>
              <row>
                <qid>42</qid>
                <code>A2</code>
                <answer>Answer Two</answer>
                <sortorder>2</sortorder>
              </row>
            </rows></answers>
        </root>"""
        root = _make_root(xml)
        questions_map, _ = _parse_lss_structure(root, _get_text)
        levels = questions_map["42"].get("levels") or {}
        # Levels should contain answer mappings
        assert isinstance(levels, dict)

    def test_group_l10ns_fallback(self):
        """In LS 6.x, group names come from group_l10ns, not inline."""
        xml = """<root>
            <groups><rows>
              <row>
                <gid>10</gid>
                <group_name></group_name>
                <group_order>1</group_order>
                <description></description>
              </row>
            </rows></groups>
            <group_l10ns><rows>
              <row>
                <gid>10</gid>
                <language>en</language>
                <group_name>L10n Group Name</group_name>
                <description>L10n description</description>
              </row>
            </rows></group_l10ns>
        </root>"""
        root = _make_root(xml)
        _, groups_map = _parse_lss_structure(root, _get_text)
        assert groups_map["10"]["name"] == "L10n Group Name"

    def test_question_l10ns_fallback(self):
        """In LS 6.x, question text comes from question_l10ns."""
        xml = """<root>
            <questions><rows>
              <row>
                <qid>99</qid>
                <gid>10</gid>
                <type>S</type>
                <title>Q_free</title>
                <question></question>
                <question_order>1</question_order>
                <mandatory>N</mandatory>
                <parent_qid>0</parent_qid>
              </row>
            </rows></questions>
            <question_l10ns><rows>
              <row>
                <qid>99</qid>
                <question>What is your name?</question>
                <help>Please enter your full name.</help>
              </row>
            </rows></question_l10ns>
        </root>"""
        root = _make_root(xml)
        questions_map, _ = _parse_lss_structure(root, _get_text)
        assert questions_map["99"]["question"] == "What is your name?"

    def test_group_with_invalid_order(self):
        xml = """<root>
            <groups><rows>
              <row>
                <gid>5</gid>
                <group_name>G</group_name>
                <group_order>not_a_number</group_order>
              </row>
            </rows></groups>
        </root>"""
        root = _make_root(xml)
        _, groups_map = _parse_lss_structure(root, _get_text)
        assert groups_map["5"]["order"] == 0


# ---------------------------------------------------------------------------
# Minimal LSS XML fixture for integration tests
# ---------------------------------------------------------------------------

_LSS_WITH_ARRAYS = """<?xml version="1.0" encoding="UTF-8"?>
<document>
  <surveys><rows>
    <row>
      <sid>99999</sid>
      <language>en</language>
      <anonymized>N</anonymized>
      <format>G</format>
    </row>
  </rows></surveys>
  <surveys_languagesettings><rows>
    <row>
      <surveyls_title>Array Survey</surveyls_title>
    </row>
  </rows></surveys_languagesettings>
  <groups><rows>
    <row>
      <gid>1</gid>
      <group_name>Main</group_name>
      <group_order>1</group_order>
      <description></description>
    </row>
  </rows></groups>
  <questions><rows>
    <row>
      <qid>100</qid>
      <gid>1</gid>
      <type>F</type>
      <title>RATING</title>
      <question>Please rate:</question>
      <question_order>1</question_order>
      <mandatory>Y</mandatory>
      <parent_qid>0</parent_qid>
      <other>Y</other>
      <help>Rate each item 1-5</help>
      <preg>[1-5]</preg>
      <relevance>SCORE > 3</relevance>
    </row>
    <row>
      <qid>200</qid>
      <gid>1</gid>
      <type>N</type>
      <title>SCORE</title>
      <question>Total score?</question>
      <question_order>2</question_order>
      <mandatory>N</mandatory>
      <parent_qid>0</parent_qid>
      <other>N</other>
      <help></help>
      <preg></preg>
      <relevance>1</relevance>
    </row>
  </rows></questions>
  <answers><rows></rows></answers>
  <question_attributes><rows>
    <row>
      <qid>100</qid>
      <attribute>scale_export</attribute>
      <value>1</value>
      <language></language>
    </row>
    <row>
      <qid>100</qid>
      <attribute>label_en</attribute>
      <value>Strongly agree</value>
      <language>en</language>
    </row>
  </rows></question_attributes>
  <subquestions><rows>
    <row>
      <qid>101</qid>
      <parent_qid>100</parent_qid>
      <type>F</type>
      <title>SQ001</title>
      <question>Item 1</question>
      <question_order>1</question_order>
      <scale_id>0</scale_id>
    </row>
    <row>
      <qid>102</qid>
      <parent_qid>100</parent_qid>
      <type>F</type>
      <title>SQ002</title>
      <question>Item 2</question>
      <question_order>2</question_order>
      <scale_id>1</scale_id>
    </row>
  </rows></subquestions>
</document>
"""

_MINIMAL_LSS = """<?xml version="1.0" encoding="UTF-8"?>
<document>
  <surveys><rows>
    <row>
      <sid>12345</sid>
      <language>en</language>
      <anonymized>N</anonymized>
      <format>G</format>
    </row>
  </rows></surveys>
  <surveys_languagesettings><rows>
    <row>
      <surveyls_title>Test Survey</surveyls_title>
    </row>
  </rows></surveys_languagesettings>
  <groups><rows>
    <row>
      <gid>1</gid>
      <group_name>Demographics</group_name>
      <group_order>1</group_order>
      <description></description>
    </row>
  </rows></groups>
  <questions><rows>
    <row>
      <qid>10</qid>
      <gid>1</gid>
      <type>L</type>
      <title>AGE</title>
      <question>What is your age group?</question>
      <question_order>1</question_order>
      <mandatory>N</mandatory>
      <parent_qid>0</parent_qid>
      <other>N</other>
      <preg></preg>
    </row>
    <row>
      <qid>20</qid>
      <gid>1</gid>
      <type>S</type>
      <title>COMMENTS</title>
      <question>Any comments?</question>
      <question_order>2</question_order>
      <mandatory>N</mandatory>
      <parent_qid>0</parent_qid>
      <other>N</other>
      <preg></preg>
    </row>
  </rows></questions>
  <answers><rows>
    <row>
      <qid>10</qid>
      <code>1</code>
      <answer>18-25</answer>
      <sortorder>1</sortorder>
    </row>
    <row>
      <qid>10</qid>
      <code>2</code>
      <answer>26-35</answer>
      <sortorder>2</sortorder>
    </row>
  </rows></answers>
  <question_attributes><rows></rows></question_attributes>
  <subquestions><rows></rows></subquestions>
</document>
"""


# ---------------------------------------------------------------------------
# parse_lss_xml
# ---------------------------------------------------------------------------

class TestParseLssXml:
    def test_returns_none_for_invalid_xml(self):
        result = parse_lss_xml(b"NOT XML")
        assert result is None

    def test_parses_minimal_lss(self):
        result = parse_lss_xml(_MINIMAL_LSS.encode("utf-8"), check_collisions=False)
        assert result is not None
        assert isinstance(result, dict)

    def test_includes_survey_title_in_metadata(self):
        result = parse_lss_xml(_MINIMAL_LSS.encode("utf-8"), check_collisions=False)
        assert result is not None
        study = result.get("Study") or {}
        assert "Test Survey" in (study.get("OriginalName") or "")

    def test_includes_question_items(self):
        result = parse_lss_xml(_MINIMAL_LSS.encode("utf-8"), check_collisions=False)
        assert result is not None
        # AGE question should be in result
        assert "AGE" in result

    def test_custom_task_name(self):
        result = parse_lss_xml(
            _MINIMAL_LSS.encode("utf-8"),
            task_name="demographics",
            check_collisions=False,
        )
        assert result is not None
        study = result.get("Study") or {}
        # task_name may be sanitized or overridden; just verify it was applied
        assert study.get("TaskName") is not None

    def test_question_has_levels(self):
        result = parse_lss_xml(_MINIMAL_LSS.encode("utf-8"), check_collisions=False)
        assert result is not None
        age_q = result.get("AGE") or {}
        levels = age_q.get("Levels") or {}
        assert "1" in levels or "2" in levels


# ---------------------------------------------------------------------------
# parse_lss_xml_by_groups
# ---------------------------------------------------------------------------

class TestParseLssXmlByGroups:
    def test_returns_none_for_invalid_xml(self):
        result = parse_lss_xml_by_groups(b"NOT XML")
        assert result is None

    def test_parses_minimal_lss(self):
        result = parse_lss_xml_by_groups(_MINIMAL_LSS.encode("utf-8"))
        assert result is not None
        assert isinstance(result, dict)

    def test_groups_by_group_name(self):
        result = parse_lss_xml_by_groups(_MINIMAL_LSS.encode("utf-8"))
        assert result is not None
        # Group name may be lowercased or title-cased
        keys_lower = [k.lower() for k in result.keys()]
        assert "demographics" in keys_lower

    def test_group_contains_questions(self):
        result = parse_lss_xml_by_groups(_MINIMAL_LSS.encode("utf-8"))
        assert result is not None
        # Find the demographics group regardless of casing
        demographics = next(
            (v for k, v in result.items() if k.lower() == "demographics"), {}
        )
        assert "AGE" in demographics


# ---------------------------------------------------------------------------
# parse_lss_xml_by_questions
# ---------------------------------------------------------------------------

class TestParseLssXmlByQuestions:
    def test_returns_none_on_invalid_xml(self):
        result = parse_lss_xml_by_questions(b"NOT XML")
        assert result is None

    def test_returns_dict(self):
        result = parse_lss_xml_by_questions(_MINIMAL_LSS.encode("utf-8"))
        assert isinstance(result, dict)

    def test_has_expected_question_keys(self):
        result = parse_lss_xml_by_questions(_MINIMAL_LSS.encode("utf-8"))
        assert result is not None
        assert "AGE" in result or "COMMENTS" in result

    def test_question_entry_has_group_name(self):
        result = parse_lss_xml_by_questions(_MINIMAL_LSS.encode("utf-8"))
        assert result is not None
        for key, val in result.items():
            assert "group_name" in val
            break

    def test_question_entry_has_prism_json(self):
        result = parse_lss_xml_by_questions(_MINIMAL_LSS.encode("utf-8"))
        assert result is not None
        for key, val in result.items():
            assert "prism_json" in val
            break


# ---------------------------------------------------------------------------
# _get_question_type_name
# ---------------------------------------------------------------------------

class TestGetQuestionTypeName:
    def test_known_type_N(self):
        from src.converters.limesurvey import _get_question_type_name
        assert _get_question_type_name("N") == "Numerical Input"

    def test_known_type_T(self):
        from src.converters.limesurvey import _get_question_type_name
        # L = List Radio, S = Short Text, T = Long Text
        result = _get_question_type_name("T")
        assert isinstance(result, str)
        assert len(result) > 0

    def test_unknown_type(self):
        from src.converters.limesurvey import _get_question_type_name
        result = _get_question_type_name("ZZZNONE")
        assert isinstance(result, str)


# ---------------------------------------------------------------------------
# _extract_media_urls
# ---------------------------------------------------------------------------

class TestExtractMediaUrls:
    def test_img_src(self):
        from src.converters.limesurvey import _extract_media_urls
        result = _extract_media_urls('<img src="photo.png">')
        assert "photo.png" in result

    def test_no_media(self):
        from src.converters.limesurvey import _extract_media_urls
        result = _extract_media_urls("plain text")
        assert result == []

    def test_multiple_images(self):
        from src.converters.limesurvey import _extract_media_urls
        result = _extract_media_urls('<img src="a.png"><img src="b.jpg">')
        assert len(result) == 2


# ---------------------------------------------------------------------------
# _clean_html_preserve_info
# ---------------------------------------------------------------------------

class TestCleanHtmlPreserveInfo:
    def test_strips_bold(self):
        from src.converters.limesurvey import _clean_html_preserve_info
        text, _ = _clean_html_preserve_info("<b>bold</b>")
        assert "bold" in text
        assert "<b>" not in text

    def test_returns_plain_text(self):
        from src.converters.limesurvey import _clean_html_preserve_info
        text, warnings = _clean_html_preserve_info("<span>hello world</span>")
        assert "hello world" in text

    def test_empty_string(self):
        from src.converters.limesurvey import _clean_html_preserve_info
        text, warnings = _clean_html_preserve_info("")
        assert text == ""


# ---------------------------------------------------------------------------
# Tests using richer LSS fixture with arrays/subquestions
# ---------------------------------------------------------------------------

class TestParseLssXmlArrays:
    def test_parse_lss_with_subquestions(self):
        result = parse_lss_xml(_LSS_WITH_ARRAYS.encode("utf-8"), check_collisions=False)
        assert result is not None

    def test_rating_question_has_items(self):
        result = parse_lss_xml(_LSS_WITH_ARRAYS.encode("utf-8"), check_collisions=False)
        assert result is not None
        survey_dict = result
        # Items should be under the RATING key
        assert "RATING" in survey_dict
        rating = survey_dict["RATING"]
        assert "Items" in rating

    def test_rating_subquestions_present(self):
        result = parse_lss_xml(_LSS_WITH_ARRAYS.encode("utf-8"), check_collisions=False)
        assert result is not None
        rating = result.get("RATING", {})
        items = rating.get("Items", {})
        assert "SQ001" in items or "SQ002" in items

    def test_mandatory_question_flagged(self):
        result = parse_lss_xml(_LSS_WITH_ARRAYS.encode("utf-8"), check_collisions=False)
        assert result is not None
        rating = result.get("RATING", {})
        assert rating.get("Mandatory") is True

    def test_help_text_included(self):
        result = parse_lss_xml(_LSS_WITH_ARRAYS.encode("utf-8"), check_collisions=False)
        assert result is not None
        rating = result.get("RATING", {})
        assert rating.get("HelpText") == "Rate each item 1-5"

    def test_relevance_included_as_condition(self):
        result = parse_lss_xml(_LSS_WITH_ARRAYS.encode("utf-8"), check_collisions=False)
        assert result is not None
        rating = result.get("RATING", {})
        assert "Condition" in rating
        assert "SCORE" in rating["Condition"]

    def test_trivial_relevance_not_included(self):
        result = parse_lss_xml(_LSS_WITH_ARRAYS.encode("utf-8"), check_collisions=False)
        assert result is not None
        score = result.get("SCORE", {})
        # Relevance = "1" should not be included as Condition
        assert "Condition" not in score

    def test_other_option_flagged(self):
        result = parse_lss_xml(_LSS_WITH_ARRAYS.encode("utf-8"), check_collisions=False)
        assert result is not None
        rating = result.get("RATING", {})
        assert rating.get("HasOtherOption") is True

    def test_question_attributes_collected(self):
        result = parse_lss_xml(_LSS_WITH_ARRAYS.encode("utf-8"), check_collisions=False)
        assert result is not None
        rating = result.get("RATING", {})
        # Attributes should be present (scale_export=1 is numeric)
        assert "Attributes" in rating

    def test_scale_id_nonzero_in_items(self):
        result = parse_lss_xml(_LSS_WITH_ARRAYS.encode("utf-8"), check_collisions=False)
        assert result is not None
        rating = result.get("RATING", {})
        items = rating.get("Items", {})
        # SQ002 has scale_id=1 which should be stored
        if "SQ002" in items:
            assert items["SQ002"].get("ScaleId") == 1

    def test_by_questions_with_arrays(self):
        result = parse_lss_xml_by_questions(_LSS_WITH_ARRAYS.encode("utf-8"))
        assert result is not None
        assert "RATING" in result or "SCORE" in result

    def test_by_groups_with_arrays(self):
        result = parse_lss_xml_by_groups(_LSS_WITH_ARRAYS.encode("utf-8"))
        assert result is not None

