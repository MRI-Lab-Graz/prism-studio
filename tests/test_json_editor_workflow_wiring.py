import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
JSON_EDITOR_SCRIPT = REPO_ROOT / "app" / "static" / "js" / "json-editor.js"
JSON_EDITOR_TEMPLATE = REPO_ROOT / "app" / "templates" / "json_editor.html"
SHARED_API_SCRIPT = REPO_ROOT / "app" / "static" / "js" / "shared" / "api.js"


class TestJsonEditorWorkflowWiring(unittest.TestCase):
    def test_json_editor_template_uses_shared_header_and_help_panel_macros(self):
        content = JSON_EDITOR_TEMPLATE.read_text(encoding="utf-8")

        self.assertIn(
            '{% from "includes/ui/macros.html" import page_header, help_panel %}',
            content,
        )
        self.assertIn("{{ page_header(", content)
        self.assertIn("{% call help_panel(", content)

    def test_json_editor_uses_api_fallback_for_project_requests(self):
        content = JSON_EDITOR_SCRIPT.read_text(encoding="utf-8")
        shared_api_content = SHARED_API_SCRIPT.read_text(encoding="utf-8")

        self.assertIn(
            "const jsonEditorScriptUrl = document.currentScript?.src || window.location.href;",
            content,
        )
        self.assertIn("function loadSharedFetchWithApiFallback() {", content)
        self.assertIn("async function fetchWithApiFallback(", content)
        self.assertIn(
            "return sharedFetchWithApiFallback(url, options, fallbackMessage);",
            content,
        )
        self.assertIn(
            "url.startsWith('/api/') || url.startsWith('/editor/api/')",
            shared_api_content,
        )
        self.assertIn(
            "await fetchWithApiFallback(`/editor/api/file/${fileType}`);", content
        )
        self.assertIn(
            "await fetchWithApiFallback(`/editor/api/schema/${fileType}`);", content
        )
        self.assertNotIn("await fetch(`/editor/api/file/${fileType}`)", content)
        self.assertNotIn("await fetch(`/editor/api/schema/${fileType}`)", content)


if __name__ == "__main__":
    unittest.main()
