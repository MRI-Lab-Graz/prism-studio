import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent.parent
OPEN_FORM_TEMPLATE = REPO_ROOT / "app" / "templates" / "includes" / "projects" / "open_form.html"
PROJECTS_METADATA_MODULE = REPO_ROOT / "app" / "static" / "js" / "modules" / "projects" / "metadata.js"


class TestProjectsCompactViewWiring(unittest.TestCase):
    def test_open_project_section_starts_collapsed(self):
        content = OPEN_FORM_TEMPLATE.read_text(encoding="utf-8")

        self.assertIn('aria-expanded="false" aria-controls="openProjectSection"', content)
        self.assertIn('<div class="collapse" id="openProjectSection">', content)
        self.assertNotIn('<div class="collapse show" id="openProjectSection">', content)

    def test_metadata_card_is_not_forced_open_when_shown(self):
        content = PROJECTS_METADATA_MODULE.read_text(encoding="utf-8")

        self.assertNotIn("window.bootstrap.Collapse.getOrCreateInstance(metadataSection).show();", content)


if __name__ == "__main__":
    unittest.main()