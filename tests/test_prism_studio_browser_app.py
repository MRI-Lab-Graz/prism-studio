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
    return _load_module_from_path("prism_studio_browser_app", PRISM_STUDIO_FILE)


def test_resolve_named_browser_returns_none_for_unknown_name(prism_studio_module):
    assert prism_studio_module._resolve_named_browser("not-a-browser") is None


def test_resolve_named_browser_macos_finds_installed_app(
    prism_studio_module, monkeypatch
):
    monkeypatch.setattr(prism_studio_module.sys, "platform", "darwin")
    monkeypatch.setattr(
        prism_studio_module.Path,
        "exists",
        lambda self: self == Path("/Applications/Brave Browser.app"),
    )

    assert prism_studio_module._resolve_named_browser("brave") == "Brave Browser"


def test_resolve_named_browser_macos_missing_app_returns_none(
    prism_studio_module, monkeypatch
):
    monkeypatch.setattr(prism_studio_module.sys, "platform", "darwin")
    monkeypatch.setattr(prism_studio_module.Path, "exists", lambda self: False)

    assert prism_studio_module._resolve_named_browser("brave") is None


def test_resolve_named_browser_windows_finds_exe(prism_studio_module, monkeypatch):
    monkeypatch.setattr(prism_studio_module.sys, "platform", "win32")
    monkeypatch.setenv("PROGRAMFILES", r"C:\Program Files")
    monkeypatch.setenv("PROGRAMFILES(X86)", r"C:\Program Files (x86)")
    monkeypatch.setenv("LOCALAPPDATA", r"C:\Users\test\AppData\Local")
    expected = prism_studio_module.os.path.join(
        r"C:\Program Files", "Mozilla Firefox", "firefox.exe"
    )
    monkeypatch.setattr(
        prism_studio_module.os.path, "isfile", lambda path: path == expected
    )

    assert prism_studio_module._resolve_named_browser("firefox") == expected


def test_resolve_named_browser_linux_uses_which(prism_studio_module, monkeypatch):
    monkeypatch.setattr(prism_studio_module.sys, "platform", "linux")
    monkeypatch.setattr(
        prism_studio_module.shutil,
        "which",
        lambda cmd: "/usr/bin/google-chrome-stable" if cmd == "google-chrome-stable" else None,
    )

    assert (
        prism_studio_module._resolve_named_browser("chrome")
        == "/usr/bin/google-chrome-stable"
    )


def test_list_installed_browser_names_filters_to_resolved(
    prism_studio_module, monkeypatch
):
    monkeypatch.setattr(
        prism_studio_module,
        "_resolve_named_browser",
        lambda name: "/usr/bin/firefox" if name == "firefox" else None,
    )

    assert prism_studio_module._list_installed_browser_names() == ["firefox"]


def test_open_url_with_browser_app_macos_uses_open_dash_a(
    prism_studio_module, monkeypatch
):
    monkeypatch.setattr(prism_studio_module.sys, "platform", "darwin")
    captured = {}
    monkeypatch.setattr(
        prism_studio_module.subprocess,
        "Popen",
        lambda cmd: captured.setdefault("cmd", cmd),
    )

    result = prism_studio_module._open_url_with_browser_app(
        "brave", "Brave Browser", "http://127.0.0.1:5001"
    )

    assert result is True
    assert captured["cmd"] == ["open", "-a", "Brave Browser", "http://127.0.0.1:5001"]


def test_open_url_with_browser_app_non_macos_launches_executable_directly(
    prism_studio_module, monkeypatch
):
    monkeypatch.setattr(prism_studio_module.sys, "platform", "linux")
    captured = {}
    monkeypatch.setattr(
        prism_studio_module.subprocess,
        "Popen",
        lambda cmd: captured.setdefault("cmd", cmd),
    )

    result = prism_studio_module._open_url_with_browser_app(
        "firefox", "/usr/bin/firefox", "http://127.0.0.1:5001"
    )

    assert result is True
    assert captured["cmd"] == ["/usr/bin/firefox", "http://127.0.0.1:5001"]


def test_open_url_with_browser_app_returns_false_on_launch_failure(
    prism_studio_module, monkeypatch
):
    def raise_error(cmd):
        raise OSError("no such file")

    monkeypatch.setattr(prism_studio_module.subprocess, "Popen", raise_error)

    result = prism_studio_module._open_url_with_browser_app(
        "brave", "Brave Browser", "http://127.0.0.1:5001"
    )

    assert result is False


def test_require_named_browser_returns_resolved_target(
    prism_studio_module, monkeypatch
):
    monkeypatch.setattr(
        prism_studio_module, "_resolve_named_browser", lambda name: "/usr/bin/firefox"
    )

    assert prism_studio_module._require_named_browser("firefox") == "/usr/bin/firefox"


def test_require_named_browser_exits_and_lists_installed_browsers(
    prism_studio_module, monkeypatch, capsys
):
    monkeypatch.setattr(prism_studio_module, "_resolve_named_browser", lambda name: None)
    monkeypatch.setattr(
        prism_studio_module, "_list_installed_browser_names", lambda: ["safari"]
    )

    with pytest.raises(SystemExit) as exc_info:
        prism_studio_module._require_named_browser("brave")

    assert exc_info.value.code == 1
    output = capsys.readouterr().out
    assert "brave" in output
    assert "safari" in output
