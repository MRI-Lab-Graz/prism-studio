"""number_sessions_by_date: session labels from acquisition-date order."""

import pandas as pd
import pytest

from src.participants_sessions import number_sessions_by_date


def _df(rows):
    return pd.DataFrame(rows, columns=["token", "startdate", "datestamp", "submitdate", "lastpage"])


def test_sessions_follow_date_not_file_order():
    df = _df([
        ["a", "2026-09-01 10:00:00", "", "2026-09-01 10:20:00", "5"],
        ["a", "2026-03-01 10:00:00", "", "2026-03-01 10:20:00", "5"],
        ["b", "2026-03-02 10:00:00", "", "2026-03-02 10:20:00", "5"],
    ])
    out, _ = number_sessions_by_date(df, "token")
    got = {(r.token, r.startdate[:7]): r.session for r in out.itertuples()}
    assert got == {("a", "2026-03"): "1", ("a", "2026-09"): "2", ("b", "2026-03"): "1"}


def test_identical_dates_keep_file_order():
    df = _df([
        ["a", "2026-03-01 10:00:00", "", "x", "first"],
        ["a", "2026-03-01 10:00:00", "", "x", "second"],
    ])
    out, _ = number_sessions_by_date(df, "token")
    assert list(zip(out["lastpage"], out["session"])) == [("first", "1"), ("second", "2")]


def test_float_ids_group_with_string_ids():
    df = pd.DataFrame({"id": [1.0, "1"], "startdate": ["2026-01-01", "2026-02-01"]})
    out, _ = number_sessions_by_date(df, "id")
    assert list(out["session"]) == ["1", "2"]


def test_startdate_empty_falls_back_to_datestamp():
    df = _df([
        ["a", "", "2026-09-01 10:00:00", "x", "5"],
        ["a", "2026-03-01 10:00:00", "", "x", "5"],
    ])
    out, _ = number_sessions_by_date(df, "token")
    assert list(out["datestamp"]) == ["", "2026-09-01 10:00:00"]
    assert list(out["session"]) == ["1", "2"]


def test_mixed_date_formats_parse():
    df = _df([
        ["a", "2026-09-01 10:00:00", "", "x", "1"],
        ["a", "2026-03-01", "", "x", "1"],
    ])
    out, _ = number_sessions_by_date(df, "token")
    assert list(out["session"]) == ["1", "2"]
    assert out["startdate"].iloc[0] == "2026-03-01"


def test_missing_date_is_an_error():
    df = _df([["a", "", "", "", "1"]])
    with pytest.raises(ValueError, match="a"):
        number_sessions_by_date(df, "token")


def test_existing_session_column_is_an_error():
    df = pd.DataFrame({"token": ["a"], "startdate": ["2026-01-01"], "session": ["pre"]})
    with pytest.raises(ValueError, match="session"):
        number_sessions_by_date(df, "token")


def test_incomplete_runs_are_flagged():
    df = _df([
        ["a", "2026-03-01", "", "", "3"],
        ["a", "2026-03-02", "", "2026-03-02", "9"],
    ])
    _, warnings = number_sessions_by_date(df, "token")
    text = "\n".join(warnings)
    assert "a" in text and "session 1" in text and "lastpage 3" in text


def test_uneven_session_counts_are_reported():
    df = _df([
        ["a", "2026-03-01", "", "x", "1"],
        ["a", "2026-09-01", "", "x", "1"],
        ["b", "2026-03-01", "", "x", "1"],
    ])
    _, warnings = number_sessions_by_date(df, "token")
    assert any("1 IDs x 2 sessions" in w and "1 x 1" in w for w in warnings)


def test_even_counts_complete_runs_give_no_warnings():
    df = _df([["a", "2026-03-01", "", "x", "1"], ["b", "2026-03-01", "", "x", "1"]])
    _, warnings = number_sessions_by_date(df, "token")
    assert warnings == []


def test_datestamp_only_file_orders_by_datestamp():
    df = pd.DataFrame({
        "token": ["a", "a"],
        "datestamp": ["2026-09-01 10:00:00", "2026-03-01 10:00:00"],
        "age": [31, 30],
    })
    out, _ = number_sessions_by_date(df, "token")
    assert dict(zip(out["age"], out["session"])) == {30: "1", 31: "2"}
