"""docs/specs/*.md: the vendored pages are generated in prism-specification; Studio's own page is checked here.

Fix a failure for project.md with:
python scripts/specification/generate_schema_reference.py --schemas app/schemas/stable --specs docs/specs \
    --link-prefix ../../app/schemas/stable/ --label-prefix app/schemas/stable/ --page project=project.md
"""

import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
GENERATOR = REPO / "scripts" / "specification" / "generate_schema_reference.py"


def test_project_page_matches_its_schema():
    result = subprocess.run(
        [sys.executable, str(GENERATOR), "--check",
         "--schemas", str(REPO / "app" / "schemas" / "stable"), "--specs", str(REPO / "docs" / "specs"),
         "--link-prefix", "../../app/schemas/stable/", "--label-prefix", "app/schemas/stable/",
         "--page", "project=project.md"],
        capture_output=True, text=True,
    )
    assert result.returncode == 0, result.stdout + result.stderr
