"""Compatibility shim for maintenance catalog generation."""

from pathlib import Path
import sys


_CURRENT_DIR = Path(__file__).resolve().parent
_APP_SRC_DIR = _CURRENT_DIR.parent
if str(_APP_SRC_DIR) not in sys.path:
    sys.path.insert(0, str(_APP_SRC_DIR))

from src._compat import load_canonical_module


_canonical = load_canonical_module(
    current_file=__file__,
    canonical_rel_path="maintenance/catalog_survey_library.py",
    alias="prism_backend_maintenance_catalog_survey_library",
)

generate_index = _canonical.generate_index


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="Generate a catalog of the survey library."
    )
    parser.add_argument(
        "--library",
        default="survey_library",
        help="Path to the survey library folder (default: survey_library)",
    )
    parser.add_argument(
        "--output",
        default="survey_library/CATALOG.md",
        help="Path to the output Markdown file (default: survey_library/CATALOG.md)",
    )

    args = parser.parse_args()
    generate_index(args.library, args.output)
