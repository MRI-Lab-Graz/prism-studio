"""Convert must stop when one participant_id has conflicting values."""

import pandas as pd

from src.participants_converter import ParticipantsConverter

MAPPING = {
    "version": "1.0",
    "mappings": {
        "participant_id": {
            "source_column": "participant_id",
            "standard_variable": "participant_id",
            "type": "string",
        },
        "age": {"source_column": "age", "standard_variable": "age", "type": "string"},
        "sex": {"source_column": "sex", "standard_variable": "sex", "type": "string"},
    },
}


def _run(tmp_path, rows, reject):
    src = tmp_path / "in.csv"
    pd.DataFrame(rows).to_csv(src, index=False)
    out = tmp_path / "participants.tsv"
    result = ParticipantsConverter(tmp_path).convert_participant_data(
        src, MAPPING, output_file=out, reject_conflicting_repeats=reject
    )
    return result, out


def test_conflicting_repeat_stops_and_writes_nothing(tmp_path):
    rows = [
        {"participant_id": "2", "age": 34, "sex": 1},
        {"participant_id": "2", "age": 35, "sex": 1},
    ]

    (success, df, messages), out = _run(tmp_path, rows, reject=True)

    assert not success and df is None
    assert not out.exists()
    assert "age" in messages[-1] and "one row per participant" in messages[-1]


def test_session_column_gets_a_longitudinal_hint(tmp_path):
    rows = [
        {"participant_id": "2", "session": "t1", "age": 34, "sex": 1},
        {"participant_id": "2", "session": "t2", "age": 35, "sex": 1},
    ]

    (success, _df, messages), _out = _run(tmp_path, rows, reject=True)

    assert not success
    assert "session column (session)" in messages[-1]


def test_identical_repeats_still_collapse(tmp_path):
    rows = [
        {"participant_id": "2", "session": "t1", "age": 34, "sex": 1},
        {"participant_id": "2", "session": "t2", "age": 34, "sex": 1},
    ]

    (success, df, _messages), _out = _run(tmp_path, rows, reject=True)

    assert success and len(df) == 1


def test_default_still_warns_and_keeps_first_value_for_merge(tmp_path):
    rows = [
        {"participant_id": "2", "age": 34, "sex": 1},
        {"participant_id": "2", "age": 35, "sex": 1},
    ]

    (success, df, messages), _out = _run(tmp_path, rows, reject=False)

    assert success and str(df.iloc[0]["age"]) == "34"
    assert any("differing values" in m for m in messages)
