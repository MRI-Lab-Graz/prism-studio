"""
Proxy module for participants_converter - delegates to canonical repo root
src/participants_converter.py. Uses _compat.load_canonical_module so this works
in both dev and PyInstaller bundles (where the real src/ is bundled under
backend_bundle/src/).
"""

from __future__ import annotations

from src._compat import load_canonical_module

_real = load_canonical_module(
    current_file=__file__,
    canonical_rel_path="participants_converter.py",
    alias="prism_backend_src.participants_converter",
)

# Re-export public API
ParticipantsConverter = _real.ParticipantsConverter
apply_participants_mapping = _real.apply_participants_mapping

__all__ = [
    "ParticipantsConverter",
    "apply_participants_mapping",
]
