import os
import shutil
import subprocess
import sys
from dataclasses import dataclass


@dataclass
class PickerOutcome:
    path: str = ""
    error: str | None = None
    status_code: int = 200


def _windows_subprocess_kwargs() -> dict:
    creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    return {"stderr": subprocess.STDOUT, "creationflags": creationflags}


def _powershell_executable() -> str | None:
    for candidate in ("powershell", "pwsh"):
        resolved = shutil.which(candidate)
        if resolved:
            return resolved
    return None


def _escape_powershell_single_quoted(value: str) -> str:
    return value.replace("'", "''")


def _run_windows_powershell_dialog(dialog_script: str) -> str:
    executable = _powershell_executable()
    if not executable:
        raise RuntimeError("PowerShell is not available")

    result = subprocess.check_output(
        [executable, "-NoProfile", "-STA", "-Command", dialog_script],
        **_windows_subprocess_kwargs(),
    )
    return result.decode("utf-8", errors="replace").strip()


def _prefer_powershell_dialogs_on_windows() -> bool:
    """Prefer PowerShell dialogs in packaged Windows runtime where tkinter can be flaky."""
    env_value = os.environ.get("PRISM_PICKER_BACKEND", "").strip().lower()
    if env_value == "tk":
        return False
    if env_value == "powershell":
        return True
    return bool(getattr(sys, "frozen", False))


def _browse_file_windows_powershell(project_json_only: bool) -> str:
    title = "Select project.json" if project_json_only else "Select file"
    filter_value = (
        "PRISM Project Metadata (*.json)|*.json|All files (*.*)|*.*"
        if project_json_only
        else "All files (*.*)|*.*"
    )
    script = f"""
Add-Type -AssemblyName System.Windows.Forms
[System.Windows.Forms.Application]::EnableVisualStyles()
$dialog = New-Object System.Windows.Forms.OpenFileDialog
$dialog.Title = '{_escape_powershell_single_quoted(title)}'
$dialog.Filter = '{_escape_powershell_single_quoted(filter_value)}'
$dialog.FileName = '{_escape_powershell_single_quoted("project.json" if project_json_only else "")}'
$dialog.Multiselect = $false
$dialog.CheckFileExists = $true
$dialog.RestoreDirectory = $true
if ($dialog.ShowDialog() -eq [System.Windows.Forms.DialogResult]::OK) {{
    [Console]::OutputEncoding = [System.Text.Encoding]::UTF8
    Write-Output $dialog.FileName
}}
""".strip()
    return _run_windows_powershell_dialog(script)


def _browse_folder_windows_powershell() -> str:
    script = """
Add-Type -AssemblyName System.Windows.Forms
[System.Windows.Forms.Application]::EnableVisualStyles()
$dialog = New-Object System.Windows.Forms.FolderBrowserDialog
$dialog.Description = 'Select folder for PRISM'
$dialog.ShowNewFolderButton = $true
if ($dialog.ShowDialog() -eq [System.Windows.Forms.DialogResult]::OK) {
    [Console]::OutputEncoding = [System.Text.Encoding]::UTF8
    Write-Output $dialog.SelectedPath
}
""".strip()
    return _run_windows_powershell_dialog(script)


def _browse_file_macos(project_json_only: bool) -> str:
    if project_json_only:
        script = 'POSIX path of (choose file with prompt "Select your project.json file" of type {"public.json"})'
    else:
        script = 'POSIX path of (choose file with prompt "Select a file")'

    result = subprocess.check_output(
        ["osascript", "-e", script], stderr=subprocess.STDOUT
    )
    return result.decode("utf-8").strip()


def _browse_folder_macos() -> str:
    result = subprocess.check_output(
        ["osascript", "-e", "POSIX path of (choose folder)"],
        stderr=subprocess.STDOUT,
    )
    return result.decode("utf-8").strip()


def _browse_file_tk(project_json_only: bool, topmost: bool) -> str:
    import tkinter as tk
    from tkinter import filedialog

    root = tk.Tk()
    root.withdraw()
    if topmost:
        root.wm_attributes("-topmost", 1)
        root.focus_force()

    try:
        return filedialog.askopenfilename(
            title="Select project.json" if project_json_only else "Select file",
            filetypes=(
                [("PRISM Project Metadata", "project.json")]
                if project_json_only
                else [("All files", "*.*")]
            ),
            parent=root,
        )
    finally:
        root.destroy()


def _browse_folder_tk(topmost: bool) -> str:
    import tkinter as tk
    from tkinter import filedialog

    root = tk.Tk()
    root.withdraw()
    if topmost:
        root.wm_attributes("-topmost", 1)
        root.focus_force()

    try:
        return filedialog.askdirectory(title="Select folder for PRISM", parent=root)
    finally:
        root.destroy()


def pick_file(project_json_only: bool = True) -> PickerOutcome:
    try:
        if sys.platform == "darwin":
            try:
                file_path = _browse_file_macos(project_json_only)
                if (
                    project_json_only
                    and file_path
                    and not file_path.endswith("project.json")
                ):
                    return PickerOutcome(
                        error="Please select a file named 'project.json'",
                        status_code=400,
                    )
                return PickerOutcome(path=file_path)
            except subprocess.CalledProcessError:
                return PickerOutcome(path="")

        if sys.platform.startswith("win"):
            prefer_powershell = _prefer_powershell_dialogs_on_windows()

            if prefer_powershell:
                try:
                    file_path = _browse_file_windows_powershell(project_json_only)
                    if (
                        project_json_only
                        and file_path
                        and not file_path.endswith("project.json")
                    ):
                        return PickerOutcome(
                            error="Please select a file named 'project.json'",
                            status_code=400,
                        )
                    return PickerOutcome(path=file_path)
                except Exception as powershell_err:
                    print(f"Windows PowerShell file picker failed: {powershell_err}")

            try:
                file_path = _browse_file_tk(
                    project_json_only=project_json_only, topmost=True
                )
                if (
                    project_json_only
                    and file_path
                    and not file_path.endswith("project.json")
                ):
                    return PickerOutcome(
                        error="Please select a file named 'project.json'",
                        status_code=400,
                    )
                return PickerOutcome(path=file_path)
            except Exception as tk_err:
                print(f"Windows tkinter file picker failed: {tk_err}")
                if not prefer_powershell:
                    try:
                        file_path = _browse_file_windows_powershell(project_json_only)
                        if (
                            project_json_only
                            and file_path
                            and not file_path.endswith("project.json")
                        ):
                            return PickerOutcome(
                                error="Please select a file named 'project.json'",
                                status_code=400,
                            )
                        return PickerOutcome(path=file_path)
                    except Exception as powershell_err:
                        print(
                            f"Windows PowerShell file picker failed: {powershell_err}"
                        )

                    return PickerOutcome(
                        error=(
                            "File picker unavailable on Windows. tkinter and PowerShell dialogs failed. "
                            "Please manually enter the path."
                        ),
                        status_code=500,
                    )

        if not os.environ.get("DISPLAY"):
            return PickerOutcome(
                error="File picker requires a desktop session.", status_code=501
            )

        try:
            return PickerOutcome(
                path=_browse_file_tk(project_json_only=project_json_only, topmost=False)
            )
        except Exception as linux_err:
            print(f"Linux file picker error: {linux_err}")
            return PickerOutcome(
                error=f"File picker error: {str(linux_err)}", status_code=500
            )
    except Exception as err:
        print(f"Unexpected file picker error: {err}")
        return PickerOutcome(error=str(err), status_code=500)


def pick_folder() -> PickerOutcome:
    try:
        if sys.platform == "darwin":
            try:
                return PickerOutcome(path=_browse_folder_macos())
            except subprocess.CalledProcessError:
                return PickerOutcome(path="")

        if sys.platform.startswith("win"):
            prefer_powershell = _prefer_powershell_dialogs_on_windows()

            if prefer_powershell:
                try:
                    return PickerOutcome(path=_browse_folder_windows_powershell())
                except Exception as powershell_err:
                    print(f"Windows PowerShell folder picker failed: {powershell_err}")

            try:
                return PickerOutcome(path=_browse_folder_tk(topmost=True))
            except Exception as tk_err:
                print(f"Windows tkinter folder picker failed: {tk_err}")
                if not prefer_powershell:
                    try:
                        return PickerOutcome(path=_browse_folder_windows_powershell())
                    except Exception as powershell_err:
                        print(
                            f"Windows PowerShell folder picker failed: {powershell_err}"
                        )

                    return PickerOutcome(
                        error=(
                            "Folder picker unavailable on Windows. tkinter and PowerShell dialogs failed. "
                            "Please enter path manually."
                        ),
                        status_code=500,
                    )

        if not os.environ.get("DISPLAY"):
            return PickerOutcome(
                error="Folder picker requires a desktop session. Please enter path manually.",
                status_code=501,
            )

        try:
            return PickerOutcome(path=_browse_folder_tk(topmost=True))
        except ImportError:
            print("Linux folder picker failed: tkinter not available")
            return PickerOutcome(
                error="Folder picker requires python3-tk package. Install it or enter path manually.",
                status_code=500,
            )
        except Exception as linux_err:
            print(f"Linux folder picker failed: {linux_err}")
            return PickerOutcome(
                error=f"Folder picker error: {str(linux_err)}. Please enter path manually.",
                status_code=500,
            )
    except Exception as err:
        print(f"Error opening file dialog: {err}")
        return PickerOutcome(
            error="Could not open file dialog. Please enter path manually.",
            status_code=500,
        )
