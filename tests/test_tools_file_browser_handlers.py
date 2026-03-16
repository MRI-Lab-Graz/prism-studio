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

    @patch.object(handlers, "_browse_file_windows_powershell")
    @patch.object(handlers.sys, "platform", "win32")
    def test_browse_file_uses_windows_powershell_picker(self, mock_browse_file):
        mock_browse_file.return_value = r"C:\Users\tester\Study\project.json"

        with self.app.test_request_context("/api/browse-file"):
            response = handlers.handle_api_browse_file()

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.get_json()["path"], r"C:\Users\tester\Study\project.json"
        )
        mock_browse_file.assert_called_once_with(True)

    @patch.object(handlers, "_browse_folder_windows_powershell")
    @patch.object(handlers.sys, "platform", "win32")
    def test_browse_folder_uses_windows_powershell_picker(self, mock_browse_folder):
        mock_browse_folder.return_value = r"C:\Users\tester\Study"

        with self.app.test_request_context("/api/browse-folder"):
            response = handlers.handle_api_browse_folder()

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()["path"], r"C:\Users\tester\Study")
        mock_browse_folder.assert_called_once_with()

    @patch.object(handlers, "_browse_file_windows_powershell")
    @patch.dict(sys.modules, {"tkinter": None}, clear=False)
    @patch.object(handlers.sys, "platform", "win32")
    def test_browse_file_returns_clear_windows_error_when_no_picker_available(
        self, mock_browse_file
    ):
        mock_browse_file.side_effect = RuntimeError("PowerShell is not available")

        with self.app.test_request_context("/api/browse-file"):
            response, status_code = handlers.handle_api_browse_file()

        self.assertEqual(status_code, 500)
        self.assertIn("PowerShell dialog failed", response.get_json()["error"])


if __name__ == "__main__":
    unittest.main()
