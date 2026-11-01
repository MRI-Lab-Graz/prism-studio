"""The template editor uses the shared Studio theme parts, not its own copies."""
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
EDITOR_JS = (ROOT / "app/static/js/template-editor.js").read_text(encoding="utf-8")
EDITOR_HTML = (ROOT / "app/templates/template_editor.html").read_text(encoding="utf-8")
EDITOR_CSS = (ROOT / "app/static/css/template-editor.css").read_text(encoding="utf-8")


def _function_body(source, name):
    start = source.index(f"function {name}(")
    return source[start : source.index("\n  }\n", start)]


def test_make_label_delegates_to_theme():
    body = _function_body(EDITOR_JS, "makeLabel")
    assert "StudioTheme.fieldLabel(" in body
    assert "createElement('label')" not in body
    assert "text-danger" not in body


def test_base_template_loads_theme_script():
    base = (ROOT / "app/templates/base.html").read_text(encoding="utf-8")
    assert "js/studio-theme.js" in base


def test_section_header_uses_tally_not_complete_badge():
    assert "te-section-badge" not in EDITOR_JS
    assert "✓ complete" not in EDITOR_JS
    assert "StudioTheme.tally(" in EDITOR_JS
    assert "te-section-badge" not in EDITOR_CSS


def test_editor_has_no_rings_and_uses_readiness_row():
    for source in (EDITOR_HTML, EDITOR_JS, EDITOR_CSS):
        assert "te-ring" not in source
        assert "completionRings" not in source
    assert "readiness_row(" in EDITOR_HTML


def test_project_page_uses_readiness_row_too():
    study = (ROOT / "app/templates/includes/projects/study_metadata.html").read_text(encoding="utf-8")
    assert "readiness_row(" in study
