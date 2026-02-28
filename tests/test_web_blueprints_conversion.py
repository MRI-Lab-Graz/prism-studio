
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

# Mock modules that create side effects or have complex dependencies
# We mock these BEFORE importing the handlers
sys.modules["src.web.validation"] = MagicMock()
sys.modules["src.web.services.project_registration"] = MagicMock()
sys.modules["src.converters.biometrics"] = MagicMock()
sys.modules["src.converters.id_detection"] = MagicMock()
sys.modules["helpers.physio.convert_varioport"] = MagicMock()
sys.modules["src.batch_convert"] = MagicMock()

# Now import the blueprint & handlers
try:
    from src.web.blueprints import conversion as conversion_module
    from src.web.blueprints import conversion_biometrics_handlers as biometrics_module
    from src.web.blueprints import conversion_physio_handlers as physio_module
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

if __name__ == "__main__":
    unittest.main()
