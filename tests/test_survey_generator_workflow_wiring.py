import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SURVEY_GENERATOR_SCRIPT = REPO_ROOT / "app" / "static" / "js" / "survey-generator.js"


class TestSurveyGeneratorWorkflowWiring(unittest.TestCase):
    def test_survey_generator_reloads_library_for_active_project_and_uses_api_fallback(
        self,
    ):
        content = SURVEY_GENERATOR_SCRIPT.read_text(encoding="utf-8")

        self.assertIn(
            "const surveyGeneratorScriptUrl = document.currentScript?.src || window.location.href;",
            content,
        )
        self.assertIn("function loadSharedFetchWithApiFallback() {", content)
        self.assertIn(
            "sharedFetchWithApiFallbackPromise = import(sharedApiModuleUrl).then(({ fetchWithApiFallback }) => {",
            content,
        )
        self.assertIn("async function fetchWithApiFallback(", content)
        self.assertIn(
            "return sharedFetchWithApiFallback(url, options, fallbackMessage);",
            content,
        )
        self.assertIn("function getCurrentProjectPath() {", content)
        self.assertIn("let libraryLoadToken = 0;", content)
        self.assertIn(
            "return requestToken === libraryLoadToken && window.isSameProjectPath(requestProjectPath, getCurrentProjectPath());",
            content,
        )
        self.assertIn(
            "/api/list-library-files-merged?project_path=${encodeURIComponent(requestProjectPath)}",
            content,
        )
        self.assertIn(
            "window.addEventListener('prism-project-changed', function() {", content
        )
        self.assertIn("fetchWithApiFallback('/api/generate-boilerplate', {", content)
        self.assertIn("fetchWithApiFallback(cfg.exportEndpoint, {", content)
        self.assertNotIn("fetch('/api/list-library-files-merged')", content)
        self.assertNotIn("fetch('/api/generate-boilerplate'", content)


if __name__ == "__main__":
    unittest.main()


class TestExportLanguagesLiveInTheCustomizer(unittest.TestCase):
    """The generator picks a Base Language only; export languages are chosen in Customize & Export."""

    def test_generator_has_no_export_language_checkboxes(self):
        html = (REPO_ROOT / "app" / "templates" / "survey_generator.html").read_text(encoding="utf-8")
        script = SURVEY_GENERATOR_SCRIPT.read_text(encoding="utf-8")

        self.assertNotIn("exportLanguageCheckboxes", html)
        self.assertNotIn("Export Languages", html)
        self.assertNotIn("exportLanguageCheckboxes", script)
        self.assertNotIn("export-lang-cb", script)

    def test_generator_passes_only_the_base_language_on(self):
        script = SURVEY_GENERATOR_SCRIPT.read_text(encoding="utf-8")

        self.assertIn("languages: [currentLanguage],", script)
        self.assertIn("languageHint(fileLangs, currentLanguage)", script)
        self.assertNotIn("selectedExportLanguages", script)

    def test_customizer_chooses_export_languages_from_the_groups(self):
        html = (REPO_ROOT / "app" / "templates" / "survey_customizer.html").read_text(encoding="utf-8")
        script = (REPO_ROOT / "app" / "static" / "js" / "survey-customizer.js").read_text(encoding="utf-8")

        self.assertIn('id="exportLanguageChoices"', html)
        self.assertNotIn("Set from Survey Generator", html)
        self.assertIn("survey-customizer/language-choices.js", script)

    def test_customizer_export_languages_are_a_dropdown_of_whatever_the_templates_offer(self):
        html = (REPO_ROOT / "app" / "templates" / "survey_customizer.html").read_text(encoding="utf-8")
        script = (REPO_ROOT / "app" / "static" / "js" / "survey-customizer.js").read_text(encoding="utf-8")

        self.assertIn('id="exportLanguageButton"', html)
        self.assertIn('data-bs-toggle="dropdown"', html)
        self.assertIn("resolveLanguages(", script)
        self.assertIn("languageLabel(", script)
        # no hardcoded language list
        self.assertNotIn('<option value="de">', html)

