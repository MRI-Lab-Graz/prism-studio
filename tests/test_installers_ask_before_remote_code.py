"""Installers must not run a downloaded script (`curl | sh`, `irm | iex`) without
asking, and must not carry an unused Invoke-Expression helper."""

import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = [ROOT / "install.sh", ROOT / "scripts" / "setup" / "windows.ps1"]
PIPE_TO_SHELL = re.compile(r"\|\s*(sh|bash|iex)\b")
PROMPT = re.compile(r"\bread\s(?:-\w+\s)*-p\b|Read-Host")  # read [-r] -p "..."


@pytest.mark.parametrize("script", SCRIPTS, ids=lambda p: p.name)
def test_remote_script_execution_is_preceded_by_a_prompt(script):
    lines = script.read_text(encoding="utf-8").splitlines()
    for i, line in enumerate(lines):
        if line.lstrip().startswith(("#", "echo", "Write-")) or not PIPE_TO_SHELL.search(line):
            continue  # comments and printed hints are not executed
        context = "\n".join(lines[max(0, i - 6) : i])
        assert PROMPT.search(context), f"{script.name}:{i + 1} runs remote code without asking: {line.strip()}"


def test_no_invoke_expression_helper_left_in_windows_setup():
    assert "Invoke-Expression" not in (ROOT / "scripts" / "setup" / "windows.ps1").read_text(encoding="utf-8")
