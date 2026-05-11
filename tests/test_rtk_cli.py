from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
RTK_WRAPPER = PROJECT_ROOT / "rtk"


def _run_rtk(*args: str, env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    run_env = os.environ.copy()
    if env:
        run_env.update(env)

    return subprocess.run(
        [sys.executable, str(RTK_WRAPPER), *args],
        capture_output=True,
        text=True,
        cwd=str(PROJECT_ROOT),
        timeout=30,
        env=run_env,
    )


def test_rtk_help_lists_primary_subcommands() -> None:
    result = _run_rtk("--help")
    output = (result.stdout or "") + "\n" + (result.stderr or "")

    assert result.returncode == 0, output
    assert "setup" in output
    assert "studio" in output
    assert "validator" in output
    assert "tools" in output
    assert "test" in output
    assert "coverage" in output
    assert "codecov" in output
    assert "git" in output
    assert "gh" in output


def test_rtk_validator_help_proxies_prism_help() -> None:
    result = _run_rtk("validator", "--help", env={"PRISM_SKIP_VENV_CHECK": "1"})
    output = (result.stdout or "") + "\n" + (result.stderr or "")

    assert result.returncode == 0, output
    assert "--bids" in output
    assert "--schema-version" in output


def test_rtk_tools_help_proxies_prism_tools_help() -> None:
    result = _run_rtk("tools", "--help")
    output = (result.stdout or "") + "\n" + (result.stderr or "")

    assert result.returncode == 0, output
    assert "wide-to-long" in output
    assert "environment" in output
    assert "recipes" in output


def test_rtk_git_passthrough_executes_git() -> None:
    result = _run_rtk("git", "--version")
    output = (result.stdout or "") + "\n" + (result.stderr or "")

    assert result.returncode == 0, output
    assert "git version" in output.lower()


def test_rtk_codecov_reports_missing_binary_with_hint() -> None:
    result = _run_rtk("codecov", "--version", env={"PATH": ""})
    output = (result.stdout or "") + "\n" + (result.stderr or "")

    assert result.returncode == 1, output
    assert "codecovcli" in output
    assert "pip install codecov-cli" in output
