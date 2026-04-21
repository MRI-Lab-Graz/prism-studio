import json
import os
import sys
import tempfile
import unittest
import importlib
from pathlib import Path

from flask import Flask

current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(current_dir)
app_path = os.path.join(project_root, "app")
if app_path not in sys.path:
    sys.path.insert(0, app_path)


class TestProjectsDescriptionHandlers(unittest.TestCase):
    def setUp(self):
        self.tmp_dir = tempfile.TemporaryDirectory()
        self.project_path = Path(self.tmp_dir.name) / "demo_project"
        self.project_path.mkdir(parents=True, exist_ok=True)

        self.app = Flask(__name__)

        citation_helpers = importlib.import_module(
            "src.web.blueprints.projects_citation_helpers"
        )
        description_handlers = importlib.import_module(
            "src.web.blueprints.projects_description_handlers"
        )
        project_manager_module = importlib.import_module("src.project_manager")

        self.read_citation_cff_fields = citation_helpers._read_citation_cff_fields
        self.merge_citation_fields = citation_helpers._merge_citation_fields
        self.handle_get_dataset_description = (
            description_handlers.handle_get_dataset_description
        )
        self.handle_save_dataset_description = (
            description_handlers.handle_save_dataset_description
        )
        self.project_manager = project_manager_module.ProjectManager()

    def tearDown(self):
        self.tmp_dir.cleanup()

    def _make_project(self, name: str) -> Path:
        project_path = Path(self.tmp_dir.name) / name
        project_path.mkdir(parents=True, exist_ok=True)
        return project_path

    def test_read_citation_cff_fields_preserves_rich_author_metadata(self):
        citation_path = self.project_path / "CITATION.cff"
        citation_path.write_text(
            "\n".join(
                [
                    "cff-version: 1.2.0",
                    'title: "Demo dataset"',
                    "message: >-",
                    "  If you use this dataset, please cite both the article from",
                    "  preferred-citation and the dataset itself.",
                    "type: dataset",
                    "authors:",
                    '  - family-names: "Fink"',
                    '    given-names: "Andreas"',
                    '    orcid: "https://orcid.org/0000-0001-7316-3140"',
                    '    affiliation: "University"',
                    '  - family-names: "Kannonier"',
                    '    given-names: "Anna"',
                    "",
                ]
            ),
            encoding="utf-8",
        )

        fields = self.read_citation_cff_fields(citation_path)

        self.assertIn("Authors", fields)
        self.assertEqual(fields["Authors"][0]["family-names"], "Fink")
        self.assertEqual(fields["Authors"][0]["given-names"], "Andreas")
        self.assertEqual(
            fields["Authors"][0]["orcid"],
            "https://orcid.org/0000-0001-7316-3140",
        )
        self.assertEqual(fields["Authors"][1]["family-names"], "Kannonier")

    def test_read_citation_cff_fields_parses_folded_message_block(self):
        citation_path = self.project_path / "CITATION.cff"
        citation_path.write_text(
            "\n".join(
                [
                    "cff-version: 1.2.0",
                    'title: "Demo dataset"',
                    "message: >-",
                    "  If you use this dataset, please cite both the article from",
                    "  preferred-citation and the dataset itself.",
                    "type: dataset",
                    "authors:",
                    '  - family-names: "Fink"',
                    '    given-names: "Andreas"',
                    "",
                ]
            ),
            encoding="utf-8",
        )

        fields = self.read_citation_cff_fields(citation_path)

        self.assertNotIn("HowToAcknowledge", fields)

    def test_get_dataset_description_prefers_citation_rich_authors(self):
        dataset_description = {
            "Name": "Demo",
            "BIDSVersion": "1.10.1",
            "DatasetType": "raw",
            "Authors": ["Andreas Fink", "Anna Kannonier"],
        }
        (self.project_path / "dataset_description.json").write_text(
            json.dumps(dataset_description), encoding="utf-8"
        )

        (self.project_path / "CITATION.cff").write_text(
            "\n".join(
                [
                    "cff-version: 1.2.0",
                    'title: "Demo dataset"',
                    'message: "If you use this dataset, please cite it."',
                    "type: dataset",
                    "authors:",
                    '  - family-names: "Fink"',
                    '    given-names: "Andreas"',
                    '    orcid: "https://orcid.org/0000-0001-7316-3140"',
                    '  - family-names: "Kannonier"',
                    '    given-names: "Anna"',
                    "",
                ]
            ),
            encoding="utf-8",
        )

        def get_current_project():
            return {"path": str(self.project_path), "name": "demo_project"}

        def get_bids_file_path(project_path: Path, filename: str) -> Path:
            return project_path / filename

        with self.app.test_request_context("/api/projects/description", method="GET"):
            response = self.handle_get_dataset_description(
                get_current_project=get_current_project,
                get_bids_file_path=get_bids_file_path,
                read_citation_cff_fields=self.read_citation_cff_fields,
                merge_citation_fields=self.merge_citation_fields,
                project_manager=self.project_manager,
            )

        status_code = response[1] if isinstance(response, tuple) else 200
        resp_obj = response[0] if isinstance(response, tuple) else response

        self.assertEqual(status_code, 200)
        payload = resp_obj.get_json()
        self.assertTrue(payload.get("success"))
        returned_authors = payload.get("description", {}).get("Authors") or []
        self.assertTrue(isinstance(returned_authors[0], dict))
        self.assertEqual(
            returned_authors[0].get("orcid"),
            "https://orcid.org/0000-0001-7316-3140",
        )
        issue_messages = [
            issue.get("message", "") for issue in (payload.get("issues") or [])
        ]
        self.assertFalse(
            any(
                "Authors ->" in message
                and "not valid under any of the given schemas" in message
                for message in issue_messages
            )
        )

    def test_get_dataset_description_enriches_author_roles_from_contributors(self):
        dataset_description = {
            "Name": "Demo",
            "BIDSVersion": "1.10.1",
            "DatasetType": "raw",
            "Authors": ["Andreas Fink"],
        }
        (self.project_path / "dataset_description.json").write_text(
            json.dumps(dataset_description), encoding="utf-8"
        )

        (self.project_path / "CITATION.cff").write_text(
            "\n".join(
                [
                    "cff-version: 1.2.0",
                    'title: "Demo dataset"',
                    'message: "If you use this dataset, please cite it."',
                    "type: dataset",
                    "authors:",
                    '  - family-names: "Fink"',
                    '    given-names: "Andreas"',
                    "",
                ]
            ),
            encoding="utf-8",
        )

        (self.project_path / "project.json").write_text(
            json.dumps(
                {
                    "name": "demo_project",
                    "governance": {
                        "contacts": [
                            {
                                "name": "Fink, Andreas",
                                "roles": ["Methodology", "Data curation"],
                                "orcid": "",
                                "email": "",
                                "corresponding": False,
                            }
                        ]
                    },
                }
            ),
            encoding="utf-8",
        )

        def get_current_project():
            return {"path": str(self.project_path), "name": "demo_project"}

        def get_bids_file_path(project_path: Path, filename: str) -> Path:
            return project_path / filename

        with self.app.test_request_context("/api/projects/description", method="GET"):
            response = self.handle_get_dataset_description(
                get_current_project=get_current_project,
                get_bids_file_path=get_bids_file_path,
                read_citation_cff_fields=self.read_citation_cff_fields,
                merge_citation_fields=self.merge_citation_fields,
                project_manager=self.project_manager,
            )

        status_code = response[1] if isinstance(response, tuple) else 200
        resp_obj = response[0] if isinstance(response, tuple) else response

        self.assertEqual(status_code, 200)
        payload = resp_obj.get_json()
        returned_authors = payload.get("description", {}).get("Authors") or []
        self.assertEqual(
            returned_authors[0].get("roles"),
            ["Methodology", "Data curation"],
        )
        issue_messages = [
            issue.get("message", "") for issue in (payload.get("issues") or [])
        ]
        self.assertFalse(
            any(
                "Authors ->" in message
                and "not valid under any of the given schemas" in message
                for message in issue_messages
            )
        )

    def test_save_dataset_description_syncs_contributors_orcid(self):
        (self.project_path / "dataset_description.json").write_text(
            json.dumps({"Name": "Demo", "BIDSVersion": "1.10.1", "DatasetType": "raw"}),
            encoding="utf-8",
        )

        def get_current_project():
            return {"path": str(self.project_path), "name": "demo_project"}

        def get_bids_file_path(project_path: Path, filename: str) -> Path:
            return project_path / filename

        def set_current_project(path: str, name: str | None = None):
            _ = (path, name)

        def save_last_project(path: str, name: str):
            _ = (path, name)

        request_payload = {
            "description": {
                "Name": "Demo",
                "BIDSVersion": "1.10.1",
                "DatasetType": "raw",
                "Authors": ["Andreas Fink", "Anna Kannonier"],
            },
            "citation_fields": {
                "Authors": [
                    {
                        "family-names": "Fink",
                        "given-names": "Andreas",
                        "orcid": "https://orcid.org/0000-0001-7316-3140",
                        "email": "andreas@example.org",
                        "roles": ["Methodology", "Software"],
                    },
                    {
                        "family-names": "Kannonier",
                        "given-names": "Anna",
                    },
                ]
            },
        }

        with self.app.test_request_context(
            "/api/projects/description",
            method="POST",
            json=request_payload,
        ):
            response = self.handle_save_dataset_description(
                get_current_project=get_current_project,
                get_bids_file_path=get_bids_file_path,
                read_citation_cff_fields=self.read_citation_cff_fields,
                merge_citation_fields=self.merge_citation_fields,
                project_manager=self.project_manager,
                set_current_project=set_current_project,
                save_last_project=save_last_project,
            )

        status_code = response[1] if isinstance(response, tuple) else 200
        resp_obj = response[0] if isinstance(response, tuple) else response

        self.assertEqual(status_code, 200)
        payload = resp_obj.get_json()
        self.assertTrue(payload.get("success"))

        project_json_path = self.project_path / "project.json"
        self.assertTrue(project_json_path.exists())

        project_payload = json.loads(project_json_path.read_text(encoding="utf-8"))
        contacts = (project_payload.get("governance") or {}).get("contacts") or []

        self.assertEqual(contacts[0].get("name"), "Fink, Andreas")
        self.assertEqual(
            contacts[0].get("orcid"),
            "https://orcid.org/0000-0001-7316-3140",
        )
        self.assertEqual(contacts[0].get("email"), "andreas@example.org")
        self.assertEqual(contacts[0].get("roles"), ["Methodology", "Software"])

    def test_save_dataset_description_omits_citation_owned_fields_in_json(self):
        (self.project_path / "dataset_description.json").write_text(
            json.dumps({"Name": "Demo", "BIDSVersion": "1.10.1", "DatasetType": "raw"}),
            encoding="utf-8",
        )

        def get_current_project():
            return {"path": str(self.project_path), "name": "demo_project"}

        def get_bids_file_path(project_path: Path, filename: str) -> Path:
            return project_path / filename

        def set_current_project(path: str, name: str | None = None):
            _ = (path, name)

        def save_last_project(path: str, name: str):
            _ = (path, name)

        request_payload = {
            "description": {
                "Name": "Demo",
                "BIDSVersion": "1.10.1",
                "DatasetType": "raw",
                "DatasetDOI": "10.1234/demo",
                "Authors": ["Andreas Fink"],
                "HowToAcknowledge": "Please cite this dataset.",
                "License": "CC-BY-4.0",
                "ReferencesAndLinks": ["https://example.org/paper"],
            },
            "citation_fields": {
                "Authors": [
                    {
                        "family-names": "Fink",
                        "given-names": "Andreas",
                    }
                ],
                "HowToAcknowledge": "Please cite this dataset.",
                "License": "CC-BY-4.0",
                "ReferencesAndLinks": ["https://example.org/paper"],
            },
        }

        with self.app.test_request_context(
            "/api/projects/description",
            method="POST",
            json=request_payload,
        ):
            response = self.handle_save_dataset_description(
                get_current_project=get_current_project,
                get_bids_file_path=get_bids_file_path,
                read_citation_cff_fields=self.read_citation_cff_fields,
                merge_citation_fields=self.merge_citation_fields,
                project_manager=self.project_manager,
                set_current_project=set_current_project,
                save_last_project=save_last_project,
            )

        status_code = response[1] if isinstance(response, tuple) else 200
        resp_obj = response[0] if isinstance(response, tuple) else response

        self.assertEqual(status_code, 200)
        payload = resp_obj.get_json()
        self.assertTrue(payload.get("success"))

        saved_description = json.loads(
            (self.project_path / "dataset_description.json").read_text(encoding="utf-8")
        )
        self.assertEqual(saved_description.get("Name"), "Demo")
        self.assertEqual(saved_description.get("DatasetDOI"), "10.1234/demo")
        self.assertNotIn("Authors", saved_description)
        self.assertNotIn("HowToAcknowledge", saved_description)
        self.assertNotIn("License", saved_description)
        self.assertNotIn("ReferencesAndLinks", saved_description)

        citation_text = (self.project_path / "CITATION.cff").read_text(encoding="utf-8")
        self.assertIn('family-names: "Fink"', citation_text)
        self.assertIn('given-names: "Andreas"', citation_text)
        self.assertIn('license: "CC-BY-4.0"', citation_text)
        self.assertIn('url: "https://example.org/paper"', citation_text)

    def test_save_dataset_description_regenerates_citation_and_deletes_legacy_contributors(self):
        (self.project_path / "dataset_description.json").write_text(
            json.dumps(
                {
                    "Name": "Demo",
                    "BIDSVersion": "1.10.1",
                    "DatasetType": "raw",
                }
            ),
            encoding="utf-8",
        )
        (self.project_path / "contributors.json").write_text(
            json.dumps(
                {
                    "contributors": [
                        {
                            "name": "Legacy, Person",
                            "roles": ["Conceptualization"],
                        }
                    ]
                }
            ),
            encoding="utf-8",
        )

        def get_current_project():
            return {"path": str(self.project_path), "name": "demo_project"}

        def get_bids_file_path(project_path: Path, filename: str) -> Path:
            return project_path / filename

        def set_current_project(path: str, name: str | None = None):
            _ = (path, name)

        def save_last_project(path: str, name: str):
            _ = (path, name)

        request_payload = {
            "description": {
                "Name": "Demo Updated",
                "BIDSVersion": "1.10.1",
                "DatasetType": "raw",
                "DatasetDOI": "10.1234/demo-updated",
                "Authors": ["Ada Lovelace"],
            },
            "citation_fields": {
                "Authors": [
                    {
                        "family-names": "Lovelace",
                        "given-names": "Ada",
                        "email": "ada@example.org",
                    }
                ],
                "HowToAcknowledge": "Please cite Demo Updated.",
            },
        }

        with self.app.test_request_context(
            "/api/projects/description",
            method="POST",
            json=request_payload,
        ):
            response = self.handle_save_dataset_description(
                get_current_project=get_current_project,
                get_bids_file_path=get_bids_file_path,
                read_citation_cff_fields=self.read_citation_cff_fields,
                merge_citation_fields=self.merge_citation_fields,
                project_manager=self.project_manager,
                set_current_project=set_current_project,
                save_last_project=save_last_project,
            )

        status_code = response[1] if isinstance(response, tuple) else 200
        resp_obj = response[0] if isinstance(response, tuple) else response

        self.assertEqual(status_code, 200)
        payload = resp_obj.get_json()
        self.assertTrue(payload.get("success"))

        citation_path = self.project_path / "CITATION.cff"
        self.assertTrue(citation_path.exists())
        citation_text = citation_path.read_text(encoding="utf-8")
        self.assertIn('title: "Demo Updated"', citation_text)
        self.assertIn('doi: "10.1234/demo-updated"', citation_text)
        self.assertIn('family-names: "Lovelace"', citation_text)
        self.assertIn('given-names: "Ada"', citation_text)
        self.assertIn('email: "ada@example.org"', citation_text)

        self.assertFalse((self.project_path / "contributors.json").exists())

    def test_save_dataset_description_deduplicates_citation_authors(self):
        (self.project_path / "dataset_description.json").write_text(
            json.dumps(
                {
                    "Name": "Demo",
                    "BIDSVersion": "1.10.1",
                    "DatasetType": "raw",
                }
            ),
            encoding="utf-8",
        )

        def get_current_project():
            return {"path": str(self.project_path), "name": "demo_project"}

        def get_bids_file_path(project_path: Path, filename: str) -> Path:
            return project_path / filename

        def set_current_project(path: str, name: str | None = None):
            _ = (path, name)

        def save_last_project(path: str, name: str):
            _ = (path, name)

        request_payload = {
            "description": {
                "Name": "Demo",
                "BIDSVersion": "1.10.1",
                "DatasetType": "raw",
                "Authors": ["Ada Lovelace"],
            },
            "citation_fields": {
                "Authors": [
                    {
                        "family-names": "Lovelace",
                        "given-names": "Ada",
                    },
                    {
                        "family-names": "Lovelace",
                        "given-names": "Ada",
                        "email": "ada@example.org",
                    },
                ]
            },
        }

        with self.app.test_request_context(
            "/api/projects/description",
            method="POST",
            json=request_payload,
        ):
            response = self.handle_save_dataset_description(
                get_current_project=get_current_project,
                get_bids_file_path=get_bids_file_path,
                read_citation_cff_fields=self.read_citation_cff_fields,
                merge_citation_fields=self.merge_citation_fields,
                project_manager=self.project_manager,
                set_current_project=set_current_project,
                save_last_project=save_last_project,
            )

        status_code = response[1] if isinstance(response, tuple) else 200
        resp_obj = response[0] if isinstance(response, tuple) else response

        self.assertEqual(status_code, 200)
        payload = resp_obj.get_json()
        self.assertTrue(payload.get("success"))

        citation_text = (self.project_path / "CITATION.cff").read_text(encoding="utf-8")
        self.assertEqual(citation_text.count('family-names: "Lovelace"'), 1)
        self.assertEqual(citation_text.count('given-names: "Ada"'), 1)
        self.assertIn('email: "ada@example.org"', citation_text)

    def test_save_dataset_description_preserves_corresponding_author(self):
        (self.project_path / "dataset_description.json").write_text(
            json.dumps({"Name": "Demo", "BIDSVersion": "1.10.1", "DatasetType": "raw"}),
            encoding="utf-8",
        )

        def get_current_project():
            return {"path": str(self.project_path), "name": "demo_project"}

        def get_bids_file_path(project_path: Path, filename: str) -> Path:
            return project_path / filename

        def set_current_project(path: str, name: str | None = None):
            _ = (path, name)

        def save_last_project(path: str, name: str):
            _ = (path, name)

        request_payload = {
            "description": {
                "Name": "Demo",
                "BIDSVersion": "1.10.1",
                "DatasetType": "raw",
                "Authors": ["Andreas Fink"],
            },
            "citation_fields": {
                "Authors": [
                    {
                        "family-names": "Fink",
                        "given-names": "Andreas",
                        "email": "andreas@example.org",
                        "corresponding": True,
                    },
                ]
            },
        }

        with self.app.test_request_context(
            "/api/projects/description",
            method="POST",
            json=request_payload,
        ):
            response = self.handle_save_dataset_description(
                get_current_project=get_current_project,
                get_bids_file_path=get_bids_file_path,
                read_citation_cff_fields=self.read_citation_cff_fields,
                merge_citation_fields=self.merge_citation_fields,
                project_manager=self.project_manager,
                set_current_project=set_current_project,
                save_last_project=save_last_project,
            )

        status_code = response[1] if isinstance(response, tuple) else 200
        resp_obj = response[0] if isinstance(response, tuple) else response

        self.assertEqual(status_code, 200)
        payload = resp_obj.get_json()
        self.assertTrue(payload.get("success"))

        project_json_path = self.project_path / "project.json"
        self.assertTrue(project_json_path.exists())

        project_payload = json.loads(project_json_path.read_text(encoding="utf-8"))
        contacts = (project_payload.get("governance") or {}).get("contacts") or []

        self.assertEqual(contacts[0].get("name"), "Fink, Andreas")
        self.assertEqual(contacts[0].get("email"), "andreas@example.org")
        self.assertTrue(contacts[0].get("corresponding"))

    def test_get_dataset_description_can_target_explicit_project_path(self):
        other_project = self._make_project("other_project")
        (other_project / "dataset_description.json").write_text(
            json.dumps(
                {"Name": "Other", "BIDSVersion": "1.10.1", "DatasetType": "raw"}
            ),
            encoding="utf-8",
        )

        def get_current_project():
            return {"path": str(self.project_path), "name": "demo_project"}

        def get_bids_file_path(project_path: Path, filename: str) -> Path:
            return project_path / filename

        with self.app.test_request_context(
            "/api/projects/description",
            method="GET",
            query_string={"project_path": str(other_project)},
        ):
            response = self.handle_get_dataset_description(
                get_current_project=get_current_project,
                get_bids_file_path=get_bids_file_path,
                read_citation_cff_fields=self.read_citation_cff_fields,
                merge_citation_fields=self.merge_citation_fields,
                project_manager=self.project_manager,
            )

        status_code = response[1] if isinstance(response, tuple) else 200
        resp_obj = response[0] if isinstance(response, tuple) else response
        payload = resp_obj.get_json()

        self.assertEqual(status_code, 200)
        self.assertTrue(payload.get("success"))
        self.assertEqual(payload.get("description", {}).get("Name"), "Other")

    def test_save_dataset_description_can_target_explicit_project_path(self):
        other_project = self._make_project("other_project")
        (other_project / "dataset_description.json").write_text(
            json.dumps(
                {"Name": "Other", "BIDSVersion": "1.10.1", "DatasetType": "raw"}
            ),
            encoding="utf-8",
        )

        def get_current_project():
            return {"path": str(self.project_path), "name": "demo_project"}

        def get_bids_file_path(project_path: Path, filename: str) -> Path:
            return project_path / filename

        def set_current_project(path: str, name: str | None = None):
            _ = (path, name)

        def save_last_project(path: str, name: str):
            _ = (path, name)

        with self.app.test_request_context(
            "/api/projects/description",
            method="POST",
            json={
                "project_path": str(other_project),
                "description": {
                    "Name": "Other Updated",
                    "BIDSVersion": "1.10.1",
                    "DatasetType": "raw",
                    "Authors": ["Ada Lovelace"],
                },
                "citation_fields": {"Authors": ["Ada Lovelace"]},
            },
        ):
            response = self.handle_save_dataset_description(
                get_current_project=get_current_project,
                get_bids_file_path=get_bids_file_path,
                read_citation_cff_fields=self.read_citation_cff_fields,
                merge_citation_fields=self.merge_citation_fields,
                project_manager=self.project_manager,
                set_current_project=set_current_project,
                save_last_project=save_last_project,
            )

        status_code = response[1] if isinstance(response, tuple) else 200
        resp_obj = response[0] if isinstance(response, tuple) else response
        payload = resp_obj.get_json()

        self.assertEqual(status_code, 200)
        self.assertTrue(payload.get("success"))
        saved = json.loads(
            (other_project / "dataset_description.json").read_text(encoding="utf-8")
        )
        self.assertEqual(saved["Name"], "Other Updated")


if __name__ == "__main__":
    unittest.main()
