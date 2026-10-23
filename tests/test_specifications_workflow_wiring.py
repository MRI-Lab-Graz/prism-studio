import re
import subprocess
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SPECIFICATIONS_TEMPLATE = REPO_ROOT / "app" / "templates" / "specifications.html"

_RENDER = f"""
import importlib.util, sys
sys.path[:0] = [{str(REPO_ROOT / "app")!r}, {str(REPO_ROOT)!r}]
spec = importlib.util.spec_from_file_location("ps", {str(REPO_ROOT / "app" / "prism-studio.py")!r})
m = importlib.util.module_from_spec(spec); sys.modules["ps"] = m; spec.loader.exec_module(m)
sys.stdout.write(m.app.test_client().get(sys.argv[1]).get_data(as_text=True))
"""


def render(path):
    """The page as a fresh visitor (no project open) sees it."""
    return subprocess.run(
        [sys.executable, "-c", _RENDER, path], capture_output=True, text=True, check=True, cwd=REPO_ROOT
    ).stdout


class TestSpecificationsWorkflowWiring(unittest.TestCase):
    def test_specifications_uses_shared_header_macro(self):
        template_content = SPECIFICATIONS_TEMPLATE.read_text(encoding="utf-8")

        self.assertIn(
            '{% from "includes/ui/macros.html" import page_header %}',
            template_content,
        )
        self.assertIn("{{ page_header(", template_content)

    def test_docs_menu_links_to_propose_changes(self):
        html = render("/")
        menu = html.split('aria-labelledby="docsDropdown"', 1)[1].split("</ul>", 1)[0]
        self.assertRegex(
            menu, r'href="/specifications/contribute"[^>]*>\s*<span[^>]*>(?:<i[^>]*></i>)?\s*Propose changes'
        )

    def test_overview_has_a_call_to_action(self):
        html = render("/specifications")
        article = html.split("<article", 1)[1]
        self.assertIn('href="/specifications/contribute"', article)


if __name__ == "__main__":
    unittest.main()
