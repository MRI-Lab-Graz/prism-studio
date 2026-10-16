from pathlib import Path

import yaml

FORM = Path(__file__).resolve().parent.parent / ".github" / "ISSUE_TEMPLATE" / "propose-modality.yml"


def test_issue_form_has_the_labels_the_bot_parses():
    form = yaml.safe_load(FORM.read_text(encoding="utf-8"))
    assert "type: new-modality" in form["labels"]
    labels = {item["attributes"]["label"] for item in form["body"] if item.get("type") != "markdown"}
    assert {"Proposal file", "Sample data file", "Privacy"} <= labels


def test_privacy_checkbox_is_required():
    form = yaml.safe_load(FORM.read_text(encoding="utf-8"))
    privacy = next(i for i in form["body"] if i.get("id") == "privacy")
    assert all(o["required"] for o in privacy["attributes"]["options"])


def test_form_no_longer_asks_for_a_rationale():
    form = yaml.safe_load(FORM.read_text(encoding="utf-8"))
    labels = {item["attributes"].get("label", "") for item in form["body"] if item.get("type") != "markdown"}
    assert not any("why" in label.lower() for label in labels)
    assert {"Proposal file", "Sample data file", "Privacy"} <= labels
