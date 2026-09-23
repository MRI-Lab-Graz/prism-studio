"""Re-exec must survive paths with spaces/parens (Windows download dirs)."""

import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import launcher_exec  # noqa: E402


def test_windows_path_with_spaces_stays_one_argument(tmp_path, monkeypatch):
    captured = {}
    monkeypatch.setattr(sys, "platform", "win32")
    monkeypatch.setattr(
        launcher_exec.subprocess,
        "run",
        lambda cmd, **kw: (captured.update(cmd=cmd),
                           subprocess.CompletedProcess(cmd, 0))[1],
    )
    script = tmp_path / "prism-studio-main (1)" / "app.py"
    try:
        launcher_exec.exec_python("py thon.exe", [script])
    except SystemExit as exc:
        assert exc.code == 0
    assert captured["cmd"] == ["py thon.exe", str(script)]


def test_child_receives_intact_path(tmp_path):
    """End-to-end: a real child process gets the unsplit path back."""
    workdir = tmp_path / "prism-studio-main (1)"
    workdir.mkdir()
    child = workdir / "child.py"
    child.write_text("import sys; print(sys.argv[1])")
    out = subprocess.run(
        [sys.executable, "-c",
         "import sys; sys.path.insert(0, sys.argv[1]);"
         "import launcher_exec;"
         "launcher_exec.exec_python(sys.executable, [sys.argv[2], sys.argv[2]])",
         str(Path(__file__).resolve().parents[1]), str(child)],
        capture_output=True, text=True,
    )
    assert out.stdout.strip() == str(child), out
