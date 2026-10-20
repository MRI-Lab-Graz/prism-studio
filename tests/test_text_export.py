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


# ---- references_bib ---------------------------------------------------------


def _tpl(*citations, **extra):
    return {"Study": {"References": [{"Type": "primary", "Citation": c, **extra} for c in citations]}}


def test_bib_same_paper_in_two_templates_is_one_entry():
    from src.text_export import references_bib

    c = "Smith, J. (2020). Stress. Journal."
    bib = references_bib({"a": _tpl(c), "b": _tpl(c)})
    assert bib.count("@misc") == 1


def test_bib_distinct_papers_get_sorted_suffixes_and_are_stable():
    from src.text_export import references_bib

    data = {"x": _tpl("Smith, J. (2020). Zeta."), "y": _tpl("Smith, J. (2020). Alpha.")}
    bib = references_bib(data)
    assert "smith2020a" in bib and "smith2020b" in bib
    assert bib.index("Alpha") < bib.index("Zeta")  # sorted by citation text
    assert references_bib(dict(reversed(list(data.items())))) == bib


def test_bib_escapes_specials_and_keeps_doi():
    from src.text_export import references_bib

    bib = references_bib({"a": _tpl("Smith, J. (2020). R&D in a_b.", DOI="10.1/x_y")})
    assert r"R\&D in a\_b" in bib
    assert "doi = {10.1/x_y}" in bib


def test_bib_empty():
    from src.text_export import references_bib

    assert references_bib({}) == ""
    assert references_bib({"a": {"Study": {}}}) == ""


# ---- review fixes -------------------------------------------------------------


def test_title_and_underscore_italics_are_converted_not_shown_raw():
    from src.text_export import convert

    md = "# Preregistration draft\n\n_Not filled in yet._\n"
    tex = convert(md, "tex").decode()
    assert "\\section{Preregistration draft}" in tex and "\\emph{Not filled in yet.}" in tex
    html = convert(md, "html").decode()
    assert "<h2>Preregistration draft</h2>" in html and "_Not" not in html
    assert "a_b" in convert("a_b and c_d", "md").decode()  # md stays untouched
    assert "a\\_b" in convert("a_b and c_d", "tex").decode()  # snake_case is not italic


def test_tex_maps_common_non_latin_symbols():
    from src.text_export import md_to_tex

    tex = md_to_tex("Cronbach α = .89, x ≥ 3, ± 2")
    assert "α" not in tex and "≥" not in tex and "±" not in tex
    assert "\\ensuremath{\\alpha}" in tex and "\\ensuremath{\\geq}" in tex
