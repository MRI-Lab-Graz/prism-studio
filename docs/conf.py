# Configuration file for the Sphinx documentation builder.

import os
import sys

sys.path.insert(0, os.path.abspath(".."))

project = "PRISM Studio"
copyright = "2025-2026, MRI-Lab-Graz"
author = "MRI-Lab-Graz"
release = "1.18.0"

# -- General configuration ---------------------------------------------------
extensions = [
    "myst_parser",
    "sphinx.ext.autodoc",
    "sphinx.ext.viewcode",
    "sphinx.ext.napoleon",
    "sphinxcontrib.mermaid",
]

templates_path = ["_templates"]
exclude_patterns = [
    "_build",
    "_archive",
    "Thumbs.db",
    ".DS_Store",
    "README.md",
    "archive/**",
    # Internal planning docs (superpowers skill working files), not user docs.
    "superpowers/**",
    # Advanced pages intentionally hidden from public RTD navigation.
    "LIMESURVEY_VERSION_DIFFERENCES.md",
    "PAVLOVIA_EXPORT.md",
    # Replaced by TUTORIAL_BEGINNER
    "QUICK_START.md",
]

# sphinxcontrib.mermaid defaults every diagram's rendered SVG to a fixed
# 500px height regardless of actual content size, which is why simple
# diagrams (a 3-node flowchart, say) render with a large empty band above
# the visible boxes. "auto" sizes the SVG to its own content instead.
mermaid_height = "auto"

# -- Options for HTML output -------------------------------------------------
html_theme = "shibuya"
html_static_path = ["_static", "img"]
html_css_files = ["custom.css"]
html_js_files = ["persona.js"]
html_title = "PRISM Studio Documentation (Draft)"
html_short_title = "PRISM Docs (Draft)"

# Logo for ReadTheDocs / HTML output. The file is at docs/img/prism_logo.png
html_logo = "img/prism_logo.png"

html_theme_options = {
    "accent_color": "green",
    "github_url": "https://github.com/MRI-Lab-Graz/prism-studio",
}

# -- MyST Parser configuration -----------------------------------------------
myst_enable_extensions = [
    "colon_fence",
    "deflist",
]
myst_heading_anchors = 3
