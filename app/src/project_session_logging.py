"""Proxy module for project session logging.

Delegates to canonical repo root src/project_session_logging.py and works in both
editable development and bundled runtime layouts.
"""

from __future__ import annotations

from src._compat import load_canonical_module

_real = load_canonical_module(
    current_file=__file__,
    canonical_rel_path="project_session_logging.py",
    alias="prism_backend_src.project_session_logging",
)

ProjectSessionLogger = _real.ProjectSessionLogger
activate_project_session = _real.activate_project_session
close_project_session = _real.close_project_session
record_project_session_command = _real.record_project_session_command
get_active_project_session_log_path = _real.get_active_project_session_log_path

__all__ = [
    "ProjectSessionLogger",
    "activate_project_session",
    "close_project_session",
    "record_project_session_command",
    "get_active_project_session_log_path",
]
