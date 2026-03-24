import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
BASE_TEMPLATE = REPO_ROOT / "app" / "templates" / "base.html"


class TestVersionUpdateModalWiring(unittest.TestCase):
    def test_base_template_contains_startup_update_modal(self):
        content = BASE_TEMPLATE.read_text(encoding="utf-8")

        self.assertIn("prismVersionUpdateModal", content)
        self.assertIn("prism_studio_update_available", content)
        self.assertIn("window.sessionStorage.getItem(modalStorageKey)", content)
        self.assertIn("new bootstrap.Modal(prismVersionUpdateModalEl)", content)


if __name__ == "__main__":
    unittest.main()
