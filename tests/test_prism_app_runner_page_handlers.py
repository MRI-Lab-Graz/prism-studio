from __future__ import annotations

import importlib
import sys
from pathlib import Path


def _import_handlers_module():
    app_root = Path(__file__).resolve().parents[1] / "app"
    if str(app_root) not in sys.path:
        sys.path.insert(0, str(app_root))
    return importlib.import_module("src.web.blueprints.tools_prism_app_runner_handlers")


def test_prism_app_runner_page_renders_html_when_feature_disabled(monkeypatch, tmp_path):
    handlers = _import_handlers_module()

    captured = {}

    def fake_render_template(template_name, **context):
        captured["template_name"] = template_name
        captured["context"] = context
        return "rendered-page"

    monkeypatch.setattr(handlers, "render_template", fake_render_template)

    project_root = tmp_path / "demo-project"
    project_root.mkdir(parents=True)

    result = handlers.handle_prism_app_runner(str(project_root))

    assert result == "rendered-page"
    assert captured["template_name"] == "prism_app_runner.html"
    assert captured["context"]["prism_app_runner_disabled"] is True
    assert captured["context"]["prism_app_runner_disabled_message"] == handlers.PRISM_APP_RUNNER_DISABLED_MESSAGE
    assert captured["context"]["default_bids_folder"] == str(project_root)
    assert captured["context"]["default_output_folder"] == str(project_root / "derivatives")
    assert captured["context"]["default_tmp_folder"] == str(project_root / "derivatives" / "apps_runner" / "tmp")