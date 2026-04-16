"""
Proxy module for project_structure - delegates to canonical repo root src/project_structure.py.
Uses _compat.load_canonical_module so this works in both dev and PyInstaller bundles
(where the real src/ is bundled under backend_bundle/src/).
"""

from __future__ import annotations

from src._compat import load_canonical_module

_real = load_canonical_module(
    current_file=__file__,
    canonical_rel_path="project_structure.py",
    alias="prism_backend_src.project_structure",
)

# Re-export public API
get_project_modalities_and_sessions = _real.get_project_modalities_and_sessions

__all__ = ["get_project_modalities_and_sessions"]
