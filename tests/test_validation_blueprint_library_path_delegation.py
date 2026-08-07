"""Guards against re-introducing a duplicate default-library-path resolver
in the Validate Dataset blueprint.

docs/_archive/GUI_BACKEND_AUDIT_2026-08-07.md (P1-6) found that
app/src/web/blueprints/validation.py's default-library-path logic existed
only there, with no CLI equivalent. It has since been extracted to
src.validation_library_resolution, with the CLI (app/prism.py) using the
same function. These tests confirm the blueprint's wrapper functions
actually delegate rather than reimplementing the logic again.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

from flask import Flask

APP_ROOT = Path(__file__).resolve().parents[1] / "app"
if str(APP_ROOT) not in sys.path:
    sys.path.insert(0, str(APP_ROOT))

from src.web.blueprints import validation as validation_blueprint_module  # noqa: E402
from src.web.blueprints.validation import validation_bp  # noqa: E402


def _build_app() -> Flask:
    app = Flask(
        __name__,
        root_path=str(APP_ROOT),
        template_folder="templates",
        static_folder="static",
    )
    app.secret_key = os.urandom(32)
    app.register_blueprint(validation_bp)
    return app


class TestGlobalValidationLibraryPathDelegates:
    def test_calls_shared_resolver_with_app_root(self, monkeypatch):
        app = _build_app()
        captured = {}

        def _fake(app_root):
            captured["app_root"] = app_root
            return "/sentinel/global"

        monkeypatch.setattr(
            validation_blueprint_module, "default_global_validation_library_path", _fake
        )

        with app.app_context():
            result = validation_blueprint_module._get_global_validation_library_path()

        assert result == "/sentinel/global"
        assert captured["app_root"] == str(APP_ROOT)


class TestDefaultValidationLibraryPathDelegates:
    def test_calls_shared_resolver_with_app_root_and_project_path(self, monkeypatch):
        app = _build_app()
        captured = {}

        def _fake(app_root, project_path=None):
            captured["app_root"] = app_root
            captured["project_path"] = project_path
            return "/sentinel/default"

        monkeypatch.setattr(
            validation_blueprint_module, "default_validation_library_path", _fake
        )

        with app.app_context():
            result = validation_blueprint_module._get_default_validation_library_path(
                "/some/project"
            )

        assert result == "/sentinel/default"
        assert captured["app_root"] == str(APP_ROOT)
        assert captured["project_path"] == "/some/project"
