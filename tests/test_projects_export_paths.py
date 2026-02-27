from pathlib import Path
import sys


sys.path.insert(0, str(Path(__file__).parent.parent / "app"))

from src.web.blueprints.projects import _resolve_project_root_path


def test_resolve_project_root_from_project_json(tmp_path):
    project_dir = tmp_path / "study"
    project_dir.mkdir()
    project_json = project_dir / "project.json"
    project_json.write_text("{}", encoding="utf-8")

    resolved = _resolve_project_root_path(str(project_json))

    assert resolved == project_dir


def test_resolve_project_root_from_directory(tmp_path):
    project_dir = tmp_path / "study"
    project_dir.mkdir()

    resolved = _resolve_project_root_path(str(project_dir))

    assert resolved == project_dir


def test_resolve_project_root_rejects_invalid_path(tmp_path):
    missing = tmp_path / "does_not_exist"

    resolved = _resolve_project_root_path(str(missing))

    assert resolved is None
