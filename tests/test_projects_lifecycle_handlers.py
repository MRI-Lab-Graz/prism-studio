import importlib
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from flask import Flask, session

current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(current_dir)
app_path = os.path.join(project_root, "app")
if app_path not in sys.path:
    sys.path.insert(0, app_path)

from src.project_icons import get_project_icon_classes


class _ProjectManagerStub:
    def __init__(self):
        self.validated_path = None
        self.create_calls = []
        self.init_calls = []

    def validate_structure(self, path: str):
        self.validated_path = path
        return {"valid": True, "issues": [], "fixable_issues": [], "stats": {}}

    def create_project(self, path: str, config: dict):
        self.create_calls.append((path, config))
        return {"success": True, "path": path, "created_files": [], "message": "ok"}

    def init_on_existing_bids(self, path: str, config: dict):
        self.init_calls.append((path, config))
        return {"success": True, "path": path, "created_files": [], "message": "ok"}


class TestProjectsLifecycleHandlers(unittest.TestCase):
    def setUp(self):
        self.tmp_dir = tempfile.TemporaryDirectory()
        self.project_root = Path(self.tmp_dir.name) / "demo_project"
        self.project_root.mkdir(parents=True, exist_ok=True)
        (self.project_root / "project.json").write_text("{}", encoding="utf-8")
        self.project_root_alt = Path(self.tmp_dir.name) / "demo_project_alt"
        self.project_root_alt.mkdir(parents=True, exist_ok=True)
        (self.project_root_alt / "project.json").write_text(
            '{"name": "Alt Dataset"}',
            encoding="utf-8",
        )
        self.app = Flask(__name__)
        self.app.secret_key = os.urandom(32)
        self.module = importlib.import_module(
            "src.web.blueprints.projects_lifecycle_handlers"
        )
        self.handle_validate_project = self.module.handle_validate_project
        self.handle_project_path_status = self.module.handle_project_path_status
        self.handle_set_current = self.module.handle_set_current
        self.handle_get_recent_projects = self.module.handle_get_recent_projects
        self.handle_set_recent_projects = self.module.handle_set_recent_projects
        self.handle_recruitment_location_search = (
            self.module.handle_recruitment_location_search
        )
        self.allowed_icons = set(get_project_icon_classes())

    def tearDown(self):
        self.tmp_dir.cleanup()

    def test_validate_project_accepts_project_directory(self):
        (self.project_root / "project.json").write_text(
            '{"name": "Dataset From JSON"}', encoding="utf-8"
        )
        manager = _ProjectManagerStub()
        captured = {}

        def set_current_project(path: str, name: str | None = None):
            captured["path"] = path
            captured["name"] = name

        def save_last_project(path: str | None, name: str | None):
            captured["last_path"] = path
            captured["last_name"] = name

        with self.app.test_request_context(
            "/api/projects/validate",
            method="POST",
            json={"path": str(self.project_root)},
        ):
            response = self.handle_validate_project(
                project_manager=manager,
                set_current_project=set_current_project,
                save_last_project=save_last_project,
            )

        status_code = response[1] if isinstance(response, tuple) else 200
        resp_obj = response[0] if isinstance(response, tuple) else response
        body = resp_obj.get_json()

        self.assertEqual(status_code, 200)
        self.assertTrue(body["success"])
        self.assertEqual(manager.validated_path, str(self.project_root))
        self.assertEqual(body["current_project"]["path"], str(self.project_root))
        self.assertEqual(body["current_project"]["name"], "Dataset From JSON")
        self.assertIn(body["current_project"]["icon"], self.allowed_icons)
        self.assertEqual(
            body["current_project"]["project_json_path"],
            str(self.project_root / "project.json"),
        )
        self.assertEqual(captured["path"], str(self.project_root))
        self.assertEqual(captured["name"], "Dataset From JSON")

        project_payload = json.loads(
            (self.project_root / "project.json").read_text(encoding="utf-8")
        )
        self.assertIn(project_payload.get("icon"), self.allowed_icons)

    def test_set_current_prefers_project_json_name(self):
        (self.project_root / "project.json").write_text(
            '{"name": "Resolved Name"}', encoding="utf-8"
        )
        (self.project_root / "sub-01" / "ses-01" / "func").mkdir(parents=True)
        (self.project_root / "dataset_description.json").write_text(
            "{}", encoding="utf-8"
        )
        captured = {}

        def get_current_project():
            return {
                "path": captured.get("path", ""),
                "name": captured.get("name", ""),
            }

        def set_current_project(path: str, name: str | None = None):
            captured["path"] = path
            captured["name"] = name

        def save_last_project(path: str | None, name: str | None):
            captured["last_path"] = path
            captured["last_name"] = name

        with self.app.test_request_context(
            "/api/projects/current",
            method="POST",
            json={"path": str(self.project_root), "name": "Stale Name"},
        ):
            response = self.handle_set_current(
                get_current_project=get_current_project,
                set_current_project=set_current_project,
                save_last_project=save_last_project,
            )

        status_code = response[1] if isinstance(response, tuple) else 200
        resp_obj = response[0] if isinstance(response, tuple) else response
        body = resp_obj.get_json()

        self.assertEqual(status_code, 200)
        self.assertTrue(body["success"])
        self.assertEqual(body["current"]["path"], str(self.project_root))
        self.assertEqual(body["current"]["name"], "Resolved Name")
        self.assertEqual(body["project_summary"]["subjects"], 1)
        self.assertEqual(body["project_summary"]["sessions"], 1)
        self.assertEqual(body["project_summary"]["modalities"], 1)
        self.assertEqual(body["project_summary"]["session_labels"], ["ses-01"])
        self.assertEqual(body["project_summary"]["modality_labels"], ["func"])
        self.assertTrue(body["project_summary"]["has_dataset_description"])
        self.assertFalse(body["project_summary"]["has_participants_tsv"])
        self.assertEqual(captured["name"], "Resolved Name")
        self.assertEqual(captured["last_name"], "Resolved Name")
        self.assertIn(body["current"]["icon"], self.allowed_icons)

    def test_project_path_status_accepts_project_directory(self):
        with self.app.test_request_context(
            "/api/projects/path-status",
            method="POST",
            json={"path": str(self.project_root)},
        ):
            response = self.handle_project_path_status()

        status_code = response[1] if isinstance(response, tuple) else 200
        resp_obj = response[0] if isinstance(response, tuple) else response
        body = resp_obj.get_json()

        self.assertEqual(status_code, 200)
        self.assertTrue(body["success"])
        self.assertTrue(body["available"])
        self.assertTrue(body["is_dir"])
        self.assertFalse(body["is_empty_dir"])
        self.assertTrue(body["has_non_system_entries"])
        self.assertEqual(
            body["project_json_path"], str(self.project_root / "project.json")
        )

    def test_project_path_status_ignores_system_files_for_empty_directory(self):
        target_root = Path(self.tmp_dir.name) / "empty_target"
        target_root.mkdir(parents=True, exist_ok=True)
        (target_root / "Thumbs.db").write_text("", encoding="utf-8")
        (target_root / ".DS_Store").write_text("", encoding="utf-8")

        with self.app.test_request_context(
            "/api/projects/path-status",
            method="POST",
            json={"path": str(target_root)},
        ):
            response = self.handle_project_path_status()

        status_code = response[1] if isinstance(response, tuple) else 200
        resp_obj = response[0] if isinstance(response, tuple) else response
        body = resp_obj.get_json()

        self.assertEqual(status_code, 200)
        self.assertTrue(body["success"])
        self.assertTrue(body["exists"])
        self.assertTrue(body["is_dir"])
        self.assertTrue(body["is_empty_dir"])
        self.assertFalse(body["has_non_system_entries"])
        self.assertFalse(body["available"])

    def test_create_project_forwards_datalad_opt_out(self):
        manager = _ProjectManagerStub()
        captured = {}

        def set_current_project(path: str, name: str | None = None):
            captured["path"] = path
            captured["name"] = name

        def save_last_project(path: str | None, name: str | None):
            captured["last_path"] = path
            captured["last_name"] = name

        target_path = Path(self.tmp_dir.name) / "created_project"
        with self.app.test_request_context(
            "/api/projects/create",
            method="POST",
            json={"path": str(target_path), "name": "created_project", "use_datalad": False},
        ):
            response = self.module.handle_create_project(
                project_manager=manager,
                set_current_project=set_current_project,
                save_last_project=save_last_project,
            )

        body = response.get_json()
        self.assertTrue(body["success"])
        self.assertEqual(manager.create_calls[0][1]["use_datalad"], False)

    def test_init_on_bids_forwards_datalad_default(self):
        manager = _ProjectManagerStub()
        captured = {}

        def set_current_project(path: str, name: str | None = None):
            captured["path"] = path
            captured["name"] = name

        def save_last_project(path: str | None, name: str | None):
            captured["last_path"] = path
            captured["last_name"] = name

        target_path = Path(self.tmp_dir.name) / "existing_bids"
        target_path.mkdir(parents=True, exist_ok=True)
        with self.app.test_request_context(
            "/api/projects/init-on-bids",
            method="POST",
            json={"path": str(target_path), "name": "existing_bids"},
        ):
            response = self.module.handle_init_on_bids(
                project_manager=manager,
                set_current_project=set_current_project,
                save_last_project=save_last_project,
            )

        body = response.get_json()
        self.assertTrue(body["success"])
        self.assertEqual(manager.init_calls[0][1]["use_datalad"], True)

    def test_project_state_flow_load_switch_create_mode_and_recent_reload(self):
        (self.project_root / "project.json").write_text(
            '{"name": "Primary Dataset"}',
            encoding="utf-8",
        )
        saved_last = []

        def get_current_project():
            return {
                "path": session.get("current_project_path", ""),
                "name": session.get("current_project_name", ""),
            }

        def set_current_project(path: str, name: str | None = None):
            session["current_project_path"] = path or ""
            session["current_project_name"] = name or ""

        def save_last_project(path: str | None, name: str | None):
            saved_last.append((path, name))

        with self.app.test_request_context(
            "/api/projects/current",
            method="POST",
            json={"path": str(self.project_root)},
        ):
            response = self.handle_set_current(
                get_current_project=get_current_project,
                set_current_project=set_current_project,
                save_last_project=save_last_project,
            )
        self.assertEqual(response.get_json()["current"]["name"], "Primary Dataset")

        with self.app.test_request_context(
            "/api/projects/current",
            method="POST",
            json={"path": str(self.project_root_alt), "name": "stale"},
        ):
            response = self.handle_set_current(
                get_current_project=get_current_project,
                set_current_project=set_current_project,
                save_last_project=save_last_project,
            )
        self.assertEqual(
            response.get_json()["current"]["path"], str(self.project_root_alt)
        )
        self.assertEqual(response.get_json()["current"]["name"], "Alt Dataset")

        with self.app.test_request_context(
            "/api/projects/current",
            method="POST",
            json={"path": ""},
        ):
            session["current_project_path"] = str(self.project_root_alt)
            session["current_project_name"] = "Alt Dataset"
            response = self.handle_set_current(
                get_current_project=get_current_project,
                set_current_project=set_current_project,
                save_last_project=save_last_project,
            )
        self.assertEqual(response.get_json()["current"], {"path": "", "name": ""})
        self.assertEqual(saved_last[-1], (None, None))

        recent_payload = [
            {"name": "Alt Dataset", "path": str(self.project_root_alt)},
            {"name": "Primary Dataset", "path": str(self.project_root)},
        ]
        with patch.object(
            self.module, "_save_recent_projects", return_value=recent_payload
        ) as mock_save:
            with self.app.test_request_context(
                "/api/projects/recent",
                method="POST",
                json={"projects": recent_payload},
            ):
                response = self.handle_set_recent_projects()
        self.assertTrue(response.get_json()["success"])
        self.assertEqual(response.get_json()["projects"], recent_payload)
        mock_save.assert_called_once_with(recent_payload)

        with patch.object(
            self.module, "_load_recent_projects", return_value=recent_payload
        ) as mock_load:
            with self.app.test_request_context(
                "/api/projects/recent",
                method="GET",
            ):
                response = self.handle_get_recent_projects()
        self.assertTrue(response.get_json()["success"])
        self.assertEqual(response.get_json()["projects"], recent_payload)
        mock_load.assert_called_once()

    def test_set_current_clear_closes_project_session(self):
        captured: dict[str, str | None] = {}
        closed_reasons: list[str] = []

        def get_current_project():
            return {
                "path": session.get("current_project_path", ""),
                "name": session.get("current_project_name", ""),
            }

        def set_current_project(path: str, name: str | None = None):
            captured["path"] = path
            captured["name"] = name

        def save_last_project(path: str | None, name: str | None):
            captured["last_path"] = path
            captured["last_name"] = name

        def close_project_session(*, reason: str = "session_closed"):
            closed_reasons.append(reason)

        with self.app.test_request_context(
            "/api/projects/current",
            method="POST",
            json={"path": ""},
        ):
            session["current_project_path"] = str(self.project_root)
            session["current_project_name"] = "Demo"
            response = self.handle_set_current(
                get_current_project=get_current_project,
                set_current_project=set_current_project,
                save_last_project=save_last_project,
                close_project_session=close_project_session,
            )

        body = response.get_json()
        self.assertTrue(body["success"])
        self.assertEqual(body["current"], {"path": "", "name": ""})
        self.assertEqual(captured.get("last_path"), None)
        self.assertEqual(captured.get("last_name"), None)
        self.assertEqual(closed_reasons, ["project_cleared"])

    def test_set_current_respects_valid_icon_override(self):
        requested_icon = "🧠"
        captured = {}

        def get_current_project():
            return {
                "path": captured.get("path", ""),
                "name": captured.get("name", ""),
                "icon": captured.get("icon", ""),
            }

        def set_current_project(path: str, name: str | None = None):
            captured["path"] = path
            captured["name"] = name

        def save_last_project(path: str | None, name: str | None):
            captured["last_path"] = path
            captured["last_name"] = name

        with self.app.test_request_context(
            "/api/projects/current",
            method="POST",
            json={
                "path": str(self.project_root),
                "name": "Icon Override",
                "icon": requested_icon,
            },
        ):
            response = self.handle_set_current(
                get_current_project=get_current_project,
                set_current_project=set_current_project,
                save_last_project=save_last_project,
            )

        status_code = response[1] if isinstance(response, tuple) else 200
        resp_obj = response[0] if isinstance(response, tuple) else response
        body = resp_obj.get_json()

        self.assertEqual(status_code, 200)
        self.assertTrue(body["success"])
        self.assertEqual(body["current"]["icon"], requested_icon)

        project_payload = json.loads(
            (self.project_root / "project.json").read_text(encoding="utf-8")
        )
        self.assertEqual(project_payload.get("icon"), requested_icon)

    def test_recruitment_location_search_returns_normalized_results(self):
        mocked_payload = {
            "results": [
                {
                    "name": "Graz",
                    "admin1": "Styria",
                    "country": "Austria",
                    "latitude": 47.0707,
                    "longitude": 15.4395,
                    "timezone": "Europe/Vienna",
                }
            ]
        }

        with patch.object(self.module.requests, "get") as mock_get:
            mock_get.return_value.json.return_value = mocked_payload
            mock_get.return_value.raise_for_status.return_value = None

            with self.app.test_request_context(
                "/api/projects/recruitment-location-search?q=graz",
                method="GET",
            ):
                response = self.handle_recruitment_location_search()

        status_code = response[1] if isinstance(response, tuple) else 200
        resp_obj = response[0] if isinstance(response, tuple) else response
        body = resp_obj.get_json()

        self.assertEqual(status_code, 200)
        self.assertTrue(body["success"])
        self.assertEqual(len(body["results"]), 1)
        self.assertEqual(body["results"][0]["display_name"], "Graz, Styria, Austria")

    def test_recruitment_location_search_handles_provider_error(self):
        with patch.object(self.module.requests, "get") as mock_get:
            mock_get.side_effect = self.module.requests.RequestException(
                "provider down"
            )

            with self.app.test_request_context(
                "/api/projects/recruitment-location-search?q=graz",
                method="GET",
            ):
                response = self.handle_recruitment_location_search()

        status_code = response[1] if isinstance(response, tuple) else 200
        resp_obj = response[0] if isinstance(response, tuple) else response
        body = resp_obj.get_json()

        self.assertEqual(status_code, 502)
        self.assertFalse(body["success"])
        self.assertIn("provider down", body["error"])


if __name__ == "__main__":
    unittest.main()
