"""Refreshing the template list rebuilds the dropdowns (which drops the selection);
the template still open in the editor must be selected again afterwards."""

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
import { refreshTemplateList } from %(url)s;
globalThis.document = { createElement: () => ({ dataset: {} }) };
// like a real <select>: rebuilding the options clears the selection
const select = () => {
  const s = { value: '', options: [], appendChild(o) { this.options.push(o); } };
  Object.defineProperty(s, 'innerHTML', { set() { this.options = []; this.value = ''; } });
  return s;
};
const templates = [{ filename: 'survey-aq10.json', source: 'project', path: '/p/aq10' }];
const context = {
  modalityEl: { value: 'survey' }, schemaEl: { value: 'stable' },
  getCurrentProjectPath: () => '/p', projectContextRequestToken: 1,
  withProjectPathQuery: (u) => u, apiGet: async () => ({ templates }),
  isProjectContextCurrent: () => true,
  templateStatusPrefix: () => '[FILE OK]', templateStatusTitle: () => '',
  templateMetadata: {}, projectTemplateSelectEl: select(), globalTemplateSelectEl: select(),
  updateProjectLibraryStatus() {}, updateLoadButtonState() {},
  loadedFromProjectLibrary: %(loaded)s, currentTemplateFilename: %(filename)s,
};
await refreshTemplateList(context, { silent: true });
console.log(JSON.stringify(context.projectTemplateSelectEl.value));
"""


@unittest.skipUnless(shutil.which("node"), "node not installed")
class TestSelectionAfterRefresh(unittest.TestCase):
    def selected(self, loaded, filename):
        script = textwrap.dedent(DRIVER) % {
            "url": json.dumps(WORKFLOW.as_uri()),
            "loaded": json.dumps(loaded),
            "filename": json.dumps(filename),
        }
        out = subprocess.run(
            ["node", "--input-type=module", "-e", script],
            capture_output=True, text=True, check=True,
        ).stdout
        return json.loads(out)

    def test_open_project_template_is_selected_again(self):
        self.assertEqual(self.selected(True, "survey-aq10.json"), "survey-aq10.json")

    def test_nothing_is_selected_when_the_open_template_is_not_a_project_file(self):
        self.assertEqual(self.selected(False, "survey-aq10.json"), "")

    def test_nothing_is_selected_when_the_open_file_is_gone_from_the_project(self):
        self.assertEqual(self.selected(True, "survey-deleted.json"), "")


if __name__ == "__main__":
    unittest.main()
