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
            self.assertEqual(len(payload["dirs"]), 1)
            self.assertEqual(payload["dirs"][0]["name"], "study")
            self.assertEqual(payload["dirs"][0]["path"], str(resolved_root / "study"))

    def _browse(self, root, **params):
        params.update(path=str(root), include_files="1")
        return self.client.get("/api/fs/browse", query_string=params).get_json()

    def test_fs_browse_sorts_by_size_and_modified_with_order(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            for name, size, mtime in (("a.txt", 30, 300), ("b.txt", 10, 100), ("c.txt", 20, 200)):
                f = root / name
                f.write_text("x" * size, encoding="utf-8")
                os.utime(f, (mtime, mtime))

            names = lambda p: [f["name"] for f in p["files"]]  # noqa: E731
            self.assertEqual(names(self._browse(root)), ["a.txt", "b.txt", "c.txt"])
            self.assertEqual(names(self._browse(root, sort="size")), ["b.txt", "c.txt", "a.txt"])
            self.assertEqual(names(self._browse(root, sort="size", order="desc")), ["a.txt", "c.txt", "b.txt"])
            by_date = self._browse(root, sort="modified", order="desc")
            self.assertEqual(names(by_date), ["a.txt", "c.txt", "b.txt"])
            self.assertEqual(by_date["files"][0]["modified"], 300)

    def test_fs_browse_sort_keeps_directories_sorted_and_ignores_bad_sort(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            for name, mtime in (("a_old", 100), ("b_new", 200)):
                (root / name).mkdir()
                os.utime(root / name, (mtime, mtime))

            by_date = self._browse(root, sort="modified", order="desc")
            self.assertEqual([d["name"] for d in by_date["dirs"]], ["b_new", "a_old"])
            fallback = self._browse(root, sort="bogus")
            self.assertEqual([d["name"] for d in fallback["dirs"]], ["a_old", "b_new"])

    def test_fs_browse_returns_breadcrumbs_from_root_to_current(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            current = (Path(tmp_dir) / "study").resolve()
            current.mkdir()

            crumbs = self._browse(current)["crumbs"]

            self.assertEqual(crumbs[-1], {"name": "study", "path": str(current)})
            self.assertEqual(crumbs[0]["path"], str(Path(current.anchor)))
            self.assertEqual(
                [c["path"] for c in crumbs],
                [str(p) for p in reversed([current, *current.parents])],
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

    def test_fs_browse_file_path_lists_its_parent_folder(self):
        # Pickers reopen at the previously chosen value, which is often a file.
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir).resolve()
            file_path = root / "data.csv"
            file_path.write_text("a", encoding="utf-8")

            response = self.client.get(
                "/api/fs/browse",
                query_string={"path": str(file_path), "include_files": "1"},
            )

            self.assertEqual(response.status_code, 200)
            payload = response.get_json()
            self.assertEqual(payload["path"], str(root))
            self.assertEqual([f["name"] for f in payload["files"]], ["data.csv"])

    def test_fs_mkdir_creates_folder_and_rejects_bad_names(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir).resolve()

            ok = self.client.post("/api/fs/mkdir", json={"parent": str(root), "name": "study"})
            self.assertEqual(ok.status_code, 200)
            self.assertEqual(ok.get_json()["path"], str(root / "study"))
            self.assertTrue((root / "study").is_dir())

            bad = self.client.post("/api/fs/mkdir", json={"parent": str(root), "name": "a:b"})
            self.assertEqual(bad.status_code, 400)
            self.assertIn("error", bad.get_json())

    def test_fs_browse_accepts_a_path_pasted_with_quotes(self):
        # Explorer's "Copy as path" puts double quotes around the path.
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir).resolve()
            (root / "study").mkdir()

            response = self.client.get(
                "/api/fs/browse", query_string={"path": f'"{root}"'}
            )

            self.assertEqual(response.get_json()["path"], str(root))

    def test_fs_browse_hides_entries_with_the_windows_hidden_attribute(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            (root / "visible").mkdir()
            (root / "$RECYCLE.BIN").mkdir()

            def fake_hidden(entry):
                return entry.name == "$RECYCLE.BIN"

            with mock.patch("src.web.blueprints.tools._is_hidden", fake_hidden):
                names = [d["name"] for d in self._browse(root)["dirs"]]
                shown = [
                    d["name"]
                    for d in self._browse(root, include_hidden="1")["dirs"]
                ]

            self.assertEqual(names, ["visible"])
            self.assertEqual(sorted(shown), ["$RECYCLE.BIN", "visible"])

    @unittest.skipUnless(sys.platform == "win32", "drive-relative paths are Windows-only")
    def test_fs_browse_bare_drive_letter_means_the_drive_root_not_the_cwd(self):
        drive = Path.cwd().drive
        response = self.client.get("/api/fs/browse", query_string={"path": drive})
        self.assertEqual(response.get_json()["path"], drive + "\\")

    def test_fs_browse_missing_path_falls_back_to_existing_ancestor(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir).resolve()

            response = self.client.get(
                "/api/fs/browse",
                query_string={"path": str(root / "gone" / "deeper")},
            )

            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.get_json()["path"], str(root))


if __name__ == "__main__":
    unittest.main()
