"""Session map rules: exact labels, explicit entries, no guessing."""

import json

import pytest

from src.session_map import (
    SessionMapError,
    SessionsNotMappedError,
    TimepointsNotDeclaredError,
    apply_session_map,
    load_session_map,
    project_timepoints,
    require_sessions_mapped,
    save_session_map,
    session_map_for_conversion,
    set_session_entries,
    unmapped_labels,
)


def make_project(tmp_path, timepoints="multiple", project_json=True):
    if project_json:
        study = {} if timepoints is None else {"StudyDesign": {"Timepoints": timepoints}}
        (tmp_path / "project.json").write_text(json.dumps(study))
    return tmp_path


def test_timepoints_states(tmp_path):
    assert project_timepoints(tmp_path) is None  # no project.json: not a PRISM project
    make_project(tmp_path, timepoints=None)
    assert project_timepoints(tmp_path) == "undeclared"
    make_project(tmp_path, "single")
    assert project_timepoints(tmp_path) == "single"
    make_project(tmp_path, "multiple")
    assert project_timepoints(tmp_path) == "multiple"
    make_project(tmp_path, "sometimes")  # unknown value is not a declaration
    assert project_timepoints(tmp_path) == "undeclared"


def test_timepoints_accepts_the_project_json_path(tmp_path):
    make_project(tmp_path, "multiple")
    assert project_timepoints(tmp_path / "project.json") == "multiple"


def test_missing_map_file_is_an_empty_map(tmp_path):
    assert load_session_map(make_project(tmp_path)) == {}


def test_save_then_load_round_trips_and_creates_code_folder(tmp_path):
    root = make_project(tmp_path)
    save_session_map(root, {"pre": "1", "T0": "1", "post": "2"})
    assert (root / "code" / "session_map.json").is_file()
    assert load_session_map(root) == {"pre": "1", "T0": "1", "post": "2"}  # many-to-one is fine


@pytest.mark.parametrize("target", ["", "ses-1", "a b", "é", "1_2"])
def test_invalid_targets_are_rejected(tmp_path, target):
    with pytest.raises(SessionMapError, match="pre"):
        save_session_map(make_project(tmp_path), {"pre": target})


def test_empty_source_label_is_rejected(tmp_path):
    with pytest.raises(SessionMapError):
        save_session_map(make_project(tmp_path), {"  ": "1"})


@pytest.mark.parametrize("content", ["{not json", "[]", '{"pre": 1}', '{"pre": "a b"}'])
def test_corrupt_map_file_raises_and_names_the_file(tmp_path, content):
    root = make_project(tmp_path)
    (root / "code").mkdir()
    (root / "code" / "session_map.json").write_text(content)
    with pytest.raises(SessionMapError, match="session_map.json"):
        load_session_map(root)


def test_set_session_entries_merges_without_dropping_existing_entries(tmp_path):
    root = make_project(tmp_path)
    save_session_map(root, {"pre": "1"})
    assert set_session_entries(root, {"post": "2"}) == {"pre": "1", "post": "2"}
    assert load_session_map(root) == {"pre": "1", "post": "2"}


def test_labels_compare_exactly(tmp_path):
    mapping = {"1": "a"}
    assert unmapped_labels(["1", "01", "ses-1", "Pre"], mapping) == ["01", "ses-1", "Pre"]
    assert apply_session_map(" 1 ", mapping) == "a"  # only whitespace is trimmed


def test_spreadsheet_float_artifact_matches_the_integer_label():
    assert apply_session_map(1.0, {"1": "a"}) == "a"
    assert unmapped_labels([1.0, 2.0], {"1": "a"}) == ["2"]


def test_blank_and_nan_are_unmapped_never_defaulted():
    assert unmapped_labels(["", None, float("nan"), "  "], {"1": "a"}) == [""]
    with pytest.raises(SessionsNotMappedError) as info:
        apply_session_map("", {"1": "a"})
    assert info.value.labels == [""]
    assert "(empty)" in str(info.value)


def test_unmapped_labels_are_deduplicated_in_order_of_appearance():
    assert unmapped_labels(["b", "a", "b", "c"], {}) == ["b", "a", "c"]


def test_error_lists_every_missing_label_and_names_the_ways_to_fix_it():
    with pytest.raises(SessionsNotMappedError) as info:
        require_sessions_mapped({"pre": "1"}, ["pre", "post", "T2"])
    assert info.value.labels == ["post", "T2"]
    message = str(info.value)
    assert "'post'" in message and "'T2'" in message
    assert "session_map.json" in message and "session-map set" in message


def test_require_sessions_mapped_with_no_map_is_a_no_op():
    require_sessions_mapped(None, ["anything", ""])


def test_conversion_map_by_project_state(tmp_path):
    assert session_map_for_conversion(None) is None
    assert session_map_for_conversion(tmp_path) is None  # no project.json
    make_project(tmp_path, "single")
    assert session_map_for_conversion(tmp_path) is None
    make_project(tmp_path, "multiple")
    assert session_map_for_conversion(tmp_path) == {}  # declared, nothing mapped yet
    save_session_map(tmp_path, {"pre": "1"})
    assert session_map_for_conversion(tmp_path) == {"pre": "1"}
    make_project(tmp_path, None)
    with pytest.raises(TimepointsNotDeclaredError, match="Timepoints"):
        session_map_for_conversion(tmp_path)
