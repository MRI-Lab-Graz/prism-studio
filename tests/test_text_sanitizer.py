"""
Tests for text_sanitizer module.

These tests ensure that survey text is properly cleaned of embedded annotations
before being displayed to participants.
"""

import pytest
import sys
import os

# Add app directory to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "app"))

from src.text_sanitizer import (
    sanitize_display_text,
    sanitize_answer_text,
    sanitize_question_text,
    has_annotations,
    list_annotations,
    clean_levels_dict,
)


class TestSanitizeDisplayText:
    """Tests for the main sanitize_display_text function."""

    def test_score_annotation_basic(self):
        """Test basic {score=N} removal."""
        assert sanitize_display_text("{score=0} very rarely") == "very rarely"
        assert sanitize_display_text("{score=1} often") == "often"
        assert sanitize_display_text("{score=5} always") == "always"

    def test_score_annotation_negative(self):
        """Test negative score values."""
        assert sanitize_display_text("{score=-1} negative") == "negative"
        assert sanitize_display_text("{score=-100} very negative") == "very negative"

    def test_score_annotation_large_numbers(self):
        """Test large score values."""
        assert sanitize_display_text("{score=100} maximum") == "maximum"
        assert sanitize_display_text("{score=50} half") == "half"

    def test_score_annotation_with_spaces(self):
        """Test score annotations with varying whitespace."""
        assert sanitize_display_text("{score = 0} rarely") == "rarely"
        assert sanitize_display_text("{score= 1} sometimes") == "sometimes"
        assert sanitize_display_text("{score =2} often") == "often"

    def test_score_annotation_case_insensitive(self):
        """Test case insensitivity."""
        assert sanitize_display_text("{SCORE=0} rarely") == "rarely"
        assert sanitize_display_text("{Score=1} often") == "often"
        assert sanitize_display_text("{ScOrE=2} always") == "always"

    def test_reverse_annotation(self):
        """Test {reverse} marker removal."""
        assert sanitize_display_text("{reverse} I feel sad") == "I feel sad"
        assert sanitize_display_text("{REVERSE} I feel happy") == "I feel happy"

    def test_optional_annotation(self):
        """Test {optional} marker removal."""
        assert sanitize_display_text("{optional} Additional comments") == "Additional comments"

    def test_multiple_annotations(self):
        """Test removal of multiple annotations."""
        assert sanitize_display_text("{score=1} {reverse} I feel good") == "I feel good"

    def test_no_annotations(self):
        """Test text without annotations passes through unchanged."""
        assert sanitize_display_text("Normal text") == "Normal text"
        assert sanitize_display_text("Strongly agree") == "Strongly agree"

    def test_empty_and_none(self):
        """Test handling of empty and None values."""
        assert sanitize_display_text("") == ""
        assert sanitize_display_text(None) == ""

    def test_whitespace_normalization(self):
        """Test that whitespace is normalized after annotation removal."""
        assert sanitize_display_text("{score=0}  double space") == "double space"
        assert sanitize_display_text("  {score=0} leading space") == "leading space"
        assert sanitize_display_text("{score=0} trailing space  ") == "trailing space"

    def test_preserves_limesurvey_expressions(self):
        """Test that LimeSurvey expression syntax is preserved."""
        # These should NOT be stripped
        assert "{Q1.NAOK}" in sanitize_display_text("Value: {Q1.NAOK}")
        assert "{TOKEN:FIRSTNAME}" in sanitize_display_text("Hello {TOKEN:FIRSTNAME}")

    def test_html_comments_removed(self):
        """Test that HTML comments are removed."""
        assert sanitize_display_text("Text <!-- comment --> here") == "Text here"

    def test_generic_annotation_pattern(self):
        """Test generic {key=value} pattern removal."""
        # This catches future PsyToolkit-style annotations
        assert sanitize_display_text("{weight=2} Heavy item") == "Heavy item"
        assert sanitize_display_text("{category=anxiety} I feel worried") == "I feel worried"


class TestSanitizeAnswerText:
    """Tests for sanitize_answer_text (wrapper function)."""

    def test_same_as_display_text(self):
        """Test that answer text sanitization works correctly."""
        assert sanitize_answer_text("{score=0} very rarely") == "very rarely"
        assert sanitize_answer_text("{score=1} often") == "often"


class TestSanitizeQuestionText:
    """Tests for sanitize_question_text (wrapper function)."""

    def test_basic_cleaning(self):
        """Test question text sanitization."""
        assert sanitize_question_text("{reverse} I feel sad") == "I feel sad"


class TestHasAnnotations:
    """Tests for has_annotations function."""

    def test_detects_score(self):
        """Test detection of score annotations."""
        assert has_annotations("{score=0} rarely") is True
        assert has_annotations("{score=1} often") is True

    def test_detects_reverse(self):
        """Test detection of reverse marker."""
        assert has_annotations("{reverse} text") is True

    def test_no_annotations(self):
        """Test that clean text returns False."""
        assert has_annotations("Normal text") is False
        assert has_annotations("Strongly agree") is False

    def test_empty_and_none(self):
        """Test empty and None values."""
        assert has_annotations("") is False
        assert has_annotations(None) is False


class TestListAnnotations:
    """Tests for list_annotations function."""

    def test_lists_score_annotations(self):
        """Test listing of score annotations."""
        annotations = list_annotations("{score=0} rarely")
        assert len(annotations) >= 1
        assert any("score" in desc.lower() for _, desc in annotations)

    def test_empty_for_clean_text(self):
        """Test that clean text returns empty list."""
        assert list_annotations("Normal text") == []

    def test_multiple_annotations(self):
        """Test listing multiple annotations."""
        annotations = list_annotations("{score=1} {reverse} text")
        assert len(annotations) >= 2


class TestCleanLevelsDict:
    """Tests for clean_levels_dict function."""

    def test_simple_dict(self):
        """Test cleaning simple level dictionary."""
        levels = {
            "0": "{score=0} very rarely",
            "1": "{score=0} rarely",
            "2": "{score=1} sometimes",
        }
        cleaned = clean_levels_dict(levels)
        assert cleaned["0"] == "very rarely"
        assert cleaned["1"] == "rarely"
        assert cleaned["2"] == "sometimes"

    def test_multilingual_dict(self):
        """Test cleaning multilingual level dictionary."""
        levels = {
            "0": {"en": "{score=0} very rarely", "de": "{score=0} sehr selten"},
            "1": {"en": "{score=1} often", "de": "{score=1} oft"},
        }
        cleaned = clean_levels_dict(levels)
        assert cleaned["0"]["en"] == "very rarely"
        assert cleaned["0"]["de"] == "sehr selten"
        assert cleaned["1"]["en"] == "often"
        assert cleaned["1"]["de"] == "oft"

    def test_empty_dict(self):
        """Test handling of empty dictionary."""
        assert clean_levels_dict({}) == {}
        assert clean_levels_dict(None) is None


class TestRealWorldExamples:
    """Test with real examples from PsyToolkit templates."""

    def test_bfas_example(self):
        """Test BFAS (Bergen Facebook Addiction Scale) answer format."""
        # Actual format from survey-bfas.json
        assert sanitize_answer_text("{score=0} very rarely") == "very rarely"
        assert sanitize_answer_text("{score=0} rarely") == "rarely"
        assert sanitize_answer_text("{score=1} sometimes") == "sometimes"
        assert sanitize_answer_text("{score=1} often") == "often"
        assert sanitize_answer_text("{score=1} very often") == "very often"

    def test_dass_example(self):
        """Test DASS (Depression Anxiety Stress Scale) answer format."""
        # Common Likert scale with scoring
        assert sanitize_answer_text("{score=0} Did not apply to me at all") == "Did not apply to me at all"
        assert sanitize_answer_text("{score=1} Applied to me to some degree") == "Applied to me to some degree"
        assert sanitize_answer_text("{score=2} Applied to me a considerable degree") == "Applied to me a considerable degree"
        assert sanitize_answer_text("{score=3} Applied to me very much") == "Applied to me very much"


# Import subquestion sanitizer for testing
try:
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "app"))
    from src.limesurvey_exporter import _sanitize_subquestion_code, LS_SUBQUESTION_CODE_MAX_LENGTH
    SUBQUESTION_TESTS_AVAILABLE = True
except ImportError:
    SUBQUESTION_TESTS_AVAILABLE = False


@pytest.mark.skipif(not SUBQUESTION_TESTS_AVAILABLE, reason="LimeSurvey exporter not available")
class TestSubquestionCodeSanitization:
    """Tests for LimeSurvey subquestion code sanitization."""

    def test_basic_code_within_limit(self):
        """Test codes already within 5-char limit."""
        used = set()
        assert _sanitize_subquestion_code("Q1", used, None, 1) == "Q1"
        assert _sanitize_subquestion_code("BFA01", used, None, 1) == "BFA01"

    def test_long_code_truncated(self):
        """Test that long codes are truncated to 5 chars."""
        used = set()
        result = _sanitize_subquestion_code("BFAS01", used, None, 1)
        assert len(result) <= LS_SUBQUESTION_CODE_MAX_LENGTH
        assert result == "BFA01"

    def test_very_long_code_truncated(self):
        """Test very long codes are truncated."""
        used = set()
        result = _sanitize_subquestion_code("PANAS_POSITIVE_01", used, None, 1)
        assert len(result) <= LS_SUBQUESTION_CODE_MAX_LENGTH

    def test_run_suffix_fits_in_limit(self):
        """Test that run suffix codes fit within 5 chars."""
        used = set()
        result = _sanitize_subquestion_code("BFAS01", used, 2, 1)
        assert len(result) <= LS_SUBQUESTION_CODE_MAX_LENGTH
        assert "R2" in result or "R" in result  # Should contain run indicator

    def test_multiple_runs_unique(self):
        """Test that run 1 and run 2 produce different codes."""
        used1 = set()
        used2 = set()
        code1 = _sanitize_subquestion_code("BFAS01", used1, 1, 1)
        code2 = _sanitize_subquestion_code("BFAS01", used2, 2, 1)
        assert code1 != code2
        assert len(code1) <= LS_SUBQUESTION_CODE_MAX_LENGTH
        assert len(code2) <= LS_SUBQUESTION_CODE_MAX_LENGTH

    def test_uniqueness_within_matrix(self):
        """Test that codes are unique within a matrix."""
        used = set()
        codes = []
        for i in range(1, 7):
            code = _sanitize_subquestion_code(f"BFAS0{i}", used, None, i)
            assert code not in codes, f"Duplicate code: {code}"
            codes.append(code)
            used.add(code)
        assert len(codes) == 6

    def test_special_characters_removed(self):
        """Test that special characters are removed."""
        used = set()
        result = _sanitize_subquestion_code("LOT_R_01", used, None, 1)
        assert "_" not in result
        assert len(result) <= LS_SUBQUESTION_CODE_MAX_LENGTH

    def test_starts_with_letter(self):
        """Test that codes start with a letter."""
        used = set()
        result = _sanitize_subquestion_code("01BFAS", used, None, 1)
        assert result[0].isalpha()

    def test_fallback_sequential(self):
        """Test fallback to sequential codes when collisions occur."""
        # Fill up potential codes to trigger fallback
        used = {"BFA01", "BFA02", "BFA03", "SQ001", "SQ002"}
        result = _sanitize_subquestion_code("BFAS01", used, None, 1)
        assert result not in used
        assert len(result) <= LS_SUBQUESTION_CODE_MAX_LENGTH


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
