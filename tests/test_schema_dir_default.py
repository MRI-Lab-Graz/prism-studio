"""load_schema's default schema dir must not depend on the current directory.

It defaulted to the cwd-relative "schemas", so `prism_tools.py library fill`
(and every other caller relying on the default) failed with "Could not load
schema" unless run from inside app/.
"""

import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "app"))

from src.schema_manager import load_schema  # noqa: E402


def test_load_schema_default_dir_works_from_any_cwd(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    assert load_schema("survey", version="stable") is not None


def test_library_fill_works_outside_app_dir(tmp_path):
    template = tmp_path / "survey-demo.json"
    template.write_text(json.dumps({"Study": {"TaskName": "demo"}}))
    r = subprocess.run(
        [sys.executable, str(ROOT / "prism_tools.py"), "library", "fill",
         "--modality", "survey", "--path", str(template)],
        capture_output=True,
        text=True,
        cwd=tmp_path,
        env={**os.environ, "PRISM_SKIP_VENV_CHECK": "1"},
        timeout=60,
    )
    assert "Could not load schema" not in r.stdout, r.stdout
    assert r.returncode == 0, r.stdout + r.stderr
    filled = json.loads(template.read_text())
    assert "Technical" in filled  # a top-level key the survey schema defines
