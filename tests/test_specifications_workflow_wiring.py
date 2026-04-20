import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SPECIFICATIONS_TEMPLATE = REPO_ROOT / "app" / "templates" / "specifications.html"
SPECIFICATIONS_SCRIPT = REPO_ROOT / "app" / "static" / "js" / "specifications.js"


class TestSpecificationsWorkflowWiring(unittest.TestCase):
    def test_specifications_derivative_links_follow_project_change_events(self):
        template_content = SPECIFICATIONS_TEMPLATE.read_text(encoding="utf-8")
        script_content = SPECIFICATIONS_SCRIPT.read_text(encoding="utf-8")

        self.assertIn(
            'id="specificationsRoot" data-current-project-path="{{ current_project.path or \'\' }}"',
            template_content,
        )
        self.assertIn('id="specSurveyExportLink"', template_content)
        self.assertIn('id="specRecipesLink"', template_content)
        self.assertIn(
            "data-enabled-url=\"{{ url_for('tools.survey_generator') if survey_generator_available else '' }}\"",
            template_content,
        )
        self.assertIn(
            "data-enabled-url=\"{{ url_for('tools.recipes') if recipes_available else '' }}\"",
            template_content,
        )
        self.assertIn(
            "window.addEventListener('prism-project-changed', function(event) {",
            script_content,
        )
        self.assertIn(
            "link.classList.toggle('disabled', !hasCurrentProject);", script_content
        )
        self.assertIn(
            "link.setAttribute('title', 'Please load a project first');", script_content
        )
        self.assertIn("link.removeAttribute('aria-disabled');", script_content)


if __name__ == "__main__":
    unittest.main()
