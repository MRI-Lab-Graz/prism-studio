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
            self.assertNotIn("Authors", payload)

            citation_content = (project_path / "CITATION.cff").read_text(
                encoding="utf-8"
            )
            self.assertIn('family-names: "prism-studio"', citation_content)
            self.assertIn('given-names: "dataset"', citation_content)

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

    def test_create_project_bidsignore_covers_prism_only_paths(self):
        manager = ProjectManager()

        with tempfile.TemporaryDirectory() as tmp:
            project_path = Path(tmp) / "demo_project"
            result = manager.create_project(str(project_path), {"name": "demo_project"})

            self.assertTrue(result.get("success"), result)

            bidsignore_path = project_path / ".bidsignore"
            self.assertTrue(bidsignore_path.exists())

            content = bidsignore_path.read_text(encoding="utf-8")
            self.assertIn("code/", content)
            self.assertIn("code/library/", content)
            self.assertIn("code/recipes/", content)
            self.assertIn("derivatives/", content)
            self.assertIn("recipes/", content)
            self.assertNotIn("CITATION.cff", content)

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

    def test_create_citation_cff_deduplicates_duplicate_author_entries(self):
        manager = ProjectManager()

        content = manager._create_citation_cff(
            "demo_project",
            {
                "name": "demo_project",
                "authors": [
                    "Ada Lovelace",
                    {
                        "family-names": "Lovelace",
                        "given-names": "Ada",
                        "email": "ada@example.org",
                    },
                    {
                        "family-names": "Lovelace",
                        "given-names": "Ada",
                    },
                ],
            },
        )

        self.assertEqual(content.count('family-names: "Lovelace"'), 1)
        self.assertEqual(content.count('given-names: "Ada"'), 1)
        self.assertIn('email: "ada@example.org"', content)

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
        self.assertIn("message: >-", content)
        self.assertIn(
            "If you use this dataset, please cite both the article from preferred-citation and the dataset itself.",
            content,
        )
        self.assertIn('license: "CC-BY-4.0"', content)
        self.assertIn('license-url: "https://example.org/license"', content)
        self.assertIn('url: "https://example.org/dataset"', content)
        self.assertIn('repository-code: "https://github.com/example/repo"', content)
        self.assertIn("keywords:", content)
        self.assertIn('  - "tactile"', content)
        self.assertIn('abstract: "Dataset abstract"', content)
        self.assertIn("references:", content)
        self.assertIn('type: "generic"', content)
        self.assertIn("authors:", content)
        self.assertIn('name: "Jane Doe"', content)
        self.assertIn('url: "https://osf.io/zh5rg/"', content)
        self.assertIn('doi: "10.17605/OSF.IO/ZH5RG"', content)
        self.assertIn('title: "Heed et al. manuscript"', content)

    def test_create_citation_cff_splits_semicolon_delimited_keywords(self):
        manager = ProjectManager()

        content = manager._create_citation_cff(
            "demo_project",
            {
                "name": "demo_project",
                "keywords": [
                    "Hippocampus",
                    "email-lists; social-media",
                    "Running, longitudinal",
                ],
            },
        )

        self.assertIn('  - "Hippocampus"', content)
        self.assertIn('  - "email-lists"', content)
        self.assertIn('  - "social-media"', content)
        self.assertIn('  - "Running"', content)
        self.assertIn('  - "longitudinal"', content)
        self.assertNotIn('  - "email-lists; social-media"', content)

    def test_create_citation_cff_uses_default_message_for_url_acknowledgement(self):
        manager = ProjectManager()

        content = manager._create_citation_cff(
            "demo_project",
            {
                "name": "demo_project",
                "how_to_acknowledge": "https://doi.org/10.1007/s00429-024-02885-2",
            },
        )

        self.assertIn("message: >-", content)
        self.assertIn(
            "If you use this dataset, please cite both the article from preferred-citation and the dataset itself.",
            content,
        )
        self.assertNotIn('message: "https://doi.org/10.1007/s00429-024-02885-2"', content)

    def test_build_citation_config_uses_project_json_fallbacks(self):
        manager = ProjectManager()

        with tempfile.TemporaryDirectory() as tmp:
            project_path = Path(tmp)
            project_payload = {
                "name": "workshop",
                "Basics": {
                    "DatasetName": "Workshop Test Dataset",
                    "Keywords": ["psychology", "survey"],
                },
                "Overview": {
                    "Main": "Test study overview.",
                },
                "StudyDesign": {
                    "Type": "longitudinal",
                    "TypeDescription": "Randomized intervention over 4 weeks.",
                },
                "Recruitment": {
                    "Method": "snowball",
                },
                "DataCollection": {
                    "Description": "Daily app-based questionnaires.",
                },
                "Procedure": {
                    "Overview": "Baseline, intervention, and post assessment.",
                },
                "governance": {
                    "contacts": [
                        {
                            "given": "prism-studio",
                            "family": "ff",
                            "email": "team@example.org",
                        }
                    ],
                    "preregistration": "https://osf.io/abcd1/",
                    "data_access": "https://example.org/access",
                },
                "References": {
                    "study": [
                        {
                            "title": "Primary study reference",
                            "doi": "10.1000/xyz123",
                        }
                    ]
                },
                "TaskDefinitions": {
                    "wellbeing": {
                        "modality": "survey",
                    }
                },
            }
            (project_path / "project.json").write_text(
                json.dumps(project_payload), encoding="utf-8"
            )

            config = manager._build_citation_config(
                "workshop", {"Name": "", "Authors": []}, project_path
            )
            content = manager._create_citation_cff("workshop", config)

        self.assertEqual(config.get("name"), "Workshop Test Dataset")
        self.assertIn('family-names: "ff"', content)
        self.assertIn('given-names: "prism-studio"', content)
        self.assertIn('email: "team@example.org"', content)
        self.assertIn(
            'abstract: "Test study overview. Randomized intervention over 4 weeks. Daily app-based questionnaires. Baseline, intervention, and post assessment."',
            content,
        )
        self.assertIn('  - "psychology"', content)
        self.assertIn('  - "longitudinal"', content)
        self.assertIn('  - "wellbeing"', content)
        self.assertIn('  - "survey"', content)
        self.assertNotIn('  - "snowball"', content)
        self.assertIn('doi: "10.1000/xyz123"', content)
        self.assertEqual(config.get("url"), "")

    def test_build_citation_config_separates_dataset_url_and_code_repository(self):
        manager = ProjectManager()

        with tempfile.TemporaryDirectory() as tmp:
            project_path = Path(tmp)
            project_payload = {
                "name": "demo",
                "References": {
                    "resources": [
                        {
                            "title": "Archive",
                            "url": "https://osf.io/abcd1/",
                        }
                    ]
                },
                "governance": {
                    "funding": [{"agency": "Grant Agency", "grant_number": "1234"}],
                    "ethics_approvals": [{"committee": "IRB", "approval_number": "1"}],
                },
            }
            (project_path / "project.json").write_text(
                json.dumps(project_payload), encoding="utf-8"
            )

            description = {
                "Name": "demo",
                "Authors": ["Jane Doe"],
                "DatasetLinks": {"landing": "https://example.org/dataset"},
                "ReferencesAndLinks": [
                    "[object Object]",
                    {
                        "title": "Code",
                        "url": "https://github.com/example/repo",
                    },
                ],
            }

            config = manager._build_citation_config("demo", description, project_path)
            reference_titles = [
                str(item.get("title") or "") for item in config.get("references", [])
            ]

        self.assertEqual(config.get("url"), "https://example.org/dataset")
        self.assertEqual(
            config.get("repository_code"),
            "https://github.com/example/repo",
        )
        self.assertEqual(config.get("repository"), "https://osf.io/abcd1/")
        self.assertFalse(
            any(title.lower() == "[object object]" for title in reference_titles)
        )
        self.assertFalse(any("Grant Agency" in title for title in reference_titles))

    def test_build_citation_config_avoids_url_repository_code_duplication(self):
        manager = ProjectManager()

        config = manager._build_citation_config(
            "demo",
            {
                "Name": "demo",
                "Authors": ["Jane Doe"],
                "ReferencesAndLinks": ["https://github.com/example/repo"],
            },
        )

        self.assertEqual(config.get("repository_code"), "https://github.com/example/repo")
        self.assertEqual(config.get("url"), "")

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

    def test_validate_structure_does_not_require_participants_for_empty_project(self):
        manager = ProjectManager()

        with tempfile.TemporaryDirectory() as tmp:
            project_path = Path(tmp) / "demo_project"
            created = manager.create_project(
                str(project_path), {"name": "demo_project"}
            )
            self.assertTrue(created.get("success"), created)

            result = manager.validate_structure(str(project_path))

        issue_codes = {issue.get("code") for issue in result.get("issues", [])}
        self.assertNotIn("PRISM004", issue_codes)
        self.assertTrue(result.get("stats", {}).get("has_participants_tsv"))
        self.assertFalse(result.get("stats", {}).get("participants_tsv_required"))

    def test_validate_structure_requires_participants_when_subjects_exist(self):
        manager = ProjectManager()

        with tempfile.TemporaryDirectory() as tmp:
            project_path = Path(tmp) / "demo_project"
            created = manager.create_project(
                str(project_path), {"name": "demo_project"}
            )
            self.assertTrue(created.get("success"), created)

            (project_path / "sub-001").mkdir(parents=True, exist_ok=True)
            result = manager.validate_structure(str(project_path))

        issue_codes = {issue.get("code") for issue in result.get("issues", [])}
        self.assertIn("PRISM004", issue_codes)
        self.assertFalse(result.get("stats", {}).get("has_participants_tsv"))
        self.assertTrue(result.get("stats", {}).get("participants_tsv_required"))

    def test_validate_structure_counts_bids_modalities_in_stats(self):
        manager = ProjectManager()

        with tempfile.TemporaryDirectory() as tmp:
            project_path = Path(tmp) / "demo_project"
            created = manager.create_project(
                str(project_path), {"name": "demo_project"}
            )
            self.assertTrue(created.get("success"), created)

            (project_path / "sub-001" / "func").mkdir(parents=True, exist_ok=True)
            result = manager.validate_structure(str(project_path))

        modalities = result.get("stats", {}).get("modalities", [])
        self.assertIn("func", modalities)

    def test_validate_structure_does_not_flag_missing_sidecar_for_beh(self):
        manager = ProjectManager()

        with tempfile.TemporaryDirectory() as tmp:
            project_path = Path(tmp) / "demo_project"
            created = manager.create_project(
                str(project_path), {"name": "demo_project"}
            )
            self.assertTrue(created.get("success"), created)

            beh_dir = project_path / "sub-001" / "ses-01" / "beh"
            beh_dir.mkdir(parents=True, exist_ok=True)
            (beh_dir / "sub-001_ses-01_task-demo_beh.tsv").write_text(
                "onset\tduration\tresponse_time\n0\t1\t0.5\n",
                encoding="utf-8",
            )

            result = manager.validate_structure(str(project_path))

        issue_codes = {issue.get("code") for issue in result.get("issues", [])}
        self.assertNotIn("PRISM201", issue_codes)

    def test_validate_structure_keeps_missing_sidecar_warning_for_survey(self):
        manager = ProjectManager()

        with tempfile.TemporaryDirectory() as tmp:
            project_path = Path(tmp) / "demo_project"
            created = manager.create_project(
                str(project_path), {"name": "demo_project"}
            )
            self.assertTrue(created.get("success"), created)

            survey_dir = project_path / "sub-001" / "ses-01" / "survey"
            survey_dir.mkdir(parents=True, exist_ok=True)
            (survey_dir / "sub-001_ses-01_task-demo_survey.tsv").write_text(
                "item1\n1\n",
                encoding="utf-8",
            )

            result = manager.validate_structure(str(project_path))

        issue_codes = {issue.get("code") for issue in result.get("issues", [])}
        self.assertIn("PRISM201", issue_codes)


if __name__ == "__main__":
    unittest.main()
