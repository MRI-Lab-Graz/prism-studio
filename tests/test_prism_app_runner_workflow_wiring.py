import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
PRISM_APP_RUNNER_TEMPLATE = REPO_ROOT / "app" / "templates" / "prism_app_runner.html"
PRISM_APP_RUNNER_SCRIPT = REPO_ROOT / "app" / "static" / "js" / "prism_app_runner.js"
PRISM_APP_RUNNER_HANDLERS = (
    REPO_ROOT
    / "app"
    / "src"
    / "web"
    / "blueprints"
    / "tools_prism_app_runner_handlers.py"
)


class TestPrismAppRunnerWorkflowWiring(unittest.TestCase):
    def test_prism_app_runner_script_uses_shared_api_fallback_for_backend_calls(self):
        script_content = PRISM_APP_RUNNER_SCRIPT.read_text(encoding="utf-8")

        self.assertIn(
            "const prismAppRunnerScriptUrl = document.currentScript?.src || window.location.href;",
            script_content,
        )
        self.assertIn("function loadSharedFetchWithApiFallback() {", script_content)
        self.assertIn(
            "sharedFetchWithApiFallbackPromise = import(sharedApiModuleUrl).then(({ fetchWithApiFallback }) => {",
            script_content,
        )
        self.assertIn("async function fetchWithApiFallback(url, options = {}, fallbackMessage = 'Cannot reach PRISM backend API. Please restart PRISM Studio and try again.') {", script_content)
        self.assertIn(
            "return sharedFetchWithApiFallback(url, options, fallbackMessage);",
            script_content,
        )
        self.assertIn("await fetchWithApiFallback('/api/browse-folder');", script_content)
        self.assertIn("await fetchWithApiFallback('/api/prism-app-runner/compatibility', {", script_content)
        self.assertIn("await fetchWithApiFallback('/api/prism-app-runner/remote-profiles');", script_content)
        self.assertIn("await fetchWithApiFallback(`/api/prism-app-runner/remote-profiles/${encodeURIComponent(profileName)}`, {", script_content)
        self.assertIn("await fetchWithApiFallback('/api/prism-app-runner/docker-tags', {", script_content)
        self.assertIn("await fetchWithApiFallback('/api/prism-app-runner/load-help', {", script_content)
        self.assertIn("await fetchWithApiFallback('/api/prism-app-runner/run', {", script_content)

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
