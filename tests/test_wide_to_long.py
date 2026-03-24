from __future__ import annotations

import pandas as pd

from src.converters.wide_to_long import (
    convert_wide_to_long_dataframe,
    detect_wide_session_prefixes,
    inspect_wide_to_long_columns,
)


def test_detect_wide_session_prefixes_finds_t_prefixes() -> None:
    cols = ["participant_id", "T1_ADS01", "T1_ADS02", "T2_ADS01", "T2_ADS02"]
    prefixes = detect_wide_session_prefixes(cols, min_count=2)
    assert prefixes == ["T1", "T2"]


def test_detect_wide_session_prefixes_falls_back_to_suffix_tokens() -> None:
    cols = ["participant_id", "ADS01_pre", "ADS02_pre", "ADS01_post", "ADS02_post"]
    indicators = detect_wide_session_prefixes(cols, min_count=2)
    assert indicators == ["_pre", "_post"]


def test_convert_wide_to_long_dataframe_strips_prefixes() -> None:
    df = pd.DataFrame(
        {
            "participant_id": ["sub-01", "sub-02"],
            "T1_ADS01": [1, 2],
            "T2_ADS01": [3, 4],
            "age": [20, 21],
        }
    )

    out = convert_wide_to_long_dataframe(
        df,
        session_prefixes=["T1", "T2"],
        session_column_name="session",
    )

    assert len(out) == 4
    assert set(out.columns) == {"participant_id", "age", "ADS01", "session"}
    assert set(out["session"].unique()) == {"T1", "T2"}


def test_convert_wide_to_long_dataframe_raises_without_prefixed_columns() -> None:
    df = pd.DataFrame({"participant_id": ["sub-01"], "score": [3]})

    try:
        convert_wide_to_long_dataframe(df, session_prefixes=["T1"])
    except ValueError as exc:
        assert "No columns found for the selected session indicators" in str(exc)
    else:
        raise AssertionError("Expected ValueError for missing prefixed columns")


def test_convert_wide_to_long_dataframe_applies_session_value_map() -> None:
    df = pd.DataFrame(
        {
            "participant_id": ["sub-01"],
            "T1_ADS01": [1],
            "T2_ADS01": [2],
        }
    )

    out = convert_wide_to_long_dataframe(
        df,
        session_prefixes=["T1", "T2"],
        session_column_name="session",
        session_value_map={"T1": "pre", "T2": "post"},
    )

    assert set(out["session"].unique()) == {"pre", "post"}


def test_convert_wide_to_long_dataframe_keeps_unmapped_prefix_values() -> None:
    df = pd.DataFrame(
        {
            "participant_id": ["sub-01"],
            "T1_ADS01": [1],
            "T2_ADS01": [2],
        }
    )

    out = convert_wide_to_long_dataframe(
        df,
        session_prefixes=["T1", "T2"],
        session_column_name="session",
        session_value_map={"T1": "pre"},
    )

    assert set(out["session"].unique()) == {"pre", "T2"}


def test_convert_wide_to_long_dataframe_matches_suffix_indicators() -> None:
    df = pd.DataFrame(
        {
            "participant_id": ["sub-01"],
            "ADS01_pre": [1],
            "ADS01_post": [2],
        }
    )

    out = convert_wide_to_long_dataframe(
        df,
        session_indicators=["_pre", "_post"],
        session_column_name="session",
        session_value_map={"_pre": "pre", "_post": "post"},
    )

    assert set(out.columns) == {"participant_id", "ADS01", "session"}
    assert list(out["ADS01"]) == [1, 2]
    assert list(out["session"]) == ["pre", "post"]


def test_convert_wide_to_long_dataframe_matches_middle_indicators() -> None:
    df = pd.DataFrame(
        {
            "participant_id": ["sub-01"],
            "stress_T1_score": [1],
            "stress_T2_score": [2],
        }
    )

    out = convert_wide_to_long_dataframe(
        df,
        session_indicators=["_T1_", "_T2_"],
        session_column_name="session",
    )

    assert set(out.columns) == {"participant_id", "stress_score", "session"}
    assert set(out["session"].unique()) == {"_T1_", "_T2_"}


def test_inspect_wide_to_long_columns_reports_ambiguous_repeated_indicator() -> None:
    plan = inspect_wide_to_long_columns(
        ["ADS_1_1 item name ADS_1", "participant_id"],
        session_indicators=["_1"],
    )

    assert plan["matched_columns"] == []
    assert len(plan["ambiguous_columns"]) == 1
    assert plan["ambiguous_columns"][0]["column"] == "ADS_1_1 item name ADS_1"
    assert plan["ambiguous_columns"][0]["reason"] == "indicator-occurs-multiple-times"


def test_convert_wide_to_long_dataframe_rejects_ambiguous_repeated_indicator() -> None:
    df = pd.DataFrame(
        {
            "participant_id": ["sub-01"],
            "ADS_1_1 item name ADS_1": [5],
        }
    )

    try:
        convert_wide_to_long_dataframe(
            df,
            session_indicators=["_1"],
            session_column_name="session",
        )
    except ValueError as exc:
        assert "Ambiguous session indicator matches found" in str(exc)
        assert "ADS_1_1 item name ADS_1" in str(exc)
    else:
        raise AssertionError("Expected ValueError for ambiguous repeated indicator")
