"""Explorer's zip view extracts only install.cmd into Temp; it must say so, not spew PowerShell errors."""
from pathlib import Path

CMD = (Path(__file__).resolve().parent.parent / "install.cmd").read_text(encoding="utf-8")


def test_stops_early_when_run_from_inside_the_zip():
    guard = CMD.index(r'if not exist "scripts\setup\windows.ps1"')
    assert guard < CMD.index("Unblock-File")
    assert "Extract All" in CMD
