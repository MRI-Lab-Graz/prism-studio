import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent.parent
FILESYSTEM_MODE_SCRIPT = REPO_ROOT / "app" / "static" / "js" / "filesystem-mode.js"


class TestFilesystemModeWiring(unittest.TestCase):
    def test_filesystem_mode_is_a_single_in_app_picker(self):
        content = FILESYSTEM_MODE_SCRIPT.read_text(encoding="utf-8")

        self.assertIn("window.PrismPathPicker = {", content)
        self.assertIn("pickServerFolder: pickFolder,", content)
        self.assertIn("pickServerFile: pickFile,", content)
        # No native dialog endpoints and no local/server mode detection.
        self.assertNotIn("/api/browse-", content)
        self.assertNotIn("/api/filesystem-context", content)
        self.assertNotIn("fetch", content)


if __name__ == "__main__":
    unittest.main()