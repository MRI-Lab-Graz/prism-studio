import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
RECIPES_TEMPLATE = REPO_ROOT / "app" / "templates" / "recipes.html"
RECIPES_SCRIPT = REPO_ROOT / "app" / "static" / "js" / "recipes.js"
CONVERTER_BOOTSTRAP_SCRIPT = (
    REPO_ROOT / "app" / "static" / "js" / "converter-bootstrap.js"
)
CONVERTER_LOG_RENDERER_SCRIPT = (
    REPO_ROOT / "app" / "static" / "js" / "modules" / "converter" / "log-renderer.js"
)
STUDIO_THEME_CSS = REPO_ROOT / "app" / "static" / "css" / "studio-theme.css"


class TestRecipesWorkflowWiring(unittest.TestCase):
    def test_recipes_template_uses_shared_header_and_help_panel_macros(self):
        template_content = RECIPES_TEMPLATE.read_text(encoding="utf-8")

        self.assertIn(
            '{% from "includes/ui/macros.html" import page_header, help_panel %}',
            template_content,
        )
        self.assertIn("{{ page_header(", template_content)
        self.assertIn("{% call help_panel(", template_content)

    def test_recipes_page_uses_explicit_project_paths_and_api_fallback(self):
        template_content = RECIPES_TEMPLATE.read_text(encoding="utf-8")
        script_content = RECIPES_SCRIPT.read_text(encoding="utf-8")

        self.assertIn(
            "window.currentProjectPath = {{ (current_project.path or '') | tojson }};",
            template_content,
        )
        self.assertIn(
            "const recipesScriptUrl = document.currentScript?.src || window.location.href;",
            script_content,
        )
        self.assertIn("function loadSharedFetchWithApiFallback() {", script_content)
        self.assertIn(
            "sharedFetchWithApiFallbackPromise = import(sharedApiModuleUrl).then(({ fetchWithApiFallback }) => {",
            script_content,
        )
        self.assertIn("async function fetchWithApiFallback(", script_content)
        self.assertIn(
            "return sharedFetchWithApiFallback(url, options, fallbackMessage);",
            script_content,
        )
        self.assertIn(
            "fetchWithApiFallback(`/api/recipes-modalities?dataset_path=${encodeURIComponent(requestProjectPath)}`)",
            script_content,
        )
        self.assertIn(
            "fetchWithApiFallback(`/api/recipes-sessions?dataset_path=${encodeURIComponent(requestProjectPath)}`)",
            script_content,
        )
        self.assertIn(
            "fetchWithApiFallback(`/api/projects/preferences/recipes?project_path=${encodeURIComponent(requestProjectPath)}`)",
            script_content,
        )
        self.assertIn(
            "body: JSON.stringify({ project_path: requestProjectPath, preferences: prefs }),",
            script_content,
        )
        self.assertIn(
            "const response = await fetchWithApiFallback('/api/recipes-surveys', {",
            script_content,
        )
        self.assertIn("dataset_path: requestProjectPath,", script_content)
        self.assertIn("if (data && data.missing_recipe_warning)", script_content)
        self.assertIn("Written surveys:", script_content)
        self.assertIn("function formatRecipesUsedSummary(data)", script_content)
        self.assertIn("Skipped (no recipe found):", script_content)
        self.assertIn("No recipes found here", script_content)

    def test_recipes_page_resets_state_and_ignores_stale_project_switch_responses(self):
        content = RECIPES_SCRIPT.read_text(encoding="utf-8")

        self.assertIn("let modalitiesRequestToken = 0;", content)
        self.assertIn("let sessionsRequestToken = 0;", content)
        self.assertIn("let preferencesLoadToken = 0;", content)
        self.assertIn("let recipeRunToken = 0;", content)
        self.assertIn("function resetRecipesPreferenceControls() {", content)
        self.assertIn("function resetRecipesResultsState() {", content)
        self.assertIn(
            "return requestToken === activeToken && requestProjectPath === resolveProjectPath();",
            content,
        )
        self.assertIn(
            "return runToken === recipeRunToken && requestProjectPath === resolveProjectPath();",
            content,
        )
        self.assertIn(
            "window.addEventListener('prism-project-changed', function() {", content
        )
        self.assertIn("recipeRunToken += 1;", content)
        self.assertIn("resetRecipesResultsState();", content)
        self.assertIn("refreshModalities();", content)
        self.assertIn("refreshSessions();", content)
        self.assertIn("loadRecipesPreferences();", content)
        self.assertIn("setRunAvailability();", content)

    def test_terminal_logs_highlight_backend_command_segments(self):
        recipes_content = RECIPES_SCRIPT.read_text(encoding="utf-8")
        converter_content = CONVERTER_BOOTSTRAP_SCRIPT.read_text(encoding="utf-8")
        converter_log_renderer_content = CONVERTER_LOG_RENDERER_SCRIPT.read_text(
            encoding="utf-8"
        )
        css_content = STUDIO_THEME_CSS.read_text(encoding="utf-8")

        self.assertIn("rawMessage.match(/(\\bcmd=)(.+)$/)", recipes_content)
        self.assertIn("commandSpan.className = 'backend-command-text';", recipes_content)
        self.assertIn(
            "import { appendConverterLogBatch, appendConverterLogLine } from './modules/converter/log-renderer.js';",
            converter_content,
        )
        self.assertIn(
            "rawMessage.match(/(\\bcmd=)(.+)$/)", converter_log_renderer_content
        )
        self.assertIn(
            "commandSpan.className = 'backend-command-text';",
            converter_log_renderer_content,
        )
        self.assertIn(".studio-theme .backend-command-text", css_content)


if __name__ == "__main__":
    unittest.main()
