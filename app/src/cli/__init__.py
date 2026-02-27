"""CLI modularization package for prism_tools.

This package is introduced incrementally to extract parser wiring,
command handlers, and shared services from the monolithic entry script.
"""

from src.cli.dispatch import dispatch_command
from src.cli.parser import build_parser

__all__ = ["build_parser", "dispatch_command"]
