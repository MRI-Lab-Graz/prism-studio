import json
import os
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

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


def test_real_validator_reports_errors_for_an_empty_folder(tmp_path):
    assert sp.validate_for_publish(tmp_path)


def test_real_validator_import_works_with_only_repo_root_importable(tmp_path):
    repo = Path(sp.__file__).resolve().parents[1]
    code = (
        "import sys; sys.path[:] = [p for p in sys.path if 'app' not in p.split('/')];"
        f"sys.path.insert(0, {str(repo)!r});"
        "import src.share_publish as sp;"
        f"errs = sp.validate_for_publish({str(tmp_path)!r});"
        "assert errs, errs"
    )
    env = {k: v for k, v in os.environ.items() if k != "PYTHONPATH"}
    subprocess.run([sys.executable, "-c", code], cwd=tmp_path, env=env, check=True)


def test_validator_crash_is_refused_audited_and_not_pushed(share, pushes, monkeypatch):
    def boom(p):
        raise RuntimeError("kaput")

    monkeypatch.setattr(sp, "validate_for_publish", boom)
    result = sp.publish_to_server(share, identity=ADA)
    assert result["reason"] == "validation_errors" and not result["success"]
    assert result["errors"] == ["Validation could not run: kaput"]
    assert pushes == []
    assert audit_lines(share)[0]["result"] == "refused"


def test_describe_keeps_message_for_tuples_and_code_for_objects():
    assert sp._describe(("ERROR", "PRISM101 bad", "/x")) == "PRISM101 bad"
    obj = SimpleNamespace(code="PRISM102", message="worse")
    assert sp._describe(obj) == "PRISM102 worse"
