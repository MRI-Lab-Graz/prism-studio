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
    monkeypatch.setattr(prism_studio_module, "_probe_health", lambda host, port: None)
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
    monkeypatch.setattr(prism_studio_module, "_probe_health", lambda host, port: None)
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

    assert "DataLad" not in output  # ready tools stay silent
    assert "not installed (optional)" in output
    assert "! git-annex" in output


def test_startup_step_prints_only_problems(prism_studio_module, capsys):
    capsys.readouterr()
    prism_studio_module._print_startup_step("Web modules")
    assert capsys.readouterr().out == ""

    prism_studio_module._print_startup_step("REST API", "error", "boom")
    assert "REST API" in capsys.readouterr().out


def test_startup_intro_draws_the_logo_without_a_preflight_header(
    prism_studio_module, capsys
):
    capsys.readouterr()
    prism_studio_module._print_startup_intro()
    output = capsys.readouterr().out

    assert "/\\" in output  # the prism's apex
    assert "PRISM Studio" in output
    assert "Pre-flight" not in output


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


def test_health_reachable_without_project(prism_studio_module):
    # is_prism_studio_instance() probes /health with no session; a redirect to
    # /projects made every running instance look like a foreign process.
    resp = prism_studio_module.app.test_client().get("/health")
    assert resp.status_code == 200
    from src import __version__

    payload = resp.get_json()
    assert payload["status"] == "ok" and payload["running"] is True
    assert payload["version"] == __version__
    assert payload["location"]  # where this instance runs from


def test_main_reuses_running_instance(prism_studio_module, monkeypatch):
    opened = []

    def fail(*args, **kwargs):
        raise AssertionError("must not start/replace a server when one is running")

    from src import __version__

    monkeypatch.setattr(
        prism_studio_module,
        "_probe_health",
        lambda host, port: {"status": "ok", "running": True, "version": __version__},
    )
    monkeypatch.setattr(prism_studio_module, "ensure_clean_start", fail)
    monkeypatch.setattr(prism_studio_module, "_should_relaunch_in_dedicated_terminal", fail)
    monkeypatch.setattr(prism_studio_module.webbrowser, "open", opened.append)
    monkeypatch.setattr(prism_studio_module.sys, "argv", ["prism-studio.py"])

    prism_studio_module.main()

    assert opened == ["http://127.0.0.1:5001"]


@pytest.mark.parametrize("old_health", [
    {"status": "ok", "running": True, "version": "1.22.0"},
    {"status": "ok", "running": True},  # an instance from before /health told its version
])
def test_main_replaces_a_running_instance_of_another_version(prism_studio_module, monkeypatch, old_health):
    class Replaced(Exception):
        pass

    def replace(host, port, force=False):
        raise Replaced

    monkeypatch.setattr(prism_studio_module, "_probe_health", lambda host, port: old_health)
    monkeypatch.setattr(prism_studio_module, "is_port_in_use", lambda host, port: True)
    monkeypatch.setattr(prism_studio_module, "ensure_clean_start", replace)
    monkeypatch.setattr(prism_studio_module.webbrowser, "open", lambda url: pytest.fail("opened the old instance"))
    monkeypatch.setattr(prism_studio_module.sys, "argv", ["prism-studio.py"])

    with pytest.raises(Replaced):
        prism_studio_module.main()


def test_kill_fallback_only_stops_the_listening_process(prism_studio_module, monkeypatch):
    import subprocess

    calls = []

    def fake_run(cmd, **kwargs):
        calls.append(cmd)
        return subprocess.CompletedProcess(cmd, 0, stdout="4242\n", stderr="")

    monkeypatch.setattr(prism_studio_module.sys, "platform", "linux")
    monkeypatch.setattr(subprocess, "run", fake_run)
    monkeypatch.setattr(prism_studio_module.time, "sleep", lambda s: None)

    assert prism_studio_module.try_kill_existing_process(5001) is True
    assert any("-sTCP:LISTEN" in c for c in calls[:1])  # not the browser connected to the port
    assert calls[1] == ["kill", "-9", "4242"]


def test_kill_fallback_without_lsof_says_how_to_stop_it(prism_studio_module, monkeypatch, capsys):
    import subprocess

    def missing(cmd, **kwargs):
        raise FileNotFoundError("lsof")

    monkeypatch.setattr(prism_studio_module.sys, "platform", "linux")
    monkeypatch.setattr(subprocess, "run", missing)

    assert prism_studio_module.try_kill_existing_process(5001) is False
    assert "pkill -f prism-studio.py" in capsys.readouterr().out


def test_version_ignores_stale_git_tags_in_parent_dir(
    prism_studio_module, monkeypatch, tmp_path
):
    """A ZIP unpacked inside an older git clone must report its own version."""
    from src import __version__

    (tmp_path / ".git" / "refs" / "tags").mkdir(parents=True)
    (tmp_path / ".git" / "refs" / "tags" / "v0.0.1").write_text("x")
    install_dir = tmp_path / "prism-studio"
    install_dir.mkdir()
    monkeypatch.setattr(prism_studio_module, "BASE_DIR", install_dir)
    monkeypatch.setitem(prism_studio_module._github_tag_cache, "expires_at", 0.0)

    assert prism_studio_module.get_prism_studio_version() == __version__


def test_ensure_clean_start_kills_unresponsive_prism_instance_without_force(
    prism_studio_module, monkeypatch
):
    """An old PRISM instance that ignores /shutdown must not survive a restart."""
    monkeypatch.setattr(prism_studio_module, "is_port_in_use", lambda host, port: True)
    monkeypatch.setattr(
        prism_studio_module, "is_prism_studio_instance", lambda host, port: True
    )
    monkeypatch.setattr(
        prism_studio_module, "request_existing_instance_shutdown", lambda h, p: False
    )
    killed = []
    monkeypatch.setattr(
        prism_studio_module,
        "try_kill_existing_process",
        lambda port: killed.append(port) or True,
    )
    monkeypatch.setattr(prism_studio_module, "wait_for_port_release", lambda h, p: True)

    prism_studio_module.ensure_clean_start("127.0.0.1", 5001)

    assert killed == [5001]


def test_port_probe_has_a_short_timeout(prism_studio_module, monkeypatch):
    # Windows retries a refused loopback connect for ~1-2 s unless a timeout
    # cuts it off; a live local listener accepts in well under a millisecond.
    seen = {}

    class FakeSocket:
        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

        def settimeout(self, value):
            seen["timeout"] = value

        def connect_ex(self, addr):
            return 10061

    monkeypatch.setattr(prism_studio_module.socket, "socket", lambda *a, **k: FakeSocket())

    assert prism_studio_module.is_port_in_use("127.0.0.1", 5001) is False
    assert 0 < seen["timeout"] <= 0.5


def test_instance_probe_sends_no_request_to_a_closed_port(prism_studio_module, monkeypatch):
    monkeypatch.setattr(prism_studio_module, "is_port_in_use", lambda host, port: False)

    def fail(*args, **kwargs):
        raise AssertionError("no HTTP request when nothing listens")

    monkeypatch.setattr(prism_studio_module.http.client, "HTTPConnection", fail)

    assert prism_studio_module.is_prism_studio_instance("127.0.0.1", 5001) is False
