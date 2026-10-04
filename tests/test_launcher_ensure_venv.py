"""launcher_exec.ensure_venv: the venv check shared by the root launchers.

prism-studio.py is strict (no venv -> exit); prism.py only warns, and also
skips the check in CI.
"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from launcher_exec import ensure_venv  # noqa: E402


@pytest.fixture(autouse=True)
def _no_skip_env(monkeypatch):
    monkeypatch.delenv("PRISM_SKIP_VENV_CHECK", raising=False)
    monkeypatch.delenv("CI", raising=False)


def test_strict_exits_when_venv_missing(tmp_path):
    with pytest.raises(SystemExit) as exc:
        ensure_venv(tmp_path, strict=True)
    assert exc.value.code == 2


def test_strict_exits_when_venv_python_missing(tmp_path):
    (tmp_path / ".venv").mkdir()
    with pytest.raises(SystemExit) as exc:
        ensure_venv(tmp_path, strict=True)
    assert exc.value.code == 3


def test_lenient_warns_and_continues_when_venv_missing(tmp_path, capsys):
    assert ensure_venv(tmp_path, strict=False) is None
    assert "Virtual environment not found" in capsys.readouterr().out


def test_skip_env_var_bypasses_check(tmp_path, monkeypatch):
    monkeypatch.setenv("PRISM_SKIP_VENV_CHECK", "1")
    assert ensure_venv(tmp_path, strict=True) is None


def test_ci_skips_only_lenient_check(tmp_path, monkeypatch):
    monkeypatch.setenv("CI", "1")
    assert ensure_venv(tmp_path, strict=False) is None
    with pytest.raises(SystemExit):
        ensure_venv(tmp_path, strict=True)
