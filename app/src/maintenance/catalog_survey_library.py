"""Compatibility shim for maintenance catalog generation."""

from src.maintenance.catalog_survey_library import generate_index


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
