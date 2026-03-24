from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
PRISM_TOOLS_APP = PROJECT_ROOT / "app" / "prism_tools.py"


def _run_prism_tools(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(PRISM_TOOLS_APP), *args],
        capture_output=True,
        text=True,
        cwd=str(PROJECT_ROOT),
        timeout=30,
    )


def test_environment_preview_cli_json_output(tmp_path: Path) -> None:
    input_path = tmp_path / "environment.csv"
    input_path.write_text(
        "participant_id,session,timestamp,location\n"
        "sub-01,ses-01,2026-03-24 10:00:00,Berlin\n",
        encoding="utf-8",
    )

    result = _run_prism_tools(
        "environment",
        "preview",
        "--input",
        str(input_path),
        "--separator",
        "auto",
        "--json",
    )

    output = (result.stdout or "") + (result.stderr or "")
    assert result.returncode == 0, output

    payload = json.loads(result.stdout)
    assert payload["columns"] == ["participant_id", "session", "timestamp", "location"]
    assert payload["auto_detected"]["participant_id"] == "participant_id"
    assert payload["auto_detected"]["session"] == "session"
    assert payload["auto_detected"]["timestamp"] == "timestamp"
    assert payload["auto_detected"]["location"] == "location"
    assert payload["compatibility"]["status"] == "compatible"
    assert payload["sample"][0][0] == "sub-01"