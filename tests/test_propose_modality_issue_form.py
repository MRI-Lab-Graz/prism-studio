from pathlib import Path

import yaml


def test_issue_form_is_valid_yaml_with_required_fields():
    form_path = (
        Path(__file__).resolve().parent.parent
        / ".github"
        / "ISSUE_TEMPLATE"
        / "propose-modality.yml"
    )
    form = yaml.safe_load(form_path.read_text(encoding="utf-8"))

    assert form["name"]
    assert "type: new-modality" in form["labels"]

    field_ids = {item["id"] for item in form["body"] if item.get("type") != "markdown"}
    assert {"modality_name", "suffix", "extensions", "fields"} <= field_ids

    fields_field = next(item for item in form["body"] if item.get("id") == "fields")
    assert fields_field["type"] == "textarea"
    assert "name | datatype | required | unit" in fields_field["attributes"]["description"]
