"""Right after loading a template, missing project-only fields (TaskName,
SoftwarePlatform, ...) must read as "fill these in first", not as a red failure."""

import json
import shutil
import subprocess
import textwrap
import unittest
from pathlib import Path

WORKFLOW = (
    Path(__file__).resolve().parent.parent
    / "app" / "static" / "js" / "template-editor" / "source-workflow.js"
)

DRIVER = """
import { validateCurrent } from %(url)s;
const errors = %(errors)s;
const alerts = [];
const el = { disabled: false, classList: { toggle() {}, add() {} } };
const context = {
  modalityEl: { value: 'survey' }, schemaEl: { value: 'stable' },
  getCurrentProjectPath: () => '/p', projectContextRequestToken: 1,
  getExportWordButton: () => null, currentTemplate: {}, hasExplicitTemplate: true,
  apiPost: async () => ({ ok: false, errors }),
  isProjectContextCurrent: () => true,
  btnDownload: el, btnSave: el, alertAreaEl: { querySelectorAll: () => [] },
  deriveFocusPath: (p) => p, escapeHtml: (s) => s, renderMissingSummary() {},
  showAlert: (type, html) => alerts.push({ type, html }),
};
await validateCurrent(context, %(opts)s);
console.log(JSON.stringify(alerts[0]));
"""

REQUIRED = [{"path": "Study", "message": "'TaskName' is a required property"}]
REAL_ERROR = REQUIRED + [{"path": "Study.Authors", "message": "1 is not of type 'string'"}]


@unittest.skipUnless(shutil.which("node"), "node not installed")
class TestInitialValidation(unittest.TestCase):
    def alert(self, errors, opts="{}"):
        script = textwrap.dedent(DRIVER) % {
            "url": json.dumps(WORKFLOW.as_uri()),
            "errors": json.dumps(errors),
            "opts": opts,
        }
        out = subprocess.run(
            ["node", "--input-type=module", "-e", script],
            capture_output=True, text=True, check=True,
        ).stdout
        return json.loads(out)

    def test_initial_missing_required_fields_are_a_hint_not_an_error(self):
        a = self.alert(REQUIRED, "{ initial: true }")
        self.assertEqual(a["type"], "warning")
        self.assertNotIn("Validation failed", a["html"])
        self.assertIn("TaskName", a["html"])

    def test_explicit_validate_still_fails_loudly(self):
        self.assertEqual(self.alert(REQUIRED)["type"], "danger")

    def test_initial_with_a_real_error_stays_red(self):
        self.assertEqual(self.alert(REAL_ERROR, "{ initial: true }")["type"], "danger")


if __name__ == "__main__":
    unittest.main()
