import unittest
import sys
import os
import shutil
import tempfile
import json
import io
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace
import requests
import pandas as pd
from flask import Flask, jsonify, session
from unittest.mock import patch, MagicMock

# ----------------------------------------------------------------------
# Setup Path & Mocks
# ----------------------------------------------------------------------

# Ensure 'app' is in sys.path so 'src' can be imported
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(current_dir)
app_path = os.path.join(project_root, "app")

if app_path not in sys.path:
    sys.path.insert(0, app_path)

_ORIGINAL_MODULES = {}
_MOCKED_MODULES = {
    "src.web.validation": MagicMock(),
    "src.web.services.project_registration": MagicMock(),
    "src.converters.biometrics": MagicMock(),
    "src.converters.id_detection": MagicMock(),
    "helpers.physio.convert_varioport": MagicMock(),
    "src.batch_convert": MagicMock(),
}


def setUpModule():
    global _ORIGINAL_MODULES
    _ORIGINAL_MODULES = {
        module_name: sys.modules.get(module_name) for module_name in _MOCKED_MODULES
    }
    sys.modules.update(_MOCKED_MODULES)


def tearDownModule():
    for module_name, original in _ORIGINAL_MODULES.items():
        if original is None:
            sys.modules.pop(module_name, None)
        else:
            sys.modules[module_name] = original


# Now import the blueprint & handlers
try:
    from src.web.blueprints import conversion as conversion_module
    from src.web.blueprints import conversion_biometrics_handlers as biometrics_module
    from src.web.blueprints import conversion_environment_handlers as environment_module
    from src.web.blueprints import conversion_physio_handlers as physio_module
    from src.web.blueprints import (
        conversion_participants_blueprint as participants_module,
    )
    from src.web.blueprints.conversion import conversion_bp
    from src.web.blueprints.conversion_biometrics_handlers import (
        api_biometrics_check_library,
    )
    from src.web.blueprints.conversion_physio_handlers import check_sourcedata_physio
except ImportError as e:
    print(f"Failed to import modules: {e}")
    print(f"sys.path: {sys.path}")
    raise

# ----------------------------------------------------------------------
# Test Classes
# ----------------------------------------------------------------------


class TestConversionBlueprintDelegation(unittest.TestCase):
    """Verify that the blueprint routes delegate to the extracted handler functions."""

    def setUp(self):
        self.app = Flask(__name__)
        self.app.register_blueprint(conversion_bp)
        self.client = self.app.test_client()

    @patch.object(conversion_module, "_api_biometrics_check_library")
    def test_api_biometrics_check_library_delegation(self, mock_handler):
        mock_handler.return_value = "mock_response"
        response = self.client.get("/api/biometrics-check-library")
        mock_handler.assert_called_once()
        self.assertEqual(response.data.decode(), "mock_response")

    @patch.object(conversion_module, "_api_biometrics_detect")
    def test_api_biometrics_detect_delegation(self, mock_handler):
        mock_handler.return_value = "mock_response"
        self.client.post("/api/biometrics-detect")
        mock_handler.assert_called_once()

    @patch.object(conversion_module, "_api_biometrics_convert")
    def test_api_biometrics_convert_delegation(self, mock_handler):
        mock_handler.return_value = "mock_response"
        self.client.post("/api/biometrics-convert")
        mock_handler.assert_called_once()

    @patch.object(conversion_module, "_check_sourcedata_physio")
    def test_check_sourcedata_physio_delegation(self, mock_handler):
        mock_handler.return_value = "mock_response"
        self.client.get("/api/check-sourcedata-physio")
        mock_handler.assert_called_once()

    @patch.object(conversion_module, "_api_physio_convert")
    def test_api_physio_convert_delegation(self, mock_handler):
        mock_handler.return_value = "mock_response"
        self.client.post("/api/physio-convert")
        mock_handler.assert_called_once()

    @patch.object(conversion_module, "_api_environment_convert_start")
    def test_api_environment_convert_start_delegation(self, mock_handler):
        mock_handler.return_value = "mock_response"
        self.client.post("/api/environment-convert-start")
        mock_handler.assert_called_once()

    @patch.object(conversion_module, "_api_environment_convert_status")
    def test_api_environment_convert_status_delegation(self, mock_handler):
        mock_handler.return_value = "mock_response"
        self.client.get("/api/environment-convert-status/test-job")
        mock_handler.assert_called_once_with("test-job")

    @patch.object(conversion_module, "_api_batch_convert_metrics")
    def test_api_batch_convert_metrics_delegation(self, mock_handler):
        mock_handler.return_value = "mock_response"
        self.client.get("/api/batch-convert-metrics")
        mock_handler.assert_called_once()

    @patch.object(conversion_module, "_api_environment_convert_metrics")
    def test_api_environment_convert_metrics_delegation(self, mock_handler):
        mock_handler.return_value = "mock_response"
        self.client.get("/api/environment-convert-metrics")
        mock_handler.assert_called_once()


class TestValidationLibraryResolution(unittest.TestCase):
    """Ensure validation uses one context (project or fallback), never mixed."""

    def test_prefers_project_code_library_for_validation(self):
        import importlib

        conversion_utils = importlib.import_module(
            "src.web.blueprints.conversion_utils"
        )

        with tempfile.TemporaryDirectory() as tmp:
            project_root = Path(tmp) / "project"
            (project_root / "code" / "library").mkdir(parents=True, exist_ok=True)
            fallback = Path(tmp) / "official" / "library"
            fallback.mkdir(parents=True, exist_ok=True)

            resolved = conversion_utils.resolve_validation_library_path(
                project_path=str(project_root),
                fallback_library_root=fallback,
            )

            self.assertEqual(
                resolved.resolve(),
                (project_root / "code" / "library").resolve(),
            )

    def test_uses_fallback_without_project_library(self):
        import importlib

        conversion_utils = importlib.import_module(
            "src.web.blueprints.conversion_utils"
        )

        with tempfile.TemporaryDirectory() as tmp:
            project_root = Path(tmp) / "project"
            project_root.mkdir(parents=True, exist_ok=True)
            fallback = Path(tmp) / "official" / "library"
            fallback.mkdir(parents=True, exist_ok=True)

            resolved = conversion_utils.resolve_validation_library_path(
                project_path=str(project_root),
                fallback_library_root=fallback,
            )

            self.assertEqual(resolved.resolve(), fallback.resolve())


class TestBiometricsHandlersLogic(unittest.TestCase):
    """Verify the logic of the extracted biometrics handlers."""

    def setUp(self):
        self.app = Flask(__name__)
        self.temp_dir = tempfile.mkdtemp()
        self.library_path = Path(self.temp_dir)

        # Create standard structure
        (self.library_path / "biometrics").mkdir(exist_ok=True)
        (self.library_path / "survey").mkdir(exist_ok=True)
        (self.library_path / "participants.json").touch()
        (self.library_path / "biometrics" / "biometrics-task1.json").touch()

    def tearDown(self):
        shutil.rmtree(self.temp_dir)

    def test_api_biometrics_check_library_valid(self):
        with self.app.test_request_context(
            query_string={"library_path": str(self.library_path)}
        ):
            # Call handler
            response = api_biometrics_check_library()
            # If it's a tuple (response, code), unpack it
            if isinstance(response, tuple):
                response = response[0]

            data = response.get_json()
            self.assertTrue(data["structure"]["has_biometrics_folder"])
            self.assertTrue(data["structure"]["has_survey_folder"])
            self.assertTrue(data["structure"]["has_participants_json"])
            self.assertEqual(data["structure"]["template_count"], 1)

    def test_api_biometrics_check_library_missing_path(self):
        with self.app.test_request_context():
            response = api_biometrics_check_library()
            code = 200
            if isinstance(response, tuple):
                response, code = response

            self.assertEqual(code, 400)
            self.assertIn("No library path", response.get_json()["error"])


class TestPhysioHandlersLogic(unittest.TestCase):
    """Verify the logic of the extracted physio handlers."""

    def setUp(self):
        self.app = Flask(__name__)
        self.app.secret_key = "test_secret"  # pragma: allowlist secret
        self.temp_dir = tempfile.mkdtemp()
        self.project_path = Path(self.temp_dir)

        # Create standard structure
        (self.project_path / "sourcedata").mkdir()
        (self.project_path / "sourcedata" / "physio").mkdir()

    def tearDown(self):
        shutil.rmtree(self.temp_dir)

    def test_check_sourcedata_physio_exists(self):
        with self.app.test_request_context():
            # Mock session
            with patch.object(physio_module, "session", dict()) as mock_session:
                mock_session["current_project_path"] = str(self.project_path)

                response = check_sourcedata_physio()
                # Unpack if tuple
                if isinstance(response, tuple):
                    response = response[0]

                data = response.get_json()
                self.assertTrue(data["exists"])
                self.assertIn("sourcedata/physio", data["path"])

    def test_check_sourcedata_physio_missing_project(self):
        with self.app.test_request_context():
            with patch.object(physio_module, "session", dict()) as mock_session:
                # No project path in session
                response = check_sourcedata_physio()
                code = 200
                if isinstance(response, tuple):
                    response, code = response

                self.assertEqual(code, 400)
                self.assertFalse(response.get_json()["exists"])

    def test_extract_subject_session_from_folder_path(self):
        subject, session = physio_module._extract_subject_session_from_source_path(
            "sub-07/ses-03/VPDATA.RAW"
        )
        self.assertEqual(subject, "07")
        self.assertEqual(session, "03")

    def test_extract_subject_session_from_generic_folders(self):
        subject, session = physio_module._extract_subject_session_from_source_path(
            "P001/baseline/VPDATA.RAW"
        )
        self.assertEqual(subject, "P001")
        self.assertEqual(session, "baseline")

    def test_extract_subject_session_from_folder_levels(self):
        subject, session = physio_module._extract_subject_session_from_source_path(
            "VPDATA/135/t1/VPDATA.RAW",
            subject_level_from_end=2,
            session_level_from_end=1,
        )
        self.assertEqual(subject, "135")
        self.assertEqual(session, "t1")

    def test_extract_subject_session_from_explicit_example_strings(self):
        subject, session = physio_module._extract_subject_session_from_source_path(
            "VPDATA/132/t3/VPDATA.RAW",
            subject_level_from_end=2,
            session_level_from_end=1,
            example_path="VPDATA/135/t1/VPDATA.RAW",
            subject_example_value="135",
            session_example_value="1",
        )
        self.assertEqual(subject, "132")
        self.assertEqual(session, "03")

    def test_extract_subject_from_explicit_example_without_session(self):
        subject, session = physio_module._extract_subject_session_from_source_path(
            "VPDATA/132/VPDATA.RAW",
            subject_level_from_end=1,
            session_level_from_end=1,
            example_path="VPDATA/135/VPDATA.RAW",
            subject_example_value="135",
            session_example_value="",
        )
        self.assertEqual(subject, "132")
        self.assertIsNone(session)

    def test_apply_folder_placeholders_without_session(self):
        name = physio_module._apply_folder_placeholders(
            "sub-{subject}_ses-{session}_task-rest_physio.raw",
            "sub-99/VPDATA.RAW",
        )
        self.assertEqual(name, "sub-99_task-rest_physio.raw")

    def test_apply_folder_placeholders_with_level_and_string_mapping(self):
        name = physio_module._apply_folder_placeholders(
            "sub-{subject}_ses-{session}_task-rest_physio.raw",
            "VPDATA/135/t1/VPDATA.RAW",
            subject_level_from_end=2,
            session_level_from_end=1,
            example_path="VPDATA/031/t2/VPDATA.RAW",
            subject_example_value="031",
            session_example_value="2",
        )
        self.assertEqual(name, "sub-135_ses-01_task-rest_physio.raw")


class TestSurveyConverterImports(unittest.TestCase):
    """Regression tests for survey converter module availability in Web UI."""

    def test_survey_converter_module_imports(self):
        import importlib

        module = importlib.import_module("src.converters.survey")
        self.assertIsNotNone(module)
        self.assertTrue(hasattr(module, "convert_survey_xlsx_to_prism_dataset"))

    def test_survey_template_loader_accepts_injected_kwargs(self):
        import importlib

        survey_templates = importlib.import_module("src.converters.survey_templates")

        with tempfile.TemporaryDirectory() as tmp:
            lib = Path(tmp)
            (lib / "survey-demo.json").write_text("{}", encoding="utf-8")

            templates, item_to_task, duplicates, warnings = (
                survey_templates._load_and_preprocess_templates(
                    library_dir=lib,
                    canonical_aliases=None,
                    compare_with_global=False,
                    load_global_library_path_fn=lambda: None,
                    load_global_templates_fn=lambda: {},
                    is_participant_template_fn=lambda _: False,
                    read_json_fn=lambda _: {"Study": {"TaskName": "demo"}},
                    canonicalize_template_items_fn=lambda sidecar, canonical_aliases: (
                        sidecar
                    ),
                    non_item_keys={"Study", "_aliases", "_reverse_aliases"},
                    find_matching_global_template_fn=lambda *_: (
                        None,
                        False,
                        set(),
                        set(),
                    ),
                )
            )

            self.assertIn("demo", templates)
            self.assertIsInstance(item_to_task, dict)
            self.assertEqual(duplicates, {})
            self.assertEqual(warnings, {})

    def test_survey_converter_default_authors_non_empty(self):
        import importlib

        survey_module = importlib.import_module("src.converters.survey")

        with tempfile.TemporaryDirectory() as tmp:
            output_root = Path(tmp)
            survey_module._write_survey_description(output_root, None, None)
            payload = json.loads(
                (output_root / "dataset_description.json").read_text(encoding="utf-8")
            )
            self.assertTrue(payload.get("Authors"))


class TestSurveyOfficialTemplateCopy(unittest.TestCase):
    """Regression tests for official -> project survey template copy behavior."""

    def test_fallback_copy_runs_for_non_dry_run(self):
        import importlib

        handlers = importlib.import_module(
            "src.web.blueprints.conversion_survey_handlers"
        )

        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            official_dir = tmp_path / "official" / "library" / "survey"
            official_dir.mkdir(parents=True, exist_ok=True)
            (official_dir / "survey-ads.json").write_text("{}", encoding="utf-8")

            project_root = tmp_path / "project"
            project_root.mkdir(parents=True, exist_ok=True)

            calls = {"count": 0}

            def fake_converter(*, library_dir, **kwargs):
                calls["count"] += 1
                if calls["count"] == 1:
                    raise RuntimeError("no templates matched")
                return SimpleNamespace(tasks_included=["ads"])

            with (
                patch.object(
                    handlers,
                    "_should_retry_with_official_library",
                    return_value=True,
                ),
                patch.object(
                    handlers,
                    "_resolve_official_survey_dir",
                    return_value=official_dir,
                ),
            ):
                result = handlers._run_survey_with_official_fallback(
                    fake_converter,
                    library_dir=str(tmp_path / "empty_library"),
                    fallback_project_path=str(project_root),
                    dry_run=False,
                )

            self.assertEqual(calls["count"], 2)
            self.assertEqual(result.tasks_included, ["ads"])
            copied = project_root / "code" / "library" / "survey" / "survey-ads.json"
            self.assertTrue(copied.exists())

    def test_direct_source_copy_runs_without_fallback(self):
        import importlib
        import json

        handlers = importlib.import_module(
            "src.web.blueprints.conversion_survey_handlers"
        )

        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            source_dir = tmp_path / "official" / "library" / "survey"
            source_dir.mkdir(parents=True, exist_ok=True)
            (source_dir / "survey-phq9.json").write_text(
                json.dumps({"Study": {"OriginalName": "PHQ-9"}}),
                encoding="utf-8",
            )

            project_root = tmp_path / "project"
            project_root.mkdir(parents=True, exist_ok=True)

            def fake_converter(*, library_dir, **kwargs):
                return SimpleNamespace(tasks_included=["phq9"])

            result = handlers._run_survey_with_official_fallback(
                fake_converter,
                library_dir=str(source_dir),
                fallback_project_path=str(project_root),
                dry_run=False,
            )

            self.assertEqual(result.tasks_included, ["phq9"])
            copied = project_root / "code" / "library" / "survey" / "survey-phq9.json"
            self.assertTrue(copied.exists())

            copied_payload = json.loads(copied.read_text(encoding="utf-8"))
            self.assertEqual(copied_payload["Technical"]["SoftwarePlatform"], "")
            self.assertEqual(copied_payload["Study"]["TaskName"], "phq9")
            self.assertEqual(copied_payload["Study"]["LicenseID"], "unknown")

    def test_project_template_validation_flags_missing_required_fields(self):
        import importlib
        import json

        handlers = importlib.import_module(
            "src.web.blueprints.conversion_survey_handlers"
        )

        with tempfile.TemporaryDirectory() as tmp:
            project_root = Path(tmp) / "project"
            template_dir = project_root / "code" / "library" / "survey"
            template_dir.mkdir(parents=True, exist_ok=True)

            # Intentionally missing Study.TaskName, Study.LicenseID, and Technical.SoftwarePlatform
            (template_dir / "survey-pss.json").write_text(
                json.dumps(
                    {
                        "Technical": {
                            "StimulusType": "Questionnaire",
                            "FileFormat": "tsv",
                            "Language": "en",
                            "Respondent": "self",
                        },
                        "Study": {"OriginalName": "PSS"},
                        "Metadata": {
                            "SchemaVersion": "1.1.1",
                            "CreationDate": "2026-03-05",
                        },
                    }
                ),
                encoding="utf-8",
            )

            issues = handlers._validate_project_templates_for_tasks(
                tasks=["pss"],
                project_path=str(project_root),
                schema_version="stable",
            )

            self.assertTrue(issues)
            issue_text = "\n".join(i.get("message", "") for i in issues)
            self.assertIn("SoftwarePlatform", issue_text)
            self.assertIn("TaskName", issue_text)
            self.assertIn("LicenseID", issue_text)

    def test_project_template_version_required_when_project_has_multiple_versions(
        self,
    ):
        import importlib
        import json

        handlers = importlib.import_module(
            "src.web.blueprints.conversion_survey_handlers"
        )

        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            project_root = tmp_path / "project"
            template_dir = project_root / "code" / "library" / "survey"
            template_dir.mkdir(parents=True, exist_ok=True)

            # Project template defines multiple versions but omits Study.Version.
            (template_dir / "survey-pss.json").write_text(
                json.dumps(
                    {
                        "Technical": {
                            "StimulusType": "Questionnaire",
                            "FileFormat": "tsv",
                            "SoftwarePlatform": "LimeSurvey",
                            "SoftwareVersion": "6.0",
                            "Language": "en",
                            "Respondent": "self",
                            "AdministrationMethod": "online",
                        },
                        "Study": {
                            "TaskName": "pss",
                            "OriginalName": "PSS",
                            "Citation": "Cohen et al.",
                            "License": "Proprietary",
                            "LicenseID": "Proprietary",
                            "Versions": ["short", "long"],
                        },
                        "Metadata": {
                            "SchemaVersion": "1.1.1",
                            "CreationDate": "2026-03-05",
                        },
                    }
                ),
                encoding="utf-8",
            )

            issues = handlers._validate_project_templates_for_tasks(
                tasks=["pss"],
                project_path=str(project_root),
                schema_version="stable",
            )

            issue_text = "\n".join(i.get("message", "") for i in issues)
            self.assertIn("Study -> Version", issue_text)

    def test_project_template_version_not_required_when_project_has_single_version(
        self,
    ):
        import importlib
        import json

        handlers = importlib.import_module(
            "src.web.blueprints.conversion_survey_handlers"
        )

        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            project_root = tmp_path / "project"
            template_dir = project_root / "code" / "library" / "survey"
            template_dir.mkdir(parents=True, exist_ok=True)

            # Project template defines a single version and omits Study.Version.
            (template_dir / "survey-pss.json").write_text(
                json.dumps(
                    {
                        "Technical": {
                            "StimulusType": "Questionnaire",
                            "FileFormat": "tsv",
                            "SoftwarePlatform": "Paper and Pencil",
                            "Language": "de-AT",
                            "Respondent": "self",
                            "AdministrationMethod": "paper",
                        },
                        "Study": {
                            "TaskName": "pss",
                            "OriginalName": "PSS",
                            "Citation": "Cohen et al.",
                            "License": "Proprietary",
                            "LicenseID": "Proprietary",
                            "Versions": ["short"],
                        },
                        "Metadata": {
                            "SchemaVersion": "1.1.1",
                            "CreationDate": "2026-03-05",
                        },
                    }
                ),
                encoding="utf-8",
            )

            issues = handlers._validate_project_templates_for_tasks(
                tasks=["pss"],
                project_path=str(project_root),
                schema_version="stable",
            )

            issue_text = "\n".join(i.get("message", "") for i in issues)
            self.assertNotIn("Study -> Version", issue_text)

    def test_template_completion_gate_payload(self):
        import importlib

        handlers = importlib.import_module(
            "src.web.blueprints.conversion_survey_handlers"
        )

        gate = handlers._build_template_completion_gate(
            tasks=["pss", "pss", "ads"],
            issues=[{"file": "survey-pss.json", "message": "missing"}],
        )

        self.assertTrue(gate["blocked"])
        self.assertEqual(gate["reason"], "project_template_completion_required")
        self.assertEqual(gate["tasks"], ["ads", "pss"])
        self.assertEqual(gate["issue_count"], 1)
        self.assertGreaterEqual(len(gate.get("next_steps", [])), 3)

    def test_api_survey_convert_blocks_until_templates_completed(self):
        import importlib

        handlers = importlib.import_module(
            "src.web.blueprints.conversion_survey_handlers"
        )

        app = Flask(__name__)
        app.secret_key = "test-secret"  # pragma: allowlist secret
        app.add_url_rule(
            "/api/survey-convert",
            view_func=handlers.api_survey_convert,
            methods=["POST"],
        )

        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            library_root = tmp_path / "library"
            survey_dir = library_root / "survey"
            survey_dir.mkdir(parents=True, exist_ok=True)
            (survey_dir / "survey-pss.json").write_text("{}", encoding="utf-8")

            project_root = tmp_path / "project"
            project_root.mkdir(parents=True, exist_ok=True)

            with (
                patch.object(
                    handlers,
                    "_resolve_effective_library_path",
                    return_value=library_root,
                ),
                patch.object(
                    handlers,
                    "_run_survey_with_official_fallback",
                    return_value=SimpleNamespace(tasks_included=["pss"]),
                ),
                patch.object(
                    handlers,
                    "_validate_project_templates_for_tasks",
                    return_value=[
                        {
                            "file": str(
                                project_root
                                / "code"
                                / "library"
                                / "survey"
                                / "survey-pss.json"
                            ),
                            "message": "Study.TaskName is a required property",
                        }
                    ],
                ),
            ):
                with app.test_client() as client:
                    with client.session_transaction() as sess:
                        sess["current_project_path"] = str(project_root)

                    response = client.post(
                        "/api/survey-convert",
                        data={
                            "file": (io.BytesIO(b"dummy"), "input.xlsx"),
                            "session": "01",
                        },
                        content_type="multipart/form-data",
                    )

            self.assertEqual(response.status_code, 409)
            payload = response.get_json()
            self.assertEqual(
                payload.get("error"), "project_template_completion_required"
            )
            self.assertTrue(payload.get("workflow_gate", {}).get("blocked"))
            self.assertEqual(payload.get("workflow_gate", {}).get("tasks"), ["pss"])


class TestSurveyProjectTemplateCheckEndpoint(unittest.TestCase):
    """Tests for explicit local project template pre-check endpoint."""

    def test_requires_selected_project(self):
        import importlib

        handlers = importlib.import_module(
            "src.web.blueprints.conversion_survey_handlers"
        )

        app = Flask(__name__)
        app.secret_key = "test-secret"  # pragma: allowlist secret
        app.add_url_rule(
            "/api/survey-check-project-templates",
            view_func=handlers.api_survey_check_project_templates,
            methods=["GET"],
        )

        with app.test_client() as client:
            response = client.get("/api/survey-check-project-templates")

        self.assertEqual(response.status_code, 400)
        payload = response.get_json()
        self.assertEqual(payload.get("error"), "No project selected")

    def test_reports_issues_with_workflow_gate(self):
        import importlib

        handlers = importlib.import_module(
            "src.web.blueprints.conversion_survey_handlers"
        )

        app = Flask(__name__)
        app.secret_key = "test-secret"  # pragma: allowlist secret
        app.add_url_rule(
            "/api/survey-check-project-templates",
            view_func=handlers.api_survey_check_project_templates,
            methods=["GET"],
        )

        with tempfile.TemporaryDirectory() as tmp:
            project_root = Path(tmp) / "project"
            template_dir = project_root / "code" / "library" / "survey"
            template_dir.mkdir(parents=True, exist_ok=True)
            (template_dir / "survey-pss.json").write_text("{}", encoding="utf-8")

            mocked_issues = [
                {
                    "file": str(template_dir / "survey-pss.json"),
                    "message": "Study.TaskName is a required property",
                }
            ]

            with patch.object(
                handlers,
                "_validate_project_templates_for_tasks",
                return_value=mocked_issues,
            ):
                with app.test_client() as client:
                    with client.session_transaction() as sess:
                        sess["current_project_path"] = str(project_root)

                    response = client.get("/api/survey-check-project-templates")

            self.assertEqual(response.status_code, 200)
            payload = response.get_json()
            self.assertFalse(payload.get("ok"))
            self.assertEqual(payload.get("template_count"), 1)
            self.assertEqual(payload.get("local_templates"), ["pss"])
            self.assertEqual(payload.get("tasks"), ["pss"])
            self.assertEqual(len(payload.get("issues", [])), 1)
            self.assertTrue(payload.get("workflow_gate", {}).get("blocked"))

    def test_post_with_input_returns_matching_summary(self):
        import importlib

        handlers = importlib.import_module(
            "src.web.blueprints.conversion_survey_handlers"
        )

        app = Flask(__name__)
        app.secret_key = "test-secret"  # pragma: allowlist secret
        app.add_url_rule(
            "/api/survey-check-project-templates",
            view_func=handlers.api_survey_check_project_templates,
            methods=["GET", "POST"],
        )

        with tempfile.TemporaryDirectory() as tmp:
            project_root = Path(tmp) / "project"
            template_dir = project_root / "code" / "library" / "survey"
            template_dir.mkdir(parents=True, exist_ok=True)
            (template_dir / "survey-wellbeing.json").write_text("{}", encoding="utf-8")

            with patch.object(
                handlers,
                "_infer_tasks_against_official_templates",
                return_value={
                    "tasks": ["wellbeing"],
                    "copied_tasks": ["wellbeing"],
                    "existing_tasks": [],
                    "missing_official_tasks": [],
                    "official_template_count": 110,
                    "match_error": None,
                },
            ):
                with patch.object(
                    handlers,
                    "_validate_project_templates_for_tasks",
                    return_value=[],
                ):
                    with app.test_client() as client:
                        with client.session_transaction() as sess:
                            sess["current_project_path"] = str(project_root)

                        response = client.post(
                            "/api/survey-check-project-templates",
                            data={
                                "excel": (
                                    io.BytesIO(b"id,wellbeing_q1\n1,5\n"),
                                    "input.csv",
                                ),
                                "id_column": "id",
                            },
                            content_type="multipart/form-data",
                        )

            self.assertEqual(response.status_code, 200)
            payload = response.get_json()
            self.assertTrue(payload.get("ok"))
            self.assertEqual(payload.get("local_templates"), ["wellbeing"])
            self.assertEqual(payload.get("tasks"), ["wellbeing"])
            self.assertEqual(
                payload.get("matching", {}).get("matched_tasks"), ["wellbeing"]
            )
            self.assertEqual(
                payload.get("matching", {}).get("official_template_count"), 110
            )

    def test_reports_levels_minmax_template_warning(self):
        import importlib

        handlers = importlib.import_module(
            "src.web.blueprints.conversion_survey_handlers"
        )

        app = Flask(__name__)
        app.secret_key = "test-secret"  # pragma: allowlist secret
        app.add_url_rule(
            "/api/survey-check-project-templates",
            view_func=handlers.api_survey_check_project_templates,
            methods=["GET"],
        )

        with tempfile.TemporaryDirectory() as tmp:
            project_root = Path(tmp) / "project"
            template_dir = project_root / "code" / "library" / "survey"
            template_dir.mkdir(parents=True, exist_ok=True)

            template_payload = {
                "Study": {"TaskName": "maia"},
                "MAI16": {
                    "Description": "Item text",
                    "Levels": {"0": "never", "1": "always"},
                    "MinValue": 0,
                    "MaxValue": 5,
                },
            }
            (template_dir / "survey-maia.json").write_text(
                json.dumps(template_payload), encoding="utf-8"
            )

            with patch.object(
                handlers,
                "_validate_project_templates_for_tasks",
                return_value=[],
            ):
                with app.test_client() as client:
                    with client.session_transaction() as sess:
                        sess["current_project_path"] = str(project_root)

                    response = client.get("/api/survey-check-project-templates")

            self.assertEqual(response.status_code, 200)
            payload = response.get_json()
            self.assertTrue(payload.get("ok"))
            warnings = payload.get("warnings") or []
            self.assertEqual(len(warnings), 1)
            self.assertIn("Levels and Min/Max", warnings[0].get("message", ""))

    def test_warning_scan_includes_local_templates_beyond_tasks_covered(self):
        import importlib

        handlers = importlib.import_module(
            "src.web.blueprints.conversion_survey_handlers"
        )

        app = Flask(__name__)
        app.secret_key = "test-secret"  # pragma: allowlist secret
        app.add_url_rule(
            "/api/survey-check-project-templates",
            view_func=handlers.api_survey_check_project_templates,
            methods=["POST"],
        )

        with tempfile.TemporaryDirectory() as tmp:
            project_root = Path(tmp) / "project"
            template_dir = project_root / "code" / "library" / "survey"
            template_dir.mkdir(parents=True, exist_ok=True)

            (template_dir / "survey-pss.json").write_text("{}", encoding="utf-8")
            (template_dir / "survey-maia.json").write_text(
                json.dumps(
                    {
                        "Study": {"TaskName": "maia"},
                        "MAI16": {
                            "Description": "Item text",
                            "Levels": {"0": "never", "1": "always"},
                            "MinValue": 0,
                            "MaxValue": 5,
                        },
                    }
                ),
                encoding="utf-8",
            )

            with patch.object(
                handlers,
                "_infer_tasks_against_official_templates",
                return_value={
                    "tasks": ["pss"],
                    "copied_tasks": [],
                    "existing_tasks": ["pss"],
                    "missing_official_tasks": [],
                    "official_template_count": 110,
                    "match_error": None,
                },
            ):
                with patch.object(
                    handlers,
                    "_validate_project_templates_for_tasks",
                    return_value=[],
                ):
                    with app.test_client() as client:
                        with client.session_transaction() as sess:
                            sess["current_project_path"] = str(project_root)

                        response = client.post(
                            "/api/survey-check-project-templates",
                            data={
                                "excel": (
                                    io.BytesIO(b"id,pss_q1\n1,1\n"),
                                    "T1.csv",
                                ),
                                "id_column": "id",
                            },
                            content_type="multipart/form-data",
                        )

            self.assertEqual(response.status_code, 200)
            payload = response.get_json()
            self.assertTrue(payload.get("ok"))
            self.assertEqual(payload.get("tasks"), ["pss"])
            warnings = payload.get("warnings") or []
            self.assertEqual(len(warnings), 1)
            self.assertIn("maia", warnings[0].get("message", "").lower())


class TestBiometricsOfficialTemplateCopy(unittest.TestCase):
    """Regression tests for biometrics template copy behavior."""

    def test_copy_biometrics_templates_to_project(self):
        import importlib

        handlers = importlib.import_module(
            "src.web.blueprints.conversion_biometrics_handlers"
        )

        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            source_dir = tmp_path / "official" / "library" / "biometrics"
            source_dir.mkdir(parents=True, exist_ok=True)
            (source_dir / "biometrics-ecg.json").write_text("{}", encoding="utf-8")

            project_root = tmp_path / "project"
            project_root.mkdir(parents=True, exist_ok=True)

            handlers._copy_biometrics_templates_to_project(
                source_dir=source_dir,
                tasks=["ecg"],
                project_path=str(project_root),
                log_fn=lambda *_: None,
            )

            copied = (
                project_root / "code" / "library" / "biometrics" / "biometrics-ecg.json"
            )
            self.assertTrue(copied.exists())


class TestSurveySidecarDefaults(unittest.TestCase):
    """Regression tests for required survey sidecar defaults."""

    def test_write_task_sidecars_injects_missing_software_platform(self):
        import importlib

        survey_io = importlib.import_module("src.converters.survey_io")

        with tempfile.TemporaryDirectory() as tmp:
            dataset_root = Path(tmp)

            def write_json(path, payload):
                path.write_text(json.dumps(payload), encoding="utf-8")

            survey_io._write_task_sidecars(
                tasks_with_data={"pss"},
                dataset_root=dataset_root,
                templates={"pss": {"json": {"Study": {"TaskName": "pss"}}}},
                task_acq_map={"pss": None},
                language=None,
                force=True,
                technical_overrides=None,
                missing_token="n/a",
                localize_survey_template_fn=lambda template, language: template,
                inject_missing_token_fn=lambda template, token: template,
                apply_technical_overrides_fn=lambda template, overrides: template,
                strip_internal_keys_fn=lambda template: template,
                write_json_fn=write_json,
            )

            payload = json.loads(
                (dataset_root / "task-pss_survey.json").read_text(encoding="utf-8")
            )
            self.assertIn("Technical", payload)
            self.assertIn("SoftwarePlatform", payload["Technical"])
            self.assertEqual(payload["Technical"]["SoftwarePlatform"], "")

    def test_write_task_sidecars_uses_acq_variant_filename(self):
        import importlib

        survey_io = importlib.import_module("src.converters.survey_io")

        with tempfile.TemporaryDirectory() as tmp:
            dataset_root = Path(tmp)

            def write_json(path, payload):
                path.write_text(json.dumps(payload), encoding="utf-8")

            survey_io._write_task_sidecars(
                tasks_with_data={"pss"},
                dataset_root=dataset_root,
                templates={"pss": {"json": {"Study": {"TaskName": "pss"}}}},
                task_acq_map={"pss": "10-item"},
                language=None,
                force=True,
                technical_overrides=None,
                missing_token="n/a",
                localize_survey_template_fn=lambda template, language: template,
                inject_missing_token_fn=lambda template, token: template,
                apply_technical_overrides_fn=lambda template, overrides: template,
                strip_internal_keys_fn=lambda template: template,
                write_json_fn=write_json,
            )

            self.assertTrue(
                (dataset_root / "task-pss_acq-10-item_survey.json").exists()
            )


class TestParticipantsSchemaMerge(unittest.TestCase):
    """Regression tests for participants NeuroBagel merge behavior."""

    def test_merge_neurobagel_schema_only_includes_allowed_columns(self):
        base = {
            "participant_id": {"Description": "Unique participant identifier"},
            "group": {"Description": "Participant group"},
        }
        nb_schema = {
            "group": {
                "Annotations": {
                    "IsAbout": {"TermURL": "nb:Diagnosis", "Label": "diagnosis"}
                }
            },
            "diagnosis": {"Description": "Should not be added when missing from TSV"},
        }

        messages = []

        def _logger(level, message):
            messages.append((level, message))

        merged, merged_count = participants_module._merge_neurobagel_schema_for_columns(
            base_schema=base,
            neurobagel_schema=nb_schema,
            allowed_columns=["participant_id", "group"],
            log_callback=_logger,
        )

        self.assertEqual(merged_count, 1)
        self.assertIn("group", merged)
        self.assertNotIn("diagnosis", merged)
        self.assertIn("Annotations", merged["group"])
        self.assertTrue(
            any(
                "Skipped annotation-only field 'diagnosis'" in msg
                for _, msg in messages
            )
        )

    def test_merge_preserves_existing_base_fields(self):
        base = {"age": {"Description": "Participant age"}}
        nb_schema = {
            "age": {
                "Description": "Alternative description",
                "Unit": "years",
                "Annotations": {"VariableType": "Continuous"},
            }
        }

        merged, merged_count = participants_module._merge_neurobagel_schema_for_columns(
            base_schema=base,
            neurobagel_schema=nb_schema,
            allowed_columns=["age"],
        )

        self.assertEqual(merged_count, 1)
        self.assertEqual(merged["age"]["Description"], "Participant age")
        self.assertEqual(merged["age"]["Unit"], "years")
        self.assertEqual(
            merged["age"]["Annotations"]["VariableType"],
            "Continuous",
        )

    def test_rekey_schema_maps_source_columns_to_output_columns(self):
        mapping = {
            "mappings": {
                "participant_id": {
                    "source_column": "Code",
                    "standard_variable": "participant_id",
                }
            }
        }
        nb_schema = {
            "Code": {
                "Description": "Column: Code",
                "Annotations": {
                    "IsAbout": {
                        "TermURL": "nb:ParticipantID",
                        "Label": "Participant ID",
                    }
                },
            }
        }

        aligned = participants_module._rekey_neurobagel_schema_to_output_columns(
            neurobagel_schema=nb_schema,
            mapping=mapping,
            allowed_columns=["participant_id", "age"],
        )

        self.assertIn("participant_id", aligned)
        self.assertNotIn("Code", aligned)
        self.assertEqual(aligned["participant_id"]["Description"], "Column: Code")

    def test_rekeyed_schema_merge_sets_participant_id_description(self):
        mapping = {
            "mappings": {
                "participant_id": {
                    "source_column": "Code",
                    "standard_variable": "participant_id",
                }
            }
        }
        nb_schema = {
            "Code": {
                "Description": "Column: Code",
                "Annotations": {
                    "IsAbout": {
                        "TermURL": "nb:ParticipantID",
                        "Label": "Participant ID",
                    }
                },
            }
        }

        aligned = participants_module._rekey_neurobagel_schema_to_output_columns(
            neurobagel_schema=nb_schema,
            mapping=mapping,
            allowed_columns=["participant_id"],
        )
        merged, merged_count = participants_module._merge_neurobagel_schema_for_columns(
            base_schema={"participant_id": {}},
            neurobagel_schema=aligned,
            allowed_columns=["participant_id"],
        )

        self.assertEqual(merged_count, 1)
        self.assertEqual(merged["participant_id"]["Description"], "Column: Code")


class TestParticipantMappingSaveEndpoint(unittest.TestCase):
    """Regression coverage for saving additional participant variables mapping."""

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.project_root = Path(self.temp_dir) / "demo_project"
        self.project_root.mkdir(parents=True)
        (self.project_root / "project.json").write_text("{}", encoding="utf-8")

        self.app = Flask(__name__)
        self.app.secret_key = "test_secret"  # pragma: allowlist secret
        self.app.register_blueprint(participants_module.conversion_participants_bp)
        self.client = self.app.test_client()

    def tearDown(self):
        shutil.rmtree(self.temp_dir)

    def test_save_mapping_accepts_project_json_session_path(self):
        with self.client.session_transaction() as flask_session:
            flask_session["current_project_path"] = str(
                self.project_root / "project.json"
            )

        payload = {
            "mapping": {
                "version": "1.0",
                "description": "test",
                "mappings": {
                    "age": {
                        "source_column": "age",
                        "standard_variable": "age",
                        "type": "string",
                    }
                },
            }
        }

        response = self.client.post("/api/save-participant-mapping", json=payload)
        self.assertEqual(response.status_code, 200)

        body = response.get_json()
        self.assertEqual(body.get("status"), "success")
        self.assertEqual(body.get("library_source"), "project")

        mapping_file = (
            self.project_root / "code" / "library" / "participants_mapping.json"
        )
        self.assertTrue(mapping_file.exists())

        saved = json.loads(mapping_file.read_text(encoding="utf-8"))
        self.assertIn("mappings", saved)
        self.assertIn("age", saved["mappings"])


class TestParticipantsSeparatorHelpers(unittest.TestCase):
    """Coverage for participant CSV/TSV separator handling helpers."""

    def test_normalize_separator_option(self):
        self.assertEqual(
            participants_module._normalize_separator_option("semicolon"),
            "semicolon",
        )
        self.assertEqual(
            participants_module._normalize_separator_option("AUTO"),
            "auto",
        )
        self.assertEqual(
            participants_module._normalize_separator_option(None),
            "auto",
        )

        with self.assertRaises(ValueError):
            participants_module._normalize_separator_option("space")

    def test_expected_delimiter_for_suffix(self):
        self.assertEqual(
            participants_module._expected_delimiter_for_suffix(".csv", "auto"),
            ",",
        )
        self.assertEqual(
            participants_module._expected_delimiter_for_suffix(".tsv", "auto"),
            "\t",
        )
        self.assertEqual(
            participants_module._expected_delimiter_for_suffix(".csv", "semicolon"),
            ";",
        )


class TestParticipantsMixedTimeFormatDiagnostics(unittest.TestCase):
    """Coverage for user-facing mixed timing format diagnostics."""

    def test_detect_mixed_time_style_columns_reports_column_and_examples(self):
        import pandas as pd

        df = pd.DataFrame(
            {
                "participant_id": ["001", "002", "003", "004"],
                "T1_fitness": ["04:00", "1:15", "2h", "270"],
                "age": ["21", "22", "23", "24"],
            }
        )

        issues = participants_module._detect_mixed_time_style_columns(df)
        self.assertTrue(any(issue.get("column") == "T1_fitness" for issue in issues))

        issue = next(issue for issue in issues if issue.get("column") == "T1_fitness")
        formats = issue.get("detected_formats") or []
        examples = issue.get("examples") or []

        self.assertIn("clock", formats)
        self.assertTrue(any(fmt in formats for fmt in ["hours", "numeric", "minutes"]))
        self.assertIn("04:00", examples)
        self.assertIn("2h", examples)

    def test_format_mixed_time_style_message_contains_actionable_hint(self):
        message = participants_module._format_mixed_time_style_message(
            [
                {
                    "column": "T1_fitness",
                    "detected_formats": ["clock", "hours", "numeric"],
                    "examples": ["04:00", "2h", "270"],
                }
            ]
        )

        self.assertIn("T1_fitness", message)
        self.assertIn("04:00", message)
        self.assertIn("one format", message.lower())
        self.assertIn("fix this manually", message.lower())
        self.assertIn("does not auto-convert", message.lower())


class TestParticipantsPreviewApiEdgeCases(unittest.TestCase):
    """Endpoint-level edge case coverage for participants preview API."""

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.project_root = Path(self.temp_dir) / "demo_project"
        self.project_root.mkdir(parents=True, exist_ok=True)
        (self.project_root / "project.json").write_text("{}", encoding="utf-8")

        self.app = Flask(__name__)
        self.app.secret_key = "test_secret"  # pragma: allowlist secret
        self.app.register_blueprint(participants_module.conversion_participants_bp)
        self.client = self.app.test_client()

    def tearDown(self):
        shutil.rmtree(self.temp_dir)

    def _set_project_session(self):
        with self.client.session_transaction() as flask_session:
            flask_session["current_project_path"] = str(self.project_root)

    @staticmethod
    def _build_excel_bytes(sheet_map):
        buffer = io.BytesIO()
        with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
            for sheet_name, sheet_df in sheet_map.items():
                sheet_df.to_excel(writer, sheet_name=sheet_name, index=False)
        buffer.seek(0)
        return buffer.getvalue()

    def test_preview_returns_400_when_file_missing(self):
        self._set_project_session()

        response = self.client.post("/api/participants-preview", data={"mode": "file"})

        self.assertEqual(response.status_code, 400)
        self.assertIn(
            "Missing input file", (response.get_json() or {}).get("error", "")
        )

    def test_preview_returns_400_for_invalid_separator(self):
        self._set_project_session()

        response = self.client.post(
            "/api/participants-preview",
            data={
                "mode": "file",
                "separator": "space",
                "file": (io.BytesIO(b"participant_id,age\n001,21\n"), "demo.csv"),
            },
            content_type="multipart/form-data",
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn(
            "Invalid separator option", (response.get_json() or {}).get("error", "")
        )

    def test_preview_returns_409_when_id_cannot_be_detected(self):
        self._set_project_session()

        id_detection_module = sys.modules["src.converters.id_detection"]
        old_detect = getattr(id_detection_module, "detect_id_column", None)
        old_has_pm = getattr(id_detection_module, "has_prismmeta_columns", None)
        id_detection_module.detect_id_column = lambda *_args, **_kwargs: None
        id_detection_module.has_prismmeta_columns = lambda *_args, **_kwargs: False

        try:
            response = self.client.post(
                "/api/participants-preview",
                data={
                    "mode": "file",
                    "separator": "comma",
                    "file": (io.BytesIO(b"age,sex\n21,F\n"), "demo.csv"),
                },
                content_type="multipart/form-data",
            )

            self.assertEqual(response.status_code, 409)
            payload = response.get_json() or {}
            self.assertEqual(payload.get("error"), "id_column_required")
            self.assertIn("columns", payload)
        finally:
            if old_detect is not None:
                id_detection_module.detect_id_column = old_detect
            if old_has_pm is not None:
                id_detection_module.has_prismmeta_columns = old_has_pm

    def test_detect_id_returns_single_sheet_metadata_for_excel(self):
        self._set_project_session()

        id_detection_module = sys.modules["src.converters.id_detection"]
        old_detect = getattr(id_detection_module, "detect_id_column", None)
        old_has_pm = getattr(id_detection_module, "has_prismmeta_columns", None)
        id_detection_module.detect_id_column = lambda *_args, **_kwargs: "ID"
        id_detection_module.has_prismmeta_columns = lambda *_args, **_kwargs: False

        excel_bytes = self._build_excel_bytes(
            {"Participants": pd.DataFrame([{"ID": "001", "age": "21"}])}
        )

        try:
            response = self.client.post(
                "/api/participants-detect-id",
                data={
                    "sheet": "0",
                    "file": (io.BytesIO(excel_bytes), "participants.xlsx"),
                },
                content_type="multipart/form-data",
            )

            self.assertEqual(response.status_code, 200)
            payload = response.get_json() or {}
            self.assertEqual(payload.get("sheet_count"), 1)
            self.assertEqual(payload.get("sheet_names"), ["Participants"])
            self.assertFalse(payload.get("show_sheet_selector"))
        finally:
            if old_detect is not None:
                id_detection_module.detect_id_column = old_detect
            if old_has_pm is not None:
                id_detection_module.has_prismmeta_columns = old_has_pm

    def test_detect_id_returns_multi_sheet_metadata_for_excel(self):
        self._set_project_session()

        id_detection_module = sys.modules["src.converters.id_detection"]
        old_detect = getattr(id_detection_module, "detect_id_column", None)
        old_has_pm = getattr(id_detection_module, "has_prismmeta_columns", None)
        id_detection_module.detect_id_column = lambda *_args, **_kwargs: "ID"
        id_detection_module.has_prismmeta_columns = lambda *_args, **_kwargs: False

        excel_bytes = self._build_excel_bytes(
            {
                "Participants": pd.DataFrame([{"ID": "001", "age": "21"}]),
                "Archive": pd.DataFrame([{"ID": "900", "age": "99"}]),
            }
        )

        try:
            response = self.client.post(
                "/api/participants-detect-id",
                data={
                    "sheet": "0",
                    "file": (io.BytesIO(excel_bytes), "participants.xlsx"),
                },
                content_type="multipart/form-data",
            )

            self.assertEqual(response.status_code, 200)
            payload = response.get_json() or {}
            self.assertEqual(payload.get("sheet_count"), 2)
            self.assertEqual(payload.get("sheet_names"), ["Participants", "Archive"])
            self.assertTrue(payload.get("show_sheet_selector"))
        finally:
            if old_detect is not None:
                id_detection_module.detect_id_column = old_detect
            if old_has_pm is not None:
                id_detection_module.has_prismmeta_columns = old_has_pm

    @patch.object(
        participants_module, "_load_survey_template_item_ids", return_value=set()
    )
    @patch.object(participants_module, "resolve_effective_library_path")
    def test_preview_renames_selected_id_column_to_participant_id(
        self,
        mock_resolve_library,
        _mock_template_ids,
    ):
        self._set_project_session()
        mock_resolve_library.return_value = self.project_root

        id_detection_module = sys.modules["src.converters.id_detection"]
        old_detect = getattr(id_detection_module, "detect_id_column", None)
        old_has_pm = getattr(id_detection_module, "has_prismmeta_columns", None)
        id_detection_module.detect_id_column = (
            lambda columns, *_args, explicit_id_column=None, **_kwargs: (
                explicit_id_column
                if explicit_id_column
                else ("Code" if "Code" in columns else None)
            )
        )
        id_detection_module.has_prismmeta_columns = lambda *_args, **_kwargs: False

        try:
            response = self.client.post(
                "/api/participants-preview",
                data={
                    "mode": "file",
                    "separator": "comma",
                    "id_column": "Code",
                    "file": (
                        io.BytesIO(b"Code,Age\n001,21\n002,22\n"),
                        "demo.csv",
                    ),
                },
                content_type="multipart/form-data",
            )

            self.assertEqual(response.status_code, 200)
            payload = response.get_json() or {}
            self.assertEqual(payload.get("status"), "success")
            self.assertEqual(payload.get("id_column"), "participant_id")
            self.assertEqual(payload.get("source_id_column"), "Code")
            self.assertIn("participant_id", payload.get("columns") or [])
            self.assertNotIn("Code", payload.get("columns") or [])

            preview_rows = payload.get("preview_rows") or []
            self.assertEqual(preview_rows[0].get("participant_id"), "001")
            self.assertNotIn("Code", preview_rows[0])

            preview_schema = payload.get("neurobagel_schema") or {}
            self.assertIn("participant_id", preview_schema)
            self.assertNotIn("Code", preview_schema)
        finally:
            if old_detect is not None:
                id_detection_module.detect_id_column = old_detect
            if old_has_pm is not None:
                id_detection_module.has_prismmeta_columns = old_has_pm


class TestParticipantsInputFileEdgeCases(unittest.TestCase):
    """Input-file edge-case coverage for participants converter flows."""

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.project_root = Path(self.temp_dir) / "demo_project"
        self.project_root.mkdir(parents=True, exist_ok=True)
        (self.project_root / "project.json").write_text("{}", encoding="utf-8")

        self.app = Flask(__name__)
        self.app.secret_key = "test_secret"  # pragma: allowlist secret
        self.app.register_blueprint(participants_module.conversion_participants_bp)
        self.client = self.app.test_client()

    def tearDown(self):
        shutil.rmtree(self.temp_dir)

    def _set_project_session(self):
        with self.client.session_transaction() as flask_session:
            flask_session["current_project_path"] = str(self.project_root)

    def _set_id_detection(self, detect_impl, has_prism_impl=None):
        id_detection_module = sys.modules["src.converters.id_detection"]
        old_detect = getattr(id_detection_module, "detect_id_column", None)
        old_has_pm = getattr(id_detection_module, "has_prismmeta_columns", None)
        id_detection_module.detect_id_column = detect_impl
        id_detection_module.has_prismmeta_columns = (
            has_prism_impl
            if has_prism_impl is not None
            else (lambda *_args, **_kwargs: False)
        )
        return id_detection_module, old_detect, old_has_pm

    def _restore_id_detection(self, id_detection_module, old_detect, old_has_pm):
        if old_detect is not None:
            id_detection_module.detect_id_column = old_detect
        if old_has_pm is not None:
            id_detection_module.has_prismmeta_columns = old_has_pm

    @patch.object(participants_module, "_generate_neurobagel_schema", return_value={})
    @patch.object(
        participants_module, "_load_survey_template_item_ids", return_value=set()
    )
    @patch.object(participants_module, "resolve_effective_library_path")
    @patch.object(participants_module, "read_tabular_file")
    def test_preview_rejects_fake_xlsx_content(
        self,
        mock_read_tabular_file,
        mock_resolve_library,
        _mock_template_ids,
        _mock_schema,
    ):
        self._set_project_session()
        mock_resolve_library.return_value = self.project_root
        mock_read_tabular_file.side_effect = ValueError(
            "Failed to read Excel file fake.xlsx: File is not a zip file"
        )

        id_detection_module, old_detect, old_has_pm = self._set_id_detection(
            lambda *_args, **_kwargs: "ID"
        )
        try:
            response = self.client.post(
                "/api/participants-preview",
                data={
                    "mode": "file",
                    "sheet": "0",
                    "id_column": "ID",
                    "file": (io.BytesIO(b"ID,age\n001,21\n"), "fake.xlsx"),
                },
                content_type="multipart/form-data",
            )
            self.assertEqual(response.status_code, 500)
            payload = response.get_json() or {}
            self.assertIn("error", payload)
            self.assertGreaterEqual(mock_read_tabular_file.call_count, 1)
        finally:
            self._restore_id_detection(id_detection_module, old_detect, old_has_pm)

    @patch.object(participants_module, "_generate_neurobagel_schema", return_value={})
    @patch.object(
        participants_module, "_load_survey_template_item_ids", return_value=set()
    )
    @patch.object(participants_module, "resolve_effective_library_path")
    def test_preview_accepts_cp1252_csv_input(
        self,
        mock_resolve_library,
        _mock_template_ids,
        _mock_schema,
    ):
        self._set_project_session()
        mock_resolve_library.return_value = self.project_root

        id_detection_module, old_detect, old_has_pm = self._set_id_detection(
            lambda columns, *_args, explicit_id_column=None, **_kwargs: (
                explicit_id_column
                if explicit_id_column
                else ("ID" if "ID" in columns else None)
            )
        )
        try:
            csv_text = "ID,city,age\n001,Graz,21\n002,Köln,22\n"
            csv_bytes = csv_text.encode("cp1252")
            response = self.client.post(
                "/api/participants-preview",
                data={
                    "mode": "file",
                    "separator": "comma",
                    "id_column": "ID",
                    "extra_columns": '["city"]',
                    "file": (io.BytesIO(csv_bytes), "demo.csv"),
                },
                content_type="multipart/form-data",
            )
            self.assertEqual(response.status_code, 200)
            payload = response.get_json() or {}
            self.assertEqual(payload.get("status"), "success")
            rows = payload.get("preview_rows") or []
            self.assertTrue(any((row.get("city") == "Köln") for row in rows))
        finally:
            self._restore_id_detection(id_detection_module, old_detect, old_has_pm)

    @patch.object(participants_module, "_generate_neurobagel_schema", return_value={})
    @patch.object(
        participants_module, "_load_survey_template_item_ids", return_value=set()
    )
    @patch.object(participants_module, "resolve_effective_library_path")
    def test_preview_handles_semicolon_csv_with_quoted_commas(
        self,
        mock_resolve_library,
        _mock_template_ids,
        _mock_schema,
    ):
        self._set_project_session()
        mock_resolve_library.return_value = self.project_root

        id_detection_module, old_detect, old_has_pm = self._set_id_detection(
            lambda columns, *_args, explicit_id_column=None, **_kwargs: (
                explicit_id_column
                if explicit_id_column
                else ("ID" if "ID" in columns else None)
            )
        )
        try:
            csv_text = 'ID;notes;age\n001;"A, B";21\n002;"C, D";22\n'
            response = self.client.post(
                "/api/participants-preview",
                data={
                    "mode": "file",
                    "separator": "semicolon",
                    "id_column": "ID",
                    "extra_columns": '["notes"]',
                    "file": (io.BytesIO(csv_text.encode("utf-8")), "demo.csv"),
                },
                content_type="multipart/form-data",
            )
            self.assertEqual(response.status_code, 200)
            payload = response.get_json() or {}
            self.assertEqual(payload.get("status"), "success")
            rows = payload.get("preview_rows") or []
            self.assertTrue(any((row.get("notes") == "A, B") for row in rows))
        finally:
            self._restore_id_detection(id_detection_module, old_detect, old_has_pm)

    @patch.object(participants_module, "_generate_neurobagel_schema", return_value={})
    @patch.object(
        participants_module, "_load_survey_template_item_ids", return_value=set()
    )
    @patch.object(participants_module, "resolve_effective_library_path")
    def test_preview_handles_duplicate_input_headers(
        self,
        mock_resolve_library,
        _mock_template_ids,
        _mock_schema,
    ):
        self._set_project_session()
        mock_resolve_library.return_value = self.project_root

        id_detection_module, old_detect, old_has_pm = self._set_id_detection(
            lambda *_args, **_kwargs: "ID"
        )
        try:
            csv_text = "ID,ID,age\n001,ALT,21\n"
            response = self.client.post(
                "/api/participants-preview",
                data={
                    "mode": "file",
                    "separator": "comma",
                    "id_column": "ID",
                    "file": (io.BytesIO(csv_text.encode("utf-8")), "dupe_headers.csv"),
                },
                content_type="multipart/form-data",
            )
            self.assertEqual(response.status_code, 200)
            payload = response.get_json() or {}
            source_columns = payload.get("source_columns") or []
            self.assertIn("ID", source_columns)
            self.assertTrue(any(col.startswith("ID") for col in source_columns))
        finally:
            self._restore_id_detection(id_detection_module, old_detect, old_has_pm)


class TestParticipantsConverterInputEdgeCases(unittest.TestCase):
    """Low-level converter edge-cases around participant_id normalization."""

    def test_convert_keeps_duplicate_normalized_participant_ids(self):
        from src.participants_converter import ParticipantsConverter

        with tempfile.TemporaryDirectory() as tmp:
            dataset_root = Path(tmp)
            source_path = dataset_root / "participants.csv"
            pd.DataFrame(
                [
                    {"ID": "001", "age": "21"},
                    {"ID": "1", "age": "22"},
                    {"ID": "sub-001", "age": "23"},
                ]
            ).to_csv(source_path, index=False)

            converter = ParticipantsConverter(dataset_root)
            mapping = {
                "version": "1.0",
                "mappings": {
                    "participant_id": {
                        "source_column": "ID",
                        "standard_variable": "participant_id",
                        "type": "string",
                    },
                    "age": {
                        "source_column": "age",
                        "standard_variable": "age",
                        "type": "string",
                    },
                },
            }

            success, output_df, _messages = converter.convert_participant_data(
                source_path,
                mapping,
            )

            self.assertTrue(success)
            self.assertIsNotNone(output_df)
            participant_ids = list(output_df["participant_id"])
            self.assertEqual(participant_ids, ["sub-001", "sub-1", "sub-001"])


class TestEnvironmentConversionAsyncApi(unittest.TestCase):
    """Async environment conversion endpoints should start and report jobs."""

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.project_root = Path(self.temp_dir) / "demo_project"
        self.project_root.mkdir(parents=True, exist_ok=True)

        self.app = Flask(__name__)
        self.app.secret_key = "test_secret"  # pragma: allowlist secret
        self.app.register_blueprint(conversion_bp)
        self.client = self.app.test_client()

    def tearDown(self):
        shutil.rmtree(self.temp_dir)

    def test_environment_convert_start_returns_job_id(self):
        with self.client.session_transaction() as flask_session:
            flask_session["current_project_path"] = str(self.project_root)

        with patch.object(environment_module.threading, "Thread") as mock_thread:
            response = self.client.post(
                "/api/environment-convert-start",
                data={
                    "file": (
                        io.BytesIO(
                            b"timestamp,participant_id,session\n2025-01-15 10:30:00,01,01\n"
                        ),
                        "environment.csv",
                    ),
                    "separator": "comma",
                    "timestamp_col": "timestamp",
                    "participant_col": "participant_id",
                    "session_col": "session",
                    "lat": "47.0667",
                    "lon": "15.45",
                },
                content_type="multipart/form-data",
            )

        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertTrue(payload.get("job_id"))
        mock_thread.assert_called_once()

    def test_environment_convert_status_returns_final_result(self):
        job_id = "job-123"
        with environment_module._environment_jobs_lock:
            environment_module._environment_jobs[job_id] = {
                "logs": [{"message": "done", "type": "success"}],
                "done": True,
                "status": "completed",
                "success": True,
                "result": {"row_count": 1, "skipped": 0},
                "error": None,
            }

        response = self.client.get(f"/api/environment-convert-status/{job_id}?cursor=0")

        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertTrue(payload.get("done"))
        self.assertTrue(payload.get("success"))
        self.assertEqual(payload.get("status"), "completed")
        self.assertEqual(payload.get("result", {}).get("row_count"), 1)
        self.assertEqual(len(payload.get("logs", [])), 1)

        follow_up = self.client.get(
            f"/api/environment-convert-status/{job_id}?cursor=0"
        )
        self.assertEqual(follow_up.status_code, 404)

    def test_environment_convert_cancel_marks_in_memory_job_cancelled(self):
        job_id = "job-cancel"
        with environment_module._environment_jobs_lock:
            environment_module._environment_jobs[job_id] = {
                "logs": [],
                "done": False,
                "status": "running",
                "success": None,
                "result": None,
                "error": None,
            }

        response = self.client.post(f"/api/environment-convert-cancel/{job_id}")

        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertEqual(payload.get("status"), "cancelling")
        with environment_module._environment_jobs_lock:
            self.assertEqual(
                environment_module._environment_jobs[job_id].get("status"),
                "cancelled",
            )

    def test_environment_convert_status_exposes_progress_pct(self):
        job_id = "job-progress"
        with environment_module._environment_jobs_lock:
            environment_module._environment_jobs[job_id] = {
                "logs": [{"message": "working", "type": "info"}],
                "done": False,
                "status": "running",
                "progress_pct": 42,
                "success": None,
                "result": None,
                "error": None,
            }

        response = self.client.get(f"/api/environment-convert-status/{job_id}?cursor=0")

        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertFalse(payload.get("done"))
        self.assertEqual(payload.get("progress_pct"), 42)


class TestPhysioConversionAsyncApi(unittest.TestCase):
    """Async physio conversion endpoints should expose cancellation."""

    def setUp(self):
        self.app = Flask(__name__)
        self.app.secret_key = "test_secret"  # pragma: allowlist secret
        self.app.register_blueprint(conversion_bp)
        self.client = self.app.test_client()

    def test_batch_convert_cancel_marks_job_cancelled(self):
        job_id = "batch-job-1"
        with physio_module._batch_jobs_lock:
            physio_module._batch_jobs[job_id] = {
                "logs": [],
                "done": False,
                "status": "running",
                "success": None,
                "result": None,
                "error": None,
            }

        response = self.client.post(f"/api/batch-convert-cancel/{job_id}")

        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertEqual(payload.get("status"), "cancelling")
        with physio_module._batch_jobs_lock:
            self.assertEqual(
                physio_module._batch_jobs[job_id].get("status"), "cancelled"
            )

    def test_batch_convert_status_returns_status_field(self):
        job_id = "batch-job-2"
        with physio_module._batch_jobs_lock:
            physio_module._batch_jobs[job_id] = {
                "logs": [],
                "done": True,
                "status": "completed",
                "success": True,
                "result": {"converted": 2},
                "error": None,
            }

        response = self.client.get(f"/api/batch-convert-status/{job_id}?cursor=0")

        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertEqual(payload.get("status"), "completed")
        self.assertTrue(payload.get("done"))


class TestEnvironmentConversionApiResilience(unittest.TestCase):
    """Environment conversion should survive slow external provider calls."""

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.project_root = Path(self.temp_dir) / "demo_project"
        self.project_root.mkdir(parents=True, exist_ok=True)

        self.app = Flask(__name__)
        self.app.secret_key = "test_secret"  # pragma: allowlist secret
        self.app.register_blueprint(conversion_bp)
        self.client = self.app.test_client()

    def tearDown(self):
        shutil.rmtree(self.temp_dir)

    def _response(self, payload):
        response = MagicMock()
        response.raise_for_status.return_value = None
        response.json.return_value = payload
        return response

    def _provider_side_effect(self, weather_payload, air_payload, pollen_payload):
        def _side_effect(url, params=None, timeout=None):
            hourly = set(str((params or {}).get("hourly", "")).split(","))
            if "temperature_2m" in hourly:
                return self._response(weather_payload)
            if "european_aqi" in hourly:
                if isinstance(air_payload, Exception):
                    raise air_payload
                return self._response(air_payload)
            if "birch_pollen" in hourly:
                if isinstance(pollen_payload, Exception):
                    raise pollen_payload
                return self._response(pollen_payload)
            raise AssertionError("Unexpected provider request")

        return _side_effect

    def test_fetch_environment_hour_keeps_partial_data_when_air_quality_times_out(self):
        weather_payload = {
            "hourly": {
                "time": ["2025-01-15T10:00"],
                "temperature_2m": [3.2],
                "apparent_temperature": [1.0],
                "dew_point_2m": [0.4],
                "relative_humidity_2m": [80],
                "surface_pressure": [1025],
                "precipitation": [0.0],
                "wind_speed_10m": [2.1],
                "cloud_cover": [12],
                "uv_index": [0.5],
                "shortwave_radiation": [15.0],
            }
        }
        pollen_payload = {
            "hourly": {
                "time": ["2025-01-15T10:00"],
                "birch_pollen": [10],
                "grass_pollen": [20],
                "mugwort_pollen": [0],
                "ragweed_pollen": [0],
            }
        }

        with patch.object(
            environment_module.requests,
            "get",
            side_effect=self._provider_side_effect(
                weather_payload,
                requests.Timeout("read timed out"),
                pollen_payload,
            ),
        ):
            data, warnings = environment_module._fetch_environment_hour(
                datetime(2025, 1, 15, 10, 30),
                47.0667,
                15.45,
            )

        self.assertEqual(data["temp_c"], 3.2)
        self.assertEqual(data["weather_regime"], "hochdruck")
        self.assertIsNone(data["aqi"])
        self.assertEqual(data["pollen_birch"], 10.0)
        self.assertEqual(data["pollen_total"], 30.0)
        self.assertTrue(
            any("Air quality API unavailable" in warning for warning in warnings)
        )

    def test_environment_convert_start_background_uses_detached_process(self):
        with self.client.session_transaction() as flask_session:
            flask_session["current_project_path"] = str(self.project_root)

        mock_process = SimpleNamespace(pid=9876)
        with patch.object(
            environment_module.subprocess, "Popen", return_value=mock_process
        ):
            response = self.client.post(
                "/api/environment-convert-start",
                data={
                    "file": (
                        io.BytesIO(
                            b"timestamp,participant_id,session\n2025-01-15 10:30:00,01,01\n"
                        ),
                        "environment.csv",
                    ),
                    "separator": "comma",
                    "timestamp_col": "timestamp",
                    "participant_col": "participant_id",
                    "session_col": "session",
                    "lat": "47.0667",
                    "lon": "15.45",
                    "convert_in_background": "true",
                },
                content_type="multipart/form-data",
            )

        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertTrue(payload.get("background"))
        self.assertEqual(payload.get("pid"), 9876)
        self.assertTrue(payload.get("job_id"))

    def test_environment_convert_status_reads_detached_job_result(self):
        job_id = "detached-123"
        jobs_dir = self.project_root / ".prism" / "environment_jobs"
        jobs_dir.mkdir(parents=True, exist_ok=True)
        log_path = jobs_dir / f"{job_id}.log"
        result_path = jobs_dir / f"{job_id}.result.json"

        log_path.write_text(
            "info\tDetached command: python ...\ninfo\tDone\n", encoding="utf-8"
        )
        result_path.write_text(
            json.dumps(
                {
                    "done": True,
                    "success": True,
                    "result": {"row_count": 1},
                    "error": None,
                }
            ),
            encoding="utf-8",
        )

        with environment_module._environment_detached_jobs_lock:
            environment_module._environment_detached_jobs[job_id] = {
                "pid": 1234,
                "log_path": str(log_path),
                "result_path": str(result_path),
                "cancel_path": str(jobs_dir / f"{job_id}.cancel"),
            }

        response = self.client.get(f"/api/environment-convert-status/{job_id}?cursor=0")
        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertTrue(payload.get("done"))
        self.assertTrue(payload.get("success"))
        self.assertEqual(payload.get("result", {}).get("row_count"), 1)
        self.assertEqual(len(payload.get("logs", [])), 2)

        follow_up = self.client.get(
            f"/api/environment-convert-status/{job_id}?cursor=0"
        )
        self.assertEqual(follow_up.status_code, 404)

    def test_environment_convert_cancel_writes_detached_cancel_file(self):
        job_id = "detached-cancel"
        jobs_dir = self.project_root / ".prism" / "environment_jobs"
        jobs_dir.mkdir(parents=True, exist_ok=True)
        log_path = jobs_dir / f"{job_id}.log"
        result_path = jobs_dir / f"{job_id}.result.json"
        cancel_path = jobs_dir / f"{job_id}.cancel"
        log_path.write_text("", encoding="utf-8")

        with environment_module._environment_detached_jobs_lock:
            environment_module._environment_detached_jobs[job_id] = {
                "pid": 4321,
                "log_path": str(log_path),
                "result_path": str(result_path),
                "cancel_path": str(cancel_path),
            }

        response = self.client.post(f"/api/environment-convert-cancel/{job_id}")

        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertEqual(payload.get("status"), "cancelling")
        self.assertTrue(cancel_path.exists())


class TestSharedSeparatorHelpers(unittest.TestCase):
    """Coverage for shared separator handling used by survey endpoints."""

    def test_normalize_separator_option(self):
        from src.web.blueprints import conversion_utils

        self.assertEqual(
            conversion_utils.normalize_separator_option("pipe"),
            "pipe",
        )
        self.assertEqual(
            conversion_utils.normalize_separator_option("AUTO"),
            "auto",
        )
        self.assertEqual(
            conversion_utils.normalize_separator_option(None),
            "auto",
        )

        with self.assertRaises(ValueError):
            conversion_utils.normalize_separator_option("space")

    def test_expected_delimiter_for_suffix(self):
        from src.web.blueprints import conversion_utils

        self.assertEqual(
            conversion_utils.expected_delimiter_for_suffix(".csv", "auto"),
            ",",
        )
        self.assertEqual(
            conversion_utils.expected_delimiter_for_suffix(".tsv", "auto"),
            "\t",
        )
        self.assertEqual(
            conversion_utils.expected_delimiter_for_suffix(".csv", "pipe"),
            "|",
        )

    def test_read_tabular_dataframe_robust_supports_cp1252_semicolon_csv(self):
        from src.web.blueprints import conversion_utils
        import pandas as pd

        with tempfile.TemporaryDirectory() as tmp:
            csv_path = Path(tmp) / "participants_cp1252.csv"
            # Includes umlaut encoded as cp1252 to emulate locale-specific Excel export.
            csv_bytes = "ID;name\n001;M\xfcller\n002;Schr\xf6der\n".encode("cp1252")
            csv_path.write_bytes(csv_bytes)

            df = conversion_utils.read_tabular_dataframe_robust(
                csv_path,
                expected_delimiter=";",
                dtype=str,
            )

            self.assertIsInstance(df, pd.DataFrame)
            self.assertEqual(list(df.columns), ["ID", "name"])
            self.assertEqual(df.iloc[0]["ID"], "001")
            self.assertEqual(df.iloc[0]["name"], "Müller")


class TestRenamerTemplateRequirements(unittest.TestCase):
    """UI regression checks for renamer form requirements."""

    def test_task_field_is_required(self):
        template_path = (
            Path(project_root) / "app" / "templates" / "file_management.html"
        )
        template = template_path.read_text(encoding="utf-8")
        self.assertIn('id="renamerTask"', template)
        self.assertIn(
            'id="renamerTask" value="rest" placeholder="e.g. rest" required', template
        )
        self.assertIn('id="renamerIdFromFilename"', template)
        self.assertIn('id="renamerIdFromFolder"', template)


if __name__ == "__main__":
    unittest.main()
