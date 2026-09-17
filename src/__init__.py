# src package marker for prism
__all__ = []
"""
PRISM: validation tool for BIDS-compatible research data

This package validates multi-modal research datasets in which every data file is
paired with a JSON sidecar, using extensible schemas for each modality.
"""

__version__ = "1.19.0"
__author__ = "MRI-Lab-Graz"

try:
    from pathlib import Path

    _this_dir = Path(__file__).resolve().parent
    _repo_root = _this_dir.parent
    _app_src = _repo_root / "app" / "src"
    if _app_src.is_dir():
        _app_src_str = str(_app_src)
        if _app_src_str not in __path__:
            __path__.append(_app_src_str)
except Exception:
    pass
