"""Participants import with --sessions-from-date in a content project."""

import json

import pandas as pd

from src.participants_converter import ParticipantsConverter
from src.session_order import set_order_entries

ROWS = [
    {"token": "a", "startdate": "2026-03-01 10:00:00", "submitdate": "x", "age": 30},
    {"token": "a", "startdate": "2026-09-01 10:00:00", "submitdate": "x", "age": 31},
    {"token": "c", "startdate": "2026-03-02 10:00:00", "submitdate": "x", "age": 40},
    {"token": "c", "startdate": "2026-09-02 10:00:00", "submitdate": "x", "age": 41},
]
MAPPING = {
    "version": "1.0",
    "mappings": {
        "participant_id": {"source_column": "token", "standard_variable": "participant_id", "type": "string"},
        "age": {"source_column": "age", "standard_variable": "age", "type": "string"},
    },
}


def make_project(tmp_path):
    root = tmp_path / "proj"
    root.mkdir()
    (root / "project.json").write_text(
        json.dumps({"StudyDesign": {"Timepoints": "multiple", "SessionLabels": "content"}})
    )
    set_order_entries(root, "a", {"1": "sleepdep", "2": "rested"})
    set_order_entries(root, "c", {"1": "rested", "2": "sleepdep"})
    source = tmp_path / "in.csv"
    pd.DataFrame(ROWS).to_csv(source, index=False)
    return root, source


def convert(root, source, **kwargs):
    return ParticipantsConverter(root).convert_participant_data(
        source, MAPPING, output_file=root / "participants.tsv",
        sessions_from_date="startdate", **kwargs,
    )


def test_split_columns_carry_the_condition_names(tmp_path):
    root, source = make_project(tmp_path)

    ok, df, _ = convert(root, source, session_column="session", split_sessions=True)

    assert ok
    by_id = df.set_index("participant_id")
    assert by_id.loc["sub-a", "age@ses-sleepdep"] == "30"
    assert by_id.loc["sub-c", "age@ses-sleepdep"] == "41"
    assert "age@ses-1" not in df.columns


def test_a_session_value_picks_each_participants_matching_response(tmp_path):
    root, source = make_project(tmp_path)

    ok, df, _ = convert(root, source, session_column="session", session_value="sleepdep")

    assert ok
    assert dict(zip(df["participant_id"], df["age"])) == {"sub-a": "30", "sub-c": "41"}
