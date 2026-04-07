from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

PRISM_STUDIO_FILE = Path(__file__).resolve().parents[1] / "app" / "prism-studio.py"


def _load_module_from_path(module_name: str, file_path: Path):
    spec = importlib.util.spec_from_file_location(module_name, str(file_path))
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def prism_studio_module():
    return _load_module_from_path("prism_studio_port_conflicts", PRISM_STUDIO_FILE)


def test_ensure_clean_start_skips_shutdown_for_non_prism_instance(
    prism_studio_module, monkeypatch
):
    monkeypatch.setattr(prism_studio_module, "is_port_in_use", lambda host, port: True)
    monkeypatch.setattr(
        prism_studio_module, "is_prism_studio_instance", lambda host, port: False
    )

    def fail_if_called(host, port):
        raise AssertionError("shutdown request should not be called for non-PRISM")

    monkeypatch.setattr(
        prism_studio_module,
        "request_existing_instance_shutdown",
        fail_if_called,
    )

    with pytest.raises(SystemExit) as exc_info:
        prism_studio_module.ensure_clean_start("127.0.0.1", 5001, force=False)

    assert exc_info.value.code == 1


def test_main_uses_fallback_port_for_default_non_prism_conflict(
    prism_studio_module, monkeypatch
):
    captured = {}

    def fake_is_port_in_use(host, port):
        return port == 5001

    def fake_ensure_clean_start(host, port, force=False):
        captured["port"] = port
        captured["force"] = force
        raise RuntimeError("stop-after-port-selection")

    monkeypatch.setattr(prism_studio_module, "is_port_in_use", fake_is_port_in_use)
    monkeypatch.setattr(
        prism_studio_module, "is_prism_studio_instance", lambda host, port: False
    )
    monkeypatch.setattr(prism_studio_module, "ensure_clean_start", fake_ensure_clean_start)
    monkeypatch.setattr(
        prism_studio_module,
        "_should_relaunch_in_dedicated_terminal",
        lambda args: False,
    )
    monkeypatch.setattr(prism_studio_module.sys, "argv", ["prism-studio.py"])

    with pytest.raises(RuntimeError, match="stop-after-port-selection"):
        prism_studio_module.main()

    assert captured["port"] == 5002
    assert captured["force"] is False


def test_main_does_not_auto_fallback_for_explicit_port(prism_studio_module, monkeypatch):
    captured = {}

    def fake_is_port_in_use(host, port):
        return port == 5001

    def fake_ensure_clean_start(host, port, force=False):
        captured["port"] = port
        captured["force"] = force
        raise RuntimeError("stop-after-port-selection")

    monkeypatch.setattr(prism_studio_module, "is_port_in_use", fake_is_port_in_use)
    monkeypatch.setattr(
        prism_studio_module, "is_prism_studio_instance", lambda host, port: False
    )
    monkeypatch.setattr(prism_studio_module, "ensure_clean_start", fake_ensure_clean_start)
    monkeypatch.setattr(
        prism_studio_module,
        "_should_relaunch_in_dedicated_terminal",
        lambda args: False,
    )
    monkeypatch.setattr(
        prism_studio_module.sys,
        "argv",
        ["prism-studio.py", "--port", "5001"],
    )

    with pytest.raises(RuntimeError, match="stop-after-port-selection"):
        prism_studio_module.main()

    assert captured["port"] == 5001
    assert captured["force"] is False
