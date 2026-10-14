import os
import sys
import tempfile
import unittest
from unittest import mock
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

    def test_fs_browse_skips_unreadable_entry_instead_of_truncating(self):
        # Windows home dirs hold junctions ("Application Data") whose is_dir()
        # raises PermissionError; that used to abort the whole listing.
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            (root / "Application Data").mkdir()
            (root / "Documents").mkdir()
            real_is_dir = Path.is_dir

            def flaky_is_dir(self):
                if self.name == "Application Data":
                    raise PermissionError("denied")
                return real_is_dir(self)

            with mock.patch.object(Path, "is_dir", flaky_is_dir):
                response = self.client.get(
                    "/api/fs/browse", query_string={"path": str(root)}
                )

            names = [d["name"] for d in response.get_json()["dirs"]]
            self.assertEqual(names, ["Documents"])

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
