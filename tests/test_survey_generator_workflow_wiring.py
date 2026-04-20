import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent.parent
SURVEY_GENERATOR_SCRIPT = REPO_ROOT / "app" / "static" / "js" / "survey-generator.js"


class TestSurveyGeneratorWorkflowWiring(unittest.TestCase):
    def test_survey_generator_reloads_library_for_active_project_and_uses_api_fallback(self):
        content = SURVEY_GENERATOR_SCRIPT.read_text(encoding="utf-8")

        self.assertIn("async function fetchWithApiFallback(", content)
        self.assertIn("function getCurrentProjectPath() {", content)
        self.assertIn("let libraryLoadToken = 0;", content)
        self.assertIn("return requestToken === libraryLoadToken && requestProjectPath === getCurrentProjectPath();", content)
        self.assertIn("/api/list-library-files-merged?project_path=${encodeURIComponent(requestProjectPath)}", content)
        self.assertIn("window.addEventListener('prism-project-changed', function() {", content)
        self.assertIn("fetchWithApiFallback('/api/generate-boilerplate', {", content)
        self.assertIn("fetchWithApiFallback(cfg.exportEndpoint, {", content)
        self.assertNotIn("fetch('/api/list-library-files-merged')", content)
        self.assertNotIn("fetch('/api/generate-boilerplate'", content)


if __name__ == "__main__":
    unittest.main()