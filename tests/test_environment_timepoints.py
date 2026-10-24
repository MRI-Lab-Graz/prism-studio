"""Environment import follows the project's Timepoints: single -> ses-1, multiple -> the session map."""

import json

import pytest

from src.session_map import SessionsNotMappedError, TimepointsNotDeclaredError, save_session_map
from tests.test_environment_labels import _convert as _run

ROWS = [("P1", "pre", "2025-03-04 10:00", "47.1", "15.4"), ("P2", "post", "2025-03-04 11:00", "47.1", "15.4")]


def _convert(tmp_path, monkeypatch, rows, timepoints, mapping=None, **kw):
    study = {} if timepoints is None else {"StudyDesign": {"Timepoints": timepoints}}
    return _run(tmp_path, monkeypatch, rows, project_json=json.dumps(study), mapping=mapping, **kw)


def _sessions(project):
    return sorted({p.name for p in project.glob("sub-*/ses-*")})


def test_single_project_writes_ses_1_for_any_label_and_says_so(tmp_path, monkeypatch):
    project, logs = _convert(tmp_path, monkeypatch, ROWS, "single")
    assert _sessions(project) == ["ses-1"]
    assert any("ses-1" in m and "'pre'" in m for m in logs)


def test_single_project_ignores_a_session_override(tmp_path, monkeypatch):
    project, _ = _convert(tmp_path, monkeypatch, ROWS, "single", session_col=None, session_override="x")
    assert _sessions(project) == ["ses-1"]


def test_multiple_project_uses_the_map(tmp_path, monkeypatch):
    project, _ = _convert(tmp_path, monkeypatch, ROWS, "multiple", {"pre": "1", "post": "2"})
    assert _sessions(project) == ["ses-1", "ses-2"]


def test_multiple_project_blocks_an_unmapped_label_and_writes_nothing(tmp_path, monkeypatch):
    with pytest.raises(SessionsNotMappedError):
        _convert(tmp_path, monkeypatch, ROWS, "multiple", {"pre": "1"})
    assert not list((tmp_path / "p").glob("sub-*"))


def test_undeclared_project_is_refused_with_the_declare_message(tmp_path, monkeypatch):
    with pytest.raises(TimepointsNotDeclaredError):
        _convert(tmp_path, monkeypatch, ROWS, None)
