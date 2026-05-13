import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SURVEY_GENERATOR_SCRIPT = REPO_ROOT / "app" / "static" / "js" / "survey-generator.js"
SURVEY_CUSTOMIZER_TEMPLATE = REPO_ROOT / "app" / "templates" / "survey_customizer.html"
SURVEY_CUSTOMIZER_SCRIPT = REPO_ROOT / "app" / "static" / "js" / "survey-customizer.js"
TOOLS_BLUEPRINT = REPO_ROOT / "app" / "src" / "web" / "blueprints" / "tools.py"


class TestSurveyCustomizerWorkflowWiring(unittest.TestCase):
    def test_survey_customizer_template_uses_shared_header_and_help_panel_macros(self):
        content = SURVEY_CUSTOMIZER_TEMPLATE.read_text(encoding="utf-8")

        self.assertIn(
            '{% from "includes/ui/macros.html" import page_header, help_panel %}',
            content,
        )
        self.assertIn("{{ page_header(", content)
        self.assertIn("{% call help_panel(", content)

    def test_survey_customizer_save_to_project_follows_loaded_project(self):
        generator_content = SURVEY_GENERATOR_SCRIPT.read_text(encoding="utf-8")
        template_content = SURVEY_CUSTOMIZER_TEMPLATE.read_text(encoding="utf-8")
        script_content = SURVEY_CUSTOMIZER_SCRIPT.read_text(encoding="utf-8")
        blueprint_content = TOOLS_BLUEPRINT.read_text(encoding="utf-8")

        self.assertIn("projectPath: getCurrentProjectPath(),", generator_content)
        self.assertIn('id="saveToProjectHint"', template_content)
        self.assertIn(
            "const surveyCustomizerScriptUrl = document.currentScript?.src || window.location.href;",
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
        self.assertIn("function getCurrentProjectPath() {", script_content)
        self.assertIn("let sourceProjectPath = '';", script_content)
        self.assertIn(
            "window.addEventListener('prism-project-changed', function() {",
            script_content,
        )
        self.assertIn(
            "sourceProjectPath = String(data.projectPath || getCurrentProjectPath()).trim();",
            script_content,
        )
        self.assertIn(
            "exportPayload.project_path = currentProjectPath;", script_content
        )
        self.assertIn(
            "await fetchWithApiFallback('/api/survey-customizer/load', {",
            script_content,
        )
        self.assertIn(
            "await fetchWithApiFallback('/api/survey-customizer/export', {",
            script_content,
        )
        self.assertIn(
            "await fetchWithApiFallback('/api/template-editor/export-questionnaire', {",
            script_content,
        )
        self.assertIn('if "project_path" in data', blueprint_content)
        self.assertIn('else session.get("current_project_path")', blueprint_content)


if __name__ == "__main__":
    unittest.main()
