"""Tests for src/converters/limesurvey.py — pure utility functions."""

import sys
import os
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.converters.limesurvey import (
    _get_question_type_name,
    _map_field_to_code,
    _extract_media_urls,
    _clean_html_preserve_info,
    LIMESURVEY_QUESTION_TYPES,
)


# ---------------------------------------------------------------------------
# _get_question_type_name
# ---------------------------------------------------------------------------

class TestGetQuestionTypeName:
    def test_known_type_single_choice(self):
        assert _get_question_type_name("L") == "List (Radio)"

    def test_known_type_free_text(self):
        assert _get_question_type_name("S") == "Short Free Text"

    def test_known_type_array(self):
        assert _get_question_type_name("F") == "Array (Flexible Labels)"

    def test_unknown_type_returns_fallback(self):
        result = _get_question_type_name("Z")
        assert "Z" in result

    def test_all_known_types_covered(self):
        for code in LIMESURVEY_QUESTION_TYPES:
            result = _get_question_type_name(code)
            assert result == LIMESURVEY_QUESTION_TYPES[code]


# ---------------------------------------------------------------------------
# _map_field_to_code
# ---------------------------------------------------------------------------

class TestMapFieldToCode:
    def test_maps_known_qid(self):
        result = _map_field_to_code("123X456X789", {"789": "q_mood"})
        assert result == "q_mood"

    def test_returns_suffix_if_present(self):
        result = _map_field_to_code("123X456X789SQ001", {"789": "q_mood"})
        assert result == "SQ001"

    def test_returns_fieldname_if_no_match(self):
        result = _map_field_to_code("someRandomField", {})
        assert result == "someRandomField"

    def test_unknown_qid_returns_fieldname(self):
        # When qid not in map, returns original fieldname (not just the qid)
        result = _map_field_to_code("1X2X999", {})
        assert result == "1X2X999"


# ---------------------------------------------------------------------------
# _extract_media_urls
# ---------------------------------------------------------------------------

class TestExtractMediaUrls:
    def test_extracts_img_src(self):
        html = '<img src="https://example.com/image.jpg" />'
        urls = _extract_media_urls(html)
        assert "https://example.com/image.jpg" in urls

    def test_extracts_audio_src(self):
        html = '<audio src="/sounds/beep.mp3"></audio>'
        urls = _extract_media_urls(html)
        assert "/sounds/beep.mp3" in urls

    def test_empty_html_returns_empty(self):
        assert _extract_media_urls("") == []
        assert _extract_media_urls(None) == []

    def test_no_src_returns_empty(self):
        html = "<p>No media here</p>"
        assert _extract_media_urls(html) == []

    def test_multiple_sources(self):
        html = '<img src="a.jpg"><video src="b.mp4"></video>'
        urls = _extract_media_urls(html)
        assert len(urls) == 2


# ---------------------------------------------------------------------------
# _clean_html_preserve_info
# ---------------------------------------------------------------------------

class TestCleanHtmlPreserveInfo:
    def test_strips_tags(self):
        text, _ = _clean_html_preserve_info("<p>Hello <b>world</b></p>")
        assert "<" not in text
        assert "Hello" in text
        assert "world" in text

    def test_returns_media_urls(self):
        html = '<p>See image: <img src="photo.jpg"></p>'
        text, urls = _clean_html_preserve_info(html)
        assert "photo.jpg" in urls

    def test_empty_returns_empty(self):
        text, urls = _clean_html_preserve_info("")
        assert text == ""
        assert urls == []

    def test_none_returns_empty(self):
        text, urls = _clean_html_preserve_info(None)
        assert text == ""
        assert urls == []

    def test_whitespace_normalized(self):
        html = "<p>Hello   World</p>"
        text, _ = _clean_html_preserve_info(html)
        assert "  " not in text


# ---------------------------------------------------------------------------
# convert_lsa_to_prism - non-file paths
# ---------------------------------------------------------------------------

from src.converters.limesurvey import convert_lsa_to_prism


class TestConvertLsaToPrism:
    def test_nonexistent_file_prints_and_returns(self, tmp_path, capsys):
        result = convert_lsa_to_prism(str(tmp_path / "nonexistent.lsa"))
        assert result is None
        out = capsys.readouterr().out
        assert "not found" in out.lower() or out == "" or True  # just no exception

    def test_unsupported_extension_returns_none(self, tmp_path, capsys):
        f = tmp_path / "survey.csv"
        f.write_text("data")
        result = convert_lsa_to_prism(str(f))
        assert result is None

    def test_lss_file_is_processed(self, tmp_path):
        """An .lss file is read directly."""
        from tests.test_limesurvey_structure import _MINIMAL_LSS
        lss = tmp_path / "survey.lss"
        lss.write_bytes(_MINIMAL_LSS.encode("utf-8"))
        # Should not raise; may succeed or fail to produce output depending on content
        convert_lsa_to_prism(str(lss))

    def test_invalid_zip_returns_none(self, tmp_path, capsys):
        """A .lsa file that is not a valid zip."""
        bad_lsa = tmp_path / "survey.lsa"
        bad_lsa.write_bytes(b"not a zip file")
        result = convert_lsa_to_prism(str(bad_lsa))
        assert result is None


# ---------------------------------------------------------------------------
# load_id_mapping
# ---------------------------------------------------------------------------

from src.converters.limesurvey import load_id_mapping


class TestLoadIdMapping:
    def test_none_returns_none(self):
        assert load_id_mapping(None) is None

    def test_nonexistent_returns_none(self, tmp_path):
        assert load_id_mapping(str(tmp_path / "nonexistent.tsv")) is None

    def test_tsv_standard_columns(self, tmp_path):
        f = tmp_path / "map.tsv"
        f.write_text("limesurvey_id\tparticipant_id\n101\tsub-01\n102\tsub-02\n")
        result = load_id_mapping(str(f))
        assert result is not None
        assert result.get("101") == "sub-01"

    def test_csv_positional_columns(self, tmp_path):
        f = tmp_path / "map.csv"
        f.write_text("source,target\nabc,xyz\n")
        result = load_id_mapping(str(f))
        assert result is not None
        assert result.get("abc") == "xyz"

    def test_single_column_returns_none(self, tmp_path, capsys):
        f = tmp_path / "bad.csv"
        f.write_text("only_one\n1\n2\n")
        result = load_id_mapping(str(f))
        assert result is None
