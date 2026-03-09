# Configuration file for the Sphinx documentation builder.

import os
import sys

sys.path.insert(0, os.path.abspath(".."))

project = "PRISM Studio"
copyright = "2025-2026, MRI-Lab-Graz"
author = "MRI-Lab-Graz"
release = "1.9.1"

# -- General configuration ---------------------------------------------------
extensions = [
    "myst_parser",
    "sphinx.ext.autodoc",
    "sphinx.ext.viewcode",
    "sphinx.ext.napoleon",
]

templates_path = ["_templates"]
exclude_patterns = [
    "_build",
    "_archive",
    "Thumbs.db",
    ".DS_Store",
    "README.md",
    "archive/**",
    # Development/internal docs intentionally hidden from RTD public nav.
    "CHANGELOG.md",
    "RELEASE_GUIDE.md",
    "WINDOWS_TESTING.md",
    "WINDOWS_TEST_QUICKREF.md",
    "WINDOWS_TEST_SUMMARY.md",
    "WINDOWS_VM_BUILD_TESTING.md",
    "COMPLETE_WINDOWS_SUMMARY.md",
    # Advanced pages intentionally hidden from public RTD navigation.
    "ANC_EXPORT.md",
    "BIDS_AUTO_MAPPING_COMPLETE.md",
    "BIDS_COMPLIANCE_IMPLEMENTATION.md",
    "EYETRACKING_TSV_NORMALIZATION.md",
    "GITHUB_SIGNING.md",
    "PAVLOVIA_EXPORT.md",
    "WINDOWS_BUILD.md",
    "WINDOWS_SETUP.md",
]

# -- Options for HTML output -------------------------------------------------
html_theme = "sphinx_rtd_theme"
html_static_path = ["_static", "img"]
html_title = "PRISM Studio Documentation (Draft)"
html_short_title = "PRISM Docs (Draft)"

# Logo for ReadTheDocs / HTML output. The file is at docs/img/prism_logo.png
html_logo = "img/prism_logo.png"

# -- MyST Parser configuration -----------------------------------------------
myst_enable_extensions = [
    "colon_fence",
    "deflist",
]
myst_heading_anchors = 3
