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
            project_json_only=True, topmost=True, initial_dir=None
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
            project_json_only=True, topmost=True, initial_dir=None
        )
        mock_browse_file_ps.assert_called_once_with(True, None)

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

    @patch.object(file_picker.subprocess, "check_output")
    def test_browse_folder_macos_strips_trailing_slash_and_ignores_stderr(
        self, mock_check_output
    ):
        mock_check_output.return_value = b"/Users/tester/Desktop/Study/\n"

        result = file_picker._browse_folder_macos()

        self.assertEqual(result, "/Users/tester/Desktop/Study")
        _args, kwargs = mock_check_output.call_args
        self.assertNotEqual(kwargs.get("stderr"), file_picker.subprocess.STDOUT)

    @patch.object(file_picker, "_browse_file_macos")
    @patch.object(file_picker.sys, "platform", "darwin")
    def test_pick_file_forwards_initial_dir_to_macos_picker(
        self, mock_browse_file_macos
    ):
        mock_browse_file_macos.return_value = "/Users/tester/Study/dataset_description.json"

        result = file_picker.pick_file(
            project_json_only=False, initial_dir="/Users/tester/Study"
        )

        self.assertEqual(result.status_code, 200)
        mock_browse_file_macos.assert_called_once_with(
            False, "/Users/tester/Study"
        )

    @patch.object(file_picker, "_browse_file_tk")
    @patch.object(file_picker.sys, "platform", "win32")
    def test_pick_file_forwards_initial_dir_to_windows_tkinter_picker(
        self, mock_browse_file_tk
    ):
        mock_browse_file_tk.return_value = r"C:\Users\tester\Study\dataset_description.json"

        result = file_picker.pick_file(
            project_json_only=False, initial_dir=r"C:\Users\tester\Study"
        )

        self.assertEqual(result.status_code, 200)
        mock_browse_file_tk.assert_called_once_with(
            project_json_only=False,
            topmost=True,
            initial_dir=r"C:\Users\tester\Study",
        )

    @patch("os.path.isdir", return_value=True)
    @patch.object(file_picker.subprocess, "check_output")
    def test_browse_file_macos_includes_default_location_when_initial_dir_given(
        self, mock_check_output, _mock_isdir
    ):
        mock_check_output.return_value = b"/Users/tester/Study/dataset_description.json\n"

        file_picker._browse_file_macos(
            project_json_only=False, initial_dir="/Users/tester/Study"
        )

        args, _kwargs = mock_check_output.call_args
        script = args[0][2]
        self.assertIn('default location (POSIX file "/Users/tester/Study")', script)

    @patch.object(file_picker.subprocess, "check_output")
    def test_browse_file_macos_omits_default_location_when_no_initial_dir(
        self, mock_check_output
    ):
        mock_check_output.return_value = b"/Users/tester/Study/dataset_description.json\n"

        file_picker._browse_file_macos(project_json_only=False, initial_dir=None)

        args, _kwargs = mock_check_output.call_args
        script = args[0][2]
        self.assertNotIn("default location", script)


if __name__ == "__main__":
    unittest.main()
