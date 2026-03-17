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
    @patch.object(file_picker, "_browse_file_tk")
    @patch.object(file_picker.sys, "platform", "win32")
    def test_pick_file_prefers_windows_tkinter_picker(self, mock_browse_file_tk):
        mock_browse_file_tk.return_value = r"C:\Users\tester\Study\project.json"

        result = file_picker.pick_file(project_json_only=True)

        self.assertEqual(result.status_code, 200)
        self.assertEqual(result.path, r"C:\Users\tester\Study\project.json")
        self.assertIsNone(result.error)
        mock_browse_file_tk.assert_called_once_with(
            project_json_only=True, topmost=True
        )

    @patch.object(file_picker, "_browse_folder_tk")
    @patch.object(file_picker.sys, "platform", "win32")
    def test_pick_folder_prefers_windows_tkinter_picker(self, mock_browse_folder_tk):
        mock_browse_folder_tk.return_value = r"C:\Users\tester\Study"

        result = file_picker.pick_folder()

        self.assertEqual(result.status_code, 200)
        self.assertEqual(result.path, r"C:\Users\tester\Study")
        self.assertIsNone(result.error)
        mock_browse_folder_tk.assert_called_once_with(topmost=True)

    @patch.object(file_picker, "_browse_file_windows_powershell")
    @patch.object(file_picker, "_browse_file_tk")
    @patch.object(file_picker.sys, "platform", "win32")
    def test_pick_file_falls_back_to_windows_powershell_when_tkinter_fails(
        self, mock_browse_file_tk, mock_browse_file_ps
    ):
        mock_browse_file_tk.side_effect = RuntimeError("tkinter unavailable")
        mock_browse_file_ps.return_value = r"C:\Users\tester\Study\project.json"

        result = file_picker.pick_file(project_json_only=True)

        self.assertEqual(result.status_code, 200)
        self.assertEqual(result.path, r"C:\Users\tester\Study\project.json")
        self.assertIsNone(result.error)
        mock_browse_file_tk.assert_called_once_with(
            project_json_only=True, topmost=True
        )
        mock_browse_file_ps.assert_called_once_with(True)

    @patch.object(file_picker, "_browse_file_windows_powershell")
    @patch.object(file_picker, "_browse_file_tk")
    @patch.object(file_picker.sys, "platform", "win32")
    def test_pick_file_returns_clear_windows_error_when_no_picker_available(
        self, mock_browse_file_tk, mock_browse_file_ps
    ):
        mock_browse_file_tk.side_effect = RuntimeError("tkinter unavailable")
        mock_browse_file_ps.side_effect = RuntimeError("PowerShell is not available")

        result = file_picker.pick_file(project_json_only=True)

        self.assertEqual(result.status_code, 500)
        self.assertIn("tkinter and PowerShell dialogs failed", result.error)


if __name__ == "__main__":
    unittest.main()
