"""Convert can reduce a longitudinal file to one chosen session."""

import pandas as pd

from src.participants_converter import ParticipantsConverter

MAPPING = {
    "version": "1.0",
    "mappings": {
        name: {"source_column": name, "standard_variable": name, "type": "string"}
        for name in ("participant_id", "age", "sex")
    },
}

LONGITUDINAL = [
    {"participant_id": "1", "session": "baseline", "age": 30, "sex": 2},
    {"participant_id": "1", "session": "followup", "age": 31, "sex": 2},
    {"participant_id": "2", "session": "baseline", "age": 40, "sex": 1},
    {"participant_id": "2", "session": "followup", "age": 41, "sex": 1},
]


def _convert(tmp_path, **kwargs):
    src = tmp_path / "in.csv"
    pd.DataFrame(LONGITUDINAL).to_csv(src, index=False)
    return ParticipantsConverter(tmp_path).convert_participant_data(
        src,
        MAPPING,
        output_file=tmp_path / "participants.tsv",
        reject_conflicting_repeats=True,
        **kwargs,
    )


def test_chosen_session_yields_one_row_per_participant(tmp_path):
    success, df, messages = _convert(
        tmp_path, session_column="session", session_value="followup"
    )

    assert success
    assert list(df["participant_id"]) == ["sub-1", "sub-2"]
    assert [str(age) for age in df["age"]] == ["31", "41"]
    assert any("session 'followup'" in m and "2 of 4" in m for m in messages)


def test_without_a_session_choice_conflicting_repeats_still_stop(tmp_path):
    success, df, _messages = _convert(tmp_path)

    assert not success and df is None


def test_unknown_session_fails_with_a_clear_message_and_writes_nothing(tmp_path):
    success, df, messages = _convert(
        tmp_path, session_column="session", session_value="month6"
    )

    assert not success and df is None
    assert "Session 'month6' not found" in messages[-1]
    assert not (tmp_path / "participants.tsv").exists()
