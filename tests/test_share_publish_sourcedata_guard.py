"""sourcedata/ holds raw, identifiable data and is tracked in plain git (text
policy), so publish_to_server must never send such a project to a public host."""

import subprocess

import pytest

import src.share_publish as sp
from src.share_publish import Identity

ADA = Identity("Ada", "ada@uni.at")


def git(*args, cwd):
    subprocess.run(["git", "-c", "user.name=a", "-c", "user.email=a@b.c", *args], cwd=cwd, check=True, capture_output=True)


def make_project(tmp_path, monkeypatch, *, url, with_sourcedata):
    root = tmp_path / "study"
    root.mkdir()
    git("init", "-q", cwd=root)
    git("remote", "add", "ria-store", url, cwd=root)
    (root / "dataset_description.json").write_text("{}")
    if with_sourcedata:
        (root / "sourcedata").mkdir()
        (root / "sourcedata" / "raw.csv").write_text("name,email\nAda,ada@x.at\n")
    git("add", "-A", cwd=root)
    git("commit", "-q", "-m", "init", cwd=root)
    pushes = []
    monkeypatch.setattr(sp, "is_datalad_dataset", lambda p: True)
    monkeypatch.setattr(sp, "run_datalad_push", lambda r, **kw: pushes.append(kw) or {"success": True, "message": "ok"})
    monkeypatch.setattr(sp, "run_datalad_push_verify", lambda *a, **kw: {"success": True, "verified": True, "message": "ok"})
    monkeypatch.setattr(sp, "_dataset_roots", lambda p: [p])
    monkeypatch.setattr(sp, "validate_for_publish", lambda p: [])
    return root, pushes


@pytest.mark.parametrize(
    "url",
    [
        "https://github.com/lab/study.git",
        "http://example.org/study.git",
        "git@github.com:lab/study.git",
        "ssh://git@gin.g-node.org/lab/study.git",
        "ria+https://store.example.org#~abc",
    ],
)
def test_public_target_is_refused_when_sourcedata_is_tracked(tmp_path, monkeypatch, url):
    root, pushes = make_project(tmp_path, monkeypatch, url=url, with_sourcedata=True)
    result = sp.publish_to_server(root, sibling_name="ria-store", identity=ADA)
    assert result["success"] is False and result["reason"] == "public_target_with_sourcedata"
    assert "sourcedata" in result["message"]
    assert pushes == []


@pytest.mark.parametrize("url", ["ria+ssh://lab-server.uni.at/data/store", "me@lab-server.uni.at:/data/study", "/srv/store"])
def test_internal_target_is_allowed_with_sourcedata(tmp_path, monkeypatch, url):
    root, pushes = make_project(tmp_path, monkeypatch, url=url, with_sourcedata=True)
    assert sp.publish_to_server(root, sibling_name="ria-store", identity=ADA)["success"] is True
    assert len(pushes) == 1


def test_public_target_is_fine_without_tracked_sourcedata(tmp_path, monkeypatch):
    root, pushes = make_project(tmp_path, monkeypatch, url="https://github.com/lab/s.git", with_sourcedata=False)
    assert sp.publish_to_server(root, sibling_name="ria-store", identity=ADA)["success"] is True
