"""Template editor: item rules the JSON schema cannot express."""

from src.template_validator import TemplateValidator

CHECK = TemplateValidator.validate_item_rules_from_data


def _item(**extra):
    return {"Description": {"en": "q"}, **extra}


def _by_severity(findings, severity):
    return [f for f in findings if f["severity"] == severity]


def test_a_template_without_items_gets_a_warning():
    (finding,) = CHECK({"Study": {"TaskName": "t"}, "Technical": {}})
    assert finding["severity"] == "warning" and "no items" in finding["message"]


def test_a_clean_template_has_no_findings():
    assert CHECK({"Study": {"TaskName": "t"}, "Q1": _item(MinValue=0, MaxValue=4), "Q_2-b": _item()}) == []


def test_min_above_max_is_an_error_naming_the_item():
    (finding,) = _by_severity(CHECK({"Q1": _item(MinValue=10, MaxValue=1)}), "error")
    assert finding["path"] == "Q1" and "MinValue (10)" in finding["message"] and "MaxValue (1)" in finding["message"]


def test_equal_bounds_are_fine_and_open_bounds_are_ignored():
    assert CHECK({"Q1": _item(MinValue=3, MaxValue=3), "Q2": _item(MinValue=1), "Q3": _item(MaxValue=None, MinValue=None)}) == []


def test_warn_min_above_warn_max_is_an_error():
    (finding,) = _by_severity(CHECK({"Q1": _item(WarnMinValue=9, WarnMaxValue=2)}), "error")
    assert "WarnMinValue" in finding["message"]


def test_integer_items_with_fractional_bounds_are_a_warning():
    findings = CHECK({"Q1": _item(DataType="integer", MinValue=1.5, MaxValue=4)})
    assert [f["severity"] for f in findings] == ["warning"] and "integer" in findings[0]["message"]
    assert CHECK({"Q1": _item(DataType="float", MinValue=1.5)}) == []


def test_item_ids_outside_letters_digits_underscore_hyphen_are_a_warning():
    findings = CHECK({"A B": _item(), "../x": _item(), "ünï": _item(), "ok_1": _item()})
    assert sorted(f["path"] for f in findings) == ["../x", "A B", "ünï"]
    assert all(f["severity"] == "warning" for f in findings)


def test_ids_differing_only_in_case_are_a_warning():
    (finding,) = CHECK({"AAI01": _item(), "aai01": _item()})
    assert finding["severity"] == "warning" and "AAI01" in finding["message"] and "aai01" in finding["message"]


def test_non_object_items_and_missing_values_do_not_crash():
    assert CHECK({"Q1": "text", "Q2": _item(MinValue="abc", MaxValue=1)}) == []


def test_validate_route_fails_on_an_impossible_range_and_lists_item_warnings(monkeypatch):
    import sys
    from pathlib import Path

    from flask import Flask

    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "app"))
    from src.web.blueprints.tools_template_editor_blueprint import tools_template_editor_bp

    from src.web.blueprints import tools_template_editor_blueprint as handlers

    monkeypatch.setattr(handlers, "_load_prism_schema", lambda **kwargs: {})
    app = Flask(__name__)
    app.register_blueprint(tools_template_editor_bp)
    template = {"Q1": _item(MinValue=10, MaxValue=1), "A B": _item()}
    body = app.test_client().post(
        "/api/template-editor/validate", json={"modality": "survey", "template": template, "is_global": True}
    ).get_json()
    assert not body["ok"]
    assert any(e["path"] == "Q1" and "MinValue" in e["message"] for e in body["errors"])
    assert [w["path"] for w in body["item_warnings"]] == ["A B"]


def test_pattern_errors_say_what_is_allowed_instead_of_showing_the_regex():
    from src.prism_template_validation import validate_template_against_schema

    schema = {
        "type": "object",
        "properties": {"Study": {"type": "object", "properties": {"TaskName": {"type": "string", "pattern": "^[a-zA-Z0-9][a-zA-Z0-9\\-]*$"}}}},
    }
    (error,) = validate_template_against_schema(instance={"Study": {"TaskName": "My Task!"}}, schema=schema)
    assert error["path"] == "Study/TaskName"
    assert "My Task!" in error["message"] and "letters, digits and hyphens" in error["message"]
    assert "[a-zA-Z0-9]" not in error["message"]


def _client(monkeypatch):
    import sys
    from pathlib import Path

    from flask import Flask

    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "app"))
    from src.web.blueprints import tools_template_editor_blueprint as handlers

    monkeypatch.setattr(handlers, "_load_prism_schema", lambda **kwargs: {})
    app = Flask(__name__)
    app.register_blueprint(handlers.tools_template_editor_bp)
    return app.test_client()


def test_library_templates_still_need_a_task_name_to_validate_and_to_save(monkeypatch):
    client = _client(monkeypatch)
    body = {"modality": "survey", "template": {"Study": {"TaskName": ""}, "Q1": _item()}, "is_global": True}
    validated = client.post("/api/template-editor/validate", json=body).get_json()
    assert not validated["ok"] and validated["errors"][0]["path"] == "Study/TaskName"
    saved = client.post("/api/template-editor/save", json={**body, "filename": "survey-x.json"})
    assert saved.status_code == 400
    body["template"]["Study"]["TaskName"] = "x"
    assert client.post("/api/template-editor/validate", json=body).get_json()["ok"]


def test_a_wrong_value_inside_an_item_names_the_field_not_the_whole_item():
    from src.prism_template_validation import validate_template_against_schema

    item_schema = {
        "oneOf": [
            {"type": "object", "properties": {"SessionHint": {"type": "string", "pattern": "^(ses-[a-zA-Z0-9]+)?$"},
                                               "MinValue": {"type": ["number", "null"]}}, "required": ["Description"]},
            {"type": "object", "required": ["AliasOf"]},
        ]
    }
    schema = {"type": "object", "additionalProperties": item_schema}
    errors = validate_template_against_schema(
        instance={"Q1": {"Description": "q", "SessionHint": "session 1", "MinValue": "x"}}, schema=schema
    )
    assert errors and all(len(e["message"]) < 160 for e in errors), errors
    assert any(e["path"].endswith("Q1/SessionHint") and "ses-<label>" in e["message"] for e in errors) or any(
        e["path"].endswith("Q1/MinValue") for e in errors
    ), errors


def test_empty_description_and_empty_level_labels_are_warnings():
    findings = CHECK({
        "Q1": {"Description": {"de": "", "en": ""}, "Levels": {"1": {"de": "", "en": ""}, "2": {"en": "ok"}}},
        "Q2": {"Description": ""},
        "Q3": {"Description": {"en": "fine"}, "Levels": {"1": "text"}},
    })
    messages = sorted((f["path"], f["severity"]) for f in findings)
    assert messages == [("Q1", "warning"), ("Q1/Levels/1", "warning"), ("Q2", "warning")]


def test_an_alias_of_an_unknown_item_is_a_warning():
    findings = CHECK({"Q1": _item(), "Q2": {"AliasOf": "Q9"}, "Q3": {"AliasOf": "Q1"}})
    assert [(f["path"], f["severity"]) for f in findings] == [("Q2", "warning")] and "Q9" in findings[0]["message"]


def test_proto_is_not_a_usable_item_id():
    assert any("__proto__" in f["message"] for f in CHECK({"__proto__": _item()}))
