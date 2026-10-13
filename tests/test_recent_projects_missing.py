import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "app"))

from src.web.blueprints import projects_helpers
from src.web.blueprints.projects_helpers import _load_recent_projects


def _store(monkeypatch, tmp_path, entries):
    file_path = tmp_path / "recent.json"
    file_path.write_text(json.dumps(entries), encoding="utf-8")
    monkeypatch.setattr(projects_helpers, "_recent_projects_file", lambda: file_path)
    return file_path


def test_recent_projects_whose_folder_is_gone_are_not_listed(monkeypatch, tmp_path):
    alive = tmp_path / "alive"
    alive.mkdir()
    gone = tmp_path / "gone"  # never created: e.g. a deleted pytest tmp dir
    _store(monkeypatch, tmp_path, [{"path": str(gone)}, {"path": str(alive)}])

    assert [p["path"] for p in _load_recent_projects()] == [str(alive.resolve())]


def test_hiding_missing_projects_does_not_rewrite_the_stored_list(monkeypatch, tmp_path):
    # An unmounted network drive must come back once it is mounted again.
    gone = tmp_path / "gone"
    file_path = _store(monkeypatch, tmp_path, [{"path": str(gone)}])
    before = file_path.read_text(encoding="utf-8")

    _load_recent_projects()

    assert file_path.read_text(encoding="utf-8") == before
