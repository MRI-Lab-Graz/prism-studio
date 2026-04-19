import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent.parent
SHARED_API_MODULE = REPO_ROOT / "app" / "static" / "js" / "shared" / "api.js"
PROJECTS_CORE_MODULE = (
    REPO_ROOT / "app" / "static" / "js" / "modules" / "projects" / "core.js"
)
PROJECTS_EXPORT_MODULE = (
    REPO_ROOT / "app" / "static" / "js" / "modules" / "projects" / "export.js"
)
PROJECTS_METADATA_MODULE = (
    REPO_ROOT / "app" / "static" / "js" / "modules" / "projects" / "metadata.js"
)
OPEN_FORM_TEMPLATE = (
    REPO_ROOT / "app" / "templates" / "includes" / "projects" / "open_form.html"
)


class TestProjectsWorkflowWiring(unittest.TestCase):
    def test_shared_api_exports_desktop_fallback_helper(self):
        content = SHARED_API_MODULE.read_text(encoding="utf-8")

        self.assertIn("export async function fetchWithApiFallback(", content)
        self.assertIn("url.startsWith('/api/')", content)
        self.assertIn("return 'http://127.0.0.1:5001';", content)

    def test_new_project_draft_clear_uses_api_fallback(self):
        content = PROJECTS_CORE_MODULE.read_text(encoding="utf-8")

        self.assertIn("fetchWithApiFallback('/api/projects/current', {", content)

    def test_file_browser_uses_fallback_and_button_rows(self):
        content = PROJECTS_CORE_MODULE.read_text(encoding="utf-8")

        self.assertIn("const res = await fetchWithApiFallback(url);", content)
        self.assertIn(
            'class="d-flex align-items-center w-100 px-3 py-2 border-0 border-bottom fb-project-json text-start"',
            content,
        )
        self.assertIn(
            'class="d-flex align-items-center w-100 px-3 py-2 border-0 border-bottom fb-dir text-start bg-white"',
            content,
        )
        self.assertIn(
            'aria-label="Select project.json at ${_escHtml(data.project_json_path)}"',
            content,
        )

    def test_export_structure_shows_loading_and_failure_placeholders(self):
        content = PROJECTS_EXPORT_MODULE.read_text(encoding="utf-8")

        self.assertIn("let projectStructureLoadToken = 0;", content)
        self.assertIn("renderProjectStructureStatus('Loading current project structure...');", content)
        self.assertIn(
            "renderProjectStructureStatus('Could not load current project structure.', 'warning');",
            content,
        )
        self.assertIn(
            "const resp = await fetchWithApiFallback('/api/projects/export/structure', {",
            content,
        )

    def test_metadata_reset_clears_validation_state(self):
        content = PROJECTS_METADATA_MODULE.read_text(encoding="utf-8")

        self.assertIn(
            "el.classList.remove('is-invalid', 'required-field-empty', 'required-field-filled');",
            content,
        )
        self.assertIn("el.removeAttribute('aria-invalid');", content)
        self.assertIn("el.setCustomValidity('');", content)

    def test_file_browser_template_announces_dynamic_updates(self):
        content = OPEN_FORM_TEMPLATE.read_text(encoding="utf-8")

        self.assertIn('id="fsBrowserList" aria-live="polite"', content)
        self.assertIn(
            'id="fsBrowserSelectedHint" style="display:none;" role="status" aria-live="polite"',
            content,
        )


if __name__ == "__main__":
    unittest.main()