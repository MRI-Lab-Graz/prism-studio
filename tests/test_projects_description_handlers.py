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
        self.handle_get_metadata_status = (
            description_handlers.handle_get_metadata_status
        )
        self.handle_regenerate_citation = (
            description_handlers.handle_regenerate_citation
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

    def test_read_citation_cff_fields_parses_keywords_and_abstract(self):
        citation_path = self.project_path / "CITATION.cff"
        citation_path.write_text(
            "\n".join(
                [
                    "cff-version: 1.2.0",
                    'title: "BrainHearthlon"',
                    "message: >-",
                    "  OPTIONAL. Instructions how researchers using this dataset should acknowledge the original authors.",
                    "  This field can also be used to define a publication that should be cited in publications that use the dataset",
                    'abstract: "Intervention study abstract."',
                    "keywords:",
                    '  - "Running intervention"',
                    '  - "Heart rate variability (HRV)"',
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

        self.assertEqual(fields.get("Title"), "BrainHearthlon")
        self.assertEqual(fields.get("Description"), "Intervention study abstract.")
        self.assertEqual(
            fields.get("Keywords"),
            ["Running intervention", "Heart rate variability (HRV)"],
        )
        self.assertNotIn("HowToAcknowledge", fields)

    def test_read_citation_cff_fields_does_not_treat_contact_as_authors(self):
        citation_path = self.project_path / "CITATION.cff"
        citation_path.write_text(
            "\n".join(
                [
                    "cff-version: 1.2.0",
                    'title: "Demo dataset"',
                    'message: "If you use this dataset, please cite it."',
                    "type: dataset",
                    "authors:",
                    '  - family-names: "Koschutnig"',
                    '    given-names: "Karl"',
                    '    orcid: "https://orcid.org/0000-0001-6234-0498"',
                    '  - family-names: "Fink"',
                    '    given-names: "Andreas"',
                    "contact:",
                    '  - family-names: "Koschutnig"',
                    '    given-names: "Karl"',
                    '    email: "karl.koschutnig@uni-graz.at"',
                    "references:",
                    '  - url: "https://example.org/paper"',
                    "",
                ]
            ),
            encoding="utf-8",
        )

        fields = self.read_citation_cff_fields(citation_path)

        self.assertIn("Authors", fields)
        authors = fields["Authors"]
        self.assertEqual(len(authors), 2)

        author_names = []
        for author in authors:
            given = str(author.get("given-names") or "").strip()
            family = str(author.get("family-names") or "").strip()
            name = str(author.get("name") or "").strip()
            if given or family:
                author_names.append(f"{given} {family}".strip())
            elif name:
                author_names.append(name)

        self.assertCountEqual(author_names, ["Karl Koschutnig", "Andreas Fink"])
        self.assertTrue(all("email" not in author for author in authors))

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

    def test_get_dataset_description_uses_citation_for_placeholder_metadata(self):
        dataset_description = {
            "Name": "PRISM Survey Dataset",
            "BIDSVersion": "1.10.1",
            "DatasetType": "raw",
            "Authors": ["prism-studio"],
            "Acknowledgements": "This dataset was created using the PRISM framework.",
            "Keywords": ["psychology", "survey", "PRISM"],
            "Description": "A PRISM-compatible dataset for psychological research.",
        }
        (self.project_path / "dataset_description.json").write_text(
            json.dumps(dataset_description), encoding="utf-8"
        )

        (self.project_path / "CITATION.cff").write_text(
            "\n".join(
                [
                    "cff-version: 1.2.0",
                    'title: "BrainHearthlon"',
                    'message: "Please cite BrainHearthlon et al. (2026)."',
                    'abstract: "Study abstract from citation."',
                    "keywords:",
                    '  - "Running intervention"',
                    '  - "Depressive symptoms"',
                    "type: dataset",
                    "authors:",
                    '  - family-names: "Koschutnig"',
                    '    given-names: "Karl"',
                    '  - family-names: "Fink"',
                    '    given-names: "Andreas"',
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
        returned = payload.get("description", {})

        self.assertEqual(returned.get("Name"), "BrainHearthlon")
        self.assertEqual(returned.get("Acknowledgements"), "Please cite BrainHearthlon et al. (2026).")
        self.assertEqual(
            returned.get("Keywords"),
            ["Running intervention", "Depressive symptoms"],
        )
        self.assertEqual(returned.get("Description"), "Study abstract from citation.")

        returned_authors = returned.get("Authors") or []
        self.assertTrue(isinstance(returned_authors[0], dict))
        self.assertEqual(returned_authors[0].get("family-names"), "Koschutnig")

    def test_get_dataset_description_keeps_dataset_authors_when_citation_authors_mismatch(self):
        dataset_description = {
            "Name": "Demo",
            "BIDSVersion": "1.10.1",
            "DatasetType": "raw",
            "Authors": ["Andreas Fink"],
        }
        (self.project_path / "dataset_description.json").write_text(
            json.dumps(dataset_description), encoding="utf-8"
        )

        # Simulate malformed/misaligned citation author content.
        (self.project_path / "CITATION.cff").write_text(
            "\n".join(
                [
                    "cff-version: 1.2.0",
                    'title: "Demo dataset"',
                    'message: "If you use this dataset, please cite it."',
                    "type: dataset",
                    "authors:",
                    '  - family-names: "dataset"',
                    '    given-names: "OPTIONAL. List of individuals who contributed to the creation/curation of the"',
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
        self.assertEqual(returned_authors, ["Andreas Fink"])

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

    def test_get_dataset_description_enriches_string_authors_from_project_contacts(self):
        dataset_description = {
            "Name": "Demo",
            "BIDSVersion": "1.10.1",
            "DatasetType": "raw",
            "Authors": ["Koschutnig, Karl"],
        }
        (self.project_path / "dataset_description.json").write_text(
            json.dumps(dataset_description), encoding="utf-8"
        )

        (self.project_path / "project.json").write_text(
            json.dumps(
                {
                    "name": "demo_project",
                    "governance": {
                        "contacts": [
                            {
                                "name": "Koschutnig, Karl",
                                "roles": ["Data curation"],
                                "orcid": "https://orcid.org/0000-0001-6234-0498",
                                "email": "karl.koschutnig@uni-graz.at",
                                "corresponding": True,
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
        self.assertTrue(payload.get("success"))
        returned_authors = payload.get("description", {}).get("Authors") or []
        self.assertTrue(isinstance(returned_authors[0], dict))
        self.assertEqual(returned_authors[0].get("family-names"), "Koschutnig")
        self.assertEqual(returned_authors[0].get("given-names"), "Karl")
        self.assertEqual(
            returned_authors[0].get("orcid"),
            "https://orcid.org/0000-0001-6234-0498",
        )
        self.assertEqual(
            returned_authors[0].get("email"),
            "karl.koschutnig@uni-graz.at",
        )
        self.assertEqual(returned_authors[0].get("roles"), ["Data curation"])
        self.assertTrue(returned_authors[0].get("corresponding"))

    def test_get_dataset_description_prefers_project_json_over_stale_derived_metadata(self):
        (self.project_path / "dataset_description.json").write_text(
            json.dumps(
                {
                    "Name": "Stale Dataset",
                    "BIDSVersion": "1.10.1",
                    "DatasetType": "raw",
                    "DatasetDOI": "10.1111/stale",
                    "License": "CC-BY-4.0",
                    "Funding": ["Old funding"],
                    "EthicsApprovals": ["OLD-001"],
                }
            ),
            encoding="utf-8",
        )

        (self.project_path / "project.json").write_text(
            json.dumps(
                {
                    "name": "Canonical Dataset",
                    "Basics": {
                        "DatasetName": "Canonical Dataset",
                        "DatasetDOI": "10.2222/canonical",
                        "License": "CC0-1.0",
                        "Funding": ["FWF P12345"],
                        "EthicsApprovals": ["EK-2026-001"],
                        "Keywords": ["memory", "attention"],
                    },
                }
            ),
            encoding="utf-8",
        )

        (self.project_path / "CITATION.cff").write_text(
            "\n".join(
                [
                    "cff-version: 1.2.0",
                    'title: "Manual citation edit"',
                    'message: "Please cite manually edited citation."',
                    'license: "CC-BY-4.0"',
                    "type: dataset",
                    "authors:",
                    '  - family-names: "Doe"',
                    '    given-names: "Jane"',
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
        returned = payload.get("description", {})
        self.assertEqual(returned.get("Name"), "Canonical Dataset")
        self.assertEqual(returned.get("DatasetDOI"), "10.2222/canonical")
        self.assertEqual(returned.get("License"), "CC0-1.0")
        self.assertEqual(returned.get("Funding"), ["FWF P12345"])
        self.assertEqual(returned.get("EthicsApprovals"), ["EK-2026-001"])
        self.assertEqual(returned.get("Keywords"), ["memory", "attention"])

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

        project_payload = json.loads(
            (self.project_path / "project.json").read_text(encoding="utf-8")
        )
        self.assertEqual(project_payload.get("name"), "Demo")
        basics = project_payload.get("Basics") or {}
        self.assertEqual(basics.get("DatasetName"), "Demo")
        self.assertEqual(basics.get("DatasetDOI"), "10.1234/demo")
        self.assertEqual(basics.get("License"), "CC-BY-4.0")

    def test_get_metadata_status_reports_consistency_issues(self):
        (self.project_path / "project.json").write_text(
            json.dumps(
                {
                    "name": "Project Name",
                    "Basics": {
                        "DatasetName": "Project Name",
                        "DatasetDOI": "10.1000/project",
                    },
                }
            ),
            encoding="utf-8",
        )
        (self.project_path / "dataset_description.json").write_text(
            json.dumps(
                {
                    "Name": "Dataset Name",
                    "BIDSVersion": "1.10.1",
                    "DatasetType": "raw",
                    "DatasetDOI": "10.1000/dataset",
                }
            ),
            encoding="utf-8",
        )

        def get_current_project():
            return {"path": str(self.project_path), "name": "demo_project"}

        with self.app.test_request_context(
            "/api/projects/metadata/status",
            method="GET",
        ):
            response = self.handle_get_metadata_status(
                get_current_project=get_current_project,
                project_manager=self.project_manager,
            )

        status_code = response[1] if isinstance(response, tuple) else 200
        resp_obj = response[0] if isinstance(response, tuple) else response
        payload = resp_obj.get_json()

        self.assertEqual(status_code, 200)
        self.assertTrue(payload.get("success"))
        self.assertFalse(payload.get("consistent"))
        self.assertTrue(payload.get("issues"))

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

    def test_regenerate_citation_uses_canonical_project_metadata(self):
        dataset_description = {
            "Name": "Demo",
            "BIDSVersion": "1.10.1",
            "DatasetType": "raw",
            "Authors": ["Ada Lovelace"],
        }
        (self.project_path / "dataset_description.json").write_text(
            json.dumps(dataset_description),
            encoding="utf-8",
        )
        (self.project_path / "project.json").write_text(
            json.dumps(
                {
                    "name": "demo_project",
                    "Basics": {
                        "Authors": ["Ada Lovelace"],
                        "License": "CC-BY-4.0",
                        "DOI": "10.1000/demo",
                        "HowToAcknowledge": "Please cite Demo.",
                    },
                }
            ),
            encoding="utf-8",
        )

        (self.project_path / "CITATION.cff").write_text(
            self.project_manager._create_citation_cff(
                "Demo",
                {
                    "name": "Demo",
                    "authors": ["Ada Lovelace"],
                },
            ),
            encoding="utf-8",
        )
        stale_status = self.project_manager.get_citation_cff_status(self.project_path)
        self.assertFalse(stale_status.get("consistent"))

        def get_current_project():
            return {"path": str(self.project_path), "name": "demo_project"}

        def get_bids_file_path(project_path: Path, filename: str) -> Path:
            return project_path / filename

        with self.app.test_request_context(
            "/api/projects/citation/regenerate",
            method="POST",
            json={"project_path": str(self.project_path)},
        ):
            response = self.handle_regenerate_citation(
                get_current_project=get_current_project,
                get_bids_file_path=get_bids_file_path,
                project_manager=self.project_manager,
            )

        status_code = response[1] if isinstance(response, tuple) else 200
        resp_obj = response[0] if isinstance(response, tuple) else response

        self.assertEqual(status_code, 200)
        payload = resp_obj.get_json()
        self.assertTrue(payload.get("success"))
        self.assertTrue(payload.get("consistent"), payload)
        self.assertEqual(payload.get("consistency_issues"), [])

        citation_text = (self.project_path / "CITATION.cff").read_text(encoding="utf-8")
        self.assertIn('doi: "10.1000/demo"', citation_text)
        self.assertIn('license: "CC-BY-4.0"', citation_text)
        self.assertIn("message: >-", citation_text)

    def test_regenerate_citation_preserves_governance_contact_metadata(self):
        dataset_description = {
            "Name": "Demo",
            "BIDSVersion": "1.10.1",
            "DatasetType": "raw",
        }
        (self.project_path / "dataset_description.json").write_text(
            json.dumps(dataset_description),
            encoding="utf-8",
        )
        (self.project_path / "project.json").write_text(
            json.dumps(
                {
                    "name": "demo_project",
                    "Basics": {
                        "Authors": ["Ada Lovelace"],
                    },
                    "governance": {
                        "contacts": [
                            {
                                "name": "Lovelace, Ada",
                                "email": "ada@example.org",
                                "orcid": "https://orcid.org/0000-0000-0000-0001",
                                "corresponding": True,
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

        with self.app.test_request_context(
            "/api/projects/citation/regenerate",
            method="POST",
            json={"project_path": str(self.project_path)},
        ):
            response = self.handle_regenerate_citation(
                get_current_project=get_current_project,
                get_bids_file_path=get_bids_file_path,
                project_manager=self.project_manager,
            )

        status_code = response[1] if isinstance(response, tuple) else 200
        resp_obj = response[0] if isinstance(response, tuple) else response

        self.assertEqual(status_code, 200)
        payload = resp_obj.get_json()
        self.assertTrue(payload.get("success"))

        citation_text = (self.project_path / "CITATION.cff").read_text(encoding="utf-8")
        self.assertIn('email: "ada@example.org"', citation_text)
        self.assertIn('orcid: "https://orcid.org/0000-0000-0000-0001"', citation_text)
        self.assertIn("contact:", citation_text)

    def test_save_dataset_description_omits_citation_fields_when_citation_refresh_fails(self):
        (self.project_path / "dataset_description.json").write_text(
            json.dumps({"Name": "Demo", "BIDSVersion": "1.10.1", "DatasetType": "raw"}),
            encoding="utf-8",
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

        class _FailingCitationProjectManager:
            def __init__(self, wrapped):
                self._wrapped = wrapped

            def validate_dataset_description(self, description):
                return self._wrapped.validate_dataset_description(description)

            def update_citation_cff(self, project_path, description):
                raise RuntimeError("simulated citation write failure")

        failing_manager = _FailingCitationProjectManager(self.project_manager)

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
                "HowToAcknowledge": "Please cite this dataset.",
                "License": "CC-BY-4.0",
                "ReferencesAndLinks": ["https://example.org/paper"],
            }
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
                project_manager=failing_manager,
                set_current_project=set_current_project,
                save_last_project=save_last_project,
            )

        status_code = response[1] if isinstance(response, tuple) else 200
        resp_obj = response[0] if isinstance(response, tuple) else response
        payload = resp_obj.get_json()

        self.assertEqual(status_code, 200)
        self.assertTrue(payload.get("success"))

        saved_description = json.loads(
            (self.project_path / "dataset_description.json").read_text(encoding="utf-8")
        )
        self.assertNotIn("Authors", saved_description)
        self.assertNotIn("HowToAcknowledge", saved_description)
        self.assertNotIn("License", saved_description)
        self.assertNotIn("ReferencesAndLinks", saved_description)

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
