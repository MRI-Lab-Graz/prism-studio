# Configuration file for the Sphinx documentation builder.

import os
import sys

sys.path.insert(0, os.path.abspath(".."))

project = "PRISM"
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
]

# -- Options for HTML output -------------------------------------------------
html_theme = "sphinx_rtd_theme"
html_static_path = ["_static", "img"]

# Logo for ReadTheDocs / HTML output. The file is at docs/img/prism_logo.jpg
html_logo = "img/prism_logo.jpg"

# -- MyST Parser configuration -----------------------------------------------
myst_enable_extensions = [
    "colon_fence",
    "deflist",
]
myst_heading_anchors = 3
