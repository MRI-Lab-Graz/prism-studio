"""Every project-path comparison in the frontend must use isSameProjectPath.

The server answers /api/projects/current with ``str(Path(...))``, so on Windows
the navbar store can replace a forward-slash project path with the backslash
spelling of the same project mid-request. Raw ``===`` comparisons then read that
as a project switch: the study metadata form stayed locked (every field gray),
and the DataLad progress poller silently stopped updating.

The ES modules import the helper; the classic page scripts get it from
``window`` via a bridge in base.html. This guards both halves, because a missing
bridge fails at runtime with a bare TypeError inside an event handler.
"""

import re
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
JS_ROOT = REPO_ROOT / "app" / "static" / "js"
BASE_TEMPLATE = REPO_ROOT / "app" / "templates" / "base.html"
HELPER_MODULE = JS_ROOT / "shared" / "project-state.js"

# Matches `somePath === other` / `other !== somePath` - the raw comparison that
# this whole fix exists to remove.
RAW_PATH_COMPARISON = re.compile(
    r"[Pp]ath\s*(?:===|!==)\s*[A-Za-z_]|(?:===|!==)\s*[A-Za-z_]*[Pp]ath\b"
)

# Comparisons that are not filesystem project paths, or are already safe.
ALLOWED = (
    "fieldPath",  # JSON pointer inside the template editor, not a filesystem path
    "isSameProjectPath",
    "typeof",
    "=== ''",
    "!== ''",
    "=== null",
    "!== null",
    "=== undefined",
    "!== undefined",
    "res.new",
)


class TestProjectPathIdentityWiring(unittest.TestCase):
    def test_helper_is_exported_once(self):
        content = HELPER_MODULE.read_text(encoding="utf-8")
        self.assertIn("export function isSameProjectPath(", content)
        self.assertIn("export function normalizeProjectPathForCompare(", content)
        # Folding separators is the whole point; folding case would be wrong on
        # Linux/macOS, where two spellings really are two different projects.
        self.assertIn("replace(/\\\\/g, '/')", content)
        self.assertNotIn("toLowerCase()", content.split("normalizeProjectPathForCompare")[-1])

    def test_base_template_bridges_helper_to_classic_scripts(self):
        content = BASE_TEMPLATE.read_text(encoding="utf-8")
        self.assertIn("window.isSameProjectPath = isSameProjectPath;", content)
        self.assertIn("js/shared/project-state.js", content)

    def test_no_raw_project_path_comparisons_remain(self):
        offenders = []
        for js_file in sorted(JS_ROOT.rglob("*.js")):
            if js_file.name.endswith(".test.js"):
                continue
            for number, line in enumerate(
                js_file.read_text(encoding="utf-8").splitlines(), start=1
            ):
                if not RAW_PATH_COMPARISON.search(line):
                    continue
                if any(token in line for token in ALLOWED):
                    continue
                offenders.append(
                    f"{js_file.relative_to(REPO_ROOT)}:{number}: {line.strip()}"
                )

        self.assertEqual(
            offenders,
            [],
            "Compare project paths with isSameProjectPath(), not ===/!==:\n"
            + "\n".join(offenders),
        )


if __name__ == "__main__":
    unittest.main()
