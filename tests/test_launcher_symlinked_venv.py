"""prism-studio.py must start from a venv whose python is a symlink.

install.sh falls back to a symlinked venv when `venv --copies` fails (uv-managed
Python aborts in ensurepip on macOS), so the launcher has to accept it.
"""
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent


@pytest.mark.skipif(sys.platform == "win32", reason="POSIX venv layout")
def test_launcher_runs_with_symlinked_venv_python(tmp_path):
    for name in ("prism-studio.py", "launcher_exec.py"):
        shutil.copy(ROOT / name, tmp_path / name)
    (tmp_path / "app").mkdir()
    (tmp_path / "app" / "prism-studio.py").write_text(
        "import sys; print('APP_STARTED', sys.prefix)\n"
    )
    subprocess.run(
        [sys.executable, "-m", "venv", "--symlinks", "--without-pip", str(tmp_path / ".venv")],
        check=True,
    )
    assert (tmp_path / ".venv" / "bin" / "python").is_symlink()

    # Other test modules set PRISM_SKIP_VENV_CHECK in os.environ at import time.
    env = {k: v for k, v in os.environ.items() if k != "PRISM_SKIP_VENV_CHECK"}
    out = subprocess.run(
        [sys.executable, str(tmp_path / "prism-studio.py")],
        capture_output=True, text=True, timeout=60, env=env,
    )

    assert out.returncode == 0, out.stdout + out.stderr
    assert "APP_STARTED" in out.stdout
    assert Path(out.stdout.split("APP_STARTED", 1)[1].strip()).resolve() == (tmp_path / ".venv").resolve()
