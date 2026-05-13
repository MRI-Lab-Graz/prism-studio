"""Compatibility shim for project metadata cleanup."""

from pathlib import Path
import sys

_CURRENT_DIR = Path(__file__).resolve().parent
_APP_SRC_DIR = _CURRENT_DIR.parent
if str(_APP_SRC_DIR) not in sys.path:
    sys.path.insert(0, str(_APP_SRC_DIR))

from src._compat import load_canonical_module

_canonical = load_canonical_module(
    current_file=__file__,
    canonical_rel_path="maintenance/project_metadata_cleanup.py",
    alias="prism_backend_maintenance_project_metadata_cleanup",
)

ProjectMetadataCleanupReport = _canonical.ProjectMetadataCleanupReport
cleanup_project_metadata = _canonical.cleanup_project_metadata
