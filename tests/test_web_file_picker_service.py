import os
import sys
import unittest
from unittest.mock import patch

current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(current_dir)
app_path = os.path.join(project_root, "app")

if app_path not in sys.path:
    sys.path.insert(0, app_path)

from src.web.services import file_picker  # noqa: E402


class TestWebFilePickerService(unittest.TestCase):
    @patch.object(file_picker, "_browse_file_windows_powershell")
    @patch.object(file_picker.sys, "platform", "win32")
    def test_pick_file_uses_windows_powershell_picker(self, mock_browse_file):
        mock_browse_file.return_value = r"C:\Users\tester\Study\project.json"

        result = file_picker.pick_file(project_json_only=True)

        self.assertEqual(result.status_code, 200)
        self.assertEqual(result.path, r"C:\Users\tester\Study\project.json")
        self.assertIsNone(result.error)
        mock_browse_file.assert_called_once_with(True)

    @patch.object(file_picker, "_browse_folder_windows_powershell")
    @patch.object(file_picker.sys, "platform", "win32")
    def test_pick_folder_uses_windows_powershell_picker(self, mock_browse_folder):
        mock_browse_folder.return_value = r"C:\Users\tester\Study"

        result = file_picker.pick_folder()

        self.assertEqual(result.status_code, 200)
        self.assertEqual(result.path, r"C:\Users\tester\Study")
        self.assertIsNone(result.error)
        mock_browse_folder.assert_called_once_with()

    @patch.object(file_picker, "_browse_file_windows_powershell")
    @patch.dict(sys.modules, {"tkinter": None}, clear=False)
    @patch.object(file_picker.sys, "platform", "win32")
    def test_pick_file_returns_clear_windows_error_when_no_picker_available(
        self, mock_browse_file
    ):
        mock_browse_file.side_effect = RuntimeError("PowerShell is not available")

        result = file_picker.pick_file(project_json_only=True)

        self.assertEqual(result.status_code, 500)
        self.assertIn("PowerShell dialog failed", result.error)


if __name__ == "__main__":
    unittest.main()
