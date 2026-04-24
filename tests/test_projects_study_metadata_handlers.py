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


class _DummyProjectManager:
    def __init__(self):
        self.update_calls = []

    def update_citation_cff(self, project_path, dataset_desc):
        self.update_calls.append(
            {
                "project_path": Path(project_path),
                "dataset_desc": dataset_desc,
            }
        )
        return None


class TestProjectsStudyMetadataHandlers(unittest.TestCase):
    def setUp(self):
        self.tmp_dir = tempfile.TemporaryDirectory()
        self.project_root = Path(self.tmp_dir.name) / "demo_project"
        self.project_root.mkdir(parents=True, exist_ok=True)
        (self.project_root / "project.json").write_text(
            json.dumps({"Metadata": {}, "Recruitment": {}}),
            encoding="utf-8",
        )

        self.app = Flask(__name__)

        metadata_helpers = importlib.import_module(
            "src.web.blueprints.projects_metadata_helpers"
        )
        study_metadata_handlers = importlib.import_module(
            "src.web.blueprints.projects_study_metadata_handlers"
        )

        self.read_project_json = metadata_helpers._read_project_json
        self.write_project_json = metadata_helpers._write_project_json
        self.handle_save_study_metadata = (
            study_metadata_handlers.handle_save_study_metadata
        )

    def tearDown(self):
        self.tmp_dir.cleanup()

    def _make_project(self, name: str) -> Path:
        project_root = Path(self.tmp_dir.name) / name
        project_root.mkdir(parents=True, exist_ok=True)
        (project_root / "project.json").write_text(
            json.dumps({"Metadata": {}, "Recruitment": {}}),
            encoding="utf-8",
        )
        return project_root

    def test_save_study_metadata_normalizes_recruitment_lists_to_strings(self):
        def get_current_project():
            return {"path": str(self.project_root), "name": "demo_project"}

        def get_bids_file_path(project_path: Path, filename: str) -> Path:
            return project_path / filename

        def compute_methods_completeness(project_data, dataset_desc):
            return {"score": 0}

        payload = {
            "Recruitment": {
                "Method": ["social-media", "participant-pool"],
                "Location": [
                    "Graz, Austria",
                    "Linz, Upper Austria, Austria",
                    "Vienna, Vienna, Austria",
                ],
            }
        }

        with self.app.test_request_context(
            "/api/projects/study-metadata",
            method="POST",
            json=payload,
        ):
            response = self.handle_save_study_metadata(
                get_current_project=get_current_project,
                read_project_json=self.read_project_json,
                write_project_json=self.write_project_json,
                get_bids_file_path=get_bids_file_path,
                editable_sections=("Recruitment",),
                compute_methods_completeness=compute_methods_completeness,
                project_manager=_DummyProjectManager(),
            )

        status_code = response[1] if isinstance(response, tuple) else 200
        resp_obj = response[0] if isinstance(response, tuple) else response

        self.assertEqual(status_code, 200)
        self.assertTrue(resp_obj.get_json().get("success"))

        saved = json.loads(
            (self.project_root / "project.json").read_text(encoding="utf-8")
        )
        self.assertEqual(
            saved["Recruitment"]["Location"],
            "Graz, Austria; Linz, Upper Austria, Austria; Vienna, Vienna, Austria",
        )
        self.assertEqual(
            saved["Recruitment"]["Method"],
            "social-media; participant-pool",
        )

    def test_save_study_metadata_preserves_overview_lists_as_lists(self):
        def get_current_project():
            return {"path": str(self.project_root), "name": "demo_project"}

        def get_bids_file_path(project_path: Path, filename: str) -> Path:
            return project_path / filename

        def compute_methods_completeness(project_data, dataset_desc):
            return {"score": 0}

        payload = {
            "Overview": {
                "IndependentVariables": [
                    "ballet intervention",
                    "contemporary dance intervention",
                    "no intervention",
                ],
                "DependentVariables": ["interest", "intervention experience"],
                "ControlVariables": ["age", "sex"],
                "QualityAssessment": ["manual QC", "double-check scoring"],
            }
        }

        with self.app.test_request_context(
            "/api/projects/study-metadata",
            method="POST",
            json=payload,
        ):
            response = self.handle_save_study_metadata(
                get_current_project=get_current_project,
                read_project_json=self.read_project_json,
                write_project_json=self.write_project_json,
                get_bids_file_path=get_bids_file_path,
                editable_sections=("Overview",),
                compute_methods_completeness=compute_methods_completeness,
                project_manager=_DummyProjectManager(),
            )

        status_code = response[1] if isinstance(response, tuple) else 200
        resp_obj = response[0] if isinstance(response, tuple) else response

        self.assertEqual(status_code, 200)
        self.assertTrue(resp_obj.get_json().get("success"))

        saved = json.loads(
            (self.project_root / "project.json").read_text(encoding="utf-8")
        )
        self.assertEqual(
            saved["Overview"]["IndependentVariables"],
            [
                "ballet intervention",
                "contemporary dance intervention",
                "no intervention",
            ],
        )
        self.assertEqual(
            saved["Overview"]["QualityAssessment"],
            ["manual QC", "double-check scoring"],
        )

    def test_save_study_metadata_persists_basics_keywords_and_related_fields(self):
        def get_current_project():
            return {"path": str(self.project_root), "name": "demo_project"}

        def get_bids_file_path(project_path: Path, filename: str) -> Path:
            return project_path / filename

        def compute_methods_completeness(project_data, dataset_desc):
            return {"score": 0}

        payload = {
            "Basics": {
                "Name": "RIBS Study",
                "Authors": ["Ada Lovelace", "Grace Hopper"],
                "Keywords": ["psychology", "bipolar", "ribs"],
                "EthicsApprovals": ["EK-2026-001"],
                "Funding": ["FWF P12345"],
            }
        }

        with self.app.test_request_context(
            "/api/projects/study-metadata",
            method="POST",
            json=payload,
        ):
            response = self.handle_save_study_metadata(
                get_current_project=get_current_project,
                read_project_json=self.read_project_json,
                write_project_json=self.write_project_json,
                get_bids_file_path=get_bids_file_path,
                editable_sections=("Basics",),
                compute_methods_completeness=compute_methods_completeness,
                project_manager=_DummyProjectManager(),
            )

        status_code = response[1] if isinstance(response, tuple) else 200
        resp_obj = response[0] if isinstance(response, tuple) else response

        self.assertEqual(status_code, 200)
        self.assertTrue(resp_obj.get_json().get("success"))

        saved = json.loads(
            (self.project_root / "project.json").read_text(encoding="utf-8")
        )
        self.assertEqual(saved["Basics"]["Name"], "RIBS Study")
        self.assertEqual(saved["Basics"]["Authors"], ["Ada Lovelace", "Grace Hopper"])
        self.assertEqual(saved["Basics"]["Keywords"], ["psychology", "bipolar", "ribs"])
        self.assertEqual(saved["Basics"]["EthicsApprovals"], ["EK-2026-001"])
        self.assertEqual(saved["Basics"]["Funding"], ["FWF P12345"])

    def test_save_study_metadata_can_target_explicit_project_path(self):
        other_project = self._make_project("other_project")

        def get_current_project():
            return {"path": str(self.project_root), "name": "demo_project"}

        def get_bids_file_path(project_path: Path, filename: str) -> Path:
            return project_path / filename

        def compute_methods_completeness(project_data, dataset_desc):
            return {"score": 0}

        payload = {
            "project_path": str(other_project),
            "Basics": {
                "Name": "Other Study",
                "Authors": ["Ada Lovelace"],
            },
        }

        with self.app.test_request_context(
            "/api/projects/study-metadata",
            method="POST",
            json=payload,
        ):
            response = self.handle_save_study_metadata(
                get_current_project=get_current_project,
                read_project_json=self.read_project_json,
                write_project_json=self.write_project_json,
                get_bids_file_path=get_bids_file_path,
                editable_sections=("Basics",),
                compute_methods_completeness=compute_methods_completeness,
                project_manager=_DummyProjectManager(),
            )

        status_code = response[1] if isinstance(response, tuple) else 200
        resp_obj = response[0] if isinstance(response, tuple) else response

        self.assertEqual(status_code, 200)
        self.assertTrue(resp_obj.get_json().get("success"))

        saved = json.loads((other_project / "project.json").read_text(encoding="utf-8"))
        self.assertEqual(saved["Basics"]["Name"], "Other Study")
        self.assertFalse(
            json.loads(
                (self.project_root / "project.json").read_text(encoding="utf-8")
            ).get("Basics")
        )

    def test_save_study_metadata_refreshes_citation_from_basics_when_description_is_placeholder(self):
        (self.project_root / "dataset_description.json").write_text(
            json.dumps(
                {
                    "Name": "REQUIRED. Name of the dataset",
                    "Authors": [
                        "OPTIONAL. List of individuals who contributed to the creation/curation of the dataset"
                    ],
                    "License": "RECOMMENDED. The license for the dataset",
                }
            ),
            encoding="utf-8",
        )

        def get_current_project():
            return {"path": str(self.project_root), "name": "demo_project"}

        def get_bids_file_path(project_path: Path, filename: str) -> Path:
            return project_path / filename

        def compute_methods_completeness(project_data, dataset_desc):
            return {"score": 0}

        payload = {
            "Basics": {
                "Name": "BrainHearthlon",
                "Authors": ["Fink, Andreas"],
            }
        }

        manager = _DummyProjectManager()
        with self.app.test_request_context(
            "/api/projects/study-metadata",
            method="POST",
            json=payload,
        ):
            response = self.handle_save_study_metadata(
                get_current_project=get_current_project,
                read_project_json=self.read_project_json,
                write_project_json=self.write_project_json,
                get_bids_file_path=get_bids_file_path,
                editable_sections=("Basics",),
                compute_methods_completeness=compute_methods_completeness,
                project_manager=manager,
            )

        status_code = response[1] if isinstance(response, tuple) else 200
        resp_obj = response[0] if isinstance(response, tuple) else response

        self.assertEqual(status_code, 200)
        self.assertTrue(resp_obj.get_json().get("success"))
        self.assertEqual(len(manager.update_calls), 1)

        citation_desc = manager.update_calls[0]["dataset_desc"]
        self.assertEqual(citation_desc.get("Name"), "BrainHearthlon")
        self.assertEqual(citation_desc.get("Authors"), ["Fink, Andreas"])

    def test_save_study_metadata_refreshes_citation_without_dataset_description_file(self):
        def get_current_project():
            return {"path": str(self.project_root), "name": "demo_project"}

        def get_bids_file_path(project_path: Path, filename: str) -> Path:
            return project_path / filename

        def compute_methods_completeness(project_data, dataset_desc):
            return {"score": 0}

        payload = {
            "Basics": {
                "Name": "Preliminary Study",
                "Authors": ["Ada Lovelace"],
            }
        }

        manager = _DummyProjectManager()
        with self.app.test_request_context(
            "/api/projects/study-metadata",
            method="POST",
            json=payload,
        ):
            response = self.handle_save_study_metadata(
                get_current_project=get_current_project,
                read_project_json=self.read_project_json,
                write_project_json=self.write_project_json,
                get_bids_file_path=get_bids_file_path,
                editable_sections=("Basics",),
                compute_methods_completeness=compute_methods_completeness,
                project_manager=manager,
            )

        status_code = response[1] if isinstance(response, tuple) else 200
        resp_obj = response[0] if isinstance(response, tuple) else response

        self.assertEqual(status_code, 200)
        self.assertTrue(resp_obj.get_json().get("success"))
        self.assertEqual(len(manager.update_calls), 1)

        citation_desc = manager.update_calls[0]["dataset_desc"]
        self.assertEqual(citation_desc.get("Name"), "Preliminary Study")
        self.assertEqual(citation_desc.get("Authors"), ["Ada Lovelace"])
