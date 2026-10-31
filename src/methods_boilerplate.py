"""The methods boilerplate of selected library templates, written once for Studio's Survey Generator and
`prism_tools library generate-methods-text`: same text, same schema version, same project link."""

from __future__ import annotations

GITHUB_URL = "https://github.com/MRI-Lab-Graz/prism-studio"


def write_methods_boilerplate(files_or_folders, output_path, *, lang: str = "en") -> None:
    """Write the boilerplate to output_path (.md) and, next to it, the .html version."""
    from src.reporting import generate_methods_text
    from src.schema_manager import DEFAULT_SCHEMA_VERSION

    generate_methods_text(
        files_or_folders, output_path, lang=lang, github_url=GITHUB_URL, schema_version=DEFAULT_SCHEMA_VERSION
    )
