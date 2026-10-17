import json
from pathlib import Path


def _load_verify_repo_module():
    import importlib.util

    module_path = Path(__file__).with_name("verify_repo.py")
    spec = importlib.util.spec_from_file_location("verify_repo", module_path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def _write_schema(schema_dir: Path, name: str, schema: dict) -> None:
    schema_dir.mkdir(parents=True, exist_ok=True)
    (schema_dir / f"{name}.schema.json").write_text(
        json.dumps(schema), encoding="utf-8"
    )


def _valid_schema(name: str) -> dict:
    return {
        "$schema": "http://json-schema.org/draft-07/schema#",
        "$id": f"https://prism.org/schemas/{name}/v1.0.0",
        "version": "1.0.0",
        "title": name.title(),
        "description": f"Schema for {name}.",
        "type": "object",
        "properties": {"Metadata": {"type": "object"}},
        "required": ["Metadata"],
    }


def test_passes_for_well_formed_modality_schema(tmp_path: Path, capsys) -> None:
    verify_repo = _load_verify_repo_module()
    schema_dir = tmp_path / "app" / "schemas" / "stable"
    _write_schema(schema_dir, "survey", _valid_schema("survey"))

    verify_repo.check_modality_schema_conventions(str(tmp_path))
    output = capsys.readouterr().out

    assert "[✗]" not in output
    assert "follow PRISM conventions" in output


def test_flags_required_field_not_in_properties(tmp_path: Path, capsys) -> None:
    verify_repo = _load_verify_repo_module()
    schema_dir = tmp_path / "app" / "schemas" / "stable"
    bad_schema = _valid_schema("survey")
    bad_schema["required"] = ["Metadata", "Nonexistent"]
    _write_schema(schema_dir, "survey", bad_schema)

    verify_repo.check_modality_schema_conventions(str(tmp_path))
    output = capsys.readouterr().out

    assert "Nonexistent" in output
    assert "not declared in 'properties'" in output


def test_flags_id_version_mismatch(tmp_path: Path, capsys) -> None:
    verify_repo = _load_verify_repo_module()
    schema_dir = tmp_path / "app" / "schemas" / "stable"
    bad_schema = _valid_schema("survey")
    bad_schema["$id"] = "https://prism.org/schemas/survey/v1.0.0"
    bad_schema["version"] = "2.0.0"
    _write_schema(schema_dir, "survey", bad_schema)

    verify_repo.check_modality_schema_conventions(str(tmp_path))
    output = capsys.readouterr().out

    assert "does not match" in output


def test_flags_invalid_json_schema_draft(tmp_path: Path, capsys) -> None:
    verify_repo = _load_verify_repo_module()
    schema_dir = tmp_path / "app" / "schemas" / "stable"
    bad_schema = _valid_schema("survey")
    bad_schema["type"] = "not-a-real-type"
    _write_schema(schema_dir, "survey", bad_schema)

    verify_repo.check_modality_schema_conventions(str(tmp_path))
    output = capsys.readouterr().out

    assert "not a valid JSON Schema" in output


def test_ignores_app_internal_schemas(tmp_path: Path, capsys) -> None:
    verify_repo = _load_verify_repo_module()
    schema_dir = tmp_path / "app" / "schemas" / "stable"
    # entities.schema.json has no $id/version/Study-Technical envelope at all
    # and must never be flagged by this check -- it is not community-extensible.
    _write_schema(schema_dir, "entities", {"entityOrder": ["sub"]})

    verify_repo.check_modality_schema_conventions(str(tmp_path))
    output = capsys.readouterr().out

    assert "[✗]" not in output


def test_skipped_when_schema_dir_missing(tmp_path: Path, capsys) -> None:
    verify_repo = _load_verify_repo_module()

    verify_repo.check_modality_schema_conventions(str(tmp_path))
    output = capsys.readouterr().out

    assert "skipped" in output


def test_flags_non_object_json(tmp_path: Path, capsys) -> None:
    """Test that non-object JSON (array, string, number) is properly caught."""
    verify_repo = _load_verify_repo_module()
    schema_dir = tmp_path / "app" / "schemas" / "stable"
    schema_dir.mkdir(parents=True, exist_ok=True)

    # Test with an array
    (schema_dir / "survey.schema.json").write_text("[]", encoding="utf-8")
    verify_repo.check_modality_schema_conventions(str(tmp_path))
    output = capsys.readouterr().out
    assert "[✗]" in output
    assert "must be an object" in output
    assert "got list" in output

    # Test with a string
    (schema_dir / "biometrics.schema.json").write_text('"todo"', encoding="utf-8")
    verify_repo.check_modality_schema_conventions(str(tmp_path))
    output = capsys.readouterr().out
    assert "[✗]" in output
    assert "must be an object" in output
    assert "got str" in output

    # Test with a number
    (schema_dir / "physio.schema.json").write_text("123", encoding="utf-8")
    verify_repo.check_modality_schema_conventions(str(tmp_path))
    output = capsys.readouterr().out
    assert "[✗]" in output
    assert "must be an object" in output
    assert "got int" in output
