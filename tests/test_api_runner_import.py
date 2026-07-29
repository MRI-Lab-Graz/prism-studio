"""Regression test: src/api.py must import cleanly from prism-studio.py's
actual bootstrap, not just whatever sys.path pytest happens to already have.

runner.py, schema_manager.py, and issues.py are canonical only under
app/src/, not mirrored into top-level src/. src/api.py used to do a bare
`from runner import validate_dataset` (etc.) that only ever worked by
accident if something else had already put app/src on sys.path -- under
prism-studio.py's real bootstrap (which only adds app/, not app/src) this
raised ModuleNotFoundError, silently disabling the REST API's
/validate and /schemas endpoints (500 "not available") and demoting the
Studio's in-process validator to its slower subprocess fallback.

Run in a subprocess with a from-scratch sys.path so that other tests in
this session (which may have already imported app/src as a side effect)
can't mask a regression here.
"""

import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
APP_DIR = REPO_ROOT / "app"

_CHECKED_NAMES = (
    "validate_dataset",
    "get_available_schema_versions",
    "load_all_schemas",
    "tuple_to_issue",
    "issues_to_dict",
    "summarize_issues",
)

_PROBE_SCRIPT = f"""
import sys
sys.path.insert(0, {str(APP_DIR)!r})

# Matches app/prism-studio.py's own bootstrap order: only the app/ directory
# is added to sys.path before src.api is imported.
from src.dedicated_terminal import should_stream_frozen_logs_to_attached_terminal
from src.api import create_api_blueprint
import src.api as api_mod

missing = [name for name in {_CHECKED_NAMES!r} if getattr(api_mod, name, None) is None]
if missing:
    raise SystemExit("missing: " + ",".join(missing))
print("OK")
"""


def test_src_api_resolves_runner_schema_manager_issues_from_app_bootstrap():
    result = subprocess.run(
        [sys.executable, "-c", _PROBE_SCRIPT],
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "OK" in result.stdout
