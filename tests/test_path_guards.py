"""Path checks in project handlers: sibling-folder escape and the root/home guard."""

import sys
from pathlib import Path

import pytest
from flask import Flask

sys.path.insert(0, str(Path(__file__).parent.parent / "app"))

from src.web.blueprints.projects_lifecycle_handlers import _is_filesystem_root_or_home
from src.web.blueprints.projects_sourcedata_handlers import handle_get_sourcedata_file


def test_filesystem_root_and_home_are_protected():
    assert _is_filesystem_root_or_home(Path(Path.home().anchor))
    assert _is_filesystem_root_or_home(Path.home())
    assert not _is_filesystem_root_or_home(Path.home() / "study")


def _call(project: Path, name: str):
    app = Flask(__name__)
    with app.test_request_context(f"/x?name={name}"):
        resp = handle_get_sourcedata_file(lambda: {"path": str(project)})
    return resp


def test_sourcedata_download_serves_files_inside_sourcedata(tmp_path):
    (tmp_path / "sourcedata").mkdir()
    (tmp_path / "sourcedata" / "a.txt").write_text("ok")
    resp = _call(tmp_path, "a.txt")
    assert resp.status_code == 200


def test_sourcedata_download_rejects_sibling_folder_with_same_prefix(tmp_path):
    (tmp_path / "sourcedata").mkdir()
    (tmp_path / "sourcedata_old").mkdir()
    (tmp_path / "sourcedata_old" / "secret.txt").write_text("nope")
    resp, status = _call(tmp_path, "../sourcedata_old/secret.txt")
    assert status == 400
