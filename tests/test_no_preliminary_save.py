"""A project is saved with its required metadata or not at all: there is no "preliminary state"."""
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
JS = ROOT / "app/static/js"
META = (JS / "modules/projects/metadata.js").read_text(encoding="utf-8")


def _live_sources():
    for base in (JS / "modules/projects", ROOT / "app/templates"):
        for path in base.rglob("*"):
            if path.suffix in {".js", ".html"} and ".test." not in path.name:
                yield path, path.read_text(encoding="utf-8")


def test_no_preliminary_wording_or_ids_remain():
    hits = [str(p.relative_to(ROOT)) for p, text in _live_sources() if re.search(r"preliminary", text, re.I)]
    assert not hits, hits


def test_the_confirm_dialog_is_gone():
    assert not (JS / "modules/projects/preliminary-save-modal.js").exists()


def test_save_is_disabled_while_required_fields_are_missing():
    start = META.index("    if (!isCreateMode) {")
    branch = META[start:META.index("        return;\n    }", start)]
    assert "setCreateButtonDisabled(requiredIssueCount > 0)" in branch
