import os
import subprocess

import pytest

from src.share_publish import (
    Identity,
    apply_identity,
    identity_env,
    parse_identity,
    resolve_identity,
)


@pytest.fixture(autouse=True)
def clean_env(monkeypatch, tmp_path):
    for key in ("PRISM_USER_NAME", "PRISM_USER_EMAIL"):
        monkeypatch.delenv(key, raising=False)
    # empty global git config so the machine's own identity never leaks in
    empty = tmp_path / "gitconfig"
    empty.write_text("")
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", str(empty))
    monkeypatch.setenv("GIT_CONFIG_SYSTEM", os.devnull)
    return empty


def test_parse_identity():
    assert parse_identity("Ada Lovelace <ada@uni.at>") == Identity("Ada Lovelace", "ada@uni.at")


@pytest.mark.parametrize("bad", ["", "Ada", "<ada@uni.at>", "Ada <nope>"])
def test_parse_identity_rejects_garbage(bad):
    with pytest.raises(ValueError):
        parse_identity(bad)


def test_resolution_order(monkeypatch, clean_env):
    assert resolve_identity() is None
    clean_env.write_text("[user]\n\tname = Global\n\temail = g@x.at\n")
    assert resolve_identity() == Identity("Global", "g@x.at")
    monkeypatch.setenv("PRISM_USER_NAME", "Env")
    monkeypatch.setenv("PRISM_USER_EMAIL", "e@x.at")
    assert resolve_identity() == Identity("Env", "e@x.at")
    assert resolve_identity("Flag <f@x.at>") == Identity("Flag", "f@x.at")


def test_apply_identity_is_seen_by_child_git_and_leaves_repo_config_alone(tmp_path, monkeypatch):
    repo = tmp_path / "r"
    subprocess.run(["git", "init", "-q", str(repo)], check=True)
    (repo / "f").write_text("x")
    subprocess.run(["git", "-C", str(repo), "add", "f"], check=True)
    for key in identity_env(Identity("a", "a@b.c")):
        monkeypatch.delenv(key, raising=False)  # restored after the test
    apply_identity(Identity("Ada", "ada@uni.at"))
    subprocess.run(["git", "-C", str(repo), "commit", "-q", "-m", "m"], check=True)
    author = subprocess.run(
        ["git", "-C", str(repo), "log", "-1", "--format=%an <%ae>|%cn <%ce>"],
        capture_output=True, text=True, check=True,
    ).stdout.strip()
    assert author == "Ada <ada@uni.at>|Ada <ada@uni.at>"
    cfg = (repo / ".git" / "config").read_text()
    assert "Ada" not in cfg and "[user]" not in cfg
