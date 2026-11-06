"""An older project's saved git name and email are moved to the computer, never lost on the way."""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
for p in (ROOT, ROOT / "app"):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

from src.project_settings import adopt_legacy_project_identity  # noqa: E402


def _project(tmp_path, **extra):
    (tmp_path / ".prismrc.json").write_text(json.dumps(extra), encoding="utf-8")
    return tmp_path


def _saved(tmp_path):
    return json.loads((tmp_path / ".prismrc.json").read_text(encoding="utf-8"))


def _computer(monkeypatch, identity):
    stored = {}
    monkeypatch.setattr("src.datalad_doctor.get_git_identity", lambda: identity)
    monkeypatch.setattr("src.datalad_doctor.set_git_identity", lambda n, e: stored.update(name=n, email=e))
    return stored


def test_a_complete_identity_moves_to_the_computer_and_leaves_the_project(tmp_path, monkeypatch):
    stored = _computer(monkeypatch, {"name": "", "email": ""})
    adopt_legacy_project_identity(_project(tmp_path, gitUserName="Ada", gitUserEmail="ada@example.org", other=1))
    assert stored == {"name": "Ada", "email": "ada@example.org"}
    assert _saved(tmp_path) == {"other": 1}


def test_an_identity_the_computer_already_has_wins_and_the_project_copy_is_removed(tmp_path, monkeypatch):
    stored = _computer(monkeypatch, {"name": "Me", "email": "me@example.org"})
    adopt_legacy_project_identity(_project(tmp_path, gitUserName="Ada", gitUserEmail="ada@example.org"))
    assert stored == {} and _saved(tmp_path) == {}


def test_a_half_identity_that_cannot_move_stays_in_the_project(tmp_path, monkeypatch):
    stored = _computer(monkeypatch, {"name": "", "email": ""})
    adopt_legacy_project_identity(_project(tmp_path, gitUserName="Ada"))
    assert stored == {} and _saved(tmp_path) == {"gitUserName": "Ada"}
