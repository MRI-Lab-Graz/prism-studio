import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SPECIFICATIONS_TEMPLATE = REPO_ROOT / "app" / "templates" / "specifications.html"


class TestSpecificationsWorkflowWiring(unittest.TestCase):
    def test_specifications_uses_shared_header_macro(self):
        template_content = SPECIFICATIONS_TEMPLATE.read_text(encoding="utf-8")

        self.assertIn(
            '{% from "includes/ui/macros.html" import page_header %}',
            template_content,
        )
        self.assertIn("{{ page_header(", template_content)


if __name__ == "__main__":
    unittest.main()
