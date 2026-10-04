"""The JSON editor backend imports as src.json_editor.*, without sys.path edits.

It used to push app/src/json_editor/src onto sys.path, so its modules were
importable as the top-level names `backend` and `schema_loader`.
"""

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

PROBE = """
import json, sys
sys.path.insert(0, {app!r})
before = list(sys.path)
import src.json_editor_blueprint
import src.cli.commands.json_editor as cli
cli._load_json_editor_backend()
print(json.dumps({{
    "added": [p for p in sys.path if p not in before],
    "top_level": [m for m in ("backend", "schema_loader") if m in sys.modules],
}}))
"""


def test_json_editor_needs_no_sys_path_entries():
    r = subprocess.run(
        [sys.executable, "-c", PROBE.format(app=str(ROOT / "app"))],
        capture_output=True,
        text=True,
        cwd=ROOT,
        env={"PRISM_STARTUP_HIDE_DETAILS": "1", "PATH": ""},
    )
    assert r.returncode == 0, r.stderr
    got = json.loads(r.stdout.strip().splitlines()[-1])
    assert got == {"added": [], "top_level": []}
