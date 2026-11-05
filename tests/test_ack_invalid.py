"""An acknowledged invalid save or push (--allow-invalid / "Save anyway") gets through both git hooks.

One environment variable (PRISM_ACK_INVALID), set only for the one acknowledged command; the hooks inherit it.
"""

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "app"))

import src.save_gate as sg  # noqa: E402
import src.share_publish as sp  # noqa: E402
from tests.test_save_gate_check import calls, repo  # noqa: E402,F401
from tests.test_share_publish_gate import ADA, audit_lines, pushes, share  # noqa: E402,F401

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(autouse=True)
def _no_ack(monkeypatch):
    monkeypatch.delenv(sg.ACK_INVALID_ENV, raising=False)


def test_the_save_check_passes_an_invalid_dataset_only_when_acknowledged(tmp_path, calls, monkeypatch):  # noqa: F811
    calls["full_result"] = ["PRISM101 bad"]
    project = repo(tmp_path / "p", commits=2)
    assert sg.check_save(project) == sg.SaveCheck(False, ["PRISM101 bad"], "validation_errors")
    monkeypatch.setenv(sg.ACK_INVALID_ENV, "1")
    assert sg.check_save(project) == sg.SaveCheck(True, ["PRISM101 bad"], "acknowledged")


def test_ack_invalid_restores_the_environment_even_after_an_exception(monkeypatch):
    with pytest.raises(RuntimeError):
        with sg.ack_invalid():
            assert os.environ[sg.ACK_INVALID_ENV] == "1"
            raise RuntimeError("boom")
    assert sg.ACK_INVALID_ENV not in os.environ
    monkeypatch.setenv(sg.ACK_INVALID_ENV, "earlier")
    with sg.ack_invalid():
        pass
    assert os.environ[sg.ACK_INVALID_ENV] == "earlier"


def test_publish_check_honours_the_acknowledgement_too(share, monkeypatch):  # noqa: F811
    monkeypatch.setattr(sp, "validate_for_publish", lambda p: ["a", "b"])
    assert sp.check_for_hook(share) == ["a", "b"]
    monkeypatch.setenv(sg.ACK_INVALID_ENV, "1")
    assert sp.check_for_hook(share) == []
    last = audit_lines(share)[-1]
    assert last["result"] == "hook_acknowledged" and last["error_count"] == 2


def test_publish_with_allow_invalid_sends_and_audits_pushed_with_errors(share, pushes, monkeypatch):  # noqa: F811
    monkeypatch.setattr(sp, "validate_for_publish", lambda p: ["a", "b"])
    seen = []
    monkeypatch.setattr(
        sp, "run_datalad_push",
        lambda root, **kw: seen.append(os.environ.get(sg.ACK_INVALID_ENV)) or {"success": True, "message": "ok"},
    )
    result = sp.publish_to_server(share, identity=ADA, allow_invalid=True)
    assert result["success"] and result["reason"] == "pushed_with_errors" and result["errors"] == ["a", "b"]
    assert seen == ["1"] and sg.ACK_INVALID_ENV not in os.environ  # the pre-push hook passes for this push only
    [line] = audit_lines(share)
    assert line["result"] == "pushed_with_errors" and line["error_count"] == 2


def test_publish_without_allow_invalid_still_refuses(share, pushes, monkeypatch):  # noqa: F811
    monkeypatch.setattr(sp, "validate_for_publish", lambda p: ["a", "b"])
    result = sp.publish_to_server(share, identity=ADA)
    assert not result["success"] and result["reason"] == "validation_errors" and not pushes


def test_a_validator_that_cannot_run_is_never_acknowledged_away(share, pushes, monkeypatch):  # noqa: F811
    def crash(p):
        raise RuntimeError("boom")

    monkeypatch.setattr(sp, "validate_for_publish", crash)
    result = sp.publish_to_server(share, identity=ADA, allow_invalid=True)
    assert not result["success"] and result["reason"] == "validation_errors" and not pushes
    monkeypatch.setenv(sg.ACK_INVALID_ENV, "1")
    assert sp.check_for_hook(share) == ["Validation could not run: boom"]


@pytest.mark.skipif(not shutil.which("datalad") or not shutil.which("git-annex"), reason="needs DataLad and git-annex")
@pytest.mark.slow
def test_a_real_acknowledged_save_gets_through_the_installed_hook(tmp_path, monkeypatch):
    from src.project_manager import ProjectManager

    cfg = tmp_path / "gitconfig"
    cfg.write_text("[user]\n\tname = Ada\n\temail = ada@example.org\n")
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", str(cfg))
    monkeypatch.setenv("GIT_CONFIG_NOSYSTEM", "1")
    monkeypatch.setenv("PRISM_TOOLS", str(ROOT / "prism_tools.py"))
    root = tmp_path / "study"
    root.mkdir()
    (root / "project.json").write_text(json.dumps({"Basics": {"Name": "Ack"}}) + "\n", encoding="utf-8")
    (root / "dataset_description.json").write_text(
        json.dumps({"Name": "Ack", "BIDSVersion": "1.10.0", "DatasetType": "raw"}) + "\n", encoding="utf-8"
    )
    pm = ProjectManager()
    enabled = pm.enable_datalad_for_project(root, message="start")
    assert enabled["success"] and enabled["save_gate_hook"]["installed"], enabled

    survey = root / "sub-01" / "survey"
    survey.mkdir(parents=True)
    (survey / "sub-01_task-x_wrongsuffix.tsv").write_text("a\n", encoding="utf-8")
    saved = pm.save_datalad_snapshot(root, message="anyway", allow_invalid=True)
    assert saved["success"], saved
    log = subprocess.run(["git", "-C", str(root), "log", "-1", "--format=%s"], capture_output=True, text=True).stdout
    assert log.strip().startswith("anyway [saved with ") and log.strip().endswith("validation error(s)]")
    assert sg.ACK_INVALID_ENV not in os.environ

    # the next commit without the acknowledgement is refused by the hook again
    (survey / "sub-01_task-y_wrongsuffix.tsv").write_text("b\n", encoding="utf-8")
    subprocess.run(["git", "-C", str(root), "add", "."], check=True, capture_output=True)
    commit = subprocess.run(["git", "-C", str(root), "commit", "-m", "sneak"], capture_output=True, text=True)
    assert commit.returncode != 0 and "save gate" in commit.stderr.lower()
