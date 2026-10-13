"""Sessions come from completed responses only; overrides and the review table."""

import pandas as pd
import pytest

from src.participants_sessions import number_sessions_by_date, session_assignment_table

COLS = ["id", "token", "startdate", "submitdate", "lastpage"]
# Mirrors the real archive: a (1 abandoned + 2 completed), b (only abandoned), c (1 completed).
ROWS = [
    ["1", "a", "2026-03-01 09:00:00", "", "2"],
    ["2", "a", "2026-03-01 11:00:00", "2026-03-01 11:20:00", "5"],
    ["3", "a", "2026-09-01 10:00:00", "2026-09-01 10:20:00", "5"],
    ["4", "b", "2026-03-02 10:00:00", "", "4"],
    ["5", "b", "2026-03-02 10:05:00", "", ""],
    ["6", "c", "2026-03-03 10:00:00", "2026-03-03 10:10:00", "5"],
]


def _df(rows=ROWS):
    return pd.DataFrame(rows, columns=COLS)


def _by_id(out):
    return dict(zip(out["id"], out["session"]))


def test_only_completed_responses_get_a_session():
    out, _ = number_sessions_by_date(_df(), "token")

    assert _by_id(out) == {"2": "1", "3": "2", "6": "1"}


def test_incomplete_responses_are_left_out_and_counted():
    _, warnings = number_sessions_by_date(_df(), "token")

    text = "\n".join(warnings)
    assert warnings[0].startswith("Sessions numbered by startdate")
    assert "3 incomplete response(s) left out" in text


def test_participant_without_a_completed_response_is_named():
    _, warnings = number_sessions_by_date(_df(), "token")

    assert any(w.startswith("No completed response for: b") for w in warnings)


def test_identical_dates_keep_file_order():
    rows = [
        ["1", "a", "2026-03-01 10:00:00", "x", "5"],
        ["2", "a", "2026-03-01 10:00:00", "x", "5"],
    ]
    out, _ = number_sessions_by_date(_df(rows), "token")

    assert _by_id(out) == {"1": "1", "2": "2"}


def test_a_file_without_submitdate_treats_every_response_as_completed():
    df = pd.DataFrame({"token": ["a", "a"], "startdate": ["2026-03-01", "2026-09-01"]})
    out, _ = number_sessions_by_date(df, "token")

    assert list(out["session"]) == ["1", "2"]


def test_skip_decision_removes_a_completed_response():
    out, _ = number_sessions_by_date(_df(), "token", decisions={"2": {"skip": True}})

    assert _by_id(out) == {"3": "1", "6": "1"}


def test_session_decision_sets_an_exact_label_and_can_include_an_incomplete_response():
    decisions = {"4": {"session": "pre"}, "3": {"session": "post"}}
    out, _ = number_sessions_by_date(_df(), "token", decisions=decisions)

    assert _by_id(out) == {"2": "1", "3": "post", "4": "pre", "6": "1"}


def test_duplicate_label_is_a_blocker():
    with pytest.raises(ValueError, match=r"a.*'1'.*2.*3|a.*'1'.*3.*2"):
        number_sessions_by_date(_df(), "token", decisions={"3": {"session": "1"}})


def test_stale_decision_is_ignored_with_a_warning():
    out, warnings = number_sessions_by_date(_df(), "token", decisions={"999": {"skip": True}})

    assert _by_id(out) == {"2": "1", "3": "2", "6": "1"}
    assert "Ignored decisions for responses not in this file: 999" in warnings


def test_undated_completed_response_is_an_error_but_undated_incomplete_is_not():
    rows = [["1", "a", "", "", "2"], ["2", "a", "2026-03-01", "x", "5"]]
    out, _ = number_sessions_by_date(_df(rows), "token")
    assert _by_id(out) == {"2": "1"}

    rows = [["1", "a", "", "x", "5"]]
    with pytest.raises(ValueError, match="a"):
        number_sessions_by_date(_df(rows), "token")


def test_existing_session_column_is_still_an_error():
    df = _df().assign(session="pre")
    with pytest.raises(ValueError, match="session"):
        number_sessions_by_date(df, "token")


def test_table_lists_every_response_with_reason_and_session():
    rows, _ = session_assignment_table(_df(), "token", decisions={"3": {"skip": True}})

    by_id = {r["response_id"]: r for r in rows}
    assert [r["response_id"] for r in rows] == ["1", "2", "3", "4", "5", "6"]
    assert by_id["1"] | {"date": ""} == {
        "participant": "a", "response_id": "1", "date": "", "completed": False,
        "lastpage": "2", "session": None, "reason": "incomplete",
    }
    assert (by_id["2"]["session"], by_id["2"]["reason"]) == ("1", "auto")
    assert (by_id["3"]["session"], by_id["3"]["reason"]) == (None, "skipped")
    assert by_id["2"]["date"].startswith("2026-03-01")
