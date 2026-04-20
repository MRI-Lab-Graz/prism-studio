import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
PARTICIPANTS_TEMPLATE = REPO_ROOT / "app" / "templates" / "converter_participants.html"
PARTICIPANTS_MODULE = (
    REPO_ROOT / "app" / "static" / "js" / "modules" / "converter" / "participants.js"
)
CONVERTER_STYLES = REPO_ROOT / "app" / "static" / "css" / "converter.css"


class TestConverterParticipantsWorkflowWiring(unittest.TestCase):
    def test_case_guide_starts_hidden_and_uses_dynamic_placeholders(self):
        content = PARTICIPANTS_TEMPLATE.read_text(encoding="utf-8")

        self.assertIn('<div class="mb-3 d-none" id="participantsCaseGuide">', content)
        self.assertIn('id="participantsQuickChecklist"', content)
        self.assertIn('id="participantsCaseGuideCards"', content)
        self.assertIn('id="participantsActiveCaseBadge">Choose a case</span>', content)
        self.assertNotIn('id="participantsModeSection"', content)
        self.assertNotIn('id="participantsWorkflowModeHint"', content)
        self.assertNotIn("Workflow Status", content)
        self.assertIn('id="participantsMappingActionCol"', content)
        self.assertIn('id="participantsPreviewActionCol"', content)
        self.assertIn('id="participantsConvertActionCol"', content)

    def test_template_no_longer_hardcodes_legacy_workflow_radios(self):
        content = PARTICIPANTS_TEMPLATE.read_text(encoding="utf-8")

        self.assertNotIn('id="participantsWorkflowModeImport"', content)
        self.assertNotIn('id="participantsWorkflowModeExisting"', content)
        self.assertNotIn('id="participantsFileActionSection"', content)
        self.assertNotIn("Always available", content)
        self.assertNotIn("Requires participants.tsv", content)

    def test_participants_module_blocks_preview_and_save_until_case_selected(self):
        content = PARTICIPANTS_MODULE.read_text(encoding="utf-8")

        self.assertIn("function hasParticipantsSelectedCase() {", content)
        self.assertIn("caseGuide.classList.add('d-none');", content)
        self.assertIn(
            "Choose Case 1, Case 2, or Case 3 before previewing participant data.",
            content,
        )
        self.assertIn(
            "Choose Case 1, Case 2, or Case 3 before saving participant files.",
            content,
        )

    def test_case_cards_define_distinct_icons_and_styles(self):
        module_content = PARTICIPANTS_MODULE.read_text(encoding="utf-8")
        style_content = CONVERTER_STYLES.read_text(encoding="utf-8")

        self.assertIn("iconClass: 'fas fa-file-import'", module_content)
        self.assertIn("iconClass: 'fas fa-pen-to-square'", module_content)
        self.assertIn("iconClass: 'fas fa-code-branch'", module_content)
        self.assertIn("actionLabel: 'Replace'", module_content)
        self.assertIn("actionLabel: 'Modify'", module_content)
        self.assertIn("actionLabel: 'Merge'", module_content)
        self.assertIn("Current: ${escapeHtml(activeCase.actionLabel)}", module_content)
        self.assertIn(
            "convertLabel: '2. Save Existing Participant Files'", module_content
        )
        self.assertIn(
            "const showMappingAction = mode === 'file' && hasSelectedCase;",
            module_content,
        )
        self.assertIn(
            "mappingActionCol.classList.toggle('d-none', !showMappingAction);",
            module_content,
        )
        self.assertIn("useCaseHint:", module_content)
        self.assertIn("participants-case-card-hint", module_content)
        self.assertIn("participants-case-card-title", module_content)
        self.assertIn("participants-case-card-label", module_content)
        self.assertIn(
            "const badgeText = isSelected ? 'Current' : 'Select';", module_content
        )
        self.assertIn("activeDescription.classList.add('d-none');", module_content)
        self.assertIn("participants-case-card-icon", module_content)
        self.assertIn(".participants-case-card-title", style_content)
        self.assertIn(".participants-case-card-label", style_content)
        self.assertIn(".participants-case-card-icon-import", style_content)
        self.assertIn(".participants-case-card-icon-existing", style_content)
        self.assertIn(".participants-case-card-icon-merge", style_content)
        self.assertIn(".participants-case-card-hint", style_content)
        self.assertIn(".participants-case-card-detail", style_content)

    def test_participants_module_resets_project_bound_state_and_uses_explicit_project_path(
        self,
    ):
        content = PARTICIPANTS_MODULE.read_text(encoding="utf-8")

        self.assertIn(
            "function getParticipantsProjectSchemaUrl(projectPath = resolveCurrentProjectPath()) {",
            content,
        )
        self.assertIn(
            "/api/projects/participants?project_path=${encodeURIComponent(projectPath)}",
            content,
        )
        self.assertIn("project_path: currentProjectPath,", content)
        self.assertIn("Please select a project first from the top of the page", content)
        self.assertIn(
            "window.addEventListener('prism-project-changed', function() {", content
        )
        self.assertIn("resetParticipantsPanelState();", content)
        self.assertIn("updateParticipantsButtonState();", content)


if __name__ == "__main__":
    unittest.main()
