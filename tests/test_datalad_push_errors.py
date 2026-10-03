"""Push to DataLad server: SSH failures are explained in plain words (sync and finalize)."""

import sys
from pathlib import Path
from unittest.mock import patch

import pytest

ROOT = Path(__file__).resolve().parents[1]
for p in (ROOT, ROOT / "app"):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

from src.datalad_doctor import classify_ssh_error, explain_failure, explain_ssh_failures  # noqa: E402
from src.project_manager import ProjectManager  # noqa: E402

DENIED = "CommandError: kalle@h.at: Permission denied (publickey,password)."


def test_local_file_permission_error_is_not_blamed_on_the_ssh_key():
    assert classify_ssh_error("[Errno 13] Permission denied: '/data/x'")[0] == "unknown"


def test_explain_failure_keeps_the_original_text_and_points_to_the_setup_check():
    text = explain_failure(f"Could not connect to server: {DENIED}")
    assert "did not accept your SSH key" in text
    assert DENIED in text
    assert "doctor" in text or "Check this computer" in text


def test_explain_failure_leaves_other_errors_untouched():
    assert explain_failure("Sync failed: disk full") == "Sync failed: disk full"
    assert explain_failure("") == ""


def test_decorator_rewrites_only_failed_results():
    @explain_ssh_failures
    def op(result):
        return result

    failed = op({"success": False, "message": DENIED, "create": {"x": 1}})
    assert "did not accept your SSH key" in failed["message"] and failed["create"] == {"x": 1}
    ok = {"success": True, "message": "Synced."}
    assert op(ok) == {"success": True, "message": "Synced."}
    assert op("not a dict") == "not a dict"


@pytest.fixture
def project(tmp_path):
    root = tmp_path / "demo"
    (root / ".datalad").mkdir(parents=True)
    (root / "dataset_description.json").write_text("{}\n", encoding="utf-8")
    return root


@patch("src.datalad_execution.resolve_datalad_executable", return_value="/usr/bin/datalad")
def test_sync_to_a_server_that_rejects_the_key_says_so(_exe, project):
    failure = {"success": False, "message": DENIED}
    with patch("src.datalad_execution.run_datalad_create_sibling", return_value=failure):
        result = ProjectManager().sync_project_to_ria(project, ria_url="ria+ssh://kalle@h.at/store")
    assert result["success"] is False
    assert "did not accept your SSH key" in result["message"]
    assert DENIED in result["message"]


@patch("src.datalad_execution.resolve_datalad_executable", return_value="/usr/bin/datalad")
def test_finalize_against_an_unreachable_server_says_so(_exe, project):
    failure = {"success": False, "message": "ssh: Could not resolve hostname h.at: Name or service not known"}
    with patch("src.datalad_execution.run_datalad_upload_to_sibling", return_value=failure):
        result = ProjectManager().finalize_project_upload(project, ria_url="ria+ssh://kalle@h.at/store")
    assert result["success"] is False
    assert "Cannot reach the server" in result["message"]
