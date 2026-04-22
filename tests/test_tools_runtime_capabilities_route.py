from __future__ import annotations

import importlib
import sys
from pathlib import Path

from flask import Flask

PROJECT_ROOT = Path(__file__).resolve().parent.parent
APP_ROOT = PROJECT_ROOT / "app"
PRISM_STUDIO_FILE = APP_ROOT / "prism-studio.py"
if str(APP_ROOT) not in sys.path:
    sys.path.insert(0, str(APP_ROOT))

tools_module = importlib.import_module("src.web.blueprints.tools")
tools_bp = tools_module.tools_bp


def _build_app() -> Flask:
    app = Flask(__name__)
    app.secret_key = "test-secret"  # pragma: allowlist secret
    app.register_blueprint(tools_bp)
    return app


def test_runtime_capabilities_route_reports_pyreadstat_support(monkeypatch) -> None:
    app = _build_app()
    client = app.test_client()

    monkeypatch.setattr(
        tools_module,
        "inspect_pyreadstat_write_support",
        lambda: {
            "pyreadstat_importable": True,
            "pyreadstat_write_support": True,
            "namespace_bundle_stub": False,
            "available_attrs": ["write_sav"],
            "error": None,
        },
    )
    monkeypatch.setattr(
        tools_module,
        "inspect_pandas_support",
        lambda: {
            "pandas_importable": True,
            "pandas_dataframe_support": True,
            "pandas_namespace_bundle_stub": False,
            "pandas_available_attrs": ["DataFrame"],
            "pandas_error": None,
        },
    )

    response = client.get("/api/runtime-capabilities")

    assert response.status_code == 200
    payload = response.get_json()
    assert payload["pyreadstat_write_support"] is True
    assert payload["pyreadstat_importable"] is True
    assert payload["pandas_importable"] is True
    assert payload["pandas_dataframe_support"] is True


def test_prism_studio_allows_runtime_capabilities_without_project() -> None:
    content = PRISM_STUDIO_FILE.read_text(encoding="utf-8")

    assert '"/api/runtime-capabilities"' in content
