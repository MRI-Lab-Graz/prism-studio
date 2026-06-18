from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

from src.datalad_execution import run_datalad_run, run_datalad_unlock


def test_run_datalad_unlock_command_omits_on_failure_flag(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    """Regression guard: unlike `get`/`save`, `datalad unlock` doesn't accept
    `--on-failure` — passing it makes argparse reject the whole command and
    print usage text instead of unlocking anything, so every file silently
    stayed locked."""
    seen_commands: list[list[str]] = []

    def _fake_run(command, cwd=None, capture_output=True, text=True, timeout=None, check=False):
        seen_commands.append([str(item) for item in command])
        return SimpleNamespace(returncode=0, stdout="unlock ok", stderr="")

    monkeypatch.setattr("src.datalad_execution.subprocess.run", _fake_run)

    result = run_datalad_unlock(
        tmp_path,
        paths=["sub-001/sub-001_scans.tsv"],
        datalad_executable="/usr/bin/datalad",
    )

    assert result.get("success") is True
    assert len(seen_commands) == 1
    command = seen_commands[0]
    assert "--on-failure" not in command
    assert command == ["/usr/bin/datalad", "unlock", "sub-001/sub-001_scans.tsv"]


def test_run_datalad_run_escapes_literal_curly_braces_in_command(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    """Regression guard: `datalad run` treats the command after `--` as a
    template supporting placeholders like {inputs}/{outputs}. A Python dict
    literal embedded in a -c script (e.g. `explicit_mapping={'sub-004': ...}`)
    contains raw curly braces that DataLad's templating then tries to parse
    as a placeholder, failing with 'unrecognized placeholder' before
    anything even runs. Literal braces must be escaped by doubling, exactly
    like Python's str.format()."""
    seen_commands: list[list[str]] = []

    def _fake_run(command, cwd=None, capture_output=True, text=True, timeout=None, check=False, env=None):
        seen_commands.append([str(item) for item in command])
        return SimpleNamespace(returncode=0, stdout="run ok", stderr="")

    monkeypatch.setattr("src.datalad_execution.subprocess.run", _fake_run)

    script_with_dict_literal = "result={'sub-134004': 'sub-004'}"
    result = run_datalad_run(
        tmp_path,
        message="PRISM: test",
        command=["python3", "-c", script_with_dict_literal],
        datalad_executable="/usr/bin/datalad",
    )

    assert result.get("success") is True
    command = seen_commands[0]
    script_arg = command[-1]
    assert script_arg == "result={{'sub-134004': 'sub-004'}}"
    # Sanity check: doubled braces collapse back to the original literal
    # text under str.format()-style substitution, same as DataLad's own
    # template engine would do once it recognizes there's no placeholder.
    assert script_arg.format() == script_with_dict_literal
