from __future__ import annotations

import importlib
import sys
from pathlib import Path

from flask import Flask

PROJECT_ROOT = Path(__file__).resolve().parent.parent
APP_ROOT = PROJECT_ROOT / "app"
if str(APP_ROOT) not in sys.path:
    sys.path.insert(0, str(APP_ROOT))

tools_module = importlib.import_module("src.web.blueprints.tools")
tools_bp = tools_module.tools_bp

metadata_helpers = importlib.import_module(
    "src.web.blueprints.projects_metadata_helpers"
)


def _build_app() -> Flask:
    app = Flask(__name__)
    app.secret_key = "test-secret"  # pragma: allowlist secret
    app.register_blueprint(tools_bp)
    return app


def test_api_config_exposes_backend_owned_required_fields_schema() -> None:
    """The frontend must fetch the CORE-tier field schema from the backend
    (single source of truth) instead of hardcoding its own copy - see
    projects_metadata_helpers.REQUIRED_FIELDS_SCHEMA and CLAUDE.md's
    "no duplicate implementations" rule.
    """
    app = _build_app()
    client = app.test_client()

    response = client.get("/api/config")

    assert response.status_code == 200
    payload = response.get_json()
    assert payload["studyMetadataRequiredFields"] == {
        section: sorted(fields)
        for section, fields in metadata_helpers.REQUIRED_FIELDS_SCHEMA.items()
    }
