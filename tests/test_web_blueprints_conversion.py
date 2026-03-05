
import unittest
import sys
import os
import shutil
import tempfile
import json
from pathlib import Path
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
    from src.web.blueprints import conversion_physio_handlers as physio_module
    from src.web.blueprints import conversion_participants_blueprint as participants_module
    from src.web.blueprints.conversion import conversion_bp
    from src.web.blueprints.conversion_biometrics_handlers import api_biometrics_check_library
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
        with self.app.test_request_context(query_string={'library_path': str(self.library_path)}):
            # Call handler
            response = api_biometrics_check_library()
            # If it's a tuple (response, code), unpack it
            if isinstance(response, tuple):
                response = response[0]
            
            data = response.get_json()
            self.assertTrue(data['structure']['has_biometrics_folder'])
            self.assertTrue(data['structure']['has_survey_folder'])
            self.assertTrue(data['structure']['has_participants_json'])
            self.assertEqual(data['structure']['template_count'], 1)

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
        self.app.secret_key = "test_secret"
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
        self.assertEqual(session, "3")

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
        self.assertEqual(name, "sub-135_ses-1_task-rest_physio.raw")


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
                    canonicalize_template_items_fn=lambda sidecar, canonical_aliases: sidecar,
                    non_item_keys={"Study", "_aliases", "_reverse_aliases"},
                    find_matching_global_template_fn=lambda *_: (None, False, set(), set()),
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
            "diagnosis": {
                "Description": "Should not be added when missing from TSV"
            },
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
        self.assertTrue(any("Skipped annotation-only field 'diagnosis'" in msg for _, msg in messages))

    def test_merge_preserves_existing_base_fields(self):
        base = {
            "age": {"Description": "Participant age"}
        }
        nb_schema = {
            "age": {
                "Description": "Alternative description",
                "Unit": "years",
                "Annotations": {
                    "VariableType": "Continuous"
                },
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


class TestParticipantMappingSaveEndpoint(unittest.TestCase):
    """Regression coverage for saving additional participant variables mapping."""

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.project_root = Path(self.temp_dir) / "demo_project"
        self.project_root.mkdir(parents=True)
        (self.project_root / "project.json").write_text("{}", encoding="utf-8")

        self.app = Flask(__name__)
        self.app.secret_key = "test_secret"
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

        mapping_file = self.project_root / "code" / "library" / "participants_mapping.json"
        self.assertTrue(mapping_file.exists())

        saved = json.loads(mapping_file.read_text(encoding="utf-8"))
        self.assertIn("mappings", saved)
        self.assertIn("age", saved["mappings"])


class TestRenamerTemplateRequirements(unittest.TestCase):
    """UI regression checks for renamer form requirements."""

    def test_task_field_is_required(self):
        template_path = Path(project_root) / "app" / "templates" / "file_management.html"
        template = template_path.read_text(encoding="utf-8")
        self.assertIn('id="renamerTask"', template)
        self.assertIn('id="renamerTask" value="rest" placeholder="e.g. rest" required', template)
        self.assertIn('id="renamerIdFromFilename"', template)
        self.assertIn('id="renamerIdFromFolder"', template)

if __name__ == "__main__":
    unittest.main()
