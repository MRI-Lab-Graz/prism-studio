"""Render the shipped docs/specs/*.md so the Specifications page works offline."""

import re
import sys
from pathlib import Path

from markdown_it import MarkdownIt

# slug -> (nav label, markdown file relative to docs/)
SPEC_PAGES = {
    "overview": ("Overview", "SPECIFICATIONS.md"),
    "survey": ("Survey", "specs/survey.md"),
    "biometrics": ("Biometrics", "specs/biometrics.md"),
    "biosample": ("Biosample", "specs/biosample.md"),
    "physio": ("Physio", "specs/physio.md"),
    "eyetracking": ("Eyetracking", "specs/eyetracking.md"),
    "environment": ("Environment", "specs/environment.md"),
    "events": ("Events", "specs/events.md"),
    "project": ("project.json", "specs/project.md"),
    "dataset_description": (
        "dataset_description.json",
        "specs/dataset_description.md",
    ),
    "entities": ("Filename rules", "specs/entities.md"),
    "errors": ("Validation errors & warnings", "ERROR_CODES.md"),
}

# sidebar structure: (group heading, slugs); a None heading is an ungrouped lead entry
SPEC_GROUPS = [
    (None, ["overview"]),
    (
        "Modalities",
        [
            "survey",
            "biometrics",
            "biosample",
            "physio",
            "eyetracking",
            "environment",
            "events",
        ],
    ),
    ("Project files", ["project", "dataset_description"]),
    ("Rules and codes", ["entities", "errors"]),
]

# a doc links to another doc by file name, e.g. ../ERROR_CODES.md
_SLUG_BY_FILE = {Path(f).name: slug for slug, (_, f) in SPEC_PAGES.items()}
# The specification repository cannot link into Studio's docs relatively, so its pages carry
# absolute URLs; offline they are read like the relative links they replace.
_DOCS_SITE = "https://prism-studio.readthedocs.io/en/latest/"
_REPO_FILES = "https://github.com/MRI-Lab-Graz/prism-studio/raw/main/"
_SPEC_REPO = "https://github.com/MRI-Lab-Graz/prism-specification"
_HTML_PAGE = re.compile(r"\.html(?=#|$)")
_COMMENT = re.compile(r"<!--.*?-->", re.S)
# in-app pages state facts only: drop pointers to guides and step-by-step procedures
_TUTORIAL = re.compile(
    r"^> \[!TIP\]\n(?:>[^\n]*\n?)*"  # "Starting a new ...? Use the template" callouts
    r"|^## (?:What's next|How To Use The Excel Workbook)\n.*?(?=^## |\Z)",
    re.S | re.M,
)
_md = MarkdownIt("commonmark").enable("table")  # html stays off: docs are text only


def _docs_dir() -> Path:
    meipass = getattr(sys, "_MEIPASS", None)  # PyInstaller: PrismStudio.spec ships docs/
    return Path(meipass) / "docs" if meipass else Path(__file__).parents[3] / "docs"


def _rewrite_links(tokens) -> None:
    """Point doc-to-doc links at in-app pages; unwrap links only valid on GitHub."""
    for inline in (t for t in tokens if t.type == "inline"):
        unwrap = False
        for t in inline.children:
            if t.type == "link_open":
                href = t.attrGet("href") or ""
                if href.startswith(_DOCS_SITE):
                    href = _HTML_PAGE.sub(".md", href[len(_DOCS_SITE):])
                elif href.startswith(_REPO_FILES):
                    href = href[len(_REPO_FILES):]
                elif href.startswith(_SPEC_REPO):
                    href = ""  # a pointer to a site outside the app: dropped like the guides
                if href.startswith(("http://", "https://", "#")):
                    continue
                slug = _SLUG_BY_FILE.get(Path(href.split("#")[0]).name)
                if slug and "#" not in href:
                    t.attrSet("href", f"/specifications/{slug}")
                else:
                    t.type, t.content, unwrap = "text", "", True
            elif t.type == "link_close" and unwrap:
                t.type, unwrap = "text", False


def render_spec_page(slug: str) -> str:
    if slug not in SPEC_PAGES:
        raise KeyError(slug)
    text = (_docs_dir() / SPEC_PAGES[slug][1]).read_text(encoding="utf-8")
    tokens = _md.parse(_TUTORIAL.sub("", _COMMENT.sub("", text)))
    _rewrite_links(tokens)
    for token in tokens:  # the page header is the h2: the document's h1 becomes an h3, and so on (at most h6)
        if token.type in ("heading_open", "heading_close"):
            token.tag = f"h{min(int(token.tag[1]) + 2, 6)}"
    html = _md.renderer.render(tokens, _md.options, {})
    return html.replace("<table>", '<table class="table table-sm">')
