"""The Export Word modal must not live inside a .feature-card.

.feature-card:hover applies a transform, which turns the card into the
containing block of position:fixed descendants; a modal inside it flickers
and cannot be closed.
"""
from html.parser import HTMLParser
from pathlib import Path

TEMPLATE = Path(__file__).resolve().parents[1] / "app/templates/template_editor.html"
VOID = {"input", "br", "img", "hr", "meta", "link", "option"}


class _Ancestors(HTMLParser):
    def __init__(self, target_id):
        super().__init__()
        self.target_id, self.stack, self.found = target_id, [], None

    def handle_starttag(self, tag, attrs):
        if tag in VOID:
            return
        a = dict(attrs)
        self.stack.append(a.get("class", "").split())
        if a.get("id") == self.target_id:
            self.found = [c for classes in self.stack[:-1] for c in classes]

    def handle_endtag(self, tag):
        if tag not in VOID and self.stack:
            self.stack.pop()


def test_export_word_modal_is_outside_feature_card():
    p = _Ancestors("exportWordModal")
    p.feed(TEMPLATE.read_text(encoding="utf-8"))
    assert p.found is not None
    assert "feature-card" not in p.found
