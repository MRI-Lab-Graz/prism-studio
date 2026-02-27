"""
Shared utilities for conversion blueprints.
Helper functions and common logic used across survey, biometrics, physio converters.
"""

import re
import unicodedata
from pathlib import Path
from flask import current_app


def normalize_filename(name: str) -> str:
    """Normalize filename to ASCII-safe characters (e.g., remove umlauts)."""
    dash_map = {
        ord("–"): "-",  # en dash
        ord("—"): "-",  # em dash
        ord("‑"): "-",  # non-breaking hyphen
        ord("−"): "-",  # minus sign
        ord("‐"): "-",  # hyphen
    }
    normalized = name.translate(dash_map)
    normalized = unicodedata.normalize("NFKD", normalized)
    normalized = normalized.encode("ascii", "ignore").decode("ascii")
    normalized = re.sub(r"\s+", "_", normalized)
    return normalized


def should_retry_with_official_library(err: Exception) -> bool:
    """Return true when converter error suggests official-template fallback."""
    return isinstance(err, ValueError) and (
        "no survey item columns matched" in str(err).lower()
    )


def is_project_code_library(library_dir: str | Path, project_path: str | None) -> bool:
    """Check if selected library path points to current project's code/library."""
    if not project_path:
        return False
    project_root = Path(project_path).expanduser().resolve()
    if project_root.is_file():
        project_root = project_root.parent

    library_dir = Path(library_dir).expanduser().resolve()
    code_library = project_root / "code" / "library"
    return library_dir in {code_library, code_library / "survey"}


def extract_tasks_from_output(output_root: Path) -> list[str]:
    """Extract unique task names from BIDS-style filenames in output directory."""
    tasks = set()
    for file_path in output_root.rglob("*"):
        if file_path.is_file() and "_task-" in file_path.name:
            match = re.search(r"_task-([a-zA-Z0-9]+)", file_path.name)
            if match:
                tasks.add(match.group(1))
    return sorted(tasks)


def participant_json_candidates(library_root: Path, depth: int = 3):
    """List possible participants.json locations above a library root."""
    library_root = library_root.resolve()
    candidates = [library_root / "participants.json"]
    for parent in library_root.parents[:depth]:
        candidates.append(parent / "participants.json")
    return candidates


def log_file_head(input_path: Path, suffix: str, log_func):
    """Helper to log the first few lines of a file to debug delimiter or structure issues."""
    try:
        if suffix in {".csv", ".tsv"}:
            with open(input_path, "r", encoding="utf-8", errors="replace") as f:
                head_lines = []
                for i in range(4):
                    line = f.readline()
                    if not line:
                        break
                    head_lines.append(f"  L{i + 1}: {line.strip()}")
                if head_lines:
                    log_func(
                        "Detected file content (first 4 lines):\n"
                        + "\n".join(head_lines),
                        "info",
                    )
        elif suffix == ".xlsx":
            try:
                import pandas as pd

                # Read only first few rows
                df = pd.read_excel(input_path, nrows=4)
                head_lines = []
                # Header row
                cols = [str(c) for c in df.columns]
                head_lines.append("  H:  " + "\t".join(cols))
                # Data rows
                for i, row in df.iterrows():
                    vals = [str(v) for v in row.values]
                    head_lines.append(f"  R{i + 1}: " + "\t".join(vals))
                if head_lines:
                    log_func(
                        "Detected Excel structure (first 4 rows):\n"
                        + "\n".join(head_lines),
                        "info",
                    )
            except Exception as e:
                log_func(f"Could not read Excel preview: {str(e)}", "warning")
    except Exception as e:
        log_func(f"Could not log file head: {str(e)}", "warning")


def resolve_effective_library_path() -> Path:
    """
    Automatically resolve library path:
    1. First, try project's /code/library (only if it has templates)
    2. Then try project's /official/library (or /official/library/survey)
    3. Fall back to global library

    Returns the resolved Path to the library root.
    Raises an error if no valid library is found.
    """

    def _safe_resolve(path: Path) -> Path:
        """Safely resolve path, handling network drives."""
        try:
            return path.resolve()
        except (OSError, ValueError):
            # For network paths that can't be resolved, return as-is
            return path

    def _safe_expand(path_str: str) -> Path:
        """Safely expand path, handling network drives."""
        try:
            candidate = Path(path_str)
            if "~" in path_str:
                candidate = candidate.expanduser()
            return candidate
        except (OSError, ValueError):
            return Path(path_str)

    from src.web.blueprints.projects import get_current_project

    # Try project library first, then project official templates
    project = get_current_project()
    project_path = project.get("path")
    if project_path:
        project_root = _safe_expand(project_path)
        try:
            project_root = _safe_resolve(project_root)
        except Exception:
            pass

        def _has_survey_templates(path: Path) -> bool:
            if not path.exists() or not path.is_dir():
                return False
            survey_dir = path / "survey" if (path / "survey").is_dir() else path
            try:
                return bool(list(survey_dir.glob("survey-*.json")))
            except (OSError, ValueError):
                return False

        # Preferred: project code/library
        project_library = project_root / "code" / "library"
        if _has_survey_templates(project_library):
            return project_library

        # Next: project official library
        official_library = project_root / "official" / "library"
        if _has_survey_templates(official_library):
            return official_library

        # Also accept direct official/library/survey as root
        official_survey = official_library / "survey"
        if _has_survey_templates(official_survey):
            return official_survey
        # If project libraries exist but lack templates, fall through to global library

    # Fall back to global library
    from src.config import get_effective_library_paths

    # current_app.root_path points to /app directory, we need to go up one level to get to the workspace root
    base_dir = Path(current_app.root_path)
    try:
        base_dir = base_dir.parent.resolve()
    except (OSError, ValueError):
        base_dir = base_dir.parent

    lib_paths = get_effective_library_paths(app_root=str(base_dir))

    if lib_paths.get("global_library_path"):
        global_lib = _safe_expand(lib_paths["global_library_path"])
        try:
            global_lib = _safe_resolve(global_lib)
        except Exception:
            pass
        if global_lib.exists() and global_lib.is_dir():
            return global_lib

    # Last resort: check default locations
    default_locations = [
        base_dir / "library" / "survey_i18n",
        base_dir / "survey_library",
        base_dir / "official" / "library",
    ]

    for location in default_locations:
        try:
            if location.exists() and location.is_dir():
                return location
        except (OSError, ValueError):
            continue

    raise FileNotFoundError(
        "No survey library found. Please provide templates in project /code/library (preferred), project /official/library, or configure a global library."
    )
