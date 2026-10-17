"""A stray VIRTUAL_ENV (e.g. DataLad Desktop's env) must not redirect uv into
another environment: every `uv pip install` in windows.ps1 names the .venv."""
import re
from pathlib import Path

SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "setup" / "windows.ps1"


def test_every_uv_pip_install_names_the_venv_python():
    calls = re.findall(r"uv pip install[^\n]*", SCRIPT.read_text(encoding="utf-8"))
    assert calls
    assert all("--python" in c for c in calls), calls


def test_script_is_ascii_because_powershell_5_reads_bomless_files_as_ansi():
    assert SCRIPT.read_bytes().isascii()
