"""Core validation boundary for PRISM.

This package defines the stable validator-facing interface used by CLI, API,
and web layers.
"""

from .validation import build_validation_report, determine_exit_code, validate_dataset

__all__ = ["validate_dataset", "determine_exit_code", "build_validation_report"]
