"""The packaged app has only the repo root and app/ on sys.path, not app/src.

runner.py does bare sibling imports (``from schema_manager import ...``), so a blueprint that imports
``src.runner`` at top level cannot load there: the bundled converter and tools pages came back 404
(v1.23.0 build). Runner helpers go through ``src.core.validation``, which imports them bare-first.
"""

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_survey_preview_handler_imports_without_app_src_on_the_path():
    code = (
        "import sys; sys.path[:0] = ['app', '.'];"
        "import src.web.blueprints.conversion_survey_preview_handlers"
    )
    result = subprocess.run([sys.executable, "-I", "-c", code], cwd=ROOT, capture_output=True, text=True)
    assert result.returncode == 0, result.stderr[-600:]
