"""Decisions file: code/session_assignments.json, keyed by LimeSurvey response id."""

import json

import pytest

from src.session_assignments import (
    SessionAssignmentError,
    load_session_assignments,
    set_assignment,
    survey_id_of,
    unset_assignment,
)
from tests.lsa_fixtures import make_lsa


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
    assert raw["version"] == 2
    assert raw["surveys"]["default"]["responses"]["501"] == {"skip": True}


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
    path.write_text('{"version": 2, "surveys": {"default": {"responses": {"1": {"skip": "yes"}}}}}')

    with pytest.raises(SessionAssignmentError, match="session_assignments.json"):
        load_session_assignments(tmp_path)


def test_same_response_id_in_two_surveys_is_independent(tmp_path):
    set_assignment(tmp_path, "5", survey_id="111", skip=True)

    assert load_session_assignments(tmp_path, "111") == {"5": {"skip": True}}
    assert load_session_assignments(tmp_path, "222") == {}
    assert load_session_assignments(tmp_path) == {}


def test_unset_removes_an_empty_survey_entry(tmp_path):
    set_assignment(tmp_path, "5", survey_id="111", skip=True)
    unset_assignment(tmp_path, "5", survey_id="111")

    raw = json.loads((tmp_path / "code" / "session_assignments.json").read_text())
    assert raw == {"version": 2, "surveys": {}}
    with pytest.raises(SessionAssignmentError):
        unset_assignment(tmp_path, "5", survey_id="111")


def test_old_format_file_is_reported(tmp_path):
    path = tmp_path / "code" / "session_assignments.json"
    path.parent.mkdir()
    path.write_text('{"version": 1, "responses": {"1": {"skip": true}}}')

    with pytest.raises(SessionAssignmentError, match="old format"):
        load_session_assignments(tmp_path)


def test_survey_id_of_archive_csv_and_plain_zip(tmp_path):
    import zipfile

    assert survey_id_of(make_lsa(tmp_path)) == "999999"
    assert survey_id_of(tmp_path / "data.csv") == "default"
    odd = tmp_path / "odd.lsa"
    with zipfile.ZipFile(odd, "w") as z:
        z.writestr("readme.txt", "x")
    assert survey_id_of(odd) == "default"
    assert survey_id_of(tmp_path / "missing.lsa") == "default"


def test_include_round_trip_in_the_v2_file(tmp_path):
    set_assignment(tmp_path, "25", survey_id="999999", include=True)

    assert load_session_assignments(tmp_path, "999999") == {"25": {"include": True}}
    raw = json.loads((tmp_path / "code" / "session_assignments.json").read_text())
    assert raw["surveys"]["999999"]["responses"]["25"] == {"include": True}


def test_include_needs_to_be_the_only_decision(tmp_path):
    with pytest.raises(SessionAssignmentError, match="(?i)exactly one"):
        set_assignment(tmp_path, "1", include=True, skip=True)
    with pytest.raises(SessionAssignmentError, match="(?i)exactly one"):
        set_assignment(tmp_path, "1", include=True, session="pre")


@pytest.mark.parametrize("bad", [{"include": False}, {"include": "yes"}, {"include": True, "skip": True}])
def test_a_malformed_include_entry_in_the_file_is_rejected(tmp_path, bad):
    (tmp_path / "code").mkdir()
    (tmp_path / "code" / "session_assignments.json").write_text(
        json.dumps({"version": 2, "surveys": {"d": {"responses": {"1": bad}}}})
    )
    with pytest.raises(SessionAssignmentError):
        load_session_assignments(tmp_path, "d")
