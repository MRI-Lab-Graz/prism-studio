import json
import os
import subprocess

import pytest

import src.share_publish as sp
from src.share_publish import Identity

ADA = Identity("Ada", "ada@uni.at")


def git(*args, cwd):
    subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True)


@pytest.fixture
def pushes():
    return []


@pytest.fixture
def share(tmp_path, monkeypatch, pushes):
    server = tmp_path / "server.git"
    subprocess.run(["git", "init", "-q", "--bare", str(server)], check=True)
    root = tmp_path / "share" / "study"
    root.mkdir(parents=True)
    git("init", "-q", cwd=root)
    git("remote", "add", "ria-store", str(server), cwd=root)
    (root / ".datalad").mkdir()
    monkeypatch.setattr(sp, "is_datalad_dataset", lambda p: True)

    def fake_push(project_root, **kw):
        pushes.append(kw)
        return {"success": True, "message": "ok"}

    monkeypatch.setattr(sp, "run_datalad_push", fake_push)
    monkeypatch.setattr(
        sp, "run_datalad_push_verify",
        lambda *a, **kw: {"success": True, "verified": True, "message": "ok"},
    )
    monkeypatch.setattr(sp, "_dataset_roots", lambda p: [p])
    monkeypatch.setattr(sp, "validate_for_publish", lambda p: [])
    return root


def audit_lines(root):
    return [json.loads(l) for l in sp.audit_path(root).read_text().splitlines()]


def test_valid_dataset_is_pushed_and_audited(share, pushes):
    result = sp.publish_to_server(share, identity=ADA)
    assert result["success"] and result["reason"] == "pushed"
    assert pushes and pushes[0]["sibling_name"] == "ria-store"
    [line] = audit_lines(share)
    assert line["result"] == "pushed" and line["identity"] == "Ada <ada@uni.at>"
    assert line["error_count"] == 0 and line["sibling"] == "ria-store"


def test_invalid_dataset_is_refused_and_nothing_is_pushed(share, pushes, monkeypatch):
    monkeypatch.setattr(sp, "validate_for_publish", lambda p: ["PRISM101 bad", "PRISM102 worse"])
    result = sp.publish_to_server(share, identity=ADA)
    assert not result["success"] and result["reason"] == "validation_errors"
    assert result["errors"] == ["PRISM101 bad", "PRISM102 worse"]
    assert pushes == []
    [line] = audit_lines(share)
    assert line["result"] == "refused" and line["error_count"] == 2


def test_missing_identity_is_refused_before_validation_and_audited(share, pushes, monkeypatch):
    monkeypatch.setattr(sp, "resolve_identity", lambda *a: None)
    monkeypatch.setattr(sp, "validate_for_publish", lambda p: pytest.fail("must not validate"))
    result = sp.publish_to_server(share)
    assert result["reason"] == "no_identity" and pushes == []
    assert audit_lines(share)[0]["identity"] is None


def test_missing_sibling_is_refused(share, pushes):
    result = sp.publish_to_server(share, sibling_name="nope", identity=ADA)
    assert result["reason"] == "no_sibling" and pushes == []


def test_not_a_dataset_is_refused(share, monkeypatch):
    monkeypatch.setattr(sp, "is_datalad_dataset", lambda p: False)
    assert sp.publish_to_server(share, identity=ADA)["reason"] == "not_a_dataset"


def test_failed_push_is_reported_and_audited(share, monkeypatch):
    monkeypatch.setattr(sp, "run_datalad_push", lambda *a, **k: {"success": False, "message": "boom"})
    result = sp.publish_to_server(share, identity=ADA)
    assert not result["success"] and result["reason"] == "push_failed"
    assert audit_lines(share)[0]["result"] == "push_failed"


def test_publishing_does_not_dirty_the_working_tree(share):
    sp.publish_to_server(share, identity=ADA)
    status = subprocess.run(
        ["git", "status", "--porcelain"], cwd=share, capture_output=True, text=True, check=True
    ).stdout
    assert status.strip() == ""


def test_can_publish_needs_dataset_and_sibling(share, monkeypatch):
    assert sp.can_publish(share) is True
    monkeypatch.setattr(sp, "is_datalad_dataset", lambda p: False)
    assert sp.can_publish(share) is False


def test_non_git_folder_writes_no_audit_and_does_not_raise(tmp_path, monkeypatch):
    cwd = tmp_path / "cwd"
    cwd.mkdir()
    monkeypatch.chdir(cwd)
    folder = tmp_path / "plain"
    folder.mkdir()
    monkeypatch.setattr(sp, "is_datalad_dataset", lambda p: False)
    result = sp.publish_to_server(folder, identity=ADA)
    assert result["reason"] == "not_a_dataset"
    assert not (cwd / "prism").exists()
    assert not (folder / "prism").exists()
