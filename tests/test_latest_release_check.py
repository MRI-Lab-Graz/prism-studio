from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest
import requests

PRISM_STUDIO_FILE = Path(__file__).resolve().parents[1] / "app" / "prism-studio.py"


def _load_module_from_path(module_name: str, file_path: Path):
    spec = importlib.util.spec_from_file_location(module_name, str(file_path))
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def prism_studio_module():
    return _load_module_from_path("prism_studio_latest_release_check", PRISM_STUDIO_FILE)


def test_fetch_latest_github_release_uses_requests_not_raw_http_client(
    prism_studio_module, monkeypatch
):
    """Regression test: a TLS failure specific to `http.client`'s default cert
    paths (the frozen-macOS bug) must not be able to recur, because the
    check must go through `requests` like the rest of the codebase does.
    """

    class FakeResponse:
        status_code = 200

        def json(self):
            return {
                "tag_name": "v1.20.0",
                "html_url": "https://example.invalid/releases/v1.20.0",
            }

    captured = {}

    def fake_get(url, headers=None, timeout=None):
        captured["url"] = url
        return FakeResponse()

    monkeypatch.setattr(prism_studio_module.requests, "get", fake_get)

    tag, url = prism_studio_module._fetch_latest_github_release()

    assert tag == "v1.20.0"
    assert url == "https://example.invalid/releases/v1.20.0"
    assert captured["url"].startswith("https://api.github.com/")


def test_fetch_latest_github_release_swallows_tls_errors(
    prism_studio_module, monkeypatch
):
    def fake_get(url, headers=None, timeout=None):
        raise requests.exceptions.SSLError("certificate verify failed")

    monkeypatch.setattr(prism_studio_module.requests, "get", fake_get)

    tag, url = prism_studio_module._fetch_latest_github_release()

    assert (tag, url) == (None, None)


def test_fetch_latest_github_release_returns_none_on_non_200(
    prism_studio_module, monkeypatch
):
    class FakeResponse:
        status_code = 404

        def json(self):
            raise AssertionError("json() should not be called on non-200 response")

    monkeypatch.setattr(
        prism_studio_module.requests, "get", lambda *a, **k: FakeResponse()
    )

    tag, url = prism_studio_module._fetch_latest_github_release()

    assert (tag, url) == (None, None)
