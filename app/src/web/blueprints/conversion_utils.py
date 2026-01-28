"""
Shared utilities for conversion blueprints.
Helper functions and common logic used across survey, biometrics, physio converters.
"""

from pathlib import Path
from flask import current_app


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
                    head_lines.append(f"  L{i+1}: {line.strip()}")
                if head_lines:
                    log_func("Detected file content (first 4 lines):\n" + "\n".join(head_lines), "info")
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
                    head_lines.append(f"  R{i+1}: " + "\t".join(vals))
                if head_lines:
                    log_func("Detected Excel structure (first 4 rows):\n" + "\n".join(head_lines), "info")
            except Exception as e:
                log_func(f"Could not read Excel preview: {str(e)}", "warning")
    except Exception as e:
        log_func(f"Could not log file head: {str(e)}", "warning")


def resolve_effective_library_path() -> Path:
    """
    Automatically resolve library path:
    1. First, try project's /code/library (only if it has templates)
    2. Fall back to global library
    
    Returns the resolved Path to the library root.
    Raises an error if no valid library is found.
    """
    from src.web.blueprints.projects import get_current_project
    
    # Try project library first, but only if it has templates
    project = get_current_project()
    project_path = project.get("path")
    if project_path:
        project_library = Path(project_path).expanduser().resolve() / "code" / "library"
        if project_library.exists() and project_library.is_dir():
            # Check if the library has any survey templates
            survey_dir = project_library / "survey" if (project_library / "survey").is_dir() else project_library
            if list(survey_dir.glob("survey-*.json")):
                return project_library
            # If project library exists but is empty, fall through to global library
    
    # Fall back to global library
    from src.config import get_effective_library_paths
    # current_app.root_path points to /app directory, we need to go up one level to get to the workspace root
    base_dir = Path(current_app.root_path).parent.resolve()
    lib_paths = get_effective_library_paths(app_root=str(base_dir))
    
    if lib_paths.get("global_library_path"):
        global_lib = Path(lib_paths["global_library_path"]).expanduser().resolve()
        if global_lib.exists() and global_lib.is_dir():
            return global_lib
    
    # Last resort: check default locations
    default_locations = [
        base_dir / "library" / "survey_i18n",
        base_dir / "survey_library",
        base_dir / "official" / "library",
    ]
    
    for location in default_locations:
        if location.exists() and location.is_dir():
            return location
    
    raise FileNotFoundError(
        "No survey library found. Please create a project with /code/library or configure a global library."
    )
