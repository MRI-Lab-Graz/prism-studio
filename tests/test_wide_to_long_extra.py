"""Tests for src/converters/wide_to_long.py — wide-to-long column conversion."""

import sys
import os
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.converters.wide_to_long import (
    detect_wide_session_prefixes,
    inspect_wide_to_long_columns,
    convert_wide_to_long_dataframe,
    _find_indicator_spans,
    _strip_indicator_from_column_name,
    _format_ambiguous_indicator_error,
)


# ---------------------------------------------------------------------------
# detect_wide_session_prefixes
# ---------------------------------------------------------------------------

class TestDetectWideSessionPrefixes:
    def test_t_prefix_detected(self):
        cols = ["T1_score", "T1_age", "T1_weight", "T2_score", "T2_age", "T2_weight"]
        result = detect_wide_session_prefixes(cols, min_count=2)
        assert "T1" in result
        assert "T2" in result

    def test_below_min_count_not_detected(self):
        cols = ["T1_score", "T1_age"]  # only 2, default min_count=3
        result = detect_wide_session_prefixes(cols)
        assert result == []

    def test_suffix_pattern_detected(self):
        cols = ["score_pre", "age_pre", "weight_pre", "score_post", "age_post", "weight_post"]
        result = detect_wide_session_prefixes(cols, min_count=3)
        assert any("pre" in r.lower() for r in result)

    def test_empty_columns(self):
        assert detect_wide_session_prefixes([]) == []

    def test_wave_prefix(self):
        cols = [f"wave1_{i}" for i in range(5)] + [f"wave2_{i}" for i in range(5)]
        result = detect_wide_session_prefixes(cols, min_count=3)
        assert "wave1" in result or "wave1".lower() in [r.lower() for r in result]


# ---------------------------------------------------------------------------
# _find_indicator_spans
# ---------------------------------------------------------------------------

class TestFindIndicatorSpans:
    def test_prefix_match(self):
        spans = _find_indicator_spans("T1_score", "T1")
        assert len(spans) == 1

    def test_suffix_match(self):
        spans = _find_indicator_spans("score_T1", "_T1")
        assert len(spans) == 1

    def test_no_match(self):
        spans = _find_indicator_spans("score_T2", "T1")
        assert spans == []

    def test_embedded_not_matched_without_boundary(self):
        # T1 inside T12 — next char is alnum, should be excluded
        spans = _find_indicator_spans("T12_score", "T1")
        assert spans == []

    def test_empty_indicator(self):
        spans = _find_indicator_spans("T1_score", "")
        assert spans == []


# ---------------------------------------------------------------------------
# _strip_indicator_from_column_name
# ---------------------------------------------------------------------------

class TestStripIndicatorFromColumnName:
    def test_prefix_stripped(self):
        result = _strip_indicator_from_column_name("T1_score", "T1")
        assert result == "score"

    def test_suffix_stripped(self):
        result = _strip_indicator_from_column_name("score_T1", "_T1")
        assert result == "score"

    def test_no_match_unchanged(self):
        result = _strip_indicator_from_column_name("age", "T1")
        assert result == "age"


# ---------------------------------------------------------------------------
# inspect_wide_to_long_columns
# ---------------------------------------------------------------------------

class TestInspectWideToLongColumns:
    def test_basic_prefix_mapping(self):
        cols = ["T1_score", "T2_score", "participant_id"]
        result = inspect_wide_to_long_columns(cols, session_indicators=["T1", "T2"])
        assert "T1_score" in result["rename_map"]
        assert result["rename_map"]["T1_score"] == "score"

    def test_shared_columns_identified(self):
        cols = ["T1_score", "T2_score", "participant_id"]
        result = inspect_wide_to_long_columns(cols, session_indicators=["T1", "T2"])
        assert "participant_id" in result["shared_columns"]

    def test_no_indicators_raises(self):
        with pytest.raises(ValueError, match="No session indicators"):
            inspect_wide_to_long_columns(["T1_score"], session_indicators=[])

    def test_ambiguous_multiple_indicators(self):
        # Column matches both T1 and T12 — ambiguous if T12 also matches
        cols = ["T1_T2_score"]
        result = inspect_wide_to_long_columns(cols, session_indicators=["T1", "T2"])
        assert len(result["ambiguous_columns"]) > 0 or "T1_T2_score" not in result["rename_map"]

    def test_indicator_upper_to_cols(self):
        cols = ["T1_score", "T1_age"]
        result = inspect_wide_to_long_columns(cols, session_indicators=["T1"])
        assert len(result["indicator_upper_to_cols"]["T1"]) == 2


# ---------------------------------------------------------------------------
# _format_ambiguous_indicator_error
# ---------------------------------------------------------------------------

class TestFormatAmbiguousIndicatorError:
    def test_message_contains_column(self):
        ambiguous = [
            {"column": "T1_T2_score", "reason": "multiple-indicators-match",
             "details": [{"indicator": "T1", "output_column": "T2_score"},
                         {"indicator": "T2", "output_column": "T1_score"}]}
        ]
        msg = _format_ambiguous_indicator_error(ambiguous)
        assert "T1_T2_score" in msg

    def test_repeated_indicator_message(self):
        ambiguous = [
            {"column": "T1_T1_score", "reason": "indicator-occurs-multiple-times",
             "details": [{"indicator": "T1", "match_count": 2}]}
        ]
        msg = _format_ambiguous_indicator_error(ambiguous)
        assert "T1_T1_score" in msg


# ---------------------------------------------------------------------------
# convert_wide_to_long_dataframe
# ---------------------------------------------------------------------------

class TestConvertWideLongDataframe:
    @pytest.fixture
    def simple_wide_df(self):
        import pandas as pd
        return pd.DataFrame({
            "participant_id": ["p01", "p02"],
            "T1_score": [10, 20],
            "T2_score": [11, 21],
        })

    def test_basic_conversion(self, simple_wide_df):
        result = convert_wide_to_long_dataframe(
            simple_wide_df, session_indicators=["T1", "T2"]
        )
        assert len(result) == 4  # 2 participants × 2 sessions
        assert "session" in result.columns
        assert "score" in result.columns

    def test_session_values_correct(self, simple_wide_df):
        result = convert_wide_to_long_dataframe(
            simple_wide_df, session_indicators=["T1", "T2"]
        )
        assert set(result["session"]) == {"T1", "T2"}

    def test_session_value_map(self, simple_wide_df):
        result = convert_wide_to_long_dataframe(
            simple_wide_df,
            session_indicators=["T1", "T2"],
            session_value_map={"T1": "pre", "T2": "post"},
        )
        assert set(result["session"]) == {"pre", "post"}

    def test_no_matched_columns_raises(self, simple_wide_df):
        with pytest.raises(ValueError, match="No columns found"):
            convert_wide_to_long_dataframe(
                simple_wide_df, session_indicators=["wave1", "wave2"]
            )

    def test_custom_session_column_name(self, simple_wide_df):
        result = convert_wide_to_long_dataframe(
            simple_wide_df,
            session_indicators=["T1", "T2"],
            session_column_name="timepoint",
        )
        assert "timepoint" in result.columns

    def test_run_indicators(self):
        import pandas as pd
        df = pd.DataFrame({
            "participant_id": ["p01"],
            "T1_run1_score": [5],
            "T1_run2_score": [6],
            "T2_run1_score": [7],
            "T2_run2_score": [8],
        })
        result = convert_wide_to_long_dataframe(
            df,
            session_indicators=["T1", "T2"],
            run_indicators=["run1", "run2"],
        )
        assert "run" in result.columns
