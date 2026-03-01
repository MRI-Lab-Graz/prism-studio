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

    def test_create_project_normalizes_invalid_dataset_type(self):
        manager = ProjectManager()

        with tempfile.TemporaryDirectory() as tmp:
            project_path = Path(tmp) / "demo_project"
            result = manager.create_project(
                str(project_path),
                {"name": "demo_project", "dataset_type": "study"},
            )

            self.assertTrue(result.get("success"), result)

            desc_path = project_path / "dataset_description.json"
            payload = json.loads(desc_path.read_text(encoding="utf-8"))
            self.assertEqual(payload.get("DatasetType"), "raw")

    def test_create_citation_cff_includes_demo_author_fields_when_empty(self):
        manager = ProjectManager()

        content = manager._create_citation_cff("demo_project", {"name": "demo_project"})

        self.assertIn("given-names", content)
        self.assertIn("family-names", content)
        self.assertIn("type: dataset", content)

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

    def test_create_citation_cff_includes_extended_dataset_fields(self):
        manager = ProjectManager()

        content = manager._create_citation_cff(
            "demo_project",
            {
                "name": "Limb assignment task B006b",
                "authors": ["Jane Doe"],
                "doi": "10.60817/9fzf-v802",
                "license": "CC-BY-4.0",
                "license_url": "https://example.org/license",
                "keywords": ["tactile", "remapping"],
                "abstract": "Dataset abstract",
                "url": "https://example.org/dataset",
                "repository_code": "https://github.com/example/repo",
                "references": [
                    "https://osf.io/zh5rg/",
                    "10.17605/OSF.IO/ZH5RG",
                    "Heed et al. manuscript",
                ],
            },
        )

        self.assertIn("type: dataset", content)
        self.assertIn('doi: "10.60817/9fzf-v802"', content)
        self.assertIn('license: "CC-BY-4.0"', content)
        self.assertIn('license-url: "https://example.org/license"', content)
        self.assertIn('url: "https://example.org/dataset"', content)
        self.assertIn('repository-code: "https://github.com/example/repo"', content)
        self.assertIn("keywords:", content)
        self.assertIn('  - "tactile"', content)
        self.assertIn('abstract: "Dataset abstract"', content)
        self.assertIn("references:", content)
        self.assertIn('type: "generic"', content)
        self.assertIn('authors:', content)
        self.assertIn('name: "Jane Doe"', content)
        self.assertIn('url: "https://osf.io/zh5rg/"', content)
        self.assertIn('doi: "10.17605/OSF.IO/ZH5RG"', content)
        self.assertIn('title: "Heed et al. manuscript"', content)

    def test_citation_status_reports_missing_file(self):
        manager = ProjectManager()

        with tempfile.TemporaryDirectory() as tmp:
            status = manager.get_citation_cff_status(Path(tmp))

        self.assertFalse(status.get("exists"))
        self.assertFalse(status.get("valid"))
        self.assertTrue(status.get("issues"))

    def test_citation_status_reports_valid_generated_file(self):
        manager = ProjectManager()

        with tempfile.TemporaryDirectory() as tmp:
            project_path = Path(tmp)
            citation_path = project_path / "CITATION.cff"
            citation_path.write_text(
                manager._create_citation_cff(
                    "demo_project",
                    {
                        "name": "demo_project",
                        "authors": ["Jane Doe"],
                        "references": ["https://example.org/ref"],
                    },
                ),
                encoding="utf-8",
            )

            status = manager.get_citation_cff_status(project_path)

        self.assertTrue(status.get("exists"))
        self.assertTrue(status.get("valid"))
        self.assertEqual(status.get("issues"), [])


if __name__ == "__main__":
    unittest.main()
