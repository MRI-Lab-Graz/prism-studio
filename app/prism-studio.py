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
import webbrowser
import threading
import socket
import uuid
from pathlib import Path
from typing import Any, Dict
from flask import (
    Flask,
    render_template,
    request,
    jsonify,
    send_file,
    flash,
    redirect,
    url_for,
    session,
)

# Setup logging for compiled version (no console on Windows)
if getattr(sys, "frozen", False):
    import logging
    log_file = Path.home() / "prism_studio.log"
    logging.basicConfig(
        filename=str(log_file),
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )
    
    # Redirect stdout/stderr to log file for compiled version
    class LogWriter:
        def __init__(self, logger, level):
            self.logger = logger
            self.level = level
            
        def write(self, message):
            if message.strip():
                self.logger.log(self.level, message.strip())
                
        def flush(self):
            pass
    
    logger = logging.getLogger()
    sys.stdout = LogWriter(logger, logging.INFO)
    sys.stderr = LogWriter(logger, logging.ERROR)
    
    print(f"PRISM Studio starting... Log file: {log_file}")

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
        get_error_description,
        get_error_documentation_url,
        shorten_path,
        get_filename_from_path,
        # Validation
        run_validation,
    )

    print("[OK] Web modules loaded from src/web/")
except ImportError as e:
    print(f"[WARN]  Could not import web modules: {e}")
    # Fallback definitions will be provided inline if needed

# Legacy alias for backwards compatibility
run_main_validator = run_validation

# Import core components
try:
    from src.survey_manager import SurveyManager
    print("[OK] SurveyManager loaded")
except ImportError as e:
    SurveyManager = None
    print(f"[WARN]  Could not import SurveyManager: {e}")

try:
    from src.recipes_surveys import compute_survey_recipes
except ImportError as e:
    compute_survey_recipes = None
    print(f"[WARN]  Could not import compute_survey_recipes: {e}")


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

# Reset current project on each app start (per browser session cookie).
# This keeps the initial landing page empty, even if an old session cookie exists.
app.config["PRISM_STARTUP_ID"] = uuid.uuid4().hex

# Initialize Survey Manager with global library paths
from src.config import get_effective_library_paths

lib_paths = get_effective_library_paths(app_root=str(BASE_DIR))
if lib_paths["global_library_path"]:
    survey_library_path = Path(lib_paths["global_library_path"])
    print(f"[INFO]  Using global library: {survey_library_path}")
else:
    # Fallback to legacy survey_library folder
    survey_library_path = BASE_DIR / "survey_library"
    print(f"[INFO]  Using fallback library: {survey_library_path}")

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
    print(f"[INFO]  JSON Editor not available: {e}")
except Exception as e:
    print(f"[WARN]  Error registering JSON Editor blueprint: {e}")

# Register REST API blueprint
try:
    from src.api import create_api_blueprint

    schema_dir = str(BASE_DIR / "schemas")
    api_bp = create_api_blueprint(schema_dir=schema_dir)
    app.register_blueprint(api_bp)
    print("[OK] REST API registered at /api/v1")
except ImportError as e:
    print(f"[INFO]  REST API not available: {e}")
except Exception as e:
    print(f"[WARN]  Error registering REST API blueprint: {e}")

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
    print(f"[WARN]  Error importing modular blueprints: {e}")
except Exception as e:
    print(f"[WARN]  Error registering modular blueprints: {e}")

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


@app.before_request
def ensure_project_selected_first():
    """Force users to pick a project first in Prism Studio.

    This keeps all features consistently anchored to the active project path
    (stored in session as current_project_path/current_project_name).
    """
    # If this is a new Prism Studio process start, clear any persisted project selection.
    if session.get("_prism_startup_id") != app.config.get("PRISM_STARTUP_ID"):
        session.pop("current_project_path", None)
        session.pop("current_project_name", None)
        session["_prism_startup_id"] = app.config.get("PRISM_STARTUP_ID")

    if session.get("current_project_path"):
        return None

    path = request.path or "/"

    # Always allow static assets and the project manager itself.
    if path.startswith("/static/"):
        return None
    if path == "/projects" or path.startswith("/api/projects/"):
        return None

    # Allow utility endpoints needed before a project is selected (used on /projects).
    if path == "/api/browse-folder":
        return None
    if path == "/api/browse-file":
        return None
    if path.startswith("/api/settings/"):
        return None

    # Allow documentation/specs and embedded editor/API tools without a project.
    if path == "/specifications":
        return None
    if path.startswith("/api/v1/"):
        return None
    if path.startswith("/editor"):
        return None

    # Allow tool landing pages (GET) even without a project
    # This avoids the "clicking link does nothing" behavior (silent redirects)
    # The tools themselves handle the absence of a project UI-wise.
    if request.method == "GET" and path in (
        "/",
        "/converter",
        "/validate",
        "/recipes",
        "/survey-generator",
        "/survey-customizer",
        "/template-editor",
        "/library-editor",
        "/neurobagel",
    ):
        return None

    # Allow API endpoints needed by tools that work without a project
    if path in (
        "/api/list-library-files",
        "/api/survey-customizer/load",
        "/api/survey-customizer/export",
        "/api/survey-customizer/formats",
        "/api/generate-lss",
        "/api/generate-boilerplate",
    ):
        return None

    # Allow validation API and results even without a project
    # This enables one-off validation of uploaded ZIPs or folders.
    if (
        path == "/upload" 
        or path == "/validate_folder" 
        or path.startswith("/api/progress/") 
        or path.startswith("/results/") 
        or path.startswith("/download_report/")
        or path.startswith("/cleanup/")
        or path == "/api/validate"
    ):
        return None

    # For pages, redirect to the project selector.
    if request.method == "GET":
        return redirect(url_for("projects.projects_page"))

    # For non-GET requests, return a structured error.
    return jsonify({"success": False, "error": "No current project selected"}), 400


@app.route("/")
def index():
    """Home page with tool selection"""
    # With the global guard, we only get here if a project is already selected.
    return render_template("home.html")


@app.route("/specifications")
def specifications():
    """Page explaining the PRISM specifications"""
    return render_template("specifications.html")


@app.route("/shutdown", methods=["POST"])
def shutdown():
    """Shutdown the server"""
    import os
    import signal
    import threading
    import time
    
    def kill_server():
        time.sleep(1)
        print("🛑 Shutting down server...")
        os.kill(os.getpid(), signal.SIGINT)

    # Try Werkzeug shutdown first (works in debug mode)
    func = request.environ.get('werkzeug.server.shutdown')
    if func:
        func()
    else:
        # Fallback for Waitress/Production
        threading.Thread(target=kill_server).start()
        
    return jsonify({"success": True, "message": "Server is shutting down..."})


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

    args = parser.parse_args()

    host = "0.0.0.0" if args.public else args.host

    # Find a free port if the default one is taken
    port = args.port
    if not args.public:  # Only auto-find port for local binding
        port = find_free_port(args.port)
        if port != args.port:
            print(f"[INFO]  Port {args.port} is in use, using {port} instead")

    display_host = "localhost" if host == "127.0.0.1" else host
    url = f"http://{display_host}:{port}"

    print("Starting PRISM Studio")
    print(f"URL: {url}")
    if args.public:
        print("[WARN]  Warning: Running in public mode - accessible from other computers")
    print("Press Ctrl+C to stop the server")

    # Show log location for compiled version
    if getattr(sys, "frozen", False):
        log_file = Path.home() / "prism_studio.log"
        print(f"Log file: {log_file}")
    print()
    
    # On Windows compiled version, show a startup notification
    if getattr(sys, "frozen", False) and sys.platform.startswith('win') and not args.no_browser:
        try:
            import ctypes
            MessageBox = ctypes.windll.user32.MessageBoxW
            threading.Thread(
                target=lambda: MessageBox(
                    0,
                    f"PRISM Studio is starting...\n\nOpening browser at:\n{url}\n\nIf browser doesn't open automatically,\nplease visit the URL manually.",
                    "PRISM Studio",
                    0x40  # MB_ICONINFORMATION
                ),
                daemon=True
            ).start()
        except Exception as e:
            print(f"Could not show startup notification: {e}")

    # Open browser in a separate thread to avoid blocking the Flask server
    if not args.no_browser:

        def open_browser():
            import time
            import subprocess

            time.sleep(1.5)  # Wait for server to start (increased for compiled version)
            try:
                # Try standard webbrowser module first
                if webbrowser.open(url):
                    print("✅ Browser opened automatically")
                else:
                    # If webbrowser.open() returns False, try platform-specific fallback
                    raise Exception("webbrowser.open() returned False")
            except Exception as e:
                print(f"[INFO]  Standard browser open failed: {e}")
                
                # Platform-specific fallback
                try:
                    if sys.platform.startswith('win'):
                        # Windows fallback: use start command
                        subprocess.Popen(['cmd', '/c', 'start', '', url], shell=True)
                        print("✅ Browser opened via Windows fallback")
                    elif sys.platform == 'darwin':
                        # macOS fallback
                        subprocess.Popen(['open', url])
                        print("✅ Browser opened via macOS fallback")
                    else:
                        # Linux fallback
                        subprocess.Popen(['xdg-open', url])
                        print("✅ Browser opened via Linux fallback")
                except Exception as fallback_err:
                    print(f"[WARN]  Could not open browser automatically: {fallback_err}")
                    print(f"   Please visit {url} manually")

        browser_thread = threading.Thread(target=open_browser, daemon=True)
        browser_thread.start()

    if args.debug:
        app.run(host=host, port=port, debug=False)
    else:
        try:
            from waitress import serve

            print(f"🚀 Running with Waitress server on {host}:{port}")
            serve(app, host=host, port=port)
        except ImportError:
            print("[WARN]  Waitress not installed, falling back to Flask development server")
            app.run(host=host, port=port, debug=False)


if __name__ == "__main__":
    main()
