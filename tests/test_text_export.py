"""Markdown -> tex/docx/html converters used by the methods and preregistration exports."""

import io
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "app"))

from src.text_export import FORMATS, convert, md_to_docx, md_to_tex  # noqa: E402

MD = "## Participants\n\nText *n* = 5 and **bold**.\n\n- a\n- b"


def test_tex_escapes_specials():
    assert "Smith \\& Co. 50\\% of a\\_b" in md_to_tex("Smith & Co. 50% of a_b")


def test_tex_structure():
    tex = md_to_tex(MD)
    assert "\\section{Participants}" in tex
    assert "\\emph{n}" in tex
    assert "\\textbf{bold}" in tex
    assert "\\begin{itemize}" in tex
    assert tex.count("\\item") == 2
    assert tex.lstrip().startswith("\\documentclass")


def test_docx_roundtrip():
    docx = pytest.importorskip("docx")
    doc = docx.Document(io.BytesIO(md_to_docx(MD)))
    texts = [p.text for p in doc.paragraphs]
    assert "Participants" in texts
    assert any("Text" in t for t in texts)


def test_convert_md_passthrough():
    assert convert("Ä text", "md") == "Ä text".encode("utf-8")


def test_convert_html_contains_h2():
    assert b"<h2>Participants</h2>" in convert(MD, "html")


def test_convert_unknown_raises():
    with pytest.raises(ValueError):
        convert(MD, "pdf")


def test_formats():
    assert FORMATS == ("md", "html", "docx", "tex")


def test_docx_missing_dependency(monkeypatch):
    monkeypatch.setitem(sys.modules, "docx", None)
    with pytest.raises(RuntimeError, match="python-docx"):
        convert(MD, "docx")
