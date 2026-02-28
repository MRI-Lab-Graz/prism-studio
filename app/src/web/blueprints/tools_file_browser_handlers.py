import os
import subprocess
import sys

from flask import jsonify


def handle_api_browse_file():
    """Open a system dialog to select a file (filtering for project.json)."""
    file_path = ""
    try:
        if sys.platform == "darwin":
            try:
                script = 'POSIX path of (choose file with prompt "Select your project.json file" of type {"public.json"})'
                result = subprocess.check_output(
                    ["osascript", "-e", script], stderr=subprocess.STDOUT
                )
                file_path = result.decode("utf-8").strip()
                if file_path and not file_path.endswith("project.json"):
                    return (
                        jsonify({"error": "Please select a file named 'project.json'"}),
                        400,
                    )
            except subprocess.CalledProcessError:
                file_path = ""
        elif sys.platform.startswith("win"):
            try:
                import tkinter as tk
                from tkinter import filedialog

                root = tk.Tk()
                root.withdraw()
                root.wm_attributes("-topmost", 1)
                root.focus_force()

                file_path = filedialog.askopenfilename(
                    title="Select project.json",
                    filetypes=[("PRISM Project Metadata", "project.json")],
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
                            "error": "File picker requires tkinter. Please manually enter the path."
                        }
                    ),
                    500,
                )
            except Exception as win_err:
                print(f"File picker error: {win_err}")
                return jsonify({"error": f"File picker error: {str(win_err)}"}), 500
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
                    title="Select project.json",
                    filetypes=[("PRISM Project Metadata", "project.json")],
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
                            "error": "Folder picker requires tkinter. Please install Python with tcl/tk support, or enter path manually."
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
