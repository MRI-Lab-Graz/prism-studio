"""Rendered Studio pages must pass the W3C Nu validator (vnu).

Skipped when vnu isn't installed (brew install vnu). Pages that redirect
without an open project are not rendered, so they are not covered.
"""

import shutil
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent

PAGES = [
    "/", "/projects", "/survey-generator", "/survey-customizer", "/converter",
    "/recipes", "/template-editor", "/specifications", "/validate",
]

# webkitdirectory/directory are non-standard but needed for folder pickers.
IGNORED = r".*Attribute .(webkitdirectory|directory). not allowed.*"

_RENDER = f"""
import importlib.util, sys
sys.path[:0] = [{str(REPO_ROOT / "app")!r}, {str(REPO_ROOT)!r}]
spec = importlib.util.spec_from_file_location("ps", {str(REPO_ROOT / "app" / "prism-studio.py")!r})
m = importlib.util.module_from_spec(spec); sys.modules["ps"] = m; spec.loader.exec_module(m)
c = m.app.test_client()
for p in {PAGES!r}:
    r = c.get(p)
    assert r.status_code == 200, (p, r.status_code)
    open(sys.argv[1] + "/" + (p.strip("/") or "home") + ".html", "wb").write(r.data)
"""


@pytest.mark.skipif(not shutil.which("vnu"), reason="vnu not installed")
def test_rendered_pages_are_valid_html(tmp_path):
    subprocess.run([sys.executable, "-c", _RENDER, str(tmp_path)], check=True, cwd=REPO_ROOT)
    r = subprocess.run(
        ["vnu", "--errors-only", "--filterpattern", IGNORED, *map(str, tmp_path.glob("*.html"))],
        capture_output=True, text=True,
    )
    assert r.returncode == 0, (r.stdout + r.stderr)[:6000]
