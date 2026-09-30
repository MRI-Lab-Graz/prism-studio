"""Browser (Playwright) harness: the real Studio app in-process, one throwaway project.

Skips itself when playwright or its Chromium is not installed:
    pip install playwright && playwright install chromium
"""

from __future__ import annotations

import importlib.util
import json
import sys
import threading
from pathlib import Path

import pytest

pytest.importorskip("playwright.sync_api")
from playwright.sync_api import sync_playwright  # noqa: E402
from werkzeug.serving import make_server  # noqa: E402

PRISM_STUDIO_FILE = Path(__file__).resolve().parents[2] / "app" / "prism-studio.py"


@pytest.fixture(scope="session")
def studio_url(tmp_path_factory):
    settings_dir = tmp_path_factory.mktemp("app-settings")
    spec = importlib.util.spec_from_file_location("prism_studio_e2e", PRISM_STUDIO_FILE)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module  # Flask locates app/static via the registered module
    spec.loader.exec_module(module)

    # Setting a project also saves "last project" to the user's real app settings.
    config = sys.modules["src.config"]
    original = config._get_user_app_settings_dir
    config._get_user_app_settings_dir = lambda: settings_dir

    server = make_server("127.0.0.1", 0, module.app, threaded=True)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{server.server_port}"
    server.shutdown()
    config._get_user_app_settings_dir = original


@pytest.fixture(scope="session")
def browser():
    with sync_playwright() as p:
        try:
            b = p.chromium.launch()
        except Exception as exc:  # browser binary not installed
            pytest.skip(f"Chromium not available: {exc}")
        yield b
        b.close()


@pytest.fixture
def project(tmp_path):
    root = tmp_path / "study"
    (root / "code" / "library" / "survey").mkdir(parents=True)
    # A real PRISM project always has these; the pages request them on load.
    (root / "project.json").write_text(json.dumps({"Basics": {"Name": "e2e"}}))
    (root / "dataset_description.json").write_text(
        json.dumps({"Name": "e2e", "BIDSVersion": "1.10.0"})
    )
    return root


@pytest.fixture
def app_page(browser, studio_url, project):
    """A page with the throwaway project open; fails the test on any browser-side error."""
    context = browser.new_context()
    resp = context.request.post(
        f"{studio_url}/api/projects/current",
        data={"path": str(project), "name": "e2e"},
    )
    assert resp.ok, resp.text()
    page = context.new_page()
    problems: list[str] = []
    page.on("pageerror", lambda err: problems.append(f"JS error: {err}"))
    page.on(
        "console",
        lambda msg: msg.type == "error" and problems.append(f"console: {msg.text}"),
    )
    page.on(
        "response",
        lambda r: r.status >= 400 and problems.append(f"HTTP {r.status}: {r.url}"),
    )
    yield page
    context.close()
    assert not problems, "\n".join(problems)


@pytest.fixture
def page(app_page, studio_url):
    app_page.goto(f"{studio_url}/template-editor")
    return app_page
