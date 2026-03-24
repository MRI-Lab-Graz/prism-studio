import os
import sys
import tempfile
from pathlib import Path

current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(current_dir)
app_path = os.path.join(project_root, "app")
if app_path not in sys.path:
    sys.path.insert(0, app_path)

from src.web.blueprints import projects_metadata_helpers as metadata_helpers


def test_write_project_json_normalizes_paths_section():
    with tempfile.TemporaryDirectory() as tmp_dir:
        project_root = Path(tmp_dir)

        payload = {
            "name": "demo",
            "paths": {
                "sourcedata": r"sourcedata\\survey",
                "rawdata": "rawdata//nested///level",
                "remote": "https://example.org/path",
            },
        }

        metadata_helpers._write_project_json(project_root, payload)

        saved = (project_root / "project.json").read_text(encoding="utf-8")
        assert '"sourcedata": "sourcedata/survey"' in saved
        assert '"rawdata": "rawdata/nested/level"' in saved
        assert '"remote": "https://example.org/path"' in saved


def test_read_project_json_normalizes_legacy_windows_paths():
    with tempfile.TemporaryDirectory() as tmp_dir:
        project_root = Path(tmp_dir)
        (project_root / "project.json").write_text(
            '{"name": "demo", "paths": {"sourcedata": "code\\\\library\\\\survey"}}',
            encoding="utf-8",
        )

        loaded = metadata_helpers._read_project_json(project_root)

        assert loaded["paths"]["sourcedata"] == "code/library/survey"
