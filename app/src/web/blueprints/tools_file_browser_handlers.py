import os
import shutil
import subprocess
import sys

from flask import jsonify, request


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


def _browse_file_windows_powershell(project_json_only: bool) -> str:
    title = "Select project.json" if project_json_only else "Select file"
    filter_value = (
        "PRISM Project Metadata (project.json)|project.json|JSON Files (*.json)|*.json|All files (*.*)|*.*"
        if project_json_only
        else "All files (*.*)|*.*"
    )
    script = f"""
Add-Type -AssemblyName System.Windows.Forms
[System.Windows.Forms.Application]::EnableVisualStyles()
$dialog = New-Object System.Windows.Forms.OpenFileDialog
$dialog.Title = '{_escape_powershell_single_quoted(title)}'
$dialog.Filter = '{_escape_powershell_single_quoted(filter_value)}'
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


def handle_api_browse_file():
    """Open a system dialog to select a file (filtering for project.json)."""
    file_path = ""
    project_json_only = (request.args.get("project_json_only") or "1").strip() != "0"
    try:
        if sys.platform == "darwin":
            try:
                if project_json_only:
                    script = 'POSIX path of (choose file with prompt "Select your project.json file" of type {"public.json"})'
                else:
                    script = 'POSIX path of (choose file with prompt "Select a file")'
                result = subprocess.check_output(
                    ["osascript", "-e", script], stderr=subprocess.STDOUT
                )
                file_path = result.decode("utf-8").strip()
                if (
                    project_json_only
                    and file_path
                    and not file_path.endswith("project.json")
                ):
                    return (
                        jsonify({"error": "Please select a file named 'project.json'"}),
                        400,
                    )
            except subprocess.CalledProcessError:
                file_path = ""
        elif sys.platform.startswith("win"):
            try:
                file_path = _browse_file_windows_powershell(project_json_only)
                if not file_path:
                    return jsonify({"path": ""}), 200
            except Exception as powershell_err:
                print(f"Windows PowerShell file picker failed: {powershell_err}")
                try:
                    import tkinter as tk
                    from tkinter import filedialog

                    root = tk.Tk()
                    root.withdraw()
                    root.wm_attributes("-topmost", 1)
                    root.focus_force()

                    file_path = filedialog.askopenfilename(
                        title="Select project.json"
                        if project_json_only
                        else "Select file",
                        filetypes=(
                            [("PRISM Project Metadata", "project.json")]
                            if project_json_only
                            else [("All files", "*.*")]
                        ),
                        parent=root,
                    )
                    root.destroy()

                    if not file_path:
                        return jsonify({"path": ""}), 200
                except ImportError as import_err:
                    print(f"File picker error: tkinter not available - {import_err}")
                    return (
                        jsonify(
                            {
                                "error": "File picker unavailable on Windows. PowerShell dialog failed and tkinter is not available. Please manually enter the path."
                            }
                        ),
                        500,
                    )
                except Exception as win_err:
                    print(f"File picker error: {win_err}")
                    return (
                        jsonify(
                            {
                                "error": f"File picker error: {str(win_err)}"
                            }
                        ),
                        500,
                    )
        else:
            try:
                if not os.environ.get("DISPLAY"):
                    return (
                        jsonify({"error": "File picker requires a desktop session."}),
                        501,
                    )

                import tkinter as tk
                from tkinter import filedialog

                root = tk.Tk()
                root.withdraw()
                file_path = filedialog.askopenfilename(
                    title="Select project.json" if project_json_only else "Select file",
                    filetypes=(
                        [("PRISM Project Metadata", "project.json")]
                        if project_json_only
                        else [("All files", "*.*")]
                    ),
                )
                root.destroy()
                if not file_path:
                    return jsonify({"path": ""}), 200
            except Exception as linux_err:
                print(f"Linux file picker error: {linux_err}")
                return jsonify({"error": f"File picker error: {str(linux_err)}"}), 500

        return jsonify({"path": file_path})
    except Exception as e:
        print(f"Unexpected file picker error: {e}")
        return jsonify({"error": str(e)}), 500


def handle_api_browse_folder():
    """Open a system dialog to select a folder."""
    folder_path = ""
    try:
        if sys.platform == "darwin":
            try:
                script = "POSIX path of (choose folder)"
                result = subprocess.check_output(
                    ["osascript", "-e", script], stderr=subprocess.STDOUT
                )
                folder_path = result.decode("utf-8").strip()
            except subprocess.CalledProcessError:
                folder_path = ""
        elif sys.platform.startswith("win"):
            try:
                folder_path = _browse_folder_windows_powershell()
                if not folder_path:
                    return jsonify({"path": ""}), 200
            except Exception as powershell_err:
                print(f"Windows PowerShell folder picker failed: {powershell_err}")
                try:
                    import tkinter as tk
                    from tkinter import filedialog

                    root = tk.Tk()
                    root.withdraw()
                    root.wm_attributes("-topmost", 1)
                    root.focus_force()

                    folder_path = filedialog.askdirectory(
                        title="Select folder for PRISM", parent=root
                    )
                    root.destroy()

                    if not folder_path:
                        return jsonify({"path": ""}), 200
                except ImportError:
                    print("Windows folder picker failed: tkinter not available")
                    return (
                        jsonify(
                            {
                                "error": "Folder picker unavailable on Windows. PowerShell dialog failed and tkinter is not available. Please enter path manually."
                            }
                        ),
                        500,
                    )
                except Exception as win_err:
                    print(f"Windows folder picker failed: {win_err}")
                    import traceback

                    traceback.print_exc()
                    return (
                        jsonify(
                            {
                                "error": f"Folder picker error: {str(win_err)}. Please enter path manually."
                            }
                        ),
                        500,
                    )
        else:
            try:
                if not os.environ.get("DISPLAY"):
                    return (
                        jsonify(
                            {
                                "error": "Folder picker requires a desktop session. Please enter path manually."
                            }
                        ),
                        501,
                    )

                import tkinter as tk
                from tkinter import filedialog

                root = tk.Tk()
                root.withdraw()
                root.attributes("-topmost", True)
                root.focus_force()

                folder_path = filedialog.askdirectory(
                    title="Select folder for PRISM", parent=root
                )
                root.destroy()

                if not folder_path:
                    return jsonify({"path": ""}), 200
            except ImportError:
                print("Linux folder picker failed: tkinter not available")
                return (
                    jsonify(
                        {
                            "error": "Folder picker requires python3-tk package. Install it or enter path manually."
                        }
                    ),
                    500,
                )
            except Exception as linux_err:
                print(f"Linux folder picker failed: {linux_err}")
                import traceback

                traceback.print_exc()
                return (
                    jsonify(
                        {
                            "error": f"Folder picker error: {str(linux_err)}. Please enter path manually."
                        }
                    ),
                    500,
                )

        return jsonify({"path": folder_path})
    except Exception as e:
        print(f"Error opening file dialog: {e}")
        return (
            jsonify(
                {"error": "Could not open file dialog. Please enter path manually."}
            ),
            500,
        )
