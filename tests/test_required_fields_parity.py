import importlib
import re
import sys
from pathlib import Path

from flask import Flask

root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(root / "app"))

h = importlib.import_module("src.web.blueprints.projects_study_metadata_handlers")
mh = importlib.import_module("src.web.blueprints.projects_metadata_helpers")

# Literal from the spec, deliberately not derived from REQUIRED_FIELDS.
EXPECTED = {"Basics": {"Name", "Authors", "Keywords"}, "StudyDesign": {"Timepoints"}}


def test_backend_constant_matches_spec():
    assert mh.CREATION_BLOCKING_FIELDS == EXPECTED


def test_get_response_exposes_creation_blocking_fields():
    with Flask(__name__).test_request_context("/api/projects/study-metadata"):
        r = h.handle_get_study_metadata(
            get_current_project=lambda: {"path": str(root)},
            read_project_json=lambda p: {"Metadata": {}},
            get_bids_file_path=lambda p, f: p / f,
            editable_sections=("Basics", "StudyDesign"),
            compute_methods_completeness=lambda d, dd: {},
            auto_detect_study_hints=lambda p, d: {},
        )
    assert r.get_json()["creation_blocking_fields"] == {
        k: sorted(v) for k, v in EXPECTED.items()
    }


# Two quoted names close together = a literal copy of the list. Legitimate uses
# (label maps use unquoted keys, addField() calls are 15+ lines apart) stay > 200 chars apart.
_PAIR = re.compile(
    r"""(['"])Keywords\1[\s\S]{0,200}?(['"])Timepoints\2|(['"])Timepoints\3[\s\S]{0,200}?(['"])Keywords\4"""
)
_ASSIGN = re.compile(r"\b_?creationBlockingFields\s*=\s*(?!\{\s*\}|_toFieldSets\(|_creationBlockingFields\b)\S")


def scan_js(text):
    return [m.group(0) for m in _PAIR.finditer(text)] + [
        m.group(0) for m in _ASSIGN.finditer(text)
    ]


def test_scan_flags_a_literal_copy():
    assert scan_js("const x = new Set(['Name','Authors','Keywords','Timepoints']);")
    assert scan_js('const y = ["Timepoints", "Keywords"];')
    assert scan_js("const creationBlockingFields = { Basics: new Set() };")


def test_js_has_no_private_copy():
    hits = {}
    for f in (root / "app/static/js").rglob("*.js"):
        if f.name.endswith(".test.js") or {"node_modules", "vendor"} & set(f.parts):
            continue
        found = scan_js(f.read_text(encoding="utf-8"))
        if found:
            hits[str(f.relative_to(root))] = found
    assert not hits
