import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
WIDGET_FILE = REPO_ROOT / "app" / "static" / "neurobagel_widget.html"
PARTICIPANTS_MODULE = (
    REPO_ROOT / "app" / "static" / "js" / "modules" / "converter" / "participants.js"
)


class TestParticipantsNeurobagelWidgetWiring(unittest.TestCase):
    def test_widget_renders_real_unannotated_section(self):
        content = WIDGET_FILE.read_text(encoding="utf-8")

        self.assertIn('id="neurobagelUnannotated"', content)
        self.assertIn(
            "const unannotatedContainer = document.getElementById('neurobagelUnannotated');",
            content,
        )
        self.assertIn("unannotatedContainer.innerHTML = '';", content)
        self.assertIn(
            "unannotatedContainer.appendChild(createSidebarItem(colName, colData));",
            content,
        )
        self.assertIn("All current columns are mapped.", content)
        self.assertNotIn("CUSTOM VARIABLES", content)

    def test_remove_variable_uses_participants_removal_hooks(self):
        widget_content = WIDGET_FILE.read_text(encoding="utf-8")
        participants_content = PARTICIPANTS_MODULE.read_text(encoding="utf-8")

        self.assertIn(
            "window.canRemoveParticipantVariable = function(variableName) {",
            participants_content,
        )
        self.assertIn(
            "const protectedColumns = new Set(['participantid']);",
            participants_content,
        )
        self.assertIn(
            "window.removeAdditionalParticipantVariable = async function(variableName) {",
            participants_content,
        )
        self.assertIn(
            "const canRemoveVariable = typeof window.canRemoveParticipantVariable === 'function'",
            widget_content,
        )
        self.assertIn("Remove From Output", widget_content)
        self.assertIn(
            "const removeHandler = window.removeAdditionalParticipantVariable;",
            widget_content,
        )
        self.assertIn("Could not persist removal of ${colName}:", widget_content)
        self.assertIn("return;", widget_content)

    def test_widget_resolves_sidebar_columns_back_to_state_keys(self):
        widget_content = WIDGET_FILE.read_text(encoding="utf-8")

        self.assertIn(
            "window.resolveNeurobagelColumnStateKey = function(colName) {",
            widget_content,
        )
        self.assertIn(
            "window.getNeurobagelColumnState = function(colName) {",
            widget_content,
        )
        self.assertIn(
            "const colData = window.getNeurobagelColumnState(colName);",
            widget_content,
        )
        self.assertIn(
            "const actualColName = window.resolveNeurobagelColumnStateKey(colName);",
            widget_content,
        )
        self.assertIn(
            "const keysToDelete = new Set([colName, actualColName].filter(Boolean));",
            widget_content,
        )
        self.assertIn(
            "const targetColData = window.getNeurobagelColumnState(targetCol);",
            widget_content,
        )

    def test_widget_does_not_readd_removed_columns_from_saved_schema_during_preview(self):
        widget_content = WIDGET_FILE.read_text(encoding="utf-8")

        self.assertIn(
            "const hasActivePreview = Boolean(window.lastParticipantsPreviewData && Array.isArray(window.lastParticipantsPreviewData.columns));",
            widget_content,
        )
        self.assertIn(
            "const activePreviewColumns = hasActivePreview && window.participantsTsvData && typeof window.participantsTsvData === 'object'",
            widget_content,
        )
        self.assertIn(
            "if (activePreviewColumns && !activePreviewColumns.has(cleanedColName)) {",
            widget_content,
        )
        self.assertIn("continue;", widget_content)


if __name__ == "__main__":
    unittest.main()
