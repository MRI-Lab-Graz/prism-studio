import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
BASE_TEMPLATE = REPO_ROOT / "app" / "templates" / "base.html"


class TestNavbarWorkflowGrouping(unittest.TestCase):
    def test_top_level_dropdown_labels_present(self):
        content = BASE_TEMPLATE.read_text(encoding="utf-8")

        self.assertIn('id="projectsDropdown"', content)
        self.assertIn('text-primary"></i>Project', content)
        self.assertIn('id="workflowDropdown"', content)
        self.assertIn('text-success"></i>Workflow', content)
        self.assertIn('id="docsDropdown"', content)
        self.assertIn('me-1"></i>Docs', content)
        self.assertNotIn('>Core<', content)

        # Prepare Data / Modify in PRISM / Export Derivatives / Share & Archive
        # were merged into the single Workflow dropdown, not separate top-level items.
        self.assertNotIn('id="prepareDropdown"', content)
        self.assertNotIn('id="modifyDropdown"', content)
        self.assertNotIn('id="derivativesDropdown"', content)

    def test_workflow_dropdown_contains_all_pipeline_stages(self):
        content = BASE_TEMPLATE.read_text(encoding="utf-8")
        workflow_section = content.split('id="workflowDropdown"', 1)[1].split(
            'id="docsDropdown"', 1
        )[0]

        self.assertIn('1. Prepare Data', workflow_section)
        self.assertIn('2. Modify in PRISM', workflow_section)
        self.assertIn('3. Export Derivatives', workflow_section)
        self.assertIn('4. Share &amp; Archive', workflow_section)
        self.assertIn('id="shareArchiveLink"', workflow_section)

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

        workflow_section = content.split('id="workflowDropdown"', 1)[1].split(
            'id="docsDropdown"', 1
        )[0]
        self.assertNotIn('>Specs</span>', workflow_section)

        docs_section = content.split('id="docsDropdown"', 1)[1]
        self.assertIn('>Specs</span>', docs_section)
        self.assertIn('url_for(\'specifications\')', docs_section)

    def test_workflow_menu_scrolls_instead_of_overflowing(self):
        content = BASE_TEMPLATE.read_text(encoding="utf-8")

        self.assertIn('dropdown-menu-scroll', content)
        self.assertIn('.dropdown-menu.dropdown-menu-scroll', content)

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
