# src package marker for prism
__all__ = []
"""
PRISM: BIDS-inspired validation tool for psychological research data

This package provides validation tools for multi-modal psychological/experimental datasets
following BIDS principles with custom schemas for different stimulus modalities.
"""

__version__ = "1.11.0"
__author__ = "MRI-Lab-Graz"

try:
	from pathlib import Path

	_this_dir = Path(__file__).resolve().parent
	_repo_root = _this_dir.parent.parent
	_root_src = _repo_root / "src"
	if _root_src.is_dir():
		_root_src_str = str(_root_src)
		if _root_src_str not in __path__:
			__path__.append(_root_src_str)
except Exception:
	pass
