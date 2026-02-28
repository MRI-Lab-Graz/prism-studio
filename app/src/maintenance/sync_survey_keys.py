"""Compatibility shim for survey key synchronization."""

from pathlib import Path
import sys


_CURRENT_DIR = Path(__file__).resolve().parent
_APP_SRC_DIR = _CURRENT_DIR.parent
if str(_APP_SRC_DIR) not in sys.path:
    sys.path.insert(0, str(_APP_SRC_DIR))

from src._compat import load_canonical_module


_canonical = load_canonical_module(
    current_file=__file__,
    canonical_rel_path="maintenance/sync_survey_keys.py",
    alias="prism_backend_maintenance_sync_survey_keys",
)

sync_survey_keys = _canonical.sync_survey_keys


if __name__ == "__main__":
    sync_survey_keys()
