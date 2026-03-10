import json
import os
import sys
import tempfile
import unittest
import importlib
from pathlib import Path

from flask import Flask

# Ensure 'app' is importable as top-level package path
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(current_dir)
app_path = os.path.join(project_root, "app")
if app_path not in sys.path:
    sys.path.insert(0, app_path)


class TestProjectsParticipantsHandlers(unittest.TestCase):
    def setUp(self):
        self.tmp_dir = tempfile.TemporaryDirectory()
        self.project_root = Path(self.tmp_dir.name) / "demo_project"
        self.project_root.mkdir(parents=True, exist_ok=True)
        (self.project_root / "project.json").write_text("{}", encoding="utf-8")

        self.app = Flask(__name__)

        participants_handlers = importlib.import_module(
            "src.web.blueprints.projects_participants_handlers"
        )
        self.handle_save_participants_schema = (
            participants_handlers.handle_save_participants_schema
        )

    def tearDown(self):
        self.tmp_dir.cleanup()

    def test_save_schema_accepts_project_json_current_path(self):
        def get_current_project():
            return {
                "path": str(self.project_root / "project.json"),
                "name": "demo_project",
            }

        def get_bids_file_path(project_path: Path, filename: str) -> Path:
            return project_path / filename

        payload = {"schema": {"age": {"Description": "Age", "Unit": "years"}}}

        with self.app.test_request_context(
            "/api/projects/participants",
            method="POST",
            json=payload,
        ):
            response = self.handle_save_participants_schema(
                get_current_project=get_current_project,
                get_bids_file_path=get_bids_file_path,
            )

        status_code = response[1] if isinstance(response, tuple) else 200
        resp_obj = response[0] if isinstance(response, tuple) else response

        self.assertEqual(status_code, 200)
        body = resp_obj.get_json()
        self.assertTrue(body.get("success"))

        participants_json = self.project_root / "participants.json"
        self.assertTrue(participants_json.exists())

        saved = json.loads(participants_json.read_text(encoding="utf-8"))
        self.assertIn("participant_id", saved)
        self.assertIn("age", saved)


if __name__ == "__main__":
    unittest.main()
