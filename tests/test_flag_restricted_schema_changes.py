import importlib.util
from pathlib import Path


def _load_module():
    module_path = (
        Path(__file__).resolve().parent.parent
        / "scripts"
        / "ci"
        / "flag_restricted_schema_changes.py"
    )
    spec = importlib.util.spec_from_file_location(
        "flag_restricted_schema_changes", module_path
    )
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_flags_entities_schema_change():
    mod = _load_module()
    changed = ["app/schemas/stable/entities.schema.json", "README.md"]
    assert mod.find_restricted_changes(changed) == [
        "app/schemas/stable/entities.schema.json"
    ]


def test_flags_files_across_version_folders():
    mod = _load_module()
    changed = ["app/schemas/v0.2/project.schema.json"]
    assert mod.find_restricted_changes(changed) == [
        "app/schemas/v0.2/project.schema.json"
    ]


def test_does_not_flag_community_modality_schema():
    mod = _load_module()
    changed = ["app/schemas/stable/survey.schema.json"]
    assert mod.find_restricted_changes(changed) == []


def test_does_not_flag_unrelated_file():
    mod = _load_module()
    changed = ["official/library/survey/survey-new-instrument.json"]
    assert mod.find_restricted_changes(changed) == []


def test_empty_change_list_returns_empty():
    mod = _load_module()
    assert mod.find_restricted_changes([]) == []
