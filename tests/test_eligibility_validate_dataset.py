import json

from src.issues import infer_code_from_message
from src.runner import validate_dataset


def _dataset(tmp_path):
    (tmp_path / "dataset_description.json").write_text(
        json.dumps({"Name": "t", "BIDSVersion": "1.10.1"})
    )
    (tmp_path / "sub-01").mkdir()
    (tmp_path / "project.json").write_text(
        json.dumps({"Eligibility": {"Criteria": [
            {"id": "age", "label": "Age", "type": "numeric", "mode": "include",
             "min": 18, "max": 35, "unit": "years"}]}})
    )
    (tmp_path / "participants.json").write_text(
        json.dumps({"age": {"Unit": "years", "EligibilityCriterion": "age"}})
    )
    (tmp_path / "participants.tsv").write_text("participant_id\tage\nsub-01\t17\n")
    return str(tmp_path)


def test_validator_warns_about_participant_outside_criteria(tmp_path):
    issues, _ = validate_dataset(_dataset(tmp_path), run_bids=False, run_prism=True)
    found = [i for i in issues if "PRISM602" in str(i[1])]
    assert found and all(i[0] == "WARNING" for i in found)
    assert infer_code_from_message(found[0][1]) == "PRISM602"


def test_no_eligibility_issues_without_prism_validation(tmp_path):
    issues, _ = validate_dataset(_dataset(tmp_path), run_bids=False, run_prism=False)
    assert not [i for i in issues if "PRISM602" in str(i[1])]


def test_malformed_criteria_do_not_take_down_the_validator(tmp_path):
    root = _dataset(tmp_path)
    (tmp_path / "project.json").write_text(json.dumps({"Eligibility": {"Criteria": [
        None, {"id": "age", "type": "numeric", "mode": "include", "min": "18"}]}}))
    issues, _ = validate_dataset(root, run_bids=False, run_prism=True)
    assert any("PRISM603" in str(i[1]) and "malformed" in str(i[1]) for i in issues)
