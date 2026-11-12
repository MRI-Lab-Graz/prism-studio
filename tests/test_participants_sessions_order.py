"""Date numbering names sessions from the session order of a content project."""

import pandas as pd
import pytest

from src.participants_sessions import number_sessions_by_date, session_assignment_table
from src.session_order import SessionsNotOrderedError

ORDER = {
    "P01": {"1": "sleepdep", "2": "rested"},
    "P02": {"1": "rested", "2": "sleepdep"},
}


def frame(extra=()):
    rows = [
        ("1", "P01", "2026-01-05 10:00:00"),
        ("2", "P01", "2026-02-05 10:00:00"),
        ("3", "P02", "2026-01-06 10:00:00"),
        ("4", "P02", "2026-02-06 10:00:00"),
        *extra,
    ]
    return pd.DataFrame(
        [{"id": i, "token": t, "startdate": d, "submitdate": d} for i, t, d in rows]
    )


def names(df):
    return {(r["token"], r["startdate"][:7]): r["session"] for _, r in df.iterrows()}


def test_opposite_orders_get_their_own_names():
    out, _ = number_sessions_by_date(frame(), "token", order=ORDER)
    assert names(out) == {
        ("P01", "2026-01"): "sleepdep",
        ("P01", "2026-02"): "rested",
        ("P02", "2026-01"): "rested",
        ("P02", "2026-02"): "sleepdep",
    }


def test_missing_participant_is_listed():
    with pytest.raises(SessionsNotOrderedError) as caught:
        number_sessions_by_date(frame(), "token", order={"P01": ORDER["P01"]})
    assert caught.value.problems == ["P02: not in the session order"]


def test_count_mismatch_names_both_counts():
    third = [("5", "P01", "2026-03-05 10:00:00")]
    with pytest.raises(SessionsNotOrderedError) as caught:
        number_sessions_by_date(frame(third), "token", order=ORDER)
    assert caught.value.problems == ["P01: 3 responses in this file, 2 in the session order"]


def test_a_number_missing_from_the_order_is_listed():
    order = {**ORDER, "P02": {"1": "rested", "3": "sleepdep"}}
    with pytest.raises(SessionsNotOrderedError) as caught:
        number_sessions_by_date(frame(), "token", order=order)
    assert caught.value.problems == ["P02: number 2 not in the session order"]


def test_naming_every_response_by_hand_needs_no_order():
    decisions = {"1": {"session": "sleepdep"}, "2": {"session": "rested"}}
    out, _ = number_sessions_by_date(
        frame(), "token", order={"P02": ORDER["P02"]}, decisions=decisions
    )
    assert names(out)[("P01", "2026-01")] == "sleepdep"


def test_override_clashing_with_the_order_is_a_blocker():
    decisions = {"2": {"session": "sleepdep"}}
    with pytest.raises(ValueError, match="same session label twice"):
        number_sessions_by_date(
            frame(), "token", order={"P01": {"1": "sleepdep"}, "P02": ORDER["P02"]},
            decisions=decisions,
        )


def test_lookup_uses_the_raw_id_not_the_grouping_column():
    df = frame().assign(_norm=lambda d: "sub-" + d["token"])
    out, _ = number_sessions_by_date(df, "_norm", order=ORDER, order_id_column="token")
    assert names(out)[("P02", "2026-01")] == "rested"


def test_review_table_reports_instead_of_raising():
    rows, warnings = session_assignment_table(frame(), "token", order={"P01": ORDER["P01"]})
    p02 = [r for r in rows if r["participant"] == "P02"]
    assert {r["reason"] for r in p02} == {"not in session order"}
    assert all(r["session"] is None for r in p02)
    assert any("P02: not in the session order" in w for w in warnings)
    assert {r["session"] for r in rows if r["participant"] == "P01"} == {"sleepdep", "rested"}


def test_without_an_order_the_numbers_stay():
    out, _ = number_sessions_by_date(frame(), "token")
    assert names(out)[("P02", "2026-02")] == "2"


def test_review_rows_carry_the_date_number_so_the_page_never_counts():
    rows, _ = session_assignment_table(frame(), "token", order={"P01": ORDER["P01"]})
    by_response = {r["response_id"]: r for r in rows}
    assert [(by_response[i]["number"], by_response[i]["session"]) for i in ("1", "2")] == [
        ("1", "sleepdep"), ("2", "rested"),
    ]
    assert [by_response[i]["number"] for i in ("3", "4")] == ["1", "2"]  # P02 is not named, still numbered


def test_a_named_response_has_no_number():
    rows, _ = session_assignment_table(
        frame(), "token", order=ORDER, decisions={"1": {"session": "sleepdep"}}
    )
    assert {r["response_id"]: r["number"] for r in rows}["1"] is None


def test_review_table_opens_when_a_label_clashes_and_says_so():
    # P01's 2nd response is relabelled "1", which the 1st response already has: the conversion
    # refuses this, but the review table is where it is fixed, so it must still open.
    decisions = {"2": {"session": "1"}}
    rows, warnings = session_assignment_table(frame(), "token", decisions=decisions)
    assert [r["response_id"] for r in rows if r["participant"] == "P01"] == ["1", "2"]
    clash = [w for w in warnings if "same session label twice" in w]
    assert clash and "P01" in clash[0] and "1, 2" in clash[0]
    with pytest.raises(ValueError, match="same session label twice"):
        number_sessions_by_date(frame(), "token", decisions=decisions)
