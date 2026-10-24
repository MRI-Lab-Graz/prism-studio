"""prism.py (validate_dataset) reports the project-level files the Projects page check always reported."""

import json

import pytest

from src.issues import infer_code_from_message
from src.project_manager import ProjectManager
from src.runner import validate_dataset


def _dataset(root, project_json=True, participants=True, bidsignore=True):
    root.mkdir()
    (root / "dataset_description.json").write_text(json.dumps({"Name": "t", "BIDSVersion": "1.10.0", "DatasetType": "raw"}))
    survey = root / "sub-01" / "ses-1" / "survey"
    survey.mkdir(parents=True)
    (survey / "sub-01_ses-1_task-x_survey.tsv").write_text("Q1\n1\n")
    (root / "task-x_survey.json").write_text(json.dumps({
        "Technical": {"StimulusType": "Questionnaire", "FileFormat": "tsv", "Language": "en", "Respondent": "self"},
        "Study": {"TaskName": "x", "OriginalName": "X"},
        "Metadata": {"SchemaVersion": "1.1.1", "CreationDate": "2024-01-01"},
        "Q1": {"Description": "q"},
    }))
    if project_json:
        (root / "project.json").write_text(json.dumps({"Metadata": {"SchemaVersion": "1.0.0"}, "Sessions": [], "TaskDefinitions": {}}))
    if participants:
        (root / "participants.tsv").write_text("participant_id\nsub-01\n")
    if bidsignore:
        (root / ".bidsignore").write_text("survey/\n")
    return root


def _codes(root):
    issues, _ = validate_dataset(str(root), run_bids=False, run_prism=True)
    return {infer_code_from_message(i[1]): i[0] for i in issues}


def test_a_complete_dataset_reports_none_of_them(tmp_path):
    codes = _codes(_dataset(tmp_path / "d"))
    assert not {"PRISM004", "PRISM010", "PRISM501"} & set(codes)


@pytest.mark.parametrize("missing,code", [("participants", "PRISM004"), ("project_json", "PRISM010"), ("bidsignore", "PRISM501")])
def test_each_missing_file_is_a_warning(tmp_path, missing, code):
    codes = _codes(_dataset(tmp_path / "d", **{missing: False}))
    assert codes.get(code) == "WARNING"


def test_the_projects_page_check_lists_each_one_once(tmp_path):
    root = _dataset(tmp_path / "d", participants=False, project_json=False, bidsignore=False)
    result = ProjectManager().validate_structure(str(root))
    shown = [i["code"] for i in result["issues"] + result["runner_warnings"]]
    for code in ("PRISM004", "PRISM010", "PRISM501"):
        assert shown.count(code) == 1, (code, shown)
