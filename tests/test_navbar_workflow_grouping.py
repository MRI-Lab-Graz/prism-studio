import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
BASE_TEMPLATE = REPO_ROOT / "app" / "templates" / "base.html"


class TestNavbarWorkflowGrouping(unittest.TestCase):
    def test_workflow_dropdown_labels_present(self):
        content = BASE_TEMPLATE.read_text(encoding="utf-8")

        self.assertIn('id="projectsDropdown"', content)
        self.assertIn('text-primary"></i>Project', content)
        self.assertIn('id="prepareDropdown"', content)
        self.assertIn('text-success"></i>Prepare Data', content)
        self.assertIn('id="modifyDropdown"', content)
        self.assertIn('text-primary"></i>Modify in PRISM', content)
        self.assertIn('id="derivativesDropdown"', content)
        self.assertIn('text-warning"></i>Export Derivatives', content)
        self.assertIn('id="docsDropdown"', content)
        self.assertIn('me-1"></i>Docs', content)
        self.assertNotIn('>Core<', content)

    def test_workflow_hints_present(self):
        content = BASE_TEMPLATE.read_text(encoding="utf-8")

        self.assertIn('Next: Modify in PRISM', content)
        self.assertIn('Next: Export Derivatives', content)

    def test_workflow_item_subtitles_present(self):
        content = BASE_TEMPLATE.read_text(encoding="utf-8")

        self.assertIn('navbar-flow-item-hint', content)
        self.assertIn('Set the active project used by all workflow steps', content)
        self.assertIn('Import raw source files and normalize structure', content)
        self.assertIn('Move, rename, and align files with project conventions', content)
        self.assertIn('Write curated survey tables to derivative folders', content)
        self.assertIn('Guides, tutorials, and full feature documentation', content)
        self.assertIn('Reference rules and examples used across workflows', content)

    def test_specs_lives_under_docs_dropdown(self):
        content = BASE_TEMPLATE.read_text(encoding="utf-8")

        self.assertIn('id="docsDropdown"', content)
        self.assertIn('Online Docs', content)
        self.assertIn('>Specs</span>', content)

        modify_section = content.split('id="modifyDropdown"', 1)[1].split(
            'id="derivativesDropdown"', 1
        )[0]
        self.assertNotIn('>Specs</span>', modify_section)

        docs_section = content.split('id="docsDropdown"', 1)[1]
        self.assertIn('>Specs</span>', docs_section)
        self.assertIn('url_for(\'specifications\')', docs_section)

    def test_phase_active_flags_cover_deep_paths(self):
        content = BASE_TEMPLATE.read_text(encoding="utf-8")

        self.assertIn('{% set prepare_active =', content)
        self.assertIn("request_path.startswith('/converter')", content)
        self.assertIn("request_path.startswith('/template-editor')", content)

        self.assertIn('{% set modify_active =', content)
        self.assertIn("request_path.startswith('/validate')", content)
        self.assertIn("request_path.startswith('/file-management')", content)
        self.assertIn("request_path.startswith('/editor')", content)
        self.assertNotIn("request.endpoint in ['tools.file_management', 'specifications']", content)

        self.assertIn('{% set export_active =', content)
        self.assertIn("request_path.startswith('/survey-generator')", content)
        self.assertIn("request_path.startswith('/recipes')", content)

        self.assertIn('{% set docs_active =', content)
        self.assertIn("request_path.startswith('/specifications')", content)
        self.assertIn("request.endpoint in ['specifications']", content)


if __name__ == "__main__":
    unittest.main()
