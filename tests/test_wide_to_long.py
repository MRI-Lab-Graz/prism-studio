from __future__ import annotations

import pandas as pd

from src.converters.wide_to_long import (
    convert_wide_to_long_dataframe,
    detect_wide_session_prefixes,
)


def test_detect_wide_session_prefixes_finds_t_prefixes() -> None:
    cols = ["participant_id", "T1_ADS01", "T1_ADS02", "T2_ADS01", "T2_ADS02"]
    prefixes = detect_wide_session_prefixes(cols, min_count=2)
    assert prefixes == ["T1", "T2"]


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
        assert "No prefixed columns found" in str(exc)
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
