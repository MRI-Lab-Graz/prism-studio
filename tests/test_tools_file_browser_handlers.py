import os
import sys
import unittest
from unittest.mock import patch

from flask import Flask

current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(current_dir)
app_path = os.path.join(project_root, "app")

if app_path not in sys.path:
    sys.path.insert(0, app_path)

from src.web.blueprints import tools_file_browser_handlers as handlers


class TestToolsFileBrowserHandlers(unittest.TestCase):
    def setUp(self):
        self.app = Flask(__name__)

    @patch.object(handlers.file_picker, "pick_file")
    def test_browse_file_returns_picker_path(self, mock_pick_file):
        mock_pick_file.return_value = handlers.file_picker.PickerOutcome(
            path=r"C:\Users\tester\Study\project.json"
        )

        with self.app.test_request_context("/api/browse-file"):
            response = handlers.handle_api_browse_file()

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.get_json()["path"], r"C:\Users\tester\Study\project.json"
        )
        mock_pick_file.assert_called_once_with(project_json_only=True)

    @patch.object(handlers.file_picker, "pick_folder")
    def test_browse_folder_returns_picker_path(self, mock_pick_folder):
        mock_pick_folder.return_value = handlers.file_picker.PickerOutcome(
            path=r"C:\Users\tester\Study"
        )

        with self.app.test_request_context("/api/browse-folder"):
            response = handlers.handle_api_browse_folder()

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()["path"], r"C:\Users\tester\Study")
        mock_pick_folder.assert_called_once_with()

    @patch.object(handlers.file_picker, "pick_file")
    def test_browse_file_returns_service_error(self, mock_pick_file):
        mock_pick_file.return_value = handlers.file_picker.PickerOutcome(
            error="PowerShell dialog failed",
            status_code=500,
        )

        with self.app.test_request_context("/api/browse-file"):
            response, status_code = handlers.handle_api_browse_file()

        self.assertEqual(status_code, 500)
        self.assertEqual(response.get_json()["error"], "PowerShell dialog failed")

    @patch.object(handlers.file_picker, "pick_file")
    def test_browse_file_honors_project_json_flag(self, mock_pick_file):
        mock_pick_file.return_value = handlers.file_picker.PickerOutcome(path="")

        with self.app.test_request_context("/api/browse-file?project_json_only=0"):
            handlers.handle_api_browse_file()

        mock_pick_file.assert_called_once_with(project_json_only=False)


if __name__ == "__main__":
    unittest.main()
