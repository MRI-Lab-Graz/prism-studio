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
    monkeypatch.setattr(
        prism_studio_module, "ensure_clean_start", fake_ensure_clean_start
    )
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


def test_main_does_not_auto_fallback_for_explicit_port(
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
    monkeypatch.setattr(
        prism_studio_module, "ensure_clean_start", fake_ensure_clean_start
    )
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


def test_startup_dependency_steps_report_ready_and_not_installed(
    prism_studio_module, monkeypatch, capsys
):
    monkeypatch.setattr(
        prism_studio_module.shutil,
        "which",
        lambda executable: "/usr/bin/datalad" if executable == "datalad" else None,
    )

    capsys.readouterr()
    prism_studio_module._print_startup_dependency_step("DataLad", "datalad")
    prism_studio_module._print_startup_dependency_step("git-annex", "git-annex")
    output = capsys.readouterr().out

    assert "DataLad" in output
    assert "git-annex" in output
    assert "ready" in output
    assert "not installed (optional)" in output
    assert "! git-annex" in output


def test_inject_utilities_exposes_request_api_origin(
    prism_studio_module, monkeypatch
):
    monkeypatch.setattr(prism_studio_module, "get_prism_studio_version", lambda: "1.0.0")
    monkeypatch.setattr(
        prism_studio_module,
        "get_latest_prism_studio_version",
        lambda: ("1.0.0", "https://example.invalid/release"),
    )
    monkeypatch.setattr(
        prism_studio_module,
        "is_newer_release_available",
        lambda current, latest: False,
    )

    import src.project_manager as project_manager_module

    fast_flags_seen = []

    def fake_get_datalad_status(self, project_path, *, fast=False):
        fast_flags_seen.append(fast)
        return {"path": project_path, "enabled": False}

    monkeypatch.setattr(
        project_manager_module.ProjectManager,
        "get_datalad_status",
        fake_get_datalad_status,
    )

    with prism_studio_module.app.test_request_context(
        "/",
        base_url="http://127.0.0.1:5002",
    ):
        injected = prism_studio_module.inject_utilities()

    assert injected["prism_api_origin"] == "http://127.0.0.1:5002"
    # This context processor runs on every template render across the whole
    # app, so it must use the fast DataLad status path; the full per-
    # subdataset scan would otherwise slow down every navbar page load.
    assert fast_flags_seen == [True]
