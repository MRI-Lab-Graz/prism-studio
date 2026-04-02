import importlib
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from flask import Flask

current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(current_dir)
app_path = os.path.join(project_root, "app")
if app_path not in sys.path:
    sys.path.insert(0, app_path)


class TestProjectsMethodsHandlers(unittest.TestCase):
    def setUp(self):
        self.tmp_dir = tempfile.TemporaryDirectory()
        self.project_root = Path(self.tmp_dir.name) / "demo_project"
        self.project_root.mkdir(parents=True, exist_ok=True)

        self.library_root = Path(self.tmp_dir.name) / "external_library"
        (self.library_root / "survey").mkdir(parents=True, exist_ok=True)
        (self.library_root / "survey" / "survey-ads.json").write_text(
            json.dumps(
                {
                    "Study": {
                        "TaskName": {"en": "Affective Distress Scale"},
                        "Description": {"en": "Assesses current distress symptoms."},
                    },
                    "item_01": {
                        "Levels": {
                            "1": {"en": "Not at all"},
                            "2": {"en": "Sometimes"},
                            "3": {"en": "Often"},
                        }
                    },
                }
            ),
            encoding="utf-8",
        )

        self.app = Flask(__name__)
        self.app.secret_key = os.urandom(32)

        module = importlib.import_module("src.web.blueprints.projects_methods_handlers")
        self.handle_generate_methods_section = module.handle_generate_methods_section

    def tearDown(self):
        self.tmp_dir.cleanup()

    def test_generate_methods_finds_template_from_task_name_fallback(self):
        project_data = {
            "TaskDefinitions": {
                "ads": {
                    "modality": "survey",
                }
            }
        }

        def get_current_project():
            return {"path": str(self.project_root), "name": "demo_project"}

        def read_project_json(_project_path: Path):
            return project_data

        def get_bids_file_path(project_path: Path, filename: str) -> Path:
            return project_path / filename

        def compute_participant_stats(_project_path: Path, lang: str = "en"):
            return None

        with patch("src.config.load_app_settings", return_value={}):
            with patch(
                "src.config.get_effective_template_library_path",
                return_value={
                    "effective_external_path": str(self.library_root),
                    "global_library_path": "",
                },
            ):
                with self.app.test_request_context(
                    "/api/projects/generate-methods",
                    method="POST",
                    json={
                        "language": "en",
                        "detail_level": "standard",
                        "continuous": True,
                    },
                ):
                    response = self.handle_generate_methods_section(
                        get_current_project=get_current_project,
                        read_project_json=read_project_json,
                        get_bids_file_path=get_bids_file_path,
                        compute_participant_stats=compute_participant_stats,
                    )

        status_code = response[1] if isinstance(response, tuple) else 200
        resp_obj = response[0] if isinstance(response, tuple) else response
        payload = resp_obj.get_json()

        self.assertEqual(status_code, 200)
        self.assertTrue(payload.get("success"))
        self.assertIn("Affective Distress Scale", payload.get("md", ""))
        self.assertIn("comprises 1 items", payload.get("md", ""))

    def test_generate_methods_forces_continuous_output(self):
        project_data = {
            "StudyDesign": {"Type": "quasi-experimental"},
            "TaskDefinitions": {
                "ads": {
                    "modality": "survey",
                }
            },
        }

        def get_current_project():
            return {"path": str(self.project_root), "name": "demo_project"}

        def read_project_json(_project_path: Path):
            return project_data

        def get_bids_file_path(project_path: Path, filename: str) -> Path:
            return project_path / filename

        def compute_participant_stats(_project_path: Path, lang: str = "en"):
            return None

        with patch("src.config.load_app_settings", return_value={}):
            with patch(
                "src.config.get_effective_template_library_path",
                return_value={
                    "effective_external_path": str(self.library_root),
                    "global_library_path": "",
                },
            ):
                with self.app.test_request_context(
                    "/api/projects/generate-methods",
                    method="POST",
                    json={
                        "language": "en",
                        "detail_level": "standard",
                        "continuous": False,
                    },
                ):
                    response = self.handle_generate_methods_section(
                        get_current_project=get_current_project,
                        read_project_json=read_project_json,
                        get_bids_file_path=get_bids_file_path,
                        compute_participant_stats=compute_participant_stats,
                    )

        status_code = response[1] if isinstance(response, tuple) else 200
        resp_obj = response[0] if isinstance(response, tuple) else response
        payload = resp_obj.get_json()

        self.assertEqual(status_code, 200)
        self.assertTrue(payload.get("success"))
        self.assertNotIn("## ", payload.get("md", ""))


if __name__ == "__main__":
    unittest.main()
