"""Save DataLad snapshot only for a PRISM-valid dataset, unless the user overrides (allow_invalid)."""

import sys
from pathlib import Path
from unittest.mock import Mock, patch

ROOT = Path(__file__).resolve().parents[1]
for p in (ROOT, ROOT / "app"):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

from src.project_manager import ProjectManager  # noqa: E402


def _save(tmp_path, errors=None, crash=None, seen=None, envs=None, **kwargs):
    """Run the explicit Save with a canned validator answer; return (result, datalad-save-was-run)."""
    project = tmp_path / "demo_project"
    (project / ".datalad").mkdir(parents=True)
    ran = {"save": False}

    def fake_run(command, *a, **k):
        if len(command) > 1 and command[1] == "save":
            ran["save"] = True
            if seen is not None:
                seen.append(list(command))
            if envs is not None:
                envs.append(k.get("env"))
            return Mock(returncode=0, stdout="save (ok: 1)", stderr="")
        return Mock(returncode=0, stdout="", stderr="")

    validate = Mock(side_effect=crash) if crash else Mock(return_value=errors or [])
    with patch("src.project_manager.shutil.which", return_value="/usr/bin/datalad"), patch(
        "src.project_manager.subprocess.run", side_effect=fake_run
    ), patch(
        "src.project_manager.ProjectManager._get_registered_nested_dataset_paths", return_value=set()
    ), patch("src.share_publish.validate_for_publish", validate):
        result = ProjectManager().save_datalad_snapshot(project, message="m", **kwargs)
    return result, ran["save"]


def test_save_is_refused_while_the_dataset_has_prism_errors(tmp_path):
    result, saved = _save(tmp_path, errors=["bad name", "missing sidecar"])
    assert result["success"] is False and result["validation_blocked"] is True
    assert result["validation_errors"] == ["bad name", "missing sidecar"]
    assert "2 validation error(s)" in result["error"] and "allow-invalid" in result["error"]
    assert saved is False


def test_allow_invalid_saves_despite_errors(tmp_path):
    result, saved = _save(tmp_path, errors=["bad name"], allow_invalid=True)
    assert result["success"] is True and saved is True


def test_a_valid_dataset_saves_without_the_override(tmp_path):
    result, saved = _save(tmp_path, errors=[])
    assert result["success"] is True and saved is True


def test_a_crashed_validator_refuses_like_publish_does(tmp_path):
    result, saved = _save(tmp_path, crash=RuntimeError("boom"))
    assert result["success"] is False and result["validation_blocked"] is True
    assert "boom" in result["error"] and saved is False


def test_a_snapshot_saved_despite_errors_says_so_in_its_message(tmp_path):
    seen = []
    result, saved = _save(tmp_path, errors=["bad name", "missing sidecar"], allow_invalid=True, seen=seen)
    assert saved is True
    assert "saved with 2 validation error(s)" in " ".join(seen[0])


def test_a_valid_snapshot_has_no_such_note(tmp_path):
    seen = []
    _save(tmp_path, errors=[], allow_invalid=True, seen=seen)
    assert "validation error" not in " ".join(seen[0])


def test_save_anyway_after_a_crashed_validator_is_acknowledged_and_says_so(tmp_path):
    seen, envs = [], []
    result, saved = _save(tmp_path, crash=RuntimeError("boom"), allow_invalid=True, seen=seen, envs=envs)
    assert result["success"] is True and saved is True
    assert envs[0] and envs[0].get("PRISM_ACK_INVALID") == "1"
    assert "[saved without validation: the validator could not run]" in " ".join(seen[0])
