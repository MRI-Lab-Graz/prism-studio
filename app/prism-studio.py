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
import time
import webbrowser
import threading
import socket
import uuid
import atexit
import logging
import json
import re
import ipaddress
import http.client
from pathlib import Path
from typing import Any, Dict, Optional
from flask import (
    Flask,
    render_template,
    request,
    jsonify,
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
        format="%(asctime)s - %(levelname)s - %(message)s",
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
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))


def _startup_module_check() -> None:
    """Warn early if critical modules are not importable in this runtime layout."""
    import importlib.util

    required_modules = [
        "src.participants_converter",
        "src.web.blueprints.conversion",
    ]

    missing = [m for m in required_modules if importlib.util.find_spec(m) is None]
    if missing:
        print("[WARN]  Missing critical modules: " + ", ".join(missing))
        print(
            "[WARN]  Please run setup and verify app/src contains required modules for this build."
        )


_startup_module_check()

# Import refactored web modules
get_error_description: Any = None
get_error_documentation_url: Any = None
shorten_path: Any = None
get_filename_from_path: Any = None
run_validation: Any = None

from src.cross_platform import safe_path_join

try:
    from src.web.utils import (
        get_error_description as _get_error_description,
        get_error_documentation_url as _get_error_documentation_url,
        shorten_path as _shorten_path,
        get_filename_from_path as _get_filename_from_path,
    )
    from src.web.validation import run_validation as _run_validation

    get_error_description = _get_error_description
    get_error_documentation_url = _get_error_documentation_url
    shorten_path = _shorten_path
    get_filename_from_path = _get_filename_from_path
    run_validation = _run_validation

    print("[OK] Web modules loaded from src/web/")
except ImportError as e:
    print(f"[WARN]  Could not import web modules: {e}")
    # Fallback definitions will be provided inline if needed

# Legacy alias for backwards compatibility
if run_validation:
    run_main_validator = run_validation
else:
    run_main_validator = None

# Import core components
try:
    from src.survey_manager import SurveyManager

    print("[OK] SurveyManager loaded")
except ImportError as e:
    SurveyManager = None
    print(f"[WARN]  Could not import SurveyManager: {e}")

compute_survey_recipes: Any = None
try:
    from src.recipes_surveys import compute_survey_recipes as _compute_survey_recipes

    compute_survey_recipes = _compute_survey_recipes
except ImportError as e:
    compute_survey_recipes = None
    print(f"[WARN]  Could not import compute_survey_recipes: {e}")


if getattr(sys, "frozen", False):
    template_folder = os.path.join(sys._MEIPASS, "templates")  # type: ignore
    static_folder = os.path.join(sys._MEIPASS, "static")  # type: ignore
    app = Flask(__name__, template_folder=template_folder, static_folder=static_folder)
else:
    app = Flask(__name__)

# Global shutdown flag to signal graceful termination
_shutdown_requested = threading.Event()


def cleanup_and_exit(exit_code=0):
    """Cleanup resources and exit the entire process (not just Flask)."""
    try:
        print("🛑 Cleaning up resources...")
        # Signal shutdown
        _shutdown_requested.set()
        # Give threads a moment to clean up
        time.sleep(0.5)
    except Exception as e:
        print(f"[WARN]  Error during cleanup: {e}")
    finally:
        # Force exit the entire Python process
        # This is necessary for the compiled exe and Waitress server to fully terminate
        # os._exit() immediately terminates all threads and child processes
        print("🛑 Force exiting process...")
        os._exit(exit_code)


# Register cleanup on normal exit
atexit.register(lambda: cleanup_and_exit(0))

# Secret key for session management
# In production, set PRISM_SECRET_KEY environment variable
app.secret_key = os.environ.get(
    "PRISM_SECRET_KEY", "prism-dev-key-change-in-production"
)
app.config["MAX_CONTENT_LENGTH"] = (
    1024 * 1024 * 1024
)  # 1GB max file size (metadata only)
app.config["MAX_FORM_PARTS"] = 20000  # Allow up to 20000 files/fields in upload
app.config["BASE_DIR"] = BASE_DIR  # Make BASE_DIR available to blueprints

# Track app startup for session management
app.config["PRISM_STARTUP_ID"] = uuid.uuid4().hex

# Load app settings and clear last project on startup (no autoload)
from src.config import load_app_settings, save_app_settings
from src.web.backend_monitoring import emit_backend_request_action

_app_settings = load_app_settings(app_root=str(BASE_DIR))
_app_settings.last_project_path = None
_app_settings.last_project_name = None
save_app_settings(_app_settings, app_root=str(BASE_DIR))
app.config["LAST_PROJECT_PATH"] = None
app.config["LAST_PROJECT_NAME"] = None

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

# Register Modular Blueprints (individually so one failure doesn't block others)
modular_blueprints = [
    ("src.web.blueprints.neurobagel", "neurobagel_bp", "neurobagel"),
    ("src.web.blueprints.conversion", "conversion_bp", "conversion"),
    (
        "src.web.blueprints.conversion_survey_blueprint",
        "conversion_survey_bp",
        "conversion_survey",
    ),
    (
        "src.web.blueprints.conversion_participants_blueprint",
        "conversion_participants_bp",
        "conversion_participants",
    ),
    ("src.web.blueprints.library", "library_bp", "library"),
    ("src.web.blueprints.validation", "validation_bp", "validation"),
    ("src.web.blueprints.tools", "tools_bp", "tools"),
    (
        "src.web.blueprints.tools_template_editor_blueprint",
        "tools_template_editor_bp",
        "tools_template_editor",
    ),
    ("src.web.blueprints.projects", "projects_bp", "projects"),
    (
        "src.web.blueprints.projects_library_blueprint",
        "projects_library_bp",
        "projects_library",
    ),
    (
        "src.web.blueprints.projects_export_blueprint",
        "projects_export_bp",
        "projects_export",
    ),
]

registered_modular_blueprints: list[str] = []
for module_name, blueprint_attr, label in modular_blueprints:
    try:
        module = __import__(module_name, fromlist=[blueprint_attr])
        blueprint = getattr(module, blueprint_attr)
        app.register_blueprint(blueprint)
        registered_modular_blueprints.append(label)
    except ImportError as e:
        print(f"[WARN]  Could not import modular blueprint '{label}': {e}")
    except Exception as e:
        print(f"[WARN]  Could not register modular blueprint '{label}': {e}")

if registered_modular_blueprints:
    print(
        "[OK] Modular blueprints registered: "
        + ", ".join(registered_modular_blueprints)
    )
else:
    print("[WARN]  No modular blueprints were registered")

# Note: METADATA_EXTENSIONS and SKIP_EXTENSIONS are now imported from src.web.upload
# Note: format_validation_results, get_error_description, get_error_documentation_url
#       are now imported from src.web.utils


# Global storage for validation results
validation_results: Dict[str, Any] = {}
app.config["VALIDATION_RESULTS"] = validation_results


GITHUB_TAG_CACHE_TTL_SECONDS = 1800
_github_tag_cache: Dict[str, Any] = {"value": "unknown", "expires_at": 0.0}


def _discover_git_dir(start_dir: Path) -> Optional[Path]:
    """Find .git directory from start_dir upwards, including worktree gitdir files."""
    for directory in [start_dir, *start_dir.parents]:
        git_path = directory / ".git"
        if git_path.is_dir():
            return git_path

        if git_path.is_file():
            try:
                first_line = (
                    git_path.read_text(encoding="utf-8").splitlines()[0].strip()
                )
            except (OSError, IndexError):
                continue

            if first_line.lower().startswith("gitdir:"):
                resolved = (directory / first_line.split(":", 1)[1].strip()).resolve()
                if resolved.is_dir():
                    return resolved

    return None


def _collect_git_tags(git_dir: Path) -> set[str]:
    """Collect tag names from loose refs and packed-refs in a local git repository."""
    tags: set[str] = set()

    refs_tags_dir = git_dir / "refs" / "tags"
    if refs_tags_dir.is_dir():
        for tag_ref in refs_tags_dir.rglob("*"):
            if tag_ref.is_file():
                tag_name = tag_ref.relative_to(refs_tags_dir).as_posix().strip()
                if tag_name:
                    tags.add(tag_name)

    packed_refs = git_dir / "packed-refs"
    if packed_refs.is_file():
        try:
            for line in packed_refs.read_text(encoding="utf-8").splitlines():
                stripped = line.strip()
                if not stripped or stripped.startswith("#") or stripped.startswith("^"):
                    continue

                parts = stripped.split(" ", 1)
                if len(parts) != 2:
                    continue

                ref_name = parts[1].strip()
                prefix = "refs/tags/"
                if ref_name.startswith(prefix):
                    tag_name = ref_name[len(prefix) :].strip()
                    if tag_name:
                        tags.add(tag_name)
        except OSError:
            pass

    return tags


def _tag_sort_key(tag_name: str) -> tuple[int, int, int, int, str]:
    """Sort semver-like tags above non-semver tags while keeping deterministic fallback order."""
    normalized = tag_name.strip()
    if normalized.lower().startswith("v"):
        normalized = normalized[1:]

    semver_match = re.match(r"^(\d+)\.(\d+)\.(\d+)$", normalized)
    if semver_match:
        major, minor, patch = (int(part) for part in semver_match.groups())
        return (2, major, minor, patch, "")

    partial_match = re.match(r"^(\d+)\.(\d+)$", normalized)
    if partial_match:
        major, minor = (int(part) for part in partial_match.groups())
        return (1, major, minor, 0, "")

    return (0, 0, 0, 0, tag_name.lower())


def _fetch_latest_local_git_tag() -> Optional[str]:
    """Resolve latest tag from local git metadata without network access."""
    git_dir = _discover_git_dir(BASE_DIR.resolve())
    if git_dir is None:
        return None

    tags = _collect_git_tags(git_dir)
    if not tags:
        return None

    return max(tags, key=_tag_sort_key)


def get_prism_studio_version() -> str:
    """Return cached PRISM Studio version from local git tag or package version."""
    now = time.time()
    cached_value = _github_tag_cache.get("value")
    expires_at = _github_tag_cache.get("expires_at", 0.0)
    if isinstance(cached_value, str) and now < float(expires_at):
        return cached_value

    latest_tag = _fetch_latest_local_git_tag()
    if latest_tag:
        _github_tag_cache["value"] = latest_tag
        _github_tag_cache["expires_at"] = now + GITHUB_TAG_CACHE_TTL_SECONDS
        return latest_tag

    try:
        from src import __version__ as prism_version

        if isinstance(prism_version, str) and prism_version.strip():
            _github_tag_cache["value"] = prism_version.strip()
            _github_tag_cache["expires_at"] = now + GITHUB_TAG_CACHE_TTL_SECONDS
            return prism_version.strip()
    except Exception as error:
        print(f"[WARN]  Local package version lookup failed: {error}")

    _github_tag_cache["expires_at"] = now + GITHUB_TAG_CACHE_TTL_SECONDS
    fallback = _github_tag_cache.get("value")
    return fallback if isinstance(fallback, str) else "unknown"


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
            "name": session.get("current_project_name"),
        },
        "prism_studio_version": get_prism_studio_version(),
    }


@app.before_request
def ensure_project_selected_first():
    """Force users to pick a project first in Prism Studio.

    This keeps all features consistently anchored to the active project path
    (stored in session as current_project_path/current_project_name).
    """
    emit_backend_request_action(request, app_root=str(BASE_DIR))

    # If this is a new browser session, clear any prior project selection
    if session.get("_prism_startup_id") != app.config.get("PRISM_STARTUP_ID"):
        session["_prism_startup_id"] = app.config.get("PRISM_STARTUP_ID")
        session.pop("current_project_path", None)
        session.pop("current_project_name", None)

    if session.get("current_project_path"):
        return None

    path = request.path or "/"

    # Always allow static assets and the project manager itself.
    if path.startswith("/static/"):
        return None
    if path == "/favicon.ico":
        return None
    if path == "/shutdown":
        return None
    if path == "/projects" or path.startswith("/api/projects/"):
        return None
    if path == "/assets/prism-logo" or path == "/assets/prism-logo.png":
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


@app.route("/favicon.ico")
def favicon_ico():
    """Serve favicon directly with caching"""
    from flask import send_from_directory

    return send_from_directory(
        app.static_folder,
        "prism2026.ico",
        mimetype="image/png",
        max_age=86400,  # Cache for 24 hours
    )


@app.route("/assets/prism-logo")
def prism_logo():
    """Serve PRISM logo from docs/img with caching (transparent PNG)"""
    from flask import send_file, Response

    candidates = [
        safe_path_join(BASE_DIR.parent, "docs", "img", "prism_logo.png"),
        safe_path_join(BASE_DIR, "static", "img", "prism_logo.png"),
        safe_path_join(BASE_DIR.parent, "docs", "img", "prism_logo.jpg"),
        safe_path_join(BASE_DIR, "static", "img", "prism_logo.jpg"),
    ]

    for path in candidates:
        file_path = Path(path)
        if file_path.exists():
            mimetype = "image/png" if str(path).endswith(".png") else "image/jpeg"
            return send_file(
                str(file_path),
                mimetype=mimetype,
                max_age=86400,  # Cache for 24 hours
            )

    fallback_svg = """<?xml version=\"1.0\" encoding=\"UTF-8\"?>
<svg xmlns=\"http://www.w3.org/2000/svg\" width=\"560\" height=\"160\" viewBox=\"0 0 560 160\">
  <rect width=\"100%\" height=\"100%\" fill=\"#f8f9fa\"/>
  <rect x=\"12\" y=\"12\" width=\"536\" height=\"136\" rx=\"12\" fill=\"#ffffff\" stroke=\"#dee2e6\"/>
  <text x=\"280\" y=\"95\" text-anchor=\"middle\" font-family=\"Arial, sans-serif\" font-size=\"48\" fill=\"#0d6efd\" font-weight=\"700\">PRISM</text>
  <text x=\"280\" y=\"125\" text-anchor=\"middle\" font-family=\"Arial, sans-serif\" font-size=\"16\" fill=\"#6c757d\">Studio</text>
</svg>"""
    return Response(
        fallback_svg,
        mimetype="image/svg+xml",
        headers={"Cache-Control": "public, max-age=86400"},
    )


@app.route("/specifications")
def specifications():
    """Page explaining the PRISM specifications"""
    return render_template("specifications.html")


@app.route("/health", methods=["GET"])
def health_check():
    """Health check endpoint - returns 200 if server is running."""
    return jsonify({"status": "ok", "running": True}), 200


@app.route("/shutdown", methods=["POST"])
def shutdown():
    """Shutdown the server and exit the entire application process."""

    def terminate_app():
        """Terminate the Flask server and exit the process."""
        # Brief delay to allow response to be sent
        time.sleep(0.3)

        try:
            print("🛑 Shutdown request received, terminating application...")

            # Try Werkzeug shutdown first (works in Flask dev server)
            func = request.environ.get("werkzeug.server.shutdown")
            if callable(func):
                try:
                    print("  → Stopping Werkzeug server...")
                    func()
                    time.sleep(0.2)
                except Exception as e:
                    print(f"  [INFO]  Werkzeug shutdown: {e}")
        except Exception as e:
            print(f"  [INFO]  Could not access werkzeug shutdown: {e}")
        finally:
            # Force exit the entire process
            # This ensures the exe/process completely terminates, not just the server
            cleanup_and_exit(0)

    # Start termination in a background thread so we can send the response first
    term_thread = threading.Thread(target=terminate_app, daemon=False)
    term_thread.start()

    return jsonify({"success": True, "message": "Application is shutting down..."})


# Note: Validation, Conversion, Library, and Tools routes are now handled by blueprints.
# See src/web/blueprints/ for details.


def is_port_in_use(host, port):
    """Check if a port is already in use."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        try:
            return s.connect_ex((host, port)) == 0
        except Exception:
            return False


def try_kill_existing_process(port):
    """Try to kill any existing process using the specified port."""
    try:
        if sys.platform == "win32":
            # Windows: use taskkill with netstat to find PID
            import subprocess

            result = subprocess.run(
                ["netstat", "-ano"],
                capture_output=True,
                text=True,
                check=False,
            )
            for line in result.stdout.split("\n"):
                if f":{port}" in line and "LISTENING" in line:
                    parts = line.split()
                    if parts:
                        pid = parts[-1]
                        try:
                            subprocess.run(
                                ["taskkill", "/PID", pid, "/F"],
                                capture_output=True,
                                check=False,
                            )
                            print(f"[INFO]  Stopped process {pid} on port {port}")
                            time.sleep(0.5)
                            return True
                        except Exception as e:
                            print(f"[WARN]  Could not kill process {pid}: {e}")
        else:
            # Unix: use lsof to find and kill process
            import subprocess

            result = subprocess.run(
                ["lsof", "-i", f":{port}"],
                capture_output=True,
                text=True,
                check=False,
            )
            for line in result.stdout.split("\n")[1:]:
                if line.strip():
                    parts = line.split()
                    if len(parts) >= 2:
                        pid = parts[1]
                        try:
                            subprocess.run(
                                ["kill", "-9", pid],
                                capture_output=True,
                                check=False,
                            )
                            print(f"[INFO]  Stopped process {pid} on port {port}")
                            time.sleep(0.5)
                            return True
                        except Exception as e:
                            print(f"[WARN]  Could not kill process {pid}: {e}")
    except Exception as e:
        print(f"[INFO]  Could not attempt to kill existing process: {e}")
    return False


def request_existing_instance_shutdown(host: str, port: int) -> bool:
    """Ask an existing PRISM Studio instance to stop itself cleanly."""
    try:
        # Convert wildcard bind addresses to loopback for local shutdown requests.
        shutdown_host = (
            "127.0.0.1" if ipaddress.ip_address(host).is_unspecified else host
        )
    except ValueError:
        shutdown_host = host

    shutdown_url = f"http://{shutdown_host}:{port}/shutdown"
    conn = None

    try:
        conn = http.client.HTTPConnection(shutdown_host, port, timeout=2.5)
        conn.request(
            "POST",
            "/shutdown",
            body=b"{}",
            headers={"Content-Type": "application/json"},
        )
        response = conn.getresponse()
        response.read()

        if 200 <= response.status < 300:
            print(f"[INFO]  Requested graceful shutdown at {shutdown_url}")
            return True

        print(
            f"[INFO]  Graceful shutdown endpoint returned {response.status}"
            f" {response.reason}"
        )
        return False
    except (OSError, http.client.HTTPException) as err:
        print(f"[INFO]  Graceful shutdown request failed: {err}")
        return False
    except Exception as err:
        print(f"[INFO]  Could not request graceful shutdown: {err}")
        return False
    finally:
        if conn is not None:
            conn.close()


def wait_for_port_release(host: str, port: int, timeout_seconds: float = 8.0) -> bool:
    """Wait until the target port is no longer in use."""
    deadline = time.time() + timeout_seconds
    while time.time() < deadline:
        if not is_port_in_use(host, port):
            return True
        time.sleep(0.25)
    return not is_port_in_use(host, port)


def ensure_clean_start(host: str, port: int, force: bool = False) -> None:
    """Ensure no previous process occupies the target port before startup."""
    if not is_port_in_use(host, port):
        return

    print(f"[WARN]  Port {port} is already in use")
    print("[INFO]  Attempting graceful shutdown of existing instance...")
    graceful_stop_requested = request_existing_instance_shutdown(host, port)
    if graceful_stop_requested and wait_for_port_release(host, port):
        print(f"[INFO]  Previous instance stopped gracefully, reusing port {port}")
        return

    if not force:
        print(
            f"[ERROR] Could not stop existing process on port {port} gracefully."
            f"\n        Re-run with --force-clean-start to force termination,"
            f"\n        or use --port to specify a different port."
        )
        sys.exit(1)

    print("[INFO]  Graceful shutdown unavailable; forcing clean start...")
    if not try_kill_existing_process(port):
        print(
            f"[ERROR] Could not stop existing process on port {port}."
            f"\n        Please close the existing PRISM Studio instance or use --port to specify a different port."
        )
        sys.exit(1)

    if not wait_for_port_release(host, port):
        print(
            f"[ERROR] Port {port} is still busy after stop attempt."
            f"\n        Please wait a few seconds and try again, or use --port to specify a different port."
        )
        sys.exit(1)

    print(f"[INFO]  Previous process stopped, reusing port {port}")


def main():
    """Run the web application"""
    import argparse

    def configure_debug_logging() -> None:
        logging.basicConfig(
            level=logging.DEBUG,
            format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
            force=True,
        )
        logging.getLogger("werkzeug").setLevel(logging.DEBUG)
        logging.getLogger("waitress").setLevel(logging.DEBUG)
        logging.getLogger("src").setLevel(logging.DEBUG)
        app.logger.setLevel(logging.DEBUG)
        app.config["PROPAGATE_EXCEPTIONS"] = True

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
        "--force-clean-start",
        action="store_true",
        help="Force-stop any process using the selected port before launch",
    )

    args = parser.parse_args()

    host = "0.0.0.0" if args.public else args.host  # nosec B104

    # Use the specified port and optionally enforce a force-clean startup.
    port = args.port
    ensure_clean_start(host, port, force=args.force_clean_start)

    display_host = "localhost" if host == "127.0.0.1" else host
    scheme = "http"
    url = f"{scheme}://{display_host}:{port}"

    print("Starting PRISM Studio")
    print(f"URL: {url}")
    if args.public:
        print(
            "[WARN]  Warning: Running in public mode - accessible from other computers"
        )
    print("Press Ctrl+C to stop the server")

    # Show log location for compiled version
    if getattr(sys, "frozen", False):
        log_file = Path.home() / "prism_studio.log"
        print(f"Log file: {log_file}")
    print()

    # On Windows compiled version, show a startup notification
    if (
        getattr(sys, "frozen", False)
        and sys.platform.startswith("win")
        and not args.no_browser
    ):

        def show_startup_dialog():
            """Show startup notification with proper DPI scaling using tkinter"""
            try:
                import tkinter as tk
                from tkinter import messagebox

                root = tk.Tk()
                root.withdraw()  # Hide main window
                root.attributes("-topmost", True)  # Bring to front

                messagebox.showinfo(
                    "PRISM Studio",
                    f"PRISM Studio is starting...\n\nOpening browser at:\n{url}\n\nIf browser doesn't open automatically,\nplease visit the URL manually.",
                )
                root.destroy()
            except Exception as e:
                print(f"Could not show startup notification: {e}")

        threading.Thread(target=show_startup_dialog, daemon=True).start()

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
                    if sys.platform.startswith("win"):
                        # Windows fallback: use start command
                        subprocess.Popen(["cmd", "/c", "start", "", url])
                        print("✅ Browser opened via Windows fallback")
                    elif sys.platform == "darwin":
                        # macOS fallback
                        subprocess.Popen(["open", url])
                        print("✅ Browser opened via macOS fallback")
                    else:
                        # Linux fallback
                        subprocess.Popen(["xdg-open", url])
                        print("✅ Browser opened via Linux fallback")
                except Exception as fallback_err:
                    print(
                        f"[WARN]  Could not open browser automatically: {fallback_err}"
                    )
                    print(f"   Please visit {url} manually")

        browser_thread = threading.Thread(target=open_browser, daemon=True)
        browser_thread.start()

    if args.debug:
        configure_debug_logging()
        print("[DEBUG] Debug mode enabled (verbose logging, Flask debugger active)")
        app.run(
            host=host,
            port=port,
            debug=args.debug,
            use_reloader=False,
            use_evalex=False,
        )
    else:
        try:
            from waitress import serve

            print(f"Running with Waitress server on {host}:{port}")
            serve(app, host=host, port=port)
        except ImportError:
            print(
                "[WARN]  Waitress not installed, falling back to Flask development server"
            )
            app.run(host=host, port=port, debug=False)


if __name__ == "__main__":
    main()
