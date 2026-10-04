"""Backend modules load from top-level src/ directly, with no app/src shims.

In the app runtime (app/ on sys.path, as app/prism.py, app/prism-studio.py and
app/prism_tools.py set it up) `src` is app/src, whose __path__ falls through to
the repo src/ (or backend_bundle/src when frozen). A module that exists only in
src/ therefore imports fine as `src.<name>`; the load_canonical_module shims
were a second module object per backend file.
"""

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

MODULES = [
    "anonymizer",
    "api",
    "batch_convert",
    "formatters",
    "participants_backend",
    "participants_converter",
    "project_session_logging",
    "project_structure",
    "recipe_validation",
    "recipes_surveys",
    "runtime_dependencies",
    "converters.biometrics",
    "converters.excel_to_biometrics",
    "converters.file_reader",
    "converters.limesurvey",
    "converters.wide_to_long",
    "maintenance.catalog_survey_library",
    "maintenance.fill_missing_metadata",
    "maintenance.project_metadata_cleanup",
    "maintenance.sync_biometrics_keys",
    "maintenance.sync_survey_keys",
]

PROBE = """
import importlib, json, sys
sys.path[:0] = [{app_src!r}, {app!r}]
print(json.dumps({{m: importlib.import_module("src." + m).__file__ for m in {mods!r}}}))
"""


def test_app_runtime_imports_canonical_src_files():
    code = PROBE.format(
        app_src=str(ROOT / "app" / "src"), app=str(ROOT / "app"), mods=MODULES
    )
    r = subprocess.run(
        [sys.executable, "-c", code], capture_output=True, text=True, cwd=ROOT / "app"
    )
    assert r.returncode == 0, r.stderr
    files = json.loads(r.stdout.strip().splitlines()[-1])
    app = ROOT / "app"
    wrong = {m: f for m, f in files.items() if Path(f).is_relative_to(app)}
    assert not wrong, wrong


def test_compat_helpers_are_gone():
    assert not (ROOT / "app" / "src" / "_compat.py").exists()
    assert not (ROOT / "src" / "_compat.py").exists()
