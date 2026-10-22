"""The vendored scripts/specification/check_terms.py accepts Studio's shipped term registry.

The rules themselves are tested in prism-specification, where the script is edited.
"""

import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]


def test_vendored_check_passes_on_the_shipped_terms():
    result = subprocess.run(
        [sys.executable, str(REPO / "scripts" / "specification" / "check_terms.py"),
         "--terms", str(REPO / "official" / "library" / "terms" / "biosample"),
         "--schema", str(REPO / "app" / "schemas" / "stable" / "biosample.schema.json")],
        capture_output=True, text=True,
    )
    assert result.returncode == 0, result.stdout + result.stderr
