import json
import os
import sys
import tempfile
import unittest
from pathlib import Path


current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(current_dir)
app_path = os.path.join(project_root, "app")

if app_path not in sys.path:
    sys.path.insert(0, app_path)

from src.project_manager import ProjectManager


class TestProjectManager(unittest.TestCase):
    def test_create_project_sets_default_author(self):
        manager = ProjectManager()

        with tempfile.TemporaryDirectory() as tmp:
            project_path = Path(tmp) / "demo_project"
            result = manager.create_project(str(project_path), {"name": "demo_project"})

            self.assertTrue(result.get("success"), result)

            desc_path = project_path / "dataset_description.json"
            self.assertTrue(desc_path.exists())

            payload = json.loads(desc_path.read_text(encoding="utf-8"))
            self.assertEqual(payload.get("Authors"), ["prism-studio"])

    def test_create_citation_cff_includes_demo_author_fields_when_empty(self):
        manager = ProjectManager()

        content = manager._create_citation_cff("demo_project", {"name": "demo_project"})

        self.assertIn("given-names", content)
        self.assertIn("family-names", content)
        self.assertIn("website", content)
        self.assertIn("orcid", content)
        self.assertIn("affiliation", content)
        self.assertIn("email", content)

    def test_create_citation_cff_supports_rich_author_dict(self):
        manager = ProjectManager()

        rich_author = {
            "given-names": "Alex",
            "family-names": "Example",
            "website": "https://example.org",
            "orcid": "https://orcid.org/0000-0000-0000-0001",
            "affiliation": "Example Institute",
            "email": "alex@example.org",
        }

        content = manager._create_citation_cff(
            "demo_project",
            {"name": "demo_project", "authors": [rich_author]},
        )

        self.assertIn('family-names: "Example"', content)
        self.assertIn('given-names: "Alex"', content)
        self.assertIn('website: "https://example.org"', content)
        self.assertIn('orcid: "https://orcid.org/0000-0000-0000-0001"', content)
        self.assertIn('affiliation: "Example Institute"', content)
        self.assertIn('email: "alex@example.org"', content)


if __name__ == "__main__":
    unittest.main()
