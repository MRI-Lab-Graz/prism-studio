import importlib
import json
import sys
import tempfile
from pathlib import Path

import pytest
from flask import Flask

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "app"))

h = importlib.import_module("src.web.blueprints.projects_study_metadata_handlers")
mh = importlib.import_module("src.web.blueprints.projects_metadata_helpers")

SECTIONS = ("Basics", "StudyDesign")


class _PM:
    def update_citation_cff(self, *a, **k):
        pass


@pytest.fixture
def root():
    with tempfile.TemporaryDirectory() as d:
        p = Path(d) / "p"
        p.mkdir()
        (p / "project.json").write_text(json.dumps({"Metadata": {}}), encoding="utf-8")
        yield p


def _save(root, payload):
    with Flask(__name__).test_request_context(
        "/api/projects/study-metadata", method="POST", json=payload
    ):
        r = h.handle_save_study_metadata(
            get_current_project=lambda: {"path": str(root)},
            read_project_json=mh._read_project_json,
            write_project_json=mh._write_project_json,
            get_bids_file_path=lambda p, f: p / f,
            editable_sections=SECTIONS,
            compute_methods_completeness=lambda d, dd: {},
            project_manager=_PM(),
        )
    return r


def _get(root):
    with Flask(__name__).test_request_context("/api/projects/study-metadata"):
        return h.handle_get_study_metadata(
            get_current_project=lambda: {"path": str(root)},
            read_project_json=lambda p: {"Metadata": {}},
            get_bids_file_path=lambda p, f: p / f,
            editable_sections=SECTIONS,
            compute_methods_completeness=lambda d, dd: {},
            auto_detect_study_hints=lambda p, d: {},
        )


def test_save_incomplete_returns_missing_required(root):
    r = _save(root, {"Basics": {"Name": "N"}})
    assert r.status_code == 200
    body = r.get_json()
    assert body["success"] is True
    assert set(body["missing_required"]) >= {"Authors", "Keywords", "Timepoints"}
    assert body["not_ready_message"].startswith("Tools are blocked until these required fields")


def test_save_complete_returns_no_missing(root):
    body = _save(root, {
        "Basics": {"Name": "N", "Authors": ["A"], "Keywords": ["k"]},
        "StudyDesign": {"Timepoints": "single"}}).get_json()
    assert body["missing_required"] == []
    assert body["not_ready_message"] is None


def test_get_reports_missing_required(root):
    body = _get(root).get_json()
    assert "Name" in body["missing_required"]
    assert body["not_ready_message"].startswith("Tools are blocked until these required fields")


def test_get_corrupt_project_json_is_not_a_500(root):
    (root / "project.json").write_text("{not json", encoding="utf-8")
    body = _get(root).get_json()
    assert body["missing_required"] == []
    assert "could not be read" in body["not_ready_message"]
