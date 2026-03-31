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
        self.handle_get_participants_columns = (
            participants_handlers.handle_get_participants_columns
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

    def test_get_participants_columns_reads_utf8_sig_tsv(self):
        participants_tsv = self.project_root / "participants.tsv"
        participants_tsv.write_text(
            "participant_id\tage\tgroup\nsub-001\t21\tcontrol\nsub-002\t22\tpatient\n",
            encoding="utf-8-sig",
        )

        def get_current_project():
            return {
                "path": str(self.project_root / "project.json"),
                "name": "demo_project",
            }

        def get_bids_file_path(project_path: Path, filename: str) -> Path:
            return project_path / filename

        with self.app.test_request_context(
            "/api/projects/participants/columns",
            method="GET",
        ):
            response = self.handle_get_participants_columns(
                get_current_project=get_current_project,
                get_bids_file_path=get_bids_file_path,
            )

        status_code = response[1] if isinstance(response, tuple) else 200
        resp_obj = response[0] if isinstance(response, tuple) else response

        self.assertEqual(status_code, 200)
        body = resp_obj.get_json()
        self.assertEqual(body["columns"]["group"], ["control", "patient"])

    def test_save_schema_canonicalizes_nb_participantid_key(self):
        def get_current_project():
            return {
                "path": str(self.project_root / "project.json"),
                "name": "demo_project",
            }

        def get_bids_file_path(project_path: Path, filename: str) -> Path:
            return project_path / filename

        payload = {
            "schema": {
                "participant_id": {"Description": "Unique participant identifier"},
                "Code": {
                    "Description": "Column: Code",
                    "Annotations": {
                        "IsAbout": {
                            "TermURL": "nb:ParticipantID",
                            "Label": "ParticipantID",
                        },
                        "VariableType": "Text",
                    },
                },
            }
        }

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
        saved = json.loads(participants_json.read_text(encoding="utf-8"))

        self.assertIn("participant_id", saved)
        self.assertNotIn("Code", saved)
        self.assertEqual(
            saved["participant_id"]["Description"],
            "Unique participant identifier",
        )
        self.assertIn("Annotations", saved["participant_id"])
        self.assertEqual(
            saved["participant_id"]["Annotations"]["IsAbout"]["TermURL"],
            "nb:ParticipantID",
        )

    def test_get_participants_columns_falls_back_for_csv_content(self):
        participants_tsv = self.project_root / "participants.tsv"
        participants_tsv.write_text(
            "participant_id,age,group\nsub-001,21,control\nsub-002,22,patient\n",
            encoding="utf-8",
        )

        def get_current_project():
            return {
                "path": str(self.project_root),
                "name": "demo_project",
            }

        def get_bids_file_path(project_path: Path, filename: str) -> Path:
            return project_path / filename

        with self.app.test_request_context(
            "/api/projects/participants/columns",
            method="GET",
        ):
            response = self.handle_get_participants_columns(
                get_current_project=get_current_project,
                get_bids_file_path=get_bids_file_path,
            )

        status_code = response[1] if isinstance(response, tuple) else 200
        resp_obj = response[0] if isinstance(response, tuple) else response

        self.assertEqual(status_code, 200)
        body = resp_obj.get_json()
        self.assertEqual(body["columns"]["group"], ["control", "patient"])

    def test_save_schema_does_not_rewrite_participants_values(self):
        participants_tsv = self.project_root / "participants.tsv"
        participants_tsv.write_text(
            "participant_id\tsex\tage\nsub-001\t1\t21\nsub-002\t2\t22\n",
            encoding="utf-8",
        )

        def get_current_project():
            return {
                "path": str(self.project_root / "project.json"),
                "name": "demo_project",
            }

        def get_bids_file_path(project_path: Path, filename: str) -> Path:
            return project_path / filename

        payload = {
            "schema": {
                "participant_id": {"Description": "Unique participant identifier"},
                "sex": {
                    "Description": "Biological sex",
                    "Levels": {"M": "Male", "F": "Female"},
                },
            },
            "value_rewrite_mappings": {"sex": {"1": "M", "2": "F"}},
        }

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
        self.assertEqual(
            body.get("value_rewrite_summary", {}).get("replacements"),
            0,
        )

        updated_lines = participants_tsv.read_text(encoding="utf-8").splitlines()
        self.assertEqual(updated_lines[1].split("\t")[1], "1")
        self.assertEqual(updated_lines[2].split("\t")[1], "2")


if __name__ == "__main__":
    unittest.main()
