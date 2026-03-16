import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent.parent
BASE_TEMPLATE = REPO_ROOT / "app" / "templates" / "base.html"


class TestNavbarProjectEventWiring(unittest.TestCase):
    def test_project_change_event_wires_navbar_state(self):
        content = BASE_TEMPLATE.read_text(encoding="utf-8")

        self.assertIn("window.addEventListener('prism-project-changed'", content)
        self.assertIn("function applyNavbarStateFromProjectState(projectState)", content)
        self.assertIn("setFileManagementState(Boolean(nextPath));", content)
        self.assertIn("setDerivativesState(Boolean(nextPath));", content)


if __name__ == "__main__":
    unittest.main()
