import importlib.util
import subprocess
import sys
from pathlib import Path
from unittest.mock import patch


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


def test_get_changed_files_with_git_failure():
    """Test that get_changed_files returns empty list on git failure (e.g., shallow checkout)."""
    mod = _load_module()
    with patch("subprocess.run") as mock_run:
        mock_run.side_effect = subprocess.CalledProcessError(1, "git")
        result = mod.get_changed_files("base", "head")
        assert result == []


def test_main_with_wrong_argc():
    """Test that main() returns 0 (not 1) when given wrong number of arguments."""
    mod = _load_module()
    with patch.object(sys, "argv", ["prog"]):
        exit_code = mod.main()
        assert exit_code == 0


def test_main_with_git_failure_returns_zero():
    """Test that main() returns 0 and prints advisory flag even if git fails."""
    mod = _load_module()
    with patch.object(sys, "argv", ["prog", "base", "head"]):
        with patch("subprocess.run") as mock_run:
            mock_run.side_effect = subprocess.CalledProcessError(1, "git")
            exit_code = mod.main()
            assert exit_code == 0
