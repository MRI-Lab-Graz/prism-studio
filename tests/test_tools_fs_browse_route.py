import os
import sys
import tempfile
import unittest
from pathlib import Path

from flask import Flask

current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(current_dir)
app_path = os.path.join(project_root, "app")

if app_path not in sys.path:
    sys.path.insert(0, app_path)

from src.web.blueprints.tools import tools_bp  # noqa: E402


class TestToolsFilesystemBrowseRoute(unittest.TestCase):
    def setUp(self):
        self.app = Flask(__name__)
        self.app.register_blueprint(tools_bp)
        self.client = self.app.test_client()

    def test_fs_browse_lists_visible_directories_and_project_json(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            resolved_root = root.resolve()
            (root / "study").mkdir()
            (root / ".hidden").mkdir()
            (root / "project.json").write_text("{}", encoding="utf-8")

            response = self.client.get(
                "/api/fs/browse", query_string={"path": str(root)}
            )

            self.assertEqual(response.status_code, 200)
            payload = response.get_json()
            self.assertEqual(payload["path"], str(resolved_root))
            self.assertEqual(
                payload["project_json_path"], str(resolved_root / "project.json")
            )
            self.assertTrue(payload["has_project_json"])
            self.assertEqual(
                payload["dirs"],
                [{"name": "study", "path": str(resolved_root / "study")}],
            )

    def test_fs_browse_rejects_non_directories(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            file_path = Path(tmp_dir) / "not_a_directory.txt"
            file_path.write_text("hello", encoding="utf-8")

            response = self.client.get(
                "/api/fs/browse", query_string={"path": str(file_path)}
            )

            self.assertEqual(response.status_code, 400)
            self.assertEqual(response.get_json()["error"], "Not a directory")


if __name__ == "__main__":
    unittest.main()