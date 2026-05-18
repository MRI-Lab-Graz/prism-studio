import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
BASE_TEMPLATE = REPO_ROOT / "app" / "templates" / "base.html"


class TestNavbarProjectEventWiring(unittest.TestCase):
    def test_project_change_event_wires_navbar_state(self):
        content = BASE_TEMPLATE.read_text(encoding="utf-8")

        self.assertIn("window.addEventListener('prism-project-changed'", content)
        self.assertIn(
            "function applyNavbarStateFromProjectState(projectState)", content
        )
        self.assertIn('No project loaded', content)
        self.assertIn("badge bg-light text-muted border", content)
        self.assertIn("setFileManagementState(Boolean(nextPath));", content)
        self.assertIn("setDerivativesState(Boolean(nextPath));", content)

    def test_navbar_recent_project_loader_uses_credentialed_fallback_fetch(self):
        content = BASE_TEMPLATE.read_text(encoding="utf-8")

        self.assertIn("function normalizeNavbarFetchOptions(url, options = {})", content)
        self.assertIn("credentials: 'include'", content)
        self.assertIn(
            "return fetch(fallbackUrl, normalizeNavbarFetchOptions(fallbackUrl, options));",
            content,
        )

    def test_navbar_recent_project_selection_uses_pointerdown_bridge(self):
        content = BASE_TEMPLATE.read_text(encoding="utf-8")

        self.assertIn("let pointerTriggeredButton = null;", content)
        self.assertIn("projectsRecentList.addEventListener('pointerdown'", content)
        self.assertIn("projectsRecentList.addEventListener('click'", content)
        self.assertIn("if (pointerTriggeredButton === button)", content)


if __name__ == "__main__":
    unittest.main()
