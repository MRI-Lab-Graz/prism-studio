"""Decisions file: code/session_assignments.json, keyed by LimeSurvey response id."""

import json

import pytest

from src.session_assignments import (
    SessionAssignmentError,
    load_session_assignments,
    set_assignment,
    unset_assignment,
)


def test_missing_file_means_no_decisions(tmp_path):
    assert load_session_assignments(tmp_path) == {}


def test_set_skip_and_session_round_trip(tmp_path):
    set_assignment(tmp_path, "501", skip=True)
    set_assignment(tmp_path, "502", session="pre")

    assert load_session_assignments(tmp_path) == {
        "501": {"skip": True},
        "502": {"session": "pre"},
    }
    raw = json.loads((tmp_path / "code" / "session_assignments.json").read_text())
    assert raw["version"] == 1


def test_labels_are_kept_exactly_as_given(tmp_path):
    set_assignment(tmp_path, "1", session="01")
    set_assignment(tmp_path, "2", session="1")

    assert load_session_assignments(tmp_path) == {
        "1": {"session": "01"},
        "2": {"session": "1"},
    }


def test_a_project_json_path_resolves_to_its_folder(tmp_path):
    (tmp_path / "project.json").write_text("{}")
    set_assignment(tmp_path / "project.json", "7", skip=True)

    assert load_session_assignments(tmp_path) == {"7": {"skip": True}}


def test_exactly_one_of_skip_or_session(tmp_path):
    with pytest.raises(SessionAssignmentError):
        set_assignment(tmp_path, "1")
    with pytest.raises(SessionAssignmentError):
        set_assignment(tmp_path, "1", skip=True, session="pre")
    with pytest.raises(SessionAssignmentError):
        set_assignment(tmp_path, "1", session="  ")
    assert not (tmp_path / "code" / "session_assignments.json").exists()


def test_unset_removes_one_and_rejects_unknown(tmp_path):
    set_assignment(tmp_path, "1", skip=True)
    set_assignment(tmp_path, "2", skip=True)

    assert unset_assignment(tmp_path, "1") == {"2": {"skip": True}}
    with pytest.raises(SessionAssignmentError, match="999"):
        unset_assignment(tmp_path, "999")


def test_malformed_file_is_reported(tmp_path):
    path = tmp_path / "code" / "session_assignments.json"
    path.parent.mkdir()
    path.write_text('{"version": 1, "responses": {"1": {"skip": "yes"}}}')

    with pytest.raises(SessionAssignmentError, match="session_assignments.json"):
        load_session_assignments(tmp_path)
