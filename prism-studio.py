#!/usr/bin/env python3
"""
Web interface for prism
A simple Flask web app that provides a user-friendly interface for dataset validation

This module has been refactored to use modular components from src/web/:
- src/web/utils.py: Utility functions (path handling, error formatting)
- src/web/validation.py: Validation logic and progress tracking
- src/web/upload.py: File upload processing
"""

import os
import sys
import json
import re
import tempfile
import shutil
import webbrowser
import threading
import socket
from pathlib import Path
from datetime import datetime
from typing import Optional, Callable, Any, Dict
from flask import (
    Flask,
    render_template,
    request,
    jsonify,
    send_file,
    flash,
    redirect,
    url_for,
)
from werkzeug.utils import secure_filename
import zipfile
import io
import requests
from functools import lru_cache

# Ensure we can import core validator logic from src
if getattr(sys, "frozen", False):
    # Running in a PyInstaller bundle
    BASE_DIR = Path(sys._MEIPASS)  # type: ignore
else:
    # Running in a normal Python environment
    BASE_DIR = Path(__file__).resolve().parent

SRC_DIR = BASE_DIR / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

# Import refactored web modules
try:
    from src.web import (
        # Utils
        is_system_file,
        format_validation_results,
        get_error_description,
        get_error_documentation_url,
        shorten_path,
        get_filename_from_path,
        # Validation
        run_validation,
        update_progress,
        get_progress,
        clear_progress,
        SimpleStats,
        # Upload
        process_folder_upload as _process_folder_upload,
        process_zip_upload as _process_zip_upload,
        find_dataset_root,
        METADATA_EXTENSIONS,
        SKIP_EXTENSIONS,
    )

    print("[OK] Web modules loaded from src/web/")
except ImportError as e:
    print(f"[WARN] Could not import web modules: {e}")
    # Fallback definitions will be provided inline if needed

# Legacy alias for backwards compatibility
run_main_validator = run_validation

# Import core components
try:
    from src.survey_manager import SurveyManager
    print("[OK] SurveyManager loaded")
except ImportError as e:
    SurveyManager = None
    print(f"[WARN] Could not import SurveyManager: {e}")

try:
    from src.recipes_surveys import compute_survey_recipes
except ImportError as e:
    compute_survey_recipes = None
    print(f"[WARN] Could not import compute_survey_recipes: {e}")


if getattr(sys, "frozen", False):
    template_folder = os.path.join(sys._MEIPASS, "templates")  # type: ignore
    static_folder = os.path.join(sys._MEIPASS, "static")  # type: ignore
    app = Flask(__name__, template_folder=template_folder, static_folder=static_folder)
else:
    app = Flask(__name__)

# Secret key for session management
# In production, set PRISM_SECRET_KEY environment variable
app.secret_key = os.environ.get(
    "PRISM_SECRET_KEY", "prism-dev-key-change-in-production"
)
app.config["MAX_CONTENT_LENGTH"] = (
    1024 * 1024 * 1024
)  # 1GB max file size (metadata only)
app.config["MAX_FORM_PARTS"] = 20000  # Allow up to 20000 files/fields in upload

# Initialize Survey Manager
survey_library_path = BASE_DIR / "survey_library"
survey_manager = None
if SurveyManager:
    survey_manager = SurveyManager(survey_library_path)
    app.config["SURVEY_MANAGER"] = survey_manager
    print(f"[OK] Survey Manager initialized at {survey_library_path}")

# Register JSON Editor blueprint if available
try:
    from src.json_editor_blueprint import create_json_editor_blueprint

    json_editor_bp = create_json_editor_blueprint(bids_folder=None)
    app.register_blueprint(json_editor_bp)
    print("[OK] JSON Editor blueprint registered at /editor")
except ImportError as e:
    print(f"[INFO] JSON Editor not available: {e}")
except Exception as e:
    print(f"[WARN] Error registering JSON Editor blueprint: {e}")

# Register REST API blueprint
try:
    from src.api import create_api_blueprint

    schema_dir = str(BASE_DIR / "schemas")
    api_bp = create_api_blueprint(schema_dir=schema_dir)
    app.register_blueprint(api_bp)
    print("[OK] REST API registered at /api/v1")
except ImportError as e:
    print(f"[INFO] REST API not available: {e}")
except Exception as e:
    print(f"[WARN] Error registering REST API blueprint: {e}")

# Register Modular Blueprints
try:
    from src.web.blueprints.neurobagel import neurobagel_bp
    from src.web.blueprints.conversion import conversion_bp
    from src.web.blueprints.library import library_bp
    from src.web.blueprints.validation import validation_bp
    from src.web.blueprints.tools import tools_bp
    from src.web.blueprints.projects import projects_bp

    app.register_blueprint(neurobagel_bp)
    app.register_blueprint(conversion_bp)
    app.register_blueprint(library_bp)
    app.register_blueprint(validation_bp)
    app.register_blueprint(tools_bp)
    app.register_blueprint(projects_bp)
    print("[OK] Modular blueprints registered (neurobagel, conversion, library, validation, tools, projects)")
except ImportError as e:
    print(f"[WARN] Error importing modular blueprints: {e}")
except Exception as e:
    print(f"[WARN] Error registering modular blueprints: {e}")

# Note: METADATA_EXTENSIONS and SKIP_EXTENSIONS are now imported from src.web.upload
# Note: format_validation_results, get_error_description, get_error_documentation_url
#       are now imported from src.web.utils


# Global storage for validation results
validation_results: Dict[str, Any] = {}
app.config["VALIDATION_RESULTS"] = validation_results


@app.context_processor
def inject_utilities():
    """Inject utility functions into all templates"""
    from flask import session
    return {
        "get_filename_from_path": get_filename_from_path,
        "shorten_path": shorten_path,
        "get_error_description": get_error_description,
        "get_error_documentation_url": get_error_documentation_url,
        "current_project": {
            "path": session.get("current_project_path"),
            "name": session.get("current_project_name")
        },
    }


@app.route("/favicon.ico")
def favicon():
    """Serve favicon from static folder"""
    return send_file(
        os.path.join(app.static_folder, "img", "favicon.png"),
        mimetype="image/png"
    )


@app.route("/")
def index():
    """Home page with tool selection"""
    return render_template("home.html")


@app.route("/specifications")
def specifications():
    """Page explaining the PRISM specifications"""
    return render_template("specifications.html")


# Note: Validation, Conversion, Library, and Tools routes are now handled by blueprints.
# See src/web/blueprints/ for details.

def find_free_port(start_port):
    port = start_port
    while port < 65535:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            if s.connect_ex(("127.0.0.1", port)) != 0:
                return port
            port += 1
    return start_port


def main():
    """Run the web application"""
    import argparse

    parser = argparse.ArgumentParser(description="PRISM Studio")
    parser.add_argument(
        "--host", default="127.0.0.1", help="Host to bind to (default: 127.0.0.1)"
    )
    parser.add_argument(
        "--port",
        type=int,
        default=5001,
        help="Port to bind to (default: 5001, avoiding macOS Control Center on port 5000)",
    )
    parser.add_argument("--debug", action="store_true", help="Run in debug mode")
    parser.add_argument(
        "--public",
        action="store_true",
        help="Allow external connections (sets host to 0.0.0.0)",
    )
    parser.add_argument(
        "--no-browser",
        action="store_true",
        help="Do not automatically open browser",
    )
    parser.add_argument(
        "--browser",
        type=str,
        default=None,
        help="Browser to use (e.g., 'chrome', 'firefox'). Uses system default if not specified.",
    )

    args = parser.parse_args()

    host = "0.0.0.0" if args.public else args.host

    # Find a free port if the default one is taken
    port = args.port
    if not args.public:  # Only auto-find port for local binding
        port = find_free_port(args.port)
        if port != args.port:
            print(f"[INFO] Port {args.port} is in use, using {port} instead")

    display_host = "localhost" if host == "127.0.0.1" else host
    url = f"http://{display_host}:{port}"

    print("Starting PRISM Studio")
    print(f"URL: {url}")
    if args.public:
        print("[WARN] Running in public mode - accessible from other computers")
    print("Press Ctrl+C to stop the server")
    print()

    # Open browser in a separate thread to avoid blocking the Flask server
    if not args.no_browser:

        def open_browser():
            import time

            time.sleep(1)  # Wait for server to start
            try:
                if args.browser:
                    # Try to get specific browser
                    try:
                        browser = webbrowser.get(args.browser)
                        browser.open(url)
                        print(f"[OK] Opened in {args.browser}")
                    except webbrowser.Error:
                        print(f"[WARN] Browser '{args.browser}' not found, using default")
                        webbrowser.open(url)
                        print("[OK] Browser opened automatically")
                else:
                    webbrowser.open(url)
                    print("[OK] Browser opened automatically")
            except Exception as e:
                print(f"[INFO] Could not open browser automatically: {e}")
                print(f"   Please visit {url} manually")

        browser_thread = threading.Thread(target=open_browser, daemon=True)
        browser_thread.start()

    if args.debug:
        app.run(host=host, port=port, debug=False)
    else:
        try:
            from waitress import serve

            print(f"Running with Waitress server on {host}:{port}")
            serve(app, host=host, port=port)
        except ImportError:
            print("[WARN] Waitress not installed, falling back to Flask development server")
            app.run(host=host, port=port, debug=False)


if __name__ == "__main__":
    main()
