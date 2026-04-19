import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
OPEN_FORM_TEMPLATE = (
    REPO_ROOT / "app" / "templates" / "includes" / "projects" / "open_form.html"
)
CREATE_FORM_TEMPLATE = (
    REPO_ROOT / "app" / "templates" / "includes" / "projects" / "create_form.html"
)
INIT_BIDS_TEMPLATE = (
    REPO_ROOT / "app" / "templates" / "includes" / "projects" / "init_bids_form.html"
)
EXPORT_SECTION_TEMPLATE = (
    REPO_ROOT / "app" / "templates" / "includes" / "projects" / "export_section.html"
)
PROJECTS_METADATA_MODULE = (
    REPO_ROOT / "app" / "static" / "js" / "modules" / "projects" / "metadata.js"
)
PROJECTS_TEMPLATE = REPO_ROOT / "app" / "templates" / "projects.html"
STUDY_METADATA_TEMPLATE = (
    REPO_ROOT / "app" / "templates" / "includes" / "projects" / "study_metadata.html"
)


class TestProjectsCompactViewWiring(unittest.TestCase):
    def test_open_project_section_starts_collapsed(self):
        content = OPEN_FORM_TEMPLATE.read_text(encoding="utf-8")

        self.assertIn(
            'aria-expanded="false" aria-controls="openProjectSection"', content
        )
        self.assertIn('<div class="collapse" id="openProjectSection">', content)
        self.assertNotIn('<div class="collapse show" id="openProjectSection">', content)

    def test_metadata_card_is_not_forced_open_when_shown(self):
        content = PROJECTS_METADATA_MODULE.read_text(encoding="utf-8")

        self.assertNotIn(
            "window.bootstrap.Collapse.getOrCreateInstance(metadataSection).show();",
            content,
        )

    def test_projects_header_has_preliminary_badge_placeholder(self):
        content = PROJECTS_TEMPLATE.read_text(encoding="utf-8")

        self.assertIn('id="projectsPreliminaryBadge"', content)
        self.assertIn('Preliminary', content)

    def test_study_metadata_has_preliminary_create_button(self):
        content = STUDY_METADATA_TEMPLATE.read_text(encoding="utf-8")

        self.assertIn('id="preliminaryCreateBtn"', content)
        self.assertIn('Preliminary Save', content)

    def test_create_form_requires_project_location(self):
        content = CREATE_FORM_TEMPLATE.read_text(encoding="utf-8")

        self.assertIn('id="projectPath"', content)
        self.assertIn('id="projectPath" placeholder="" required', content)

    def test_create_form_has_top_action_buttons(self):
        content = CREATE_FORM_TEMPLATE.read_text(encoding="utf-8")

        self.assertIn('id="createProjectSubmitBtnTop"', content)
        self.assertIn('id="preliminaryCreateBtnTop"', content)

    def test_projects_cards_explain_starting_points(self):
        content = PROJECTS_TEMPLATE.read_text(encoding="utf-8")

        self.assertIn('project-card--create', content)
        self.assertIn('project-card--init', content)
        self.assertIn('project-card--open', content)
        self.assertIn('New workspace', content)
        self.assertIn('Existing BIDS', content)
        self.assertIn('Existing PRISM', content)

    def test_project_forms_have_workflow_strips(self):
        create_content = CREATE_FORM_TEMPLATE.read_text(encoding="utf-8")
        init_content = INIT_BIDS_TEMPLATE.read_text(encoding="utf-8")
        open_content = OPEN_FORM_TEMPLATE.read_text(encoding="utf-8")

        self.assertIn('id="createProjectFlowStrip"', create_content)
        self.assertIn('id="initBidsFlowStrip"', init_content)
        self.assertIn('id="openProjectFlowStrip"', open_content)

    def test_export_section_has_snapshot_summary(self):
        content = EXPORT_SECTION_TEMPLATE.read_text(encoding="utf-8")

        self.assertIn('id="exportSnapshot"', content)
        self.assertIn('id="exportScopeSummary"', content)
        self.assertIn('id="exportDestinationSummary"', content)
        self.assertIn('id="exportPreferenceSummary"', content)
        self.assertIn('id="exportSessionsChip"', content)
        self.assertIn('id="exportModalitiesChip"', content)
        self.assertIn('id="exportAcqChip"', content)
        self.assertIn('id="exportOutputFolderHelp"', content)


if __name__ == "__main__":
    unittest.main()
