import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
PRISM_APP_RUNNER_TEMPLATE = REPO_ROOT / "app" / "templates" / "prism_app_runner.html"
PRISM_APP_RUNNER_HANDLERS = (
    REPO_ROOT
    / "app"
    / "src"
    / "web"
    / "blueprints"
    / "tools_prism_app_runner_handlers.py"
)


class TestPrismAppRunnerWorkflowWiring(unittest.TestCase):
    def test_prism_app_runner_template_renders_disabled_html_state(self):
        template_content = PRISM_APP_RUNNER_TEMPLATE.read_text(encoding="utf-8")

        self.assertIn('id="prismAppRunnerDisabledNotice"', template_content)
        self.assertIn("{% if prism_app_runner_disabled %}", template_content)
        self.assertIn(
            '<fieldset{% if prism_app_runner_disabled %} disabled aria-disabled="true"{% endif %}>',
            template_content,
        )

    def test_prism_app_runner_page_handler_no_longer_returns_disabled_json(self):
        handler_content = PRISM_APP_RUNNER_HANDLERS.read_text(encoding="utf-8")

        self.assertIn("return render_template(", handler_content)
        self.assertIn(
            "prism_app_runner_disabled=not PRISM_APP_RUNNER_ENABLED,", handler_content
        )
        self.assertIn(
            "prism_app_runner_disabled_message=PRISM_APP_RUNNER_DISABLED_MESSAGE,",
            handler_content,
        )


if __name__ == "__main__":
    unittest.main()
