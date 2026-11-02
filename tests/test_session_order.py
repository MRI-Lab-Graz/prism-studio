"""Per-participant session order for content projects (code/session_order.tsv)."""

import json

import pandas as pd
import pytest

from src.session_map import SessionMapError, project_session_labels
from src.session_order import (
    ORDER_FILE,
    SessionOrderError,
    content_session_order,
    import_session_order,
    load_session_order,
    remove_order_entries,
    set_order_entries,
)


def make_project(tmp_path, timepoints="multiple", labels="content"):
    design = {"Timepoints": timepoints}
    if labels is not None:
        design["SessionLabels"] = labels
    (tmp_path / "project.json").write_text(json.dumps({"StudyDesign": design}))
    return tmp_path


def write_order(root, text):
    path = root / ORDER_FILE
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


HEADER = "participant_id\tsession_number\tsession\n"


def test_round_trip(tmp_path):
    root = make_project(tmp_path)
    set_order_entries(root, "P01", {"1": "sleepdep", "2": "rested"})
    assert load_session_order(root) == {"P01": {"1": "sleepdep", "2": "rested"}}
    assert (root / ORDER_FILE).read_text(encoding="utf-8").startswith(HEADER)


def test_sub_prefix_is_stripped_once(tmp_path):
    root = make_project(tmp_path)
    write_order(root, HEADER + "sub-P01\t1\ta\nsub-sub-X\t1\tb\n")
    assert set(load_session_order(root)) == {"P01", "sub-X"}


def test_numbers_compare_exactly(tmp_path):
    root = make_project(tmp_path)
    set_order_entries(root, "P01", {"1": "a", "01": "b"})
    assert load_session_order(root)["P01"] == {"1": "a", "01": "b"}


@pytest.mark.parametrize(
    "text, line",
    [
        ("participant_id\tsession_number\n" "P01\t1\n", "session"),
        (HEADER + "P01\t1\ta\nP01\t1\tb\n", "line 3"),
        (HEADER + "P01\t1\ta\nP01\t2\ta\n", "line 3"),
        (HEADER + "P01\t1\tsleep dep\n", "line 2"),
    ],
)
def test_load_errors_name_the_line(tmp_path, text, line):
    root = make_project(tmp_path)
    write_order(root, text)
    with pytest.raises(SessionOrderError, match=line):
        load_session_order(root)


def test_import_xlsx_reads_text(tmp_path):
    root = make_project(tmp_path)
    xlsx = tmp_path / "order.xlsx"
    pd.DataFrame(
        {"participant_id": [1, 1], "session_number": [1, 2], "session": ["a", "b"]}
    ).to_excel(xlsx, index=False)
    import_session_order(root, xlsx)
    assert load_session_order(root) == {"1": {"1": "a", "2": "b"}}


def test_import_merge_replace_and_invalid_file_changes_nothing(tmp_path):
    root = make_project(tmp_path)
    set_order_entries(root, "P01", {"1": "a"})
    new = tmp_path / "new.tsv"
    new.write_text(HEADER + "P02\t1\tb\n", encoding="utf-8")
    import_session_order(root, new)
    assert set(load_session_order(root)) == {"P01", "P02"}
    import_session_order(root, new, replace=True)
    assert set(load_session_order(root)) == {"P02"}
    bad = tmp_path / "bad.tsv"
    bad.write_text(HEADER + "P03\t1\tsleep dep\n", encoding="utf-8")
    with pytest.raises(SessionOrderError):
        import_session_order(root, bad)
    assert set(load_session_order(root)) == {"P02"}


def test_remove_entries(tmp_path):
    root = make_project(tmp_path)
    set_order_entries(root, "P01", {"1": "a", "2": "b"})
    assert remove_order_entries(root, "P01", ["1"]) == {"P01": {"2": "b"}}
    assert remove_order_entries(root, "P01") == {}
    with pytest.raises(SessionOrderError):
        remove_order_entries(root, "P09")


def test_project_session_labels(tmp_path):
    assert project_session_labels(make_project(tmp_path, labels=None)) == "time"
    assert project_session_labels(make_project(tmp_path)) == "content"
    assert project_session_labels(make_project(tmp_path, "single")) == "time"
    with pytest.raises(SessionMapError):
        project_session_labels(make_project(tmp_path, labels="weird"))


def test_content_session_order_is_none_for_a_time_project(tmp_path):
    root = make_project(tmp_path, labels="time")
    write_order(root, HEADER + "P01\t1\ta\n")
    assert content_session_order(root) is None
    root = make_project(tmp_path)
    assert content_session_order(root) == {"P01": {"1": "a"}}


def test_excel_numbers_are_found_as_the_whole_number(tmp_path):
    root = make_project(tmp_path)
    sheet = tmp_path / "order.csv"  # what Excel/pandas leave behind: 1.0, 2.0
    sheet.write_text("participant_id,session_number,session\n1.0,1.0,a\n1.0,2.0,b\n01,1,c\n", encoding="utf-8")

    import_session_order(root, sheet)

    assert load_session_order(root) == {"1": {"1": "a", "2": "b"}, "01": {"1": "c"}}  # 01 stays 01


def test_a_real_decimal_is_not_a_whole_number(tmp_path):
    root = make_project(tmp_path)
    sheet = tmp_path / "order.csv"
    sheet.write_text("participant_id,session_number,session\nP1,1.5,a\n", encoding="utf-8")

    import_session_order(root, sheet)

    assert load_session_order(root) == {"P1": {"1.5": "a"}}


def test_sub_prefix_is_ignored_in_any_case(tmp_path):
    root = make_project(tmp_path)
    write_order(root, HEADER + "SUB-P01\t1\ta\nSub-P02\t1\tb\n")
    assert set(load_session_order(root)) == {"P01", "P02"}
