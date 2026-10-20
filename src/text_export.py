"""Convert the Markdown subset our generators emit (methods, preregistration) to other formats.

Subset: ``## ``/``### `` headings, ``- `` bullets, paragraphs, ``**bold**``, ``*italic*``.
"""

from __future__ import annotations

import io
import re

FORMATS = ("md", "html", "docx", "tex")
MIME = {
    "md": "text/markdown",
    "html": "text/html",
    "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "tex": "application/x-tex",
}

_TEX_SPECIALS = {
    "\\": r"\textbackslash{}",
    "&": r"\&",
    "%": r"\%",
    "$": r"\$",
    "#": r"\#",
    "_": r"\_",
    "{": r"\{",
    "}": r"\}",
    "~": r"\textasciitilde{}",
    "^": r"\textasciicircum{}",
}
_INLINE = re.compile(r"\*\*(.+?)\*\*|\*(.+?)\*")


def _blocks(md: str):
    """Yield (kind, text) with kind in h2, h3, li, p."""
    for line in md.split("\n"):
        s = line.strip()
        if not s:
            continue
        if s.startswith("### "):
            yield "h3", s[4:]
        elif s.startswith("## "):
            yield "h2", s[3:]
        elif s.startswith("- "):
            yield "li", s[2:]
        else:
            yield "p", s


def _tex_escape(text: str) -> str:
    return "".join(_TEX_SPECIALS.get(c, c) for c in text)


def _tex_inline(text: str) -> str:
    out, pos = [], 0
    for m in _INLINE.finditer(text):
        out.append(_tex_escape(text[pos : m.start()]))
        if m.group(1) is not None:
            out.append(r"\textbf{" + _tex_escape(m.group(1)) + "}")
        else:
            out.append(r"\emph{" + _tex_escape(m.group(2)) + "}")
        pos = m.end()
    out.append(_tex_escape(text[pos:]))
    return "".join(out)


def md_to_tex(md: str) -> str:
    body: list[str] = []
    in_list = False
    for kind, text in _blocks(md):
        if kind != "li" and in_list:
            body.append(r"\end{itemize}")
            in_list = False
        if kind == "li" and not in_list:
            body.append(r"\begin{itemize}")
            in_list = True
        if kind == "h2":
            body.append(r"\section{" + _tex_inline(text) + "}")
        elif kind == "h3":
            body.append(r"\subsection{" + _tex_inline(text) + "}")
        elif kind == "li":
            body.append(r"\item " + _tex_inline(text))
        else:
            body.append(_tex_inline(text) + "\n")
    if in_list:
        body.append(r"\end{itemize}")
    return (
        "\\documentclass{article}\n\\usepackage[utf8]{inputenc}\n"
        "\\usepackage[T1]{fontenc}\n\\begin{document}\n\n"
        + "\n".join(body)
        + "\n\n\\end{document}\n"
    )


def _add_runs(paragraph, text: str) -> None:
    pos = 0
    for m in _INLINE.finditer(text):
        paragraph.add_run(text[pos : m.start()])
        if m.group(1) is not None:
            paragraph.add_run(m.group(1)).bold = True
        else:
            paragraph.add_run(m.group(2)).italic = True
        pos = m.end()
    paragraph.add_run(text[pos:])


def md_to_docx(md: str) -> bytes:
    try:
        import docx
    except ImportError as exc:
        raise RuntimeError(
            "python-docx is required for Word export. "
            "Install it with: pip install python-docx"
        ) from exc
    doc = docx.Document()
    for kind, text in _blocks(md):
        if kind in ("h2", "h3"):
            doc.add_heading(text, level=2 if kind == "h2" else 3)
        else:
            _add_runs(doc.add_paragraph(style="List Bullet" if kind == "li" else None), text)
    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()


def convert(md: str, fmt: str) -> bytes:
    if fmt == "md":
        return md.encode("utf-8")
    if fmt == "html":
        from src.reporting import _md_to_html

        return _md_to_html(md).encode("utf-8")
    if fmt == "docx":
        return md_to_docx(md)
    if fmt == "tex":
        return md_to_tex(md).encode("utf-8")
    raise ValueError(f"Unknown format {fmt!r}; use one of {', '.join(FORMATS)}")
