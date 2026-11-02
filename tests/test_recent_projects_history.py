import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "app"))

from flask import Flask

from src.recent_projects import RECENT_MAX, record_recent
from src.web.blueprints import projects_helpers
from src.web.blueprints.projects_helpers import (
    _load_recent_projects,
    _record_recent_project,
)
from src.web.blueprints.projects_lifecycle_handlers import handle_set_recent_projects


def _store(monkeypatch, tmp_path, paths):
    file_path = tmp_path / "recent.json"
    file_path.write_text(json.dumps([{"path": str(p)} for p in paths]), encoding="utf-8")
    monkeypatch.setattr(projects_helpers, "_recent_projects_file", lambda: file_path)
    return file_path


def _stored_paths(file_path):
    return [p["path"] for p in json.loads(file_path.read_text(encoding="utf-8"))]


def _dirs(tmp_path, n):
    dirs = [tmp_path / f"p{i}" for i in range(n)]
    for d in dirs:
        d.mkdir()
    return dirs


def test_recording_a_sixth_project_keeps_the_older_ones(monkeypatch, tmp_path):
    dirs = _dirs(tmp_path, 7)
    file_path = _store(monkeypatch, tmp_path, dirs[:6])

    _record_recent_project({"path": str(dirs[6])})

    stored = _stored_paths(file_path)
    assert stored[0] == str(dirs[6].resolve())
    assert len(stored) == 7


def test_recording_a_known_project_moves_it_to_the_front_once(monkeypatch, tmp_path):
    dirs = _dirs(tmp_path, 3)
    file_path = _store(monkeypatch, tmp_path, dirs)

    _record_recent_project({"path": str(dirs[2])})

    assert _stored_paths(file_path) == [str(d.resolve()) for d in (dirs[2], dirs[0], dirs[1])]


def test_recording_keeps_a_project_whose_drive_is_unmounted(monkeypatch, tmp_path):
    alive, other = _dirs(tmp_path, 2)
    gone = tmp_path / "gone"
    file_path = _store(monkeypatch, tmp_path, [gone, alive])

    _record_recent_project({"path": str(other)})

    assert str(gone.resolve()) in _stored_paths(file_path)
    assert [p["path"] for p in _load_recent_projects()] == [str(d.resolve()) for d in (other, alive)]


def test_history_is_capped_at_twenty(monkeypatch, tmp_path):
    dirs = _dirs(tmp_path, 22)
    file_path = _store(monkeypatch, tmp_path, dirs[:21])

    _record_recent_project({"path": str(dirs[21])})

    assert RECENT_MAX == 20
    assert len(_stored_paths(file_path)) == 20
    assert _stored_paths(file_path)[0] == str(dirs[21].resolve())


def test_record_recent_is_a_move_to_front_with_cap():
    stored = [{"path": f"/p{i}"} for i in range(RECENT_MAX)]
    out = record_recent(stored, {"path": "/p3"})
    assert [p["path"] for p in out][:3] == ["/p3", "/p0", "/p1"]
    assert len(out) == RECENT_MAX


def test_the_route_records_one_project_instead_of_replacing_the_list(monkeypatch, tmp_path):
    dirs = _dirs(tmp_path, 7)
    file_path = _store(monkeypatch, tmp_path, dirs[:6])

    with Flask(__name__).test_request_context(
        "/api/projects/recent", method="POST", json={"project": {"path": str(dirs[6])}}
    ):
        response = handle_set_recent_projects()

    assert response.get_json()["success"]
    assert len(_stored_paths(file_path)) == 7
