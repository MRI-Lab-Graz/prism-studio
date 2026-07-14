# Configuration file for the Sphinx documentation builder.

import os
import sys

sys.path.insert(0, os.path.abspath(".."))

project = "PRISM Studio"
copyright = "2025-2026, MRI-Lab-Graz"
author = "MRI-Lab-Graz"
release = "1.16.0"

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
    # Advanced pages intentionally hidden from public RTD navigation.
    "LIMESURVEY_VERSION_DIFFERENCES.md",
    "PAVLOVIA_EXPORT.md",
]

# -- Options for HTML output -------------------------------------------------
html_theme = "sphinx_rtd_theme"
html_static_path = ["_static", "img"]
html_css_files = ["custom.css"]
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
