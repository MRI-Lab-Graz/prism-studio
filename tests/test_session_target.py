import json

import pytest

from src.session_map import (
    SINGLE_SESSION,
    SessionsNotMappedError,
    TimepointsNotDeclaredError,
    save_session_map,
    session_target,
    single_session_warning,
)


def _p(tmp_path, tp):
    d = {"StudyDesign": {"Timepoints": tp}} if tp else {}
    (tmp_path / "project.json").write_text(json.dumps(d), encoding="utf-8")
    return tmp_path


def test_no_project_json_returns_none(tmp_path):
    assert session_target(tmp_path, "pre") is None


@pytest.mark.parametrize("label", ["pre", "1", "01", "", "ses-3"])
def test_single_is_always_one(tmp_path, label):
    assert session_target(_p(tmp_path, "single"), label) == SINGLE_SESSION == "1"


def test_multiple_uses_map_and_raises_when_unmapped(tmp_path):
    p = _p(tmp_path, "multiple")
    save_session_map(p, {"pre": "1"})
    assert session_target(p, "pre") == "1"
    with pytest.raises(SessionsNotMappedError):
        session_target(p, "post")


def test_undeclared_raises(tmp_path):
    with pytest.raises(TimepointsNotDeclaredError):
        session_target(_p(tmp_path, None), "pre")


def test_single_warning_only_when_label_replaced():
    assert single_session_warning("pre") and "ses-1" in single_session_warning("pre")
    assert single_session_warning("1") is None and single_session_warning("") is None
