import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent.parent
JSON_EDITOR_SCRIPT = REPO_ROOT / "app" / "static" / "js" / "json-editor.js"


class TestJsonEditorWorkflowWiring(unittest.TestCase):
    def test_json_editor_uses_api_fallback_for_project_requests(self):
        content = JSON_EDITOR_SCRIPT.read_text(encoding="utf-8")

        self.assertIn("async function fetchWithApiFallback(", content)
        self.assertIn("url.startsWith('/api/') || url.startsWith('/editor/api/')", content)
        self.assertIn("await fetchWithApiFallback(`/editor/api/file/${fileType}`);", content)
        self.assertIn("await fetchWithApiFallback(`/editor/api/schema/${fileType}`);", content)
        self.assertNotIn("await fetch(`/editor/api/file/${fileType}`)", content)
        self.assertNotIn("await fetch(`/editor/api/schema/${fileType}`)", content)


if __name__ == "__main__":
    unittest.main()