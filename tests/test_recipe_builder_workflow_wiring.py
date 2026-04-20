import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
RECIPE_BUILDER_TEMPLATE = REPO_ROOT / "app" / "templates" / "recipe_builder.html"
RECIPE_BUILDER_SCRIPT = REPO_ROOT / "app" / "static" / "js" / "recipe_builder.js"


class TestRecipeBuilderWorkflowWiring(unittest.TestCase):
    def test_recipe_builder_template_links_to_projects_page_when_no_project_loaded(
        self,
    ):
        content = RECIPE_BUILDER_TEMPLATE.read_text(encoding="utf-8")

        self.assertIn("url_for('projects.projects_page')", content)
        self.assertNotIn("url_for('projects.projects')", content)

    def test_recipe_builder_script_uses_api_fallback_for_load_and_save_requests(self):
        content = RECIPE_BUILDER_SCRIPT.read_text(encoding="utf-8")

        self.assertIn("async function fetchWithApiFallback(", content)
        self.assertIn("const response = await fetchWithApiFallback(", content)
        self.assertIn(
            "'/api/recipe-builder/surveys?dataset_path=' + encodeURIComponent(path) + includeGlobal",
            content,
        )
        self.assertIn(
            "'/api/recipe-builder/items?task=' + encodeURIComponent(task) +", content
        )
        self.assertIn(
            "'/api/recipe-builder/load?task=' + encodeURIComponent(task) +", content
        )
        self.assertIn(
            "const response = await fetchWithApiFallback('/api/recipe-builder/save', {",
            content,
        )

    def test_recipe_builder_script_ignores_stale_async_load_responses(self):
        content = RECIPE_BUILDER_SCRIPT.read_text(encoding="utf-8")

        self.assertIn("let surveyListRequestToken = 0;", content)
        self.assertIn("let loadRequestToken = 0;", content)
        self.assertIn("if (requestToken !== surveyListRequestToken) return;", content)
        self.assertIn(
            "if (requestToken !== loadRequestToken || task !== selectedTask) return;",
            content,
        )

    def test_recipe_builder_script_resets_project_bound_selection_on_project_change(
        self,
    ):
        content = RECIPE_BUILDER_SCRIPT.read_text(encoding="utf-8")

        self.assertIn("function getCurrentProjectPath() {", content)
        self.assertIn("function resetBuilderState() {", content)
        self.assertIn("selectedTask = '';", content)
        self.assertIn(
            "surveyPicker.innerHTML = '<option value=\"\" disabled selected>— loading survey templates —</option>';",
            content,
        )
        self.assertIn(
            "surveyPicker.innerHTML = '<option value=\"\" disabled selected>— no project loaded —</option>';",
            content,
        )
        self.assertIn(
            "window.addEventListener('prism-project-changed', function () {", content
        )
        self.assertIn("projectPath = getCurrentProjectPath();", content)
        self.assertIn("resetBuilderState();", content)
        self.assertIn("loadSurveyList();", content)


if __name__ == "__main__":
    unittest.main()
