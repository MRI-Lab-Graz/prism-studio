"""`datalad run` joins its command into one shell command line (cmd.exe on
Windows, where & | % ^ are live). Project paths and filter values are embedded
in the `python -c <script>` callers pass, so run_datalad_run hands Python a
script FILE instead: nothing user-controlled is left on the command line."""

import subprocess
from pathlib import Path
from types import SimpleNamespace

import src.datalad_execution as de

NASTY = "C:\\Study & Data\\%PATH% ^ | calc"


def _run(tmp_path, monkeypatch, command):
    (tmp_path / ".git").mkdir()
    seen = {}

    def fake_run(cmd, **kwargs):
        seen["cmd"] = cmd
        sep = cmd.index("--")
        script = cmd[sep + 2]
        seen["script_arg"] = script
        seen["script_text"] = (Path(kwargs["cwd"]) / script).read_text(encoding="utf-8")
        return SimpleNamespace(returncode=0, stdout="", stderr="")

    monkeypatch.setattr(de.subprocess, "run", fake_run)
    result = de.run_datalad_run(
        tmp_path, message="m", command=command, datalad_executable="/usr/bin/datalad"
    )
    return result, seen


def test_python_dash_c_script_is_moved_into_a_file(tmp_path, monkeypatch):
    script = f"p = {NASTY!r}\nd = {{'a': 1}}\nprint(p)"
    result, seen = _run(tmp_path, monkeypatch, ["python3", "-c", script, "manifest.json"])
    assert result["success"]
    cmd = seen["cmd"]
    assert not any("calc" in part or "%PATH%" in part for part in cmd)  # nothing nasty on the command line
    assert seen["script_text"] == script  # exact script, braces not template-escaped
    assert cmd[cmd.index("--") + 3] == "manifest.json"  # extra args kept
    assert Path(seen["script_arg"]).name.startswith("prism_run_")
    assert not (tmp_path / seen["script_arg"]).exists()  # cleaned up afterwards


def test_other_commands_are_left_alone(tmp_path, monkeypatch):
    (tmp_path / ".git").mkdir()
    captured = {}
    monkeypatch.setattr(
        de.subprocess, "run", lambda cmd, **kw: captured.update(cmd=cmd) or SimpleNamespace(returncode=0, stdout="", stderr="")
    )
    de.run_datalad_run(tmp_path, message="m", command=["echo", "{x}"], datalad_executable="/usr/bin/datalad")
    assert captured["cmd"][-2:] == ["echo", "{{x}}"]
