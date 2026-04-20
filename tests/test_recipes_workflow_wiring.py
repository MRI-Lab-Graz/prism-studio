import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
RECIPES_TEMPLATE = REPO_ROOT / "app" / "templates" / "recipes.html"
RECIPES_SCRIPT = REPO_ROOT / "app" / "static" / "js" / "recipes.js"


class TestRecipesWorkflowWiring(unittest.TestCase):
    def test_recipes_page_uses_explicit_project_paths_and_api_fallback(self):
        template_content = RECIPES_TEMPLATE.read_text(encoding="utf-8")
        script_content = RECIPES_SCRIPT.read_text(encoding="utf-8")

        self.assertIn(
            "window.currentProjectPath = {{ (current_project.path or '') | tojson }};",
            template_content,
        )
        self.assertIn("async function fetchWithApiFallback(", script_content)
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


if __name__ == "__main__":
    unittest.main()
