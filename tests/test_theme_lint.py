"""Static look-and-feel lint: pages share one theme (app/static/css/studio-theme.css), so a page must not carry its own.

Checks, over app/templates/**/*.html and app/static/css/**/*.css:
  colour          a hard-coded #hex / rgb() in a style attribute, a <style> block or a page stylesheet (var(...) is fine)
  inline_style    a style="..." attribute in a template
  restyle         a selector in a page stylesheet or <style> block that mentions .btn .card .badge .form-select .form-control
  select_multiple a <select multiple> in a template (a list of choices is a pull-down plus chips: chip-list.js)
studio-theme.css itself is the theme and is not scanned. tests/theme_lint_baseline.json holds the reviewed violations per
file; a file may only get fewer. A new violation fails with file:line; fix the page, then lower the baseline
(`python tests/test_theme_lint.py --update`).
"""

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASELINE = Path(__file__).with_name("theme_lint_baseline.json")
THEME = "app/static/css/studio-theme.css"

COLOUR = re.compile(r"#[0-9a-fA-F]{3,8}\b|\brgba?\(")
VAR = re.compile(r"var\([^)]*\)")
STYLE_ATTR = re.compile(r"""\sstyle\s*=\s*("[^"]*"|'[^']*')""")
STYLE_BLOCK = re.compile(r"<style\b[^>]*>(.*?)</style>", re.S | re.I)
SELECTOR = re.compile(r"([^{};]+)\{")
RESTYLED = re.compile(r"\.(btn|card|badge|form-select|form-control)(?![\w-])")
SELECT_MULTIPLE = re.compile(r"<select\b[^>]*\bmultiple\b", re.I)
COMMENT = re.compile(r"/\*.*?\*/", re.S)


def _line(text, pos):
    return text.count("\n", 0, pos) + 1


def _blank_comments(text):
    return COMMENT.sub(lambda m: re.sub(r"[^\n]", " ", m.group()), text)  # keeps line numbers


def _colours(text, offset_text, start):
    return [
        _line(offset_text, start + m.start())
        for m in COLOUR.finditer(VAR.sub(lambda v: " " * len(v.group()), text))
    ]


def _restyled(css, offset_text, start):
    css = _blank_comments(css)
    return [
        _line(offset_text, start + m.start(1) + len(m.group(1)) - len(m.group(1).lstrip()))
        for m in SELECTOR.finditer(css)
        if RESTYLED.search(m.group(1))
    ]


def scan(root):
    """{check: {relative file: [line, ...]}} for every violation."""
    root = Path(root)
    found = {"colour": {}, "inline_style": {}, "restyle": {}, "select_multiple": {}}

    def add(check, rel, lines):
        if lines:
            found[check].setdefault(rel, []).extend(lines)

    for path in sorted((root / "app" / "templates").rglob("*.html")):
        rel, text = path.relative_to(root).as_posix(), path.read_text(encoding="utf-8")
        add("inline_style", rel, [_line(text, m.start()) for m in STYLE_ATTR.finditer(text)])
        add("select_multiple", rel, [_line(text, m.start()) for m in SELECT_MULTIPLE.finditer(text)])
        for m in STYLE_ATTR.finditer(text):
            add("colour", rel, _colours(m.group(1), text, m.start(1)))
        for m in STYLE_BLOCK.finditer(text):
            add("colour", rel, _colours(_blank_comments(m.group(1)), text, m.start(1)))
            add("restyle", rel, _restyled(m.group(1), text, m.start(1)))
    for path in sorted((root / "app" / "static" / "css").rglob("*.css")):
        rel, text = path.relative_to(root).as_posix(), path.read_text(encoding="utf-8")
        if rel == THEME:
            continue
        add("colour", rel, _colours(_blank_comments(text), text, 0))
        add("restyle", rel, _restyled(text, text, 0))
    return found


def _counts(found):
    return {check: {rel: len(lines) for rel, lines in files.items()} for check, files in found.items()}


def _baseline():
    return json.loads(BASELINE.read_text(encoding="utf-8")) if BASELINE.exists() else {}


def test_no_new_look_and_feel_violations():
    found, baseline = scan(ROOT), _baseline()
    new = [
        f"{check}: {rel}:{line}"
        for check, files in found.items()
        for rel, lines in files.items()
        if len(lines) > baseline.get(check, {}).get(rel, 0)
        for line in lines
    ]
    assert not new, "page-specific look (use the studio-theme.css tokens and classes):\n" + "\n".join(new)


def test_baseline_shrinks_when_a_page_is_fixed():
    counts, baseline = _counts(scan(ROOT)), _baseline()
    stale = [
        f"{check}: {rel} has {counts.get(check, {}).get(rel, 0)}, baseline says {n}"
        for check, files in baseline.items()
        for rel, n in files.items()
        if counts.get(check, {}).get(rel, 0) < n
    ]
    assert not stale, "fixed; lower tests/theme_lint_baseline.json (python tests/test_theme_lint.py --update):\n" + "\n".join(stale)


def test_each_check_detects_its_violation(tmp_path):
    (tmp_path / "app" / "templates").mkdir(parents=True)
    (tmp_path / "app" / "static" / "css").mkdir(parents=True)
    (tmp_path / "app" / "templates" / "p.html").write_text(
        '<div style="color: #fff">x</div>\n'
        '<div style="color: var(--a, #fff)">ok</div>\n'
        "<style>\n/* .btn in a comment */\n.page .card { margin: 0 }\n.card-header { margin: 0 }\n</style>\n"
        "<select multiple></select>\n"
    )
    (tmp_path / "app" / "static" / "css" / "page.css").write_text(".x { color: rgb(1,2,3) }\n.btn-primary:hover, .btn { top: 0 }\n")
    (tmp_path / "app" / "static" / "css" / "studio-theme.css").write_text(".btn { color: #000 }\n")
    found = scan(tmp_path)
    assert found["inline_style"] == {"app/templates/p.html": [1, 2]}
    assert found["colour"] == {"app/templates/p.html": [1], "app/static/css/page.css": [1]}
    assert found["restyle"] == {"app/templates/p.html": [5], "app/static/css/page.css": [2]}
    assert found["select_multiple"] == {"app/templates/p.html": [8]}


if __name__ == "__main__":
    if sys.argv[1:] == ["--update"]:
        BASELINE.write_text(json.dumps(_counts(scan(ROOT)), indent=1, sort_keys=True) + "\n", encoding="utf-8")
