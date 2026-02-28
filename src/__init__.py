# src package marker for prism
__all__ = []
"""
PRISM: BIDS-inspired validation tool for psychological research data

This package provides validation tools for multi-modal psychological/experimental datasets
following BIDS principles with custom schemas for different stimulus modalities.
"""

__version__ = "1.9.2"
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
