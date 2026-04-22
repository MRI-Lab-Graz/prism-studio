# src package marker for prism
__all__ = []
"""
PRISM: BIDS-inspired validation tool for psychological research data

This package provides validation tools for multi-modal psychological/experimental datasets
following BIDS principles with custom schemas for different stimulus modalities.
"""

__version__ = "1.15.1"
__author__ = "MRI-Lab-Graz"

try:
    import sys
    from pathlib import Path

    _this_dir = Path(__file__).resolve().parent
    _candidate_src_paths = []

    # Editable/dev layout: app/src package delegates to canonical repo src/.
    _repo_root = _this_dir.parent.parent
    _candidate_src_paths.append(_repo_root / "src")

    # Frozen bundle layout: canonical backend is bundled under backend_bundle/src.
    if getattr(sys, "frozen", False):
        _meipass = getattr(sys, "_MEIPASS", None)
        if _meipass:
            _candidate_src_paths.append(Path(_meipass).resolve() / "backend_bundle" / "src")
        _candidate_src_paths.append(_this_dir.parent / "backend_bundle" / "src")

    for _candidate in _candidate_src_paths:
        if _candidate.is_dir():
            _candidate_str = str(_candidate)
            if _candidate_str not in __path__:
                __path__.append(_candidate_str)
except Exception:
    pass
