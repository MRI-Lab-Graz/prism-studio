import json

from src.participants_converter import ParticipantsConverter
from src.session_map import save_session_map

MAPPING = {
    "version": "1.0",
    "description": "t",
    "mappings": {
        "participant_id": {
            "source_column": "participant_id",
            "standard_variable": "participant_id",
            "type": "string",
        }
    },
}
LONG = "participant_id,session,age\nP001,pre,21\nP001,post,22\nP002,pre,34\n"


def run(tmp_path, timepoints, mapped=None, **kwargs):
    (tmp_path / "project.json").write_text(
        json.dumps({"StudyDesign": {"Timepoints": timepoints}})
    )
    if mapped is not None:
        save_session_map(tmp_path, mapped)
    src = tmp_path / "people.csv"
    src.write_text(LONG)
    return ParticipantsConverter(tmp_path).convert_participant_data(
        source_file=src,
        mapping=MAPPING,
        output_file=tmp_path / "participants.tsv",
        session_column="session",
        session_value="pre",
        **kwargs,
    )


def test_the_chosen_session_must_be_mapped(tmp_path):
    ok, df, messages = run(tmp_path, "multiple", mapped={"post": "2"})
    assert not ok and df is None
    text = " ".join(messages)
    assert "'pre'" in text and "'post'" not in text  # only the session being imported is asked for


def test_other_sessions_need_no_entry_when_only_one_is_imported(tmp_path):
    ok, df, messages = run(tmp_path, "multiple", mapped={"pre": "1"})
    assert ok, messages
    assert len(df) == 2


def test_fully_mapped_file_imports_the_chosen_session(tmp_path):
    ok, df, messages = run(tmp_path, "multiple", mapped={"pre": "1", "post": "2"})
    assert ok, messages
    assert len(df) == 2


def test_single_timepoint_project_is_unchanged(tmp_path):
    ok, df, messages = run(tmp_path, "single")
    assert ok, messages
    assert len(df) == 2
