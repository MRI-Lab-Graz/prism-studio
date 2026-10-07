"""runner._validate_citation_cff must work without the Studio-only ProjectManager."""

import sys

from src.runner import _validate_citation_cff

GOOD = (
    "cff-version: 1.2.0\nmessage: m\ntitle: T\n"
    "authors:\n  - family-names: Doe\n    given-names: J\n"
    "version: 1.0.0\ndate-released: 2026-01-01\n"
)


def test_valid_citation_without_project_manager(tmp_path, monkeypatch):
    monkeypatch.setitem(sys.modules, "project_manager", None)
    monkeypatch.setitem(sys.modules, "src.project_manager", None)
    (tmp_path / "CITATION.cff").write_text(GOOD)
    assert _validate_citation_cff(str(tmp_path)) == []


def test_invalid_citation_reports_schema_problem(tmp_path, monkeypatch):
    monkeypatch.setitem(sys.modules, "project_manager", None)
    monkeypatch.setitem(sys.modules, "src.project_manager", None)
    (tmp_path / "CITATION.cff").write_text(GOOD.replace("title: T\n", ""))
    issues = _validate_citation_cff(str(tmp_path))
    assert issues
    sev, msg, _ = issues[0]
    assert sev == "ERROR"
    assert msg.startswith("PRISM303 CITATION.cff validation failed:")
    assert "'title' is a required property" in msg
    assert "No module named" not in msg
