"""Repeated rows per participant: identical values collapse quietly; values that
differ between sessions can be kept as one column per session (age@ses-1)."""

import pandas as pd
import pytest

from src.participants_converter import ParticipantsConverter
from src.participants_sessions import find_repeat_conflicts, split_columns_by_session

MAPPING = {
    "version": "1.0",
    "mappings": {
        name: {"source_column": name, "standard_variable": name, "type": "string"}
        for name in ("participant_id", "age", "sex")
    },
}

ROWS = [
    {"participant_id": "1", "session": "1", "age": 30, "sex": 2},
    {"participant_id": "1", "session": "2", "age": 31, "sex": 2},
    {"participant_id": "2", "session": "1", "age": 40, "sex": 1},
    {"participant_id": "2", "session": "2", "age": 41, "sex": 1},
]


def _convert(tmp_path, rows=ROWS, **kwargs):
    src = tmp_path / "in.csv"
    pd.DataFrame(rows).to_csv(src, index=False)
    return ParticipantsConverter(tmp_path).convert_participant_data(
        src,
        MAPPING,
        output_file=tmp_path / "participants.tsv",
        reject_conflicting_repeats=True,
        **kwargs,
    )


def test_identical_repeats_collapse_without_any_session_choice(tmp_path):
    rows = [{**r, "age": 30 if r["participant_id"] == "1" else 40} for r in ROWS]

    success, df, _ = _convert(tmp_path, rows)

    assert success
    assert list(df["participant_id"]) == ["sub-1", "sub-2"]


def test_find_repeat_conflicts_names_only_the_columns_that_differ():
    df = pd.DataFrame(ROWS)

    assert find_repeat_conflicts(df, "participant_id", ["age", "sex"]) == ["age"]


def test_split_sessions_keeps_each_sessions_value_in_its_own_column(tmp_path):
    success, df, messages = _convert(
        tmp_path, session_column="session", split_sessions=True
    )

    assert success, messages
    assert list(df.columns) == ["participant_id", "age@ses-1", "age@ses-2", "sex"]
    assert [str(v) for v in df["age@ses-2"]] == ["31", "41"]
    assert [str(v) for v in df["sex"]] == ["2", "1"]  # stable value stays one column


def test_session_labels_one_and_01_stay_two_different_columns(tmp_path):
    rows = [{**r, "session": "01" if r["session"] == "2" else "1"} for r in ROWS]

    success, df, _ = _convert(tmp_path, rows, session_column="session", split_sessions=True)

    assert success
    assert {"age@ses-1", "age@ses-01"} <= set(df.columns)


def test_split_sessions_needs_a_session_column(tmp_path):
    success, df, messages = _convert(tmp_path, split_sessions=True)

    assert not success and df is None
    assert "session column" in messages[-1]


def test_two_labels_that_would_name_the_same_column_are_rejected():
    df = pd.DataFrame(
        {"participant_id": ["a", "a"], "age": ["30", "31"]}, index=[0, 1]
    )
    labels = pd.Series(["Pre", "pre"], index=df.index)

    with pytest.raises(ValueError, match="same column"):
        split_columns_by_session(df, labels, ["age"])


def test_split_sessions_is_refused_in_a_one_timepoint_project(tmp_path):
    import json

    (tmp_path / "project.json").write_text(json.dumps({"StudyDesign": {"Timepoints": "single"}}))

    success, df, messages = _convert(tmp_path, session_column="session", split_sessions=True)

    assert not success
    assert any("one timepoint" in m for m in messages)
