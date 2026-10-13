"""Participants import: the project's session decisions are applied automatically."""

import pandas as pd

from src.participants_converter import ParticipantsConverter, load_participant_source
from src.session_assignments import set_assignment

ROWS = [
    {"id": "1", "token": "a", "startdate": "2026-03-01 09:00:00", "submitdate": "", "age": 29},
    {"id": "2", "token": "a", "startdate": "2026-03-01 11:00:00", "submitdate": "x", "age": 30},
    {"id": "3", "token": "a", "startdate": "2026-09-01 10:00:00", "submitdate": "x", "age": 31},
    {"id": "4", "token": "b", "startdate": "2026-03-02 10:00:00", "submitdate": "x", "age": 40},
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


def test_loader_leaves_out_the_incomplete_response(tmp_path):
    df, _ = load_participant_source(_csv(tmp_path), sessions_from_date="startdate", id_column="token")

    assert sorted(zip(df["id"].astype(str), df["session"])) == [("2", "1"), ("3", "2"), ("4", "1")]


def test_loader_applies_decisions(tmp_path):
    df, _ = load_participant_source(
        _csv(tmp_path), sessions_from_date="startdate", id_column="token",
        decisions={"2": {"skip": True}},
    )

    assert sorted(zip(df["id"].astype(str), df["session"])) == [("3", "1"), ("4", "1")]


def test_convert_reads_the_project_decisions_file(tmp_path):
    project = tmp_path / "proj"
    project.mkdir()
    set_assignment(project, "2", skip=True)  # drop a's first completed response

    ok, df, messages = ParticipantsConverter(project).convert_participant_data(
        _csv(tmp_path), MAPPING, output_file=project / "participants.tsv",
        sessions_from_date="startdate", session_column="session", session_value="1",
        reject_conflicting_repeats=True,
    )

    assert ok, messages
    assert dict(zip(df["participant_id"], df["age"].astype(str))) == {"sub-a": "31", "sub-b": "40"}
