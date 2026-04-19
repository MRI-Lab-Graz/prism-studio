import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent.parent
FILE_MANAGEMENT_TEMPLATE = REPO_ROOT / "app" / "templates" / "file_management.html"
FILE_MANAGEMENT_SCRIPT = REPO_ROOT / "app" / "static" / "js" / "file_management.js"


class TestFileManagementWorkflowWiring(unittest.TestCase):
    def test_file_management_script_uses_api_fallback_for_all_tool_requests(self):
        content = FILE_MANAGEMENT_SCRIPT.read_text(encoding="utf-8")

        self.assertIn("async function fetchWithApiFallback(", content)
        self.assertIn("await fetchWithApiFallback('/api/file-management/raw-peek', { method: 'POST', body: formData });", content)
        self.assertIn("await fetchWithApiFallback('/api/file-management/wide-to-long-preview', {", content)
        self.assertIn("await fetchWithApiFallback('/api/file-management/wide-to-long', {", content)
        self.assertIn("await fetchWithApiFallback('/api/batch-convert', {", content)
        self.assertIn("await fetchWithApiFallback('/api/physio-rename', {", content)

    def test_file_management_script_guards_unsupported_flat_project_root_copy(self):
        content = FILE_MANAGEMENT_SCRIPT.read_text(encoding="utf-8")

        self.assertIn("function renamerCanCopyToProject() {", content)
        self.assertIn(
            "Flat output can be downloaded or copied to rawdata/sourcedata. Enable folders to copy into the PRISM root.",
            content,
        )
        self.assertIn("organizeFlatStructure.disabled = true;", content)

    def test_file_management_template_defaults_flat_toggle_to_supported_destinations(self):
        content = FILE_MANAGEMENT_TEMPLATE.read_text(encoding="utf-8")

        self.assertIn('id="organizeFlatStructure" disabled', content)
        self.assertIn(
            "Project root keeps PRISM folders; use rawdata or sourcedata for flat copies.",
            content,
        )


if __name__ == "__main__":
    unittest.main()