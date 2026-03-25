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


class TestProjectsSchemaConfigHandlers(unittest.TestCase):
    def setUp(self):
        self.tmp_dir = tempfile.TemporaryDirectory()
        self.project_path = Path(self.tmp_dir.name) / "demo_project"
        self.project_path.mkdir(parents=True, exist_ok=True)
        self.app = Flask(__name__, root_path=app_path)

        handlers = importlib.import_module(
            "src.web.blueprints.projects_schema_config_handlers"
        )
        self.handle_get_project_schema_config = (
            handlers.handle_get_project_schema_config
        )
        self.handle_save_project_schema_config = (
            handlers.handle_save_project_schema_config
        )

    def tearDown(self):
        self.tmp_dir.cleanup()

    def _get_current_project(self):
        return {"path": str(self.project_path), "name": "demo_project"}

    def test_get_project_schema_config_defaults_to_stable(self):
        with self.app.test_request_context("/api/projects/schema-config", method="GET"):
            response = self.handle_get_project_schema_config(
                get_current_project=self._get_current_project
            )

        payload = response.get_json()
        self.assertTrue(payload["success"])
        self.assertEqual(payload["schema_version"], "stable")
        self.assertIn("stable", payload["available_versions"])

    def test_save_project_schema_config_preserves_existing_filename(self):
        config_path = self.project_path / "prism.config.json"
        config_path.write_text(
            json.dumps({"schemaVersion": "v0.1", "strictMode": True}, indent=2),
            encoding="utf-8",
        )

        with self.app.test_request_context(
            "/api/projects/schema-config",
            method="POST",
            json={"schema_version": "v0.2"},
        ):
            response = self.handle_save_project_schema_config(
                get_current_project=self._get_current_project
            )

        status_code = response[1] if isinstance(response, tuple) else 200
        resp_obj = response[0] if isinstance(response, tuple) else response
        payload = resp_obj.get_json()

        self.assertEqual(status_code, 200)
        self.assertTrue(payload["success"])
        self.assertEqual(payload["schema_version"], "v0.2")
        self.assertEqual(payload["config_path"], str(config_path))
        self.assertFalse((self.project_path / ".prismrc.json").exists())

        saved = json.loads(config_path.read_text(encoding="utf-8"))
        self.assertEqual(saved["schemaVersion"], "v0.2")
        self.assertTrue(saved["strictMode"])

    def test_save_project_schema_config_rejects_unknown_version(self):
        with self.app.test_request_context(
            "/api/projects/schema-config",
            method="POST",
            json={"schema_version": "v9.9"},
        ):
            response = self.handle_save_project_schema_config(
                get_current_project=self._get_current_project
            )

        status_code = response[1] if isinstance(response, tuple) else 200
        resp_obj = response[0] if isinstance(response, tuple) else response
        payload = resp_obj.get_json()

        self.assertEqual(status_code, 400)
        self.assertFalse(payload["success"])
        self.assertIn("Unknown schema version", payload["error"])
