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
        self.assertIn("badge bg-light text-muted", content)
        self.assertIn('id="navbarDataladToggle"', content)
        self.assertIn("function renderNavbarDataladState(projectState)", content)
        self.assertIn("setFileManagementState(Boolean(nextPath));", content)
        self.assertIn("setDerivativesState(Boolean(nextPath));", content)

    def test_navbar_datalad_indicator_wires_direct_save_without_menu(self):
        content = BASE_TEMPLATE.read_text(encoding="utf-8")

        self.assertNotIn('id="navbarDataladMenu"', content)
        self.assertIn('id="navbarDataladStateBadge"', content)
        self.assertIn('id="navbarDataladTrackedIcon"', content)
        self.assertIn('id="navbarDataladToggleFeedback"', content)
        self.assertIn('data-can-enable="{{ \'true\' if current_project_datalad.can_enable else \'false\' }}"', content)
        self.assertIn("function setNavbarDataladFeedback(message, kind = 'muted', toggleLabel = '')", content)
        self.assertIn("async function saveNavbarDataladSnapshot()", content)
        self.assertIn("window.prompt('Commit message for this checkpoint'", content)
        self.assertIn("navbarFetchWithApiFallback('/api/projects/datalad/save'", content)
        self.assertIn("function getNavbarDataladOperationState()", content)
        self.assertIn("function setNavbarDataladOperationState(active, source = '')", content)
        self.assertIn("function buildNavbarAutosaveFailureMessage(autosaveResult)", content)
        self.assertIn("const autosaveMessage = buildNavbarAutosaveFailureMessage(data.autosave_previous);", content)
        self.assertIn("navbarDataladToggle?.addEventListener('click', async function(e)", content)
        self.assertIn("window.setNavbarDataladFeedback = setNavbarDataladFeedback;", content)
        self.assertNotIn("const navbarDataladSaveBtn = document.getElementById('navbarDataladSaveBtn');", content)
        self.assertNotIn("const navbarDataladEnableBtn = document.getElementById('navbarDataladEnableBtn');", content)

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
