import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
LIBRARY_TEMPLATE = REPO_ROOT / "app" / "templates" / "library.html"
LIBRARY_SCRIPT = REPO_ROOT / "app" / "static" / "js" / "library.js"


class TestLibraryWorkflowWiring(unittest.TestCase):
    def test_library_template_uses_shared_header_and_help_panel_macros(self):
        content = LIBRARY_TEMPLATE.read_text(encoding="utf-8")

        self.assertIn(
            '{% from "includes/ui/macros.html" import page_header, help_panel %}',
            content,
        )
        self.assertIn("{{ page_header(", content)
        self.assertIn("{% call help_panel(", content)

    def test_library_template_keeps_draft_action_buttons_and_event_delegation(self):
        template_content = LIBRARY_TEMPLATE.read_text(encoding="utf-8")
        script_content = LIBRARY_SCRIPT.read_text(encoding="utf-8")

        self.assertIn('data-action="create-draft"', template_content)
        self.assertIn('data-action="publish-survey"', template_content)
        self.assertIn('data-action="discard-draft"', template_content)
        self.assertIn(
            '<script type="module" src="{{ url_for(\'static\', filename=\'js/library.js\', v=prism_static_asset_token) }}"></script>',
            template_content,
        )
        self.assertIn("fetchWithRelativePathFallback", script_content)
        self.assertIn("const tableBody = document.querySelector('table tbody');", script_content)
        self.assertIn(
            "event.target.closest('button[data-action][data-filename]');",
            script_content,
        )
        self.assertIn(
            "/library/api/draft/${encodeURIComponent(filename)}",
            script_content,
        )
        self.assertIn(
            "/library/api/publish/${encodeURIComponent(filename)}",
            script_content,
        )


if __name__ == "__main__":
    unittest.main()
