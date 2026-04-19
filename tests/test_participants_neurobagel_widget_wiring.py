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
        self.assertIn("const unannotatedContainer = document.getElementById('neurobagelUnannotated');", content)
        self.assertIn("unannotatedContainer.innerHTML = '';", content)
        self.assertIn("unannotatedContainer.appendChild(createSidebarItem(colName, colData));", content)
        self.assertIn("All current columns are mapped.", content)
        self.assertNotIn('CUSTOM VARIABLES', content)

    def test_remove_variable_is_limited_to_additional_columns(self):
        widget_content = WIDGET_FILE.read_text(encoding="utf-8")
        participants_content = PARTICIPANTS_MODULE.read_text(encoding="utf-8")

        self.assertIn("window.canRemoveParticipantVariable = function(variableName) {", participants_content)
        self.assertIn("if (getParticipantsWorkflowMode() === 'existing') {", participants_content)
        self.assertIn("const canRemoveVariable = typeof window.canRemoveParticipantVariable === 'function'", widget_content)
        self.assertIn("Remove From Output", widget_content)
        self.assertIn("Could not persist removal of ${colName}:", widget_content)
        self.assertIn("return;", widget_content)


if __name__ == "__main__":
    unittest.main()
