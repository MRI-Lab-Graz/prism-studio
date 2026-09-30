"""Longitudinal source files: find the session column and reduce to one session."""

import pandas as pd

import pytest

from src.participants_sessions import (
    filter_rows_to_session,
    find_session_candidates,
    scope_to_session,
    sort_session_labels,
)


def test_session_column_with_several_labels_is_a_candidate():
    df = pd.DataFrame(
        {
            "participant_id": ["a", "a", "b", "b"],
            "session": ["baseline", "followup", "baseline", "followup"],
            "age": [30, 31, 40, 41],
        }
    )

    assert find_session_candidates(df) == [
        {"column": "session", "values": ["baseline", "followup"]}
    ]


def test_session_column_with_a_single_label_is_not_a_candidate():
    df = pd.DataFrame({"participant_id": ["a", "b"], "session": ["baseline", "baseline"]})

    assert find_session_candidates(df) == []


def test_columns_that_are_not_session_like_are_ignored():
    df = pd.DataFrame({"participant_id": ["a", "b"], "group": ["x", "y"]})

    assert find_session_candidates(df) == []


def test_common_session_column_names_are_recognised():
    df = pd.DataFrame(
        {"participant_id": ["a", "a"], "Visit": ["v1", "v2"], "time_point": [1, 2]}
    )

    assert [c["column"] for c in find_session_candidates(df)] == ["Visit", "time_point"]


def test_labels_are_compared_exactly_never_normalized():
    df = pd.DataFrame({"participant_id": ["a", "a", "a"], "ses": ["1", "01", "pre"]})

    # "1" and "01" stay two different labels (order is numeric, then text).
    assert find_session_candidates(df)[0]["values"] == ["01", "1", "pre"]


def test_whole_number_floats_from_spreadsheets_are_integer_labels():
    df = pd.DataFrame({"participant_id": ["a", "a"], "session": [1.0, 2.0]})

    assert find_session_candidates(df)[0]["values"] == ["1", "2"]


def test_missing_cells_are_not_labels_and_numbers_sort_numerically():
    df = pd.DataFrame(
        {"participant_id": list("abcd"), "session": ["10", "2", None, "2"]}
    )

    assert find_session_candidates(df)[0]["values"] == ["2", "10"]


def _longitudinal():
    return pd.DataFrame(
        {
            "participant_id": ["a", "a", "b", "b"],
            "session": ["baseline", "followup", "baseline", "followup"],
            "age": [30, 31, 40, 41],
        }
    )


def test_filter_keeps_only_the_chosen_session():
    kept = filter_rows_to_session(_longitudinal(), "session", "baseline")

    assert list(kept["participant_id"]) == ["a", "b"]
    assert list(kept["age"]) == [30, 40]


def test_filter_matches_labels_exactly():
    df = pd.DataFrame({"participant_id": ["a", "b"], "ses": ["1", "01"]})

    assert list(filter_rows_to_session(df, "ses", "01")["participant_id"]) == ["b"]


def test_filter_matches_whole_number_float_labels():
    df = pd.DataFrame({"participant_id": ["a", "b"], "session": [1.0, 2.0]})

    assert list(filter_rows_to_session(df, "session", "1")["participant_id"]) == ["a"]


def test_filter_rejects_an_unknown_column():
    with pytest.raises(ValueError, match="Session column 'wave' not found"):
        filter_rows_to_session(_longitudinal(), "wave", "baseline")


def test_filter_rejects_a_session_that_is_not_in_the_column():
    with pytest.raises(ValueError, match="Session 'month6' not found"):
        filter_rows_to_session(_longitudinal(), "session", "month6")


def test_scope_to_session_reports_all_sessions_but_returns_only_the_chosen_rows():
    candidates, scoped = scope_to_session(_longitudinal(), "session", "followup")

    assert candidates == [{"column": "session", "values": ["baseline", "followup"]}]
    assert list(scoped["age"]) == [31, 41]


def test_scope_to_session_without_a_choice_keeps_every_row():
    _candidates, scoped = scope_to_session(_longitudinal(), "", "")

    assert len(scoped) == 4


def test_scope_to_session_rejects_a_session_that_is_not_in_the_file():
    with pytest.raises(ValueError, match="Session 'month6' not found"):
        scope_to_session(_longitudinal(), "session", "month6")


def test_natural_order_compares_digit_runs_by_size_but_keeps_labels_as_text():
    assert sort_session_labels(["10", "2", "1"]) == ["1", "2", "10"]
    assert sort_session_labels(["ses-10", "ses-2", "pre"]) == ["pre", "ses-2", "ses-10"]


def test_natural_order_never_rewrites_a_label():
    labels = ["01", "1", "1.0", "baseline"]

    assert sorted(sort_session_labels(labels)) == sorted(labels)
    assert all(isinstance(label, str) for label in sort_session_labels(labels))


@pytest.mark.parametrize("arrival", [["1", "01"], ["01", "1"]])
def test_natural_order_is_the_same_whatever_order_labels_arrive_in(arrival):
    assert sort_session_labels(arrival) == ["01", "1"]


def test_natural_order_does_not_parse_decimals_or_exponents():
    # "1e3" and "1,5" are text with digit runs, not numbers.
    assert sort_session_labels(["1e3", "2", "1,5"]) == ["1,5", "1e3", "2"]
