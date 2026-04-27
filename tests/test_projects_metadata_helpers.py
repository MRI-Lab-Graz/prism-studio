import os
import sys
import tempfile
from pathlib import Path

current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(current_dir)
app_path = os.path.join(project_root, "app")
if app_path not in sys.path:
    sys.path.insert(0, app_path)

from src.web.blueprints import projects_metadata_helpers as metadata_helpers


def test_write_project_json_normalizes_paths_section():
    with tempfile.TemporaryDirectory() as tmp_dir:
        project_root = Path(tmp_dir)

        payload = {
            "name": "demo",
            "paths": {
                "sourcedata": r"sourcedata\\survey",
                "rawdata": "rawdata//nested///level",
                "remote": "https://example.org/path",
            },
        }

        metadata_helpers._write_project_json(project_root, payload)

        saved = (project_root / "project.json").read_text(encoding="utf-8")
        assert '"sourcedata": "sourcedata/survey"' in saved
        assert '"rawdata": "rawdata/nested/level"' in saved
        assert '"remote": "https://example.org/path"' in saved


def test_read_project_json_normalizes_legacy_windows_paths():
    with tempfile.TemporaryDirectory() as tmp_dir:
        project_root = Path(tmp_dir)
        (project_root / "project.json").write_text(
            '{"name": "demo", "paths": {"sourcedata": "code\\\\library\\\\survey"}}',
            encoding="utf-8",
        )

        loaded = metadata_helpers._read_project_json(project_root)

        assert loaded["paths"]["sourcedata"] == "code/library/survey"


def test_read_project_json_drops_null_basics_section():
    with tempfile.TemporaryDirectory() as tmp_dir:
        project_root = Path(tmp_dir)
        (project_root / "project.json").write_text(
            '{"name": "demo", "Basics": null, "Overview": {"Main": "demo"}}',
            encoding="utf-8",
        )

        loaded = metadata_helpers._read_project_json(project_root)

        assert "Basics" not in loaded
        assert loaded["Overview"]["Main"] == "demo"


def test_write_project_json_drops_empty_basics_section():
    with tempfile.TemporaryDirectory() as tmp_dir:
        project_root = Path(tmp_dir)

        payload = {
            "name": "demo",
            "Basics": {},
            "Overview": {"Main": "demo"},
        }

        metadata_helpers._write_project_json(project_root, payload)

        saved = (project_root / "project.json").read_text(encoding="utf-8")
        assert '"Basics"' not in saved
        assert '"Overview": {' in saved


def test_read_project_json_migrates_legacy_string_list_fields():
    """Old project.json files with newline-joined strings get migrated to arrays."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        project_root = Path(tmp_dir)
        (project_root / "project.json").write_text(
            '{"Overview": {"IndependentVariables": "dance\\nnodance",'
            ' "DependentVariables": "stress; wellbeing"},'
            ' "Eligibility": {"InclusionCriteria": "Adults 18+\\nNo MRI contraindications"},'
            ' "Procedure": {"QualityControl": "attention check; exclusion"}}',
            encoding="utf-8",
        )

        loaded = metadata_helpers._read_project_json(project_root)

        assert loaded["Overview"]["IndependentVariables"] == ["dance", "nodance"]
        assert loaded["Overview"]["DependentVariables"] == ["stress", "wellbeing"]
        assert loaded["Eligibility"]["InclusionCriteria"] == [
            "Adults 18+",
            "No MRI contraindications",
        ]
        assert loaded["Procedure"]["QualityControl"] == ["attention check", "exclusion"]


def test_resolve_level_label_uses_requested_language_only():
    levels = {
        "1": {"de": "Trifft nicht zu"},
        "2": {"de": "Trifft voellig zu"},
    }

    # English was requested and is unavailable, so function falls back to raw code.
    assert metadata_helpers._resolve_level_label("1", levels, lang="en") == "1"
    assert metadata_helpers._resolve_level_label("2", levels, lang="en") == "2"


def test_compute_methods_completeness_eligibility_requires_two_combined_criteria():
    project_data = {
        "Overview": {"Main": "Overview"},
        "StudyDesign": {"Type": "cross-sectional", "TypeDescription": "Design"},
        "Recruitment": {
            "Method": "participant-pool",
            "Location": "Graz, Austria",
            "Period": {"Start": "2026-01", "End": "2026-02"},
            "Compensation": "No financial compensation",
        },
        "Eligibility": {
            "InclusionCriteria": [],
            "ExclusionCriteria": [
                "Cardiovascular diseases",
                "Neurological disorders",
            ],
        },
        "Procedure": {"Overview": "Procedure"},
        "Conditions": {},
    }

    completeness = metadata_helpers._compute_methods_completeness(
        project_data, {"Name": "Demo"}
    )

    eligibility = completeness["sections"]["Eligibility"]
    assert eligibility["required_total"] == 1
    assert eligibility["required_filled"] == 1

    project_data["Eligibility"]["ExclusionCriteria"] = ["Cardiovascular diseases"]
    completeness = metadata_helpers._compute_methods_completeness(
        project_data, {"Name": "Demo"}
    )
    eligibility = completeness["sections"]["Eligibility"]
    assert eligibility["required_total"] == 1
    assert eligibility["required_filled"] == 0
