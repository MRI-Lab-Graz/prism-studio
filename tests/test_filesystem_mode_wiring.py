import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent.parent
FILESYSTEM_MODE_SCRIPT = REPO_ROOT / "app" / "static" / "js" / "filesystem-mode.js"


class TestFilesystemModeWiring(unittest.TestCase):
    def test_filesystem_mode_uses_shared_api_fallback_for_context_detection(self):
        content = FILESYSTEM_MODE_SCRIPT.read_text(encoding="utf-8")

        self.assertIn(
            "const filesystemModeScriptUrl = document.currentScript?.src || window.location.href;",
            content,
        )
        self.assertIn("function loadSharedFetchWithApiFallback() {", content)
        self.assertIn(
            "sharedFetchWithApiFallbackPromise = import(sharedApiModuleUrl).then(({ fetchWithApiFallback }) => {",
            content,
        )
        self.assertIn(
            "const settingsResponse = await fetchWithApiFallback('/api/settings/global-library');",
            content,
        )
        self.assertIn(
            "const response = await fetchWithApiFallback('/api/filesystem-context');",
            content,
        )
        self.assertIn(
            "return sharedFetchWithApiFallback(url, options, fallbackMessage);",
            content,
        )


if __name__ == "__main__":
    unittest.main()