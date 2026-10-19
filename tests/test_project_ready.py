# tests/test_project_ready.py
import json
import pytest
from src.project_ready import (
    ProjectNotReadyError, missing_required_fields, not_ready_message, require_project_ready,
)

FULL = {
    "Basics": {"Name": "N", "Authors": ["A"], "Keywords": ["k"]},
    "StudyDesign": {"Timepoints": "single"},
}

def _proj(tmp_path, data):
    (tmp_path / "project.json").write_text(json.dumps(data), encoding="utf-8")
    return tmp_path

def test_no_project_json_is_not_gated(tmp_path):
    assert missing_required_fields(tmp_path) == []

def test_complete_project_is_ready(tmp_path):
    assert missing_required_fields(_proj(tmp_path, FULL)) == []

@pytest.mark.parametrize("section,field,label", [
    ("Basics", "Name", "Name"), ("Basics", "Authors", "Authors"),
    ("Basics", "Keywords", "Keywords"), ("StudyDesign", "Timepoints", "Timepoints"),
])
def test_each_missing_field_is_reported(tmp_path, section, field, label):
    data = json.loads(json.dumps(FULL))
    del data[section][field]
    assert missing_required_fields(_proj(tmp_path, data)) == [label]

def test_blank_and_empty_values_count_as_missing(tmp_path):
    data = {"Basics": {"Name": "  ", "Authors": [], "Keywords": [""]},
            "StudyDesign": {"Timepoints": "weekly"}}
    assert missing_required_fields(_proj(tmp_path, data)) == ["Name", "Authors", "Keywords", "Timepoints"]

def test_invalid_json_gives_readable_error(tmp_path):
    (tmp_path / "project.json").write_text("{nope", encoding="utf-8")
    with pytest.raises(ProjectNotReadyError) as exc:
        require_project_ready(tmp_path)
    assert "project.json" in str(exc.value)

def test_require_raises_with_message(tmp_path):
    _proj(tmp_path, {})
    with pytest.raises(ProjectNotReadyError) as exc:
        require_project_ready(tmp_path)
    assert exc.value.missing == ["Name", "Authors", "Keywords", "Timepoints"]
    assert "Projects page" in str(exc.value) and "Authors" in str(exc.value)

def test_accepts_project_json_path(tmp_path):
    _proj(tmp_path, FULL)
    assert missing_required_fields(tmp_path / "project.json") == []


def test_not_ready_message_exact_text():
    assert not_ready_message(["Authors", "Timepoints"]) == (
        "Tools are blocked until these required fields are set on the Projects page: "
        "Authors, Timepoints."
    )
