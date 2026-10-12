"""Participants import: sessions numbered from the acquisition date."""

import pandas as pd
import pytest

from src.participants_converter import ParticipantsConverter, load_participant_source

ROWS = [
    {"token": "a", "startdate": "2026-09-01 10:00:00", "submitdate": "x", "age": 31},
    {"token": "a", "startdate": "2026-03-01 10:00:00", "submitdate": "x", "age": 30},
    {"token": "b", "startdate": "2026-03-02 10:00:00", "submitdate": "x", "age": 40},
]
MAPPING = {
    "version": "1.0",
    "mappings": {
        "participant_id": {"source_column": "token", "standard_variable": "participant_id", "type": "string"},
        "age": {"source_column": "age", "standard_variable": "age", "type": "string"},
    },
}


def _csv(tmp_path):
    path = tmp_path / "in.csv"
    pd.DataFrame(ROWS).to_csv(path, index=False)
    return path


def test_loader_adds_session_column(tmp_path):
    df, _ = load_participant_source(_csv(tmp_path), sessions_from_date="startdate", id_column="token")
    assert sorted(zip(df["token"], df["session"])) == [("a", "1"), ("a", "2"), ("b", "1")]


def test_sessions_from_date_requires_id_column(tmp_path):
    with pytest.raises(ValueError, match="ID column"):
        load_participant_source(_csv(tmp_path), sessions_from_date="startdate")


def test_convert_picks_one_dated_session(tmp_path):
    ok, df, messages = ParticipantsConverter(tmp_path).convert_participant_data(
        _csv(tmp_path), MAPPING, output_file=tmp_path / "participants.tsv",
        sessions_from_date="startdate", session_column="session", session_value="1",
        reject_conflicting_repeats=True,
    )
    assert ok, messages
    assert dict(zip(df["participant_id"], df["age"].astype(str))) == {"sub-a": "30", "sub-b": "40"}
