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
        self.handle_get_project_preferences = handlers.handle_get_project_preferences
        self.handle_save_project_preferences = handlers.handle_save_project_preferences

    def tearDown(self):
        self.tmp_dir.cleanup()

    def _get_current_project(self):
        return {"path": str(self.project_path), "name": "demo_project"}

    def _make_project(self, name: str) -> Path:
        project_path = Path(self.tmp_dir.name) / name
        project_path.mkdir(parents=True, exist_ok=True)
        return project_path

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

    def test_get_project_schema_config_auto_sets_stable_when_no_config(self):
        """Loading a project with no config file should auto-write schemaVersion=stable."""
        config_file = self.project_path / ".prismrc.json"
        self.assertFalse(config_file.exists())

        with self.app.test_request_context("/api/projects/schema-config", method="GET"):
            response = self.handle_get_project_schema_config(
                get_current_project=self._get_current_project
            )

        payload = response.get_json()
        self.assertTrue(payload["success"])
        self.assertEqual(payload["schema_version"], "stable")
        # Config file must now exist with schemaVersion explicitly set
        self.assertTrue(config_file.exists())
        saved = json.loads(config_file.read_text(encoding="utf-8"))
        self.assertEqual(saved["schemaVersion"], "stable")

    def test_get_project_schema_config_auto_sets_stable_when_schema_version_missing(
        self,
    ):
        """Loading a project whose config lacks schemaVersion should auto-write stable."""
        config_file = self.project_path / ".prismrc.json"
        config_file.write_text(
            json.dumps({"strictMode": True}, indent=2), encoding="utf-8"
        )

        with self.app.test_request_context("/api/projects/schema-config", method="GET"):
            response = self.handle_get_project_schema_config(
                get_current_project=self._get_current_project
            )

        payload = response.get_json()
        self.assertTrue(payload["success"])
        self.assertEqual(payload["schema_version"], "stable")
        saved = json.loads(config_file.read_text(encoding="utf-8"))
        self.assertEqual(saved["schemaVersion"], "stable")
        # Existing keys must be preserved
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

    def test_get_project_preferences_can_target_explicit_project_path(self):
        other_project = self._make_project("other_project")
        (other_project / ".prismrc.json").write_text(
            json.dumps(
                {
                    "projectPreferences": {
                        "export": {
                            "output_folder": "/tmp/export-out",
                            "exclude_sessions": ["ses-02"],
                        }
                    }
                },
                indent=2,
            ),
            encoding="utf-8",
        )

        with self.app.test_request_context(
            "/api/projects/preferences/export",
            method="GET",
            query_string={"project_path": str(other_project)},
        ):
            response = self.handle_get_project_preferences(
                get_current_project=self._get_current_project,
                namespace="export",
            )

        payload = response.get_json()
        self.assertTrue(payload["success"])
        self.assertEqual(payload["preferences"]["output_folder"], "/tmp/export-out")
        self.assertEqual(payload["preferences"]["exclude_sessions"], ["ses-02"])

    def test_save_project_preferences_can_target_explicit_project_path(self):
        other_project = self._make_project("other_project")

        with self.app.test_request_context(
            "/api/projects/preferences/export",
            method="POST",
            json={
                "project_path": str(other_project),
                "preferences": {
                    "output_folder": "/tmp/export-target",
                    "exclude_modalities": ["func"],
                },
            },
        ):
            response = self.handle_save_project_preferences(
                get_current_project=self._get_current_project,
                namespace="export",
            )

        status_code = response[1] if isinstance(response, tuple) else 200
        resp_obj = response[0] if isinstance(response, tuple) else response
        payload = resp_obj.get_json()

        self.assertEqual(status_code, 200)
        self.assertTrue(payload["success"])

        saved = json.loads((other_project / ".prismrc.json").read_text(encoding="utf-8"))
        export_prefs = saved["projectPreferences"]["export"]
        self.assertEqual(export_prefs["output_folder"], "/tmp/export-target")
        self.assertEqual(export_prefs["exclude_modalities"], ["func"])
        self.assertFalse((self.project_path / ".prismrc.json").exists())

    def test_get_project_schema_config_can_target_explicit_project_path(self):
        other_project = self._make_project("other_project")
        (other_project / ".prismrc.json").write_text(
            json.dumps({"schemaVersion": "stable"}, indent=2),
            encoding="utf-8",
        )

        with self.app.test_request_context(
            "/api/projects/schema-config",
            method="GET",
            query_string={"project_path": str(other_project)},
        ):
            response = self.handle_get_project_schema_config(
                get_current_project=self._get_current_project
            )

        payload = response.get_json()
        self.assertTrue(payload["success"])
        self.assertEqual(payload["schema_version"], "stable")

    def test_save_project_schema_config_can_target_explicit_project_path(self):
        other_project = self._make_project("other_project")

        with self.app.test_request_context(
            "/api/projects/schema-config",
            method="POST",
            json={"project_path": str(other_project), "schema_version": "stable"},
        ):
            response = self.handle_save_project_schema_config(
                get_current_project=self._get_current_project
            )

        status_code = response[1] if isinstance(response, tuple) else 200
        resp_obj = response[0] if isinstance(response, tuple) else response
        payload = resp_obj.get_json()

        self.assertEqual(status_code, 200)
        self.assertTrue(payload["success"])
        saved = json.loads((other_project / ".prismrc.json").read_text(encoding="utf-8"))
        self.assertEqual(saved["schemaVersion"], "stable")
