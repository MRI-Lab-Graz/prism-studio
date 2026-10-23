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

    def test_navbar_has_a_propose_changes_entry(self):
        html = render("/")
        menu = html.split('aria-labelledby="docsDropdown"', 1)[1].split("</ul>", 1)[0]
        self.assertNotIn("Propose changes", menu)
        self.assertRegex(
            html,
            r'<li class="nav-item">\s*<a class="nav-link[^"]*"[^>]*href="/specifications/contribute"[^>]*>\s*<i[^>]*></i>Propose changes',
        )

    def test_propose_entry_is_active_only_on_its_page(self):
        link = r'<a class="nav-link( active)?"[^>]*href="/specifications/contribute"([^>]*)>'
        docs = r'<a class="nav-link dropdown-toggle( active)?" href="#" id="docsDropdown"'
        on = render("/specifications/contribute")
        m = re.search(link, on)
        self.assertTrue(m.group(1) and 'aria-current="page"' in m.group(2))
        self.assertIsNone(re.search(docs, on).group(1))
        off = render("/specifications/biosample")
        self.assertIsNone(re.search(link, off).group(1))
        self.assertTrue(re.search(docs, off).group(1))

    def test_overview_has_a_call_to_action(self):
        html = render("/specifications")
        article = html.split("<article", 1)[1]
        self.assertIn('href="/specifications/contribute"', article)


if __name__ == "__main__":
    unittest.main()
