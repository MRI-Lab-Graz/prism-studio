"""Open from server: everybody else gets their own copy of the project from the lab server.

Real DataLad, a local folder as the server (made with put-on-server; ssh is the same `datalad clone` call).
"""

import json
import shutil
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pytest

ROOT = Path(__file__).resolve().parents[1]
for p in (ROOT, ROOT / "app"):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

from src.datalad_clone import open_from_server  # noqa: E402

needs_datalad = pytest.mark.skipif(
    not shutil.which("datalad") or not shutil.which("git-annex"), reason="needs DataLad and git-annex"
)


def _run(*cmd, cwd):
    return subprocess.run(cmd, cwd=cwd, check=True, capture_output=True, text=True).stdout


def _save(root, name, data):
    path = root / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data) if isinstance(data, bytes) else path.write_text(data, encoding="utf-8")
    _run("datalad", "save", "-m", f"add {name}", cwd=root)


def _identity(tmp_path, monkeypatch, text="[user]\n\tname = Ada\n\temail = ada@example.org\n"):
    cfg = tmp_path / "gitconfig"
    cfg.write_text(text)
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", str(cfg))
    monkeypatch.setenv("GIT_CONFIG_NOSYSTEM", "1")
    monkeypatch.setenv("HOME", str(tmp_path))
    for key in ("GIT_AUTHOR_NAME", "GIT_AUTHOR_EMAIL", "GIT_COMMITTER_NAME", "GIT_COMMITTER_EMAIL", "EMAIL"):
        monkeypatch.delenv(key, raising=False)


@pytest.fixture
def server(tmp_path, monkeypatch):
    """A project with a nested subject dataset (text and annexed data), put on a local folder as the lab server."""
    from src.share_publish import Identity, put_on_server

    _identity(tmp_path, monkeypatch)
    monkeypatch.setenv("PRISM_TOOLS", str(ROOT / "prism_tools.py"))
    project = tmp_path / "project"
    _run("datalad", "create", "-c", "text2git", str(project), cwd=tmp_path)
    _save(project, "participants.tsv", "participant_id\nsub-01\n")
    _run("datalad", "create", "-c", "text2git", "-d", str(project), str(project / "sub-01"), cwd=project)
    _save(project / "sub-01", "notes.txt", "subject one\n")
    _save(project / "sub-01", "data.bin", bytes(range(256)) * 64)  # binary: annexed
    _run("datalad", "create", "-c", "text2git", "-d", str(project / "sub-01"), str(project / "sub-01" / "ses-1"), cwd=project)
    _save(project / "sub-01" / "ses-1", "notes.txt", "session one\n")
    _run("datalad", "save", "-r", "-m", "register sub-01", cwd=project)
    location = tmp_path / "server"
    with patch("src.share_publish.validate_for_publish", return_value=[]):
        put = put_on_server(project, str(location), identity=Identity("Ada", "ada@example.org"))
    assert put["success"] is True, put
    return location


@needs_datalad
def test_open_clones_the_project_into_an_empty_folder(server, tmp_path):
    target = tmp_path / "mine"
    target.mkdir()
    result = open_from_server(str(server), target)
    assert result["success"] is True, result
    assert result["path"] == str(target.resolve())
    assert (target / "participants.tsv").read_text(encoding="utf-8") == "participant_id\nsub-01\n"


@needs_datalad
def test_it_refuses_a_target_that_is_not_empty(server, tmp_path):
    target = tmp_path / "mine"
    target.mkdir()
    (target / "keep.txt").write_text("mine\n", encoding="utf-8")
    result = open_from_server(str(server), target)
    assert result["success"] is False and result["reason"] == "target_not_empty"
    assert sorted(p.name for p in target.iterdir()) == ["keep.txt"]


@pytest.mark.parametrize("location", ["https://x/y", "git://x/y", "-oProxy=x", "ext::sh -c x", ""])
def test_it_refuses_a_web_location(location, tmp_path):
    with patch("src.datalad_clone.run_datalad_clone") as clone:
        result = open_from_server(location, tmp_path / "mine")
    assert result["success"] is False and result["reason"] == "bad_location"
    clone.assert_not_called()
    assert not (tmp_path / "mine").exists()


@needs_datalad
def test_the_copy_has_origin_as_its_server(server, tmp_path):
    from src.datalad_state import datalad_state

    result = open_from_server(str(server), tmp_path / "mine")
    assert result["success"] is True, result
    assert datalad_state(tmp_path / "mine")["server"]["name"] == "origin"


@needs_datalad
def test_nested_subject_datasets_are_installed_without_content(server, tmp_path):
    target = tmp_path / "mine"
    assert open_from_server(str(server), target)["success"] is True
    nested = target / "sub-01"
    assert (nested / "notes.txt").read_text(encoding="utf-8") == "subject one\n"
    assert (nested / "ses-1" / "notes.txt").read_text(encoding="utf-8") == "session one\n"  # every level
    assert "url = ./ses-1" in (nested / ".gitmodules").read_text(encoding="utf-8")  # what real DataLad writes
    missing = _run("git", "annex", "find", "--not", "--in=here", cwd=nested).split()
    assert missing == ["data.bin"]


@needs_datalad
def test_the_copy_has_the_save_gate_hook_in_the_project_and_nested_datasets(server, tmp_path):
    from src.save_gate import has_save_hook

    target = tmp_path / "mine"
    result = open_from_server(str(server), target)
    assert result["success"] is True, result
    assert has_save_hook(target) and has_save_hook(target / "sub-01") and has_save_hook(target / "sub-01" / "ses-1")
    for repo in (target, target / "sub-01"):  # the hook does its job: an invalid commit is refused
        bad = repo / "survey" / "sub-01_task-x_wrongsuffix.tsv"
        bad.parent.mkdir(parents=True, exist_ok=True)
        bad.write_text("a\n", encoding="utf-8")
        subprocess.run(["git", "-C", str(repo), "add", "."], check=True, capture_output=True)
        commit = subprocess.run(["git", "-C", str(repo), "commit", "-m", "sneak"], capture_output=True, text=True)
        assert commit.returncode != 0 and "save gate" in commit.stderr.lower(), (repo, commit.stdout, commit.stderr)


def _server_with_submodule_url(tmp_path, url):
    """A server dataset whose .gitmodules points sub-01 at `url` (what a crafted or compromised server could hold)."""
    secret = tmp_path / "secret"
    _run("git", "init", "-q", str(secret), cwd=tmp_path)
    (secret / "s.txt").write_text("secret\n", encoding="utf-8")
    _run("git", "add", "s.txt", cwd=secret)
    _run("git", "commit", "-qm", "s", cwd=secret)
    sha = _run("git", "rev-parse", "HEAD", cwd=secret).strip()
    srv = tmp_path / "srv"
    _run("datalad", "create", str(srv), cwd=tmp_path)
    _run("git", "update-index", "--add", "--cacheinfo", f"160000,{sha},sub-01", cwd=srv)
    (srv / ".gitmodules").write_text(
        f'[submodule "sub-01"]\n\tpath = sub-01\n\turl = {str(url).replace("SECRET", str(secret))}\n', encoding="utf-8"
    )
    _run("git", "add", ".gitmodules", cwd=srv)
    _run("git", "commit", "-qm", "sub", cwd=srv)
    return srv


@needs_datalad
@pytest.mark.parametrize("url", ["SECRET", "ssh://-oproxycommand=touch pwned/y", "../../elsewhere", "ext::sh -c x"])
def test_a_nested_dataset_url_outside_the_server_is_refused(url, tmp_path, monkeypatch):
    from src.save_gate import has_save_hook

    _identity(tmp_path, monkeypatch)
    monkeypatch.setenv("PRISM_TOOLS", str(ROOT / "prism_tools.py"))
    monkeypatch.chdir(tmp_path)
    srv = _server_with_submodule_url(tmp_path, url)
    target = tmp_path / "mine"
    result = open_from_server(str(srv), target)
    assert result["success"] is False and result["reason"] == "clone_failed", result
    shown = url.replace("SECRET", str(tmp_path / "secret"))
    assert shown in result["message"] and "sub-01" in result["message"]
    assert "is not inside the project on the server" in result["message"]  # refused by the check, not by DataLad
    assert str(target) in result["message"] and "delete" in result["message"].lower()
    assert not (target / "sub-01" / "s.txt").exists()
    assert not list(tmp_path.rglob("pwned*"))
    assert has_save_hook(target)  # the incomplete copy is still gated


def _server_with_config(tmp_path, mode):
    """A real nested server dataset whose committed config tries to send a checked url (`./sub-01`) elsewhere."""
    secret = tmp_path / "secret"
    _run("git", "init", "-q", str(secret), cwd=tmp_path)
    (secret / "s.txt").write_text("secret\n", encoding="utf-8")
    _run("git", "add", ".", cwd=secret)
    _run("git", "commit", "-qm", "s", cwd=secret)
    srv = tmp_path / "srv"
    _run("datalad", "create", "-c", "text2git", str(srv), cwd=tmp_path)
    _run("datalad", "create", "-c", "text2git", "-d", str(srv), str(srv / "sub-01"), cwd=srv)
    (srv / "sub-01" / "n.txt").write_text("legit\n", encoding="utf-8")
    _run("datalad", "save", "-r", "-m", "x", cwd=srv)
    cfg = srv / ".datalad" / "config"

    def setting(key, value, file=cfg):
        _run("git", "config", "-f", str(file), key, value, cwd=srv)

    if mode == "url-substitute":
        setting("datalad.clone.url-substitute.evil", f",.*sub-01.*,{secret}")
    elif mode == "insteadof":
        setting(f"url.{secret}.insteadOf", str(srv / "sub-01"))
    elif mode == "level-2":
        _run("datalad", "create", "-c", "text2git", "-d", str(srv / "sub-01"), str(srv / "sub-01" / "ses-1"), cwd=srv)
        setting("datalad.clone.url-substitute.evil", f",.*ses-1.*,{secret}", file=srv / "sub-01" / ".datalad" / "config")
        _run("datalad", "save", "-r", "-m", "n", cwd=srv)
    elif mode == "include":
        (srv / "inc.cfg").write_text(f'[datalad "get"]\n\tsubdataset-source-candidate-000x = {secret}\n', encoding="utf-8")
        setting("include.path", "../inc.cfg")
    elif mode == "candidate":
        setting("datalad.get.subdataset-source-candidate-000x", str(secret))
    elif mode == "gitmodules-key":
        setting("submodule.sub-01.update", "!touch pwned", file=srv / ".gitmodules")
    elif mode == "duplicate-url":
        gm = srv / ".gitmodules"
        gm.write_text(gm.read_text(encoding="utf-8").replace("url = ./sub-01", f"url = {secret}\n\turl = ./sub-01"))
    _run("datalad", "save", "-r", "-m", mode, cwd=srv)
    return srv


@needs_datalad
@pytest.mark.parametrize(
    "mode", ["url-substitute", "insteadof", "level-2", "include", "candidate", "gitmodules-key", "duplicate-url"]
)
def test_server_config_that_could_redirect_a_checked_url_is_refused(mode, tmp_path, monkeypatch):
    from src.save_gate import has_save_hook

    _identity(tmp_path, monkeypatch)
    monkeypatch.setenv("PRISM_TOOLS", str(ROOT / "prism_tools.py"))
    monkeypatch.chdir(tmp_path)
    srv = _server_with_config(tmp_path, mode)
    target = tmp_path / "mine"
    result = open_from_server(str(srv), target)
    assert result["success"] is False and result["reason"] == "clone_failed", result
    refused_by = "is not inside the project on the server" if mode == "duplicate-url" else "is not accepted"
    assert refused_by in result["message"] and "delete" in result["message"].lower(), result["message"]
    assert not list(target.rglob("s.txt"))  # the foreign repository's marker file
    assert not list(tmp_path.rglob("pwned*"))
    for nested in (target / "sub-01", target / "sub-01" / "ses-1"):
        origin = subprocess.run(["git", "-C", str(nested), "remote", "get-url", "origin"], capture_output=True, text=True)
        assert str(tmp_path / "secret") not in origin.stdout
    assert has_save_hook(target)
    if mode == "level-2":  # level 1 was fine and installed; level 2 was refused before installing ses-1
        assert (target / "sub-01" / "n.txt").is_file() and "sub-01" in result["message"]


def _server_with_links(tmp_path, mode):
    """Two subject datasets; the root's config files are replaced by symlinks (committed with plain git)."""
    secret = tmp_path / "secret"
    _run("git", "init", "-q", str(secret), cwd=tmp_path)
    (secret / "s.txt").write_text("secret\n", encoding="utf-8")
    _run("git", "add", ".", cwd=secret)
    _run("git", "commit", "-qm", "s", cwd=secret)
    srv = tmp_path / "srv"
    _run("datalad", "create", "-c", "text2git", str(srv), cwd=tmp_path)
    for sub in ("sub-01", "sub-02"):
        _run("datalad", "create", "-c", "text2git", "-d", str(srv), str(srv / sub), cwd=srv)
    evil = f'[datalad "dataset"]\n\tid = x\n[datalad "clone.url-substitute"]\n\tevil = ,.*sub-02.*,{secret}\n'
    (srv / "sub-01" / "evil.cfg").write_text(evil, encoding="utf-8")
    (srv / "sub-01" / "dl").mkdir()
    (srv / "sub-01" / "dl" / "config").write_text(evil, encoding="utf-8")
    (srv / "sub-01" / "gm").write_text((srv / ".gitmodules").read_text(encoding="utf-8"), encoding="utf-8")
    _run("datalad", "save", "-r", "-m", "x", cwd=srv)
    if mode == "config-to-child":  # dangles while the root is checked, resolves once sub-01 is installed
        (srv / ".datalad" / "config").unlink()
        (srv / ".datalad" / "config").symlink_to("../sub-01/evil.cfg")
    elif mode == "dangling-config":
        (srv / ".datalad" / "config").unlink()
        (srv / ".datalad" / "config").symlink_to("../nowhere.cfg")
    elif mode == "datalad-dir":
        _run("git", "rm", "-rq", ".datalad", cwd=srv)
        shutil.rmtree(srv / ".datalad", ignore_errors=True)
        (srv / ".datalad").symlink_to("sub-01/dl")
    elif mode == "gitmodules":
        (srv / ".gitmodules").unlink()
        (srv / ".gitmodules").symlink_to("sub-01/gm")
    _run("git", "add", "-A", ".", cwd=srv)
    _run("git", "commit", "-qm", mode, cwd=srv)
    return srv


@needs_datalad
@pytest.mark.parametrize("mode", ["config-to-child", "dangling-config", "datalad-dir", "gitmodules"])
def test_a_symlinked_config_file_is_refused_not_skipped(mode, tmp_path, monkeypatch):
    _identity(tmp_path, monkeypatch)
    monkeypatch.setenv("PRISM_TOOLS", str(ROOT / "prism_tools.py"))
    monkeypatch.chdir(tmp_path)
    srv = _server_with_links(tmp_path, mode)
    target = tmp_path / "mine"
    result = open_from_server(str(srv), target)
    assert result["success"] is False and result["reason"] == "clone_failed", result
    # git itself refuses to check out a symlinked .gitmodules; DataLad still reports the clone as ok
    refused_by = "was not checked out completely" if mode == "gitmodules" else "is not a regular"
    assert refused_by in result["message"] and "delete" in result["message"].lower(), result["message"]
    assert not list(target.rglob("s.txt"))  # the foreign repository was not cloned into sub-02
    assert not (target / "sub-01" / "evil.cfg").exists()  # refused before anything nested was installed


@needs_datalad
def test_the_servers_own_origin_is_not_inherited(server, tmp_path):
    """A folder location whose own (uncommitted) .git/config names another repo as origin: DataLad would add and fetch it."""
    other = tmp_path / "other"
    _run("git", "init", "-q", str(other), cwd=tmp_path)
    (other / "o.txt").write_text("other\n", encoding="utf-8")
    _run("git", "add", ".", cwd=other)
    _run("git", "commit", "-qm", "o", cwd=other)
    for repo in (server, server / "sub-01"):
        _run("git", "remote", "add", "origin", str(other), cwd=repo)
    target = tmp_path / "mine"
    result = open_from_server(str(server), target)
    assert result["success"] is True, result
    for repo in (target, target / "sub-01", target / "sub-01" / "ses-1"):
        assert _run("git", "remote", cwd=repo).split() == ["origin"], repo
        assert "origin-2" not in _run("git", "branch", "-r", cwd=repo)


def _server_with_trap(tmp_path, mode):
    """A real server (sub-01/ses-1, sub-02) whose tree points a nested path elsewhere, and a victim dataset."""
    secret = tmp_path / "secret"
    _run("git", "init", "-q", str(secret), cwd=tmp_path)
    (secret / "s.txt").write_text("secret\n", encoding="utf-8")
    _run("git", "add", ".", cwd=secret)
    _run("git", "commit", "-qm", "s", cwd=secret)
    origin = tmp_path / "victim-origin"  # another DataLad dataset on this computer, sub-v not installed
    _run("datalad", "create", "-c", "text2git", str(origin), cwd=tmp_path)
    _run("datalad", "create", "-c", "text2git", "-d", str(origin), str(origin / "sub-v"), cwd=tmp_path)
    _run("datalad", "save", "-r", "-m", "v", cwd=origin)
    victim = tmp_path / "victim"
    _run("datalad", "clone", str(origin), str(victim), cwd=tmp_path)
    srv = tmp_path / "srv"
    _run("datalad", "create", "-c", "text2git", str(srv), cwd=tmp_path)
    for parent, child in ((srv, "sub-01"), (srv / "sub-01", "ses-1"), (srv, "sub-02")):
        _run("datalad", "create", "-c", "text2git", "-d", str(parent), str(parent / child), cwd=tmp_path)
    _run("datalad", "save", "-r", "-m", "x", cwd=srv)
    s1 = srv / "sub-01"

    def commit(repo):
        _run("git", "add", "-A", ".", cwd=repo)
        _run("git", "commit", "-qm", mode, cwd=repo)

    def link(repo, name, to):  # the nested dataset committed as a symlink, .gitmodules unchanged
        _run("git", "rm", "-q", "--cached", name, cwd=repo)
        shutil.rmtree(repo / name)
        (repo / name).symlink_to(to)
        commit(repo)

    if mode in ("deep-path", "deep-path-gm"):  # the root lists sub-01/ses-1; sub-01's own files redirect ses-1
        if mode == "deep-path":
            with open(s1 / ".datalad" / "config", "a", encoding="utf-8") as cfg:
                cfg.write(f'[datalad "clone.url-substitute"]\n\tevil = ,.*ses-1.*,{secret}\n')
        else:
            gm = s1 / ".gitmodules"
            gm.write_text(gm.read_text(encoding="utf-8").replace("url = ./ses-1", f"url = {secret}"), encoding="utf-8")
        commit(s1)
        with open(srv / ".gitmodules", "a", encoding="utf-8") as gm:
            gm.write('[submodule "deep"]\n\tpath = sub-01/ses-1\n\turl = ./sub-01/ses-1\n')
        commit(srv)
    elif mode == "sub-abs-link":
        link(srv, "sub-02", victim)
    elif mode == "ses-link-up":
        link(s1, "ses-1", victim)
        commit(srv)
    elif mode == "self-link":
        link(srv, "sub-02", ".")
    elif mode == "sub-rel-link":
        link(srv, "sub-02", "sub-01")
    return srv, victim


@needs_datalad
@pytest.mark.parametrize(
    "mode, refused",
    [
        ("deep-path", "sub-01/ses-1"),
        ("deep-path-gm", "sub-01/ses-1"),
        ("sub-abs-link", "sub-02"),
        ("ses-link-up", "ses-1"),
        ("self-link", "sub-02"),
        ("sub-rel-link", "sub-02"),
    ],
)
def test_a_nested_path_must_be_a_real_nested_dataset_of_its_own_parent(mode, refused, tmp_path, monkeypatch):
    """A `.gitmodules` path is installed only when it is a gitlink of that very dataset and a real folder."""
    from src.save_gate import has_save_hook

    _identity(tmp_path, monkeypatch)
    monkeypatch.setenv("PRISM_TOOLS", str(ROOT / "prism_tools.py"))
    monkeypatch.chdir(tmp_path)
    srv, victim = _server_with_trap(tmp_path, mode)
    target = tmp_path / "mine"
    result = open_from_server(str(srv), target)
    assert result["success"] is False and result["reason"] == "clone_failed", result
    assert f"'{refused}'" in result["message"] and "is not a nested dataset" in result["message"], result["message"]
    assert "delete" in result["message"].lower()
    assert not list(target.rglob("s.txt"))  # the foreign repository was not cloned anywhere into the copy
    assert not has_save_hook(victim)  # nothing was written into the victim
    assert not (victim / "sub-v" / ".datalad").exists()  # and nothing installed in it


def _folder_server_trap(tmp_path, mode):
    """A folder server whose files name another repository of this computer (a victim with `s.txt`)."""
    victim = tmp_path / "victim"
    _run("datalad", "create", "-c", "text2git", str(victim), cwd=tmp_path)
    _save(victim, "s.txt", "secret\n")
    head = _run("git", "rev-parse", "HEAD", cwd=victim).strip()
    srv = tmp_path / "srv"
    _run("datalad", "create", "-c", "text2git", str(srv), cwd=tmp_path)
    for sub in ("sub-01", "sub-02"):
        _run("datalad", "create", "-c", "text2git", "-d", str(srv), str(srv / sub), cwd=tmp_path)
    _run("datalad", "save", "-r", "-m", "x", cwd=srv)
    if mode in ("url-link", "srv-dir-link", "srv-gitfile"):  # sub-02 records the victim's commit
        _run("git", "update-index", "--cacheinfo", f"160000,{head},sub-02", cwd=srv)
    if mode == "url-link":  # a push is enough: a committed link, named as sub-02's url
        (srv / "lnk").symlink_to(victim)
        gm = srv / ".gitmodules"
        gm.write_text(gm.read_text(encoding="utf-8").replace("url = ./sub-02", "url = ./lnk"), encoding="utf-8")
        _run("git", "add", ".gitmodules", "lnk", cwd=srv)
    if mode in ("url-link", "srv-dir-link", "srv-gitfile"):
        _run("git", "commit", "-qm", mode, cwd=srv)
    if mode == "srv-dir-link":  # someone who can write the server folder itself
        shutil.rmtree(srv / "sub-02")
        (srv / "sub-02").symlink_to(victim)
    elif mode == "srv-gitfile":
        shutil.rmtree(srv / "sub-02" / ".git")
        (srv / "sub-02" / ".git").write_text(f"gitdir: {victim / '.git'}\n", encoding="utf-8")
    elif mode in ("loc-gitfile", "alt-gitfile"):  # the location's .git is a `gitdir:` file
        real = tmp_path / "realgit"
        shutil.move(str(srv / ".git"), str(real))
        (srv / ".git").write_text(f"gitdir: {real}\n", encoding="utf-8")
        if mode == "alt-gitfile":
            (real / "objects" / "info" / "alternates").write_text(f"{victim / '.git' / 'objects'}\n", encoding="utf-8")
    elif mode == "alt-commondir":  # the location's .git names a common git dir that has alternates
        common = tmp_path / "common"
        shutil.copytree(srv / ".git", common)
        (common / "objects" / "info" / "alternates").write_text(f"{victim / '.git' / 'objects'}\n", encoding="utf-8")
        (srv / ".git" / "commondir").write_text(f"{common}\n", encoding="utf-8")
    return srv, victim, head


@needs_datalad
@pytest.mark.parametrize(
    "mode, reason, refused",
    [
        ("url-link", "clone_failed", "'./lnk'"),
        ("srv-dir-link", "clone_failed", "'sub-02'"),
        ("srv-gitfile", "clone_failed", "'sub-02'"),
        ("loc-gitfile", "bad_location", ".git"),
        ("alt-gitfile", "bad_location", ".git"),
        ("alt-commondir", "clone_failed", "alternates"),
    ],
)
def test_a_folder_server_must_be_real_folders_without_alternates(mode, reason, refused, tmp_path, monkeypatch):
    """A folder server is read on this computer: links, `gitdir:` files and borrowed objects could name any repo."""
    _identity(tmp_path, monkeypatch)
    monkeypatch.setenv("PRISM_TOOLS", str(ROOT / "prism_tools.py"))
    monkeypatch.chdir(tmp_path)
    srv, victim, head = _folder_server_trap(tmp_path, mode)
    target = tmp_path / "mine"
    result = open_from_server(str(srv), target)
    assert result["success"] is False and result["reason"] == reason, result
    assert refused in result["message"] and "not accepted" in result["message"], result["message"]
    assert not list(target.rglob("s.txt"))  # the victim's content is not in the copy
    if (target / "sub-02" / ".git").exists():
        has = subprocess.run(["git", "-C", str(target / "sub-02"), "cat-file", "-e", head], capture_output=True)
        assert has.returncode != 0  # nor its commit
    if reason == "bad_location":
        assert not target.exists()


def _alternates(repo, foreign):
    info = repo / ".git" / "objects" / "info"
    info.mkdir(parents=True, exist_ok=True)
    (info / "alternates").write_text(f"{foreign / '.git' / 'objects'}\n", encoding="utf-8")


@needs_datalad
def test_a_folder_location_with_alternates_is_refused(server, tmp_path):
    secret = tmp_path / "secret"
    _run("git", "init", "-q", str(secret), cwd=tmp_path)
    _alternates(server, secret)
    target = tmp_path / "mine"
    result = open_from_server(str(server), target)
    assert result["success"] is False and result["reason"] == "bad_location", result
    assert "alternates" in result["message"]
    assert not target.exists()


@needs_datalad
def test_a_nested_server_folder_with_alternates_is_refused(server, tmp_path):
    secret = tmp_path / "secret"
    _run("git", "init", "-q", str(secret), cwd=tmp_path)
    _alternates(server / "sub-01", secret)
    target = tmp_path / "mine"
    result = open_from_server(str(server), target)
    assert result["success"] is False and result["reason"] == "clone_failed", result
    assert "alternates" in result["message"] and "delete" in result["message"].lower()
    assert not (target / "sub-01" / ".git" / "objects" / "info" / "alternates").exists()
    assert not (target / "sub-01" / "notes.txt").exists()  # sub-01 was not installed


@needs_datalad
def test_the_checkout_check_has_a_timeout(server, tmp_path):
    real = subprocess.run

    def slow_status(cmd, *args, **kwargs):
        if "status" in cmd:
            assert kwargs.get("timeout") == 60
            raise subprocess.TimeoutExpired(cmd, kwargs["timeout"])
        return real(cmd, *args, **kwargs)

    with patch("src.datalad_clone.subprocess.run", slow_status):
        result = open_from_server(str(server), tmp_path / "mine")
    assert result["success"] is False and result["reason"] == "clone_failed", result
    assert "did not answer within 60 seconds" in result["message"]


def test_relative_and_inside_urls():
    from src.datalad_clone import nested_url_problem

    for ok in ("./sub-01", "sub-01", "sub-01/ses-1", "/srv/lab/x/sub-01", "u@h:/srv/x/sub-01"):
        assert nested_url_problem(ok, "/srv/lab/x" if ok.startswith("/") else "u@h:/srv/x") == "", ok
    for bad in (
        "/srv/lab/xy/sub-01", "/srv/lab/x/../secret", "../x", "/etc", "C:\\x", "ssh://h/x", "-oX", "a b", "", ".",
        "u@-oProxyCommand=x:/srv/lab/x/sub", "a\nb", "ext::sh",
    ):
        assert nested_url_problem(bad, "/srv/lab/x"), bad


@needs_datalad
def test_a_relative_location_is_relative_to_the_working_directory(server, tmp_path, monkeypatch):
    monkeypatch.chdir(server.parent)
    (tmp_path / "elsewhere").mkdir()
    target = tmp_path / "elsewhere" / "mine"
    result = open_from_server(server.name, target)
    assert result["success"] is True, result
    assert (target / "participants.tsv").is_file()


@needs_datalad
@pytest.mark.parametrize("existing", [False, True])
def test_a_target_inside_a_git_work_tree_is_refused(existing, server, tmp_path):
    repo = tmp_path / "repo"
    _run("git", "init", "-q", str(repo), cwd=tmp_path)
    target = repo / "mine"
    if existing:
        target.mkdir()
    with patch("src.datalad_clone.run_datalad_clone") as clone:
        result = open_from_server(str(server), target)
    assert result["success"] is False and result["reason"] == "bad_target", result
    assert "inside a git repository" in result["message"]
    clone.assert_not_called()


def test_a_relative_target_is_refused(tmp_path):
    with patch("src.datalad_clone.run_datalad_clone") as clone:
        result = open_from_server("/srv/lab/project", "mine")
    assert result["success"] is False and result["reason"] == "bad_target", result
    clone.assert_not_called()


@needs_datalad
def test_without_a_git_identity_it_stops_before_cloning(server, tmp_path, monkeypatch):
    _identity(tmp_path, monkeypatch, text="")
    with patch("src.datalad_clone.run_datalad_clone") as clone:
        result = open_from_server(str(server), tmp_path / "mine")
    assert result["success"] is False and result["reason"] == "no_identity", result
    clone.assert_not_called()
    assert not (tmp_path / "mine").exists()


def test_without_datalad_it_stops_before_cloning(tmp_path):
    from src.datalad_doctor import datalad_preflight

    no_tools = lambda project: datalad_preflight(project, which=lambda tool: None)  # noqa: E731
    with patch("src.datalad_clone.datalad_preflight", no_tools), patch("src.datalad_clone.run_datalad_clone") as clone:
        result = open_from_server("/srv/lab/project", tmp_path / "mine")
    assert result["success"] is False and result["reason"] == "no_datalad", result
    clone.assert_not_called()


def _studio(job_id, location, target):
    import src.web.blueprints.projects_datalad_server_blueprint as studio

    studio._create_job(job_id, kind="open")
    studio._run_open_job(job_id, Path(target), {"location": str(location)})
    return studio._get_job(job_id)


def _cli(location, target, capsys):
    from src.cli.commands.datalad import cmd_datalad_open_from_server

    code = 0
    try:
        cmd_datalad_open_from_server(SimpleNamespace(location=str(location), target=str(target), json=True))
    except SystemExit as exc:
        code = exc.code
    return code, json.loads(capsys.readouterr().out)


@needs_datalad
def test_the_cli_and_studio_refuse_the_same_way(server, tmp_path, capsys):
    for name in ("cli", "studio"):
        (tmp_path / name).mkdir()
        (tmp_path / name / "keep.txt").write_text("mine\n", encoding="utf-8")
    code, cli = _cli(server, tmp_path / "cli", capsys)
    job = _studio("open-refused", server, tmp_path / "studio")
    assert code == 1 and job["status"] == "error" and job["kind"] == "open"
    assert cli["reason"] == job["result"]["reason"] == "target_not_empty"


@needs_datalad
def test_the_cli_and_studio_open_a_project_the_same_way(server, tmp_path, capsys):
    from src.save_gate import has_save_hook

    code, cli = _cli(server, tmp_path / "cli", capsys)
    job = _studio("open-ok", server, tmp_path / "studio")
    assert code == 0 and job["status"] == "complete", job
    assert cli["path"] == str((tmp_path / "cli").resolve())
    assert job["result"]["path"] == str((tmp_path / "studio").resolve())  # the page opens this project

    def files(d):
        return sorted(str(p.relative_to(d)) for p in d.rglob("*") if ".git" not in p.parts)

    assert files(tmp_path / "cli") == files(tmp_path / "studio")
    assert has_save_hook(tmp_path / "studio" / "sub-01") and has_save_hook(tmp_path / "cli" / "sub-01")


def _prism_tools(*argv):
    return subprocess.run([sys.executable, str(ROOT / "prism_tools.py"), *argv], capture_output=True, text=True, timeout=120)


def test_open_from_server_runs_through_the_real_dispatch(tmp_path):
    out = _prism_tools(
        "datalad", "open-from-server", "--location", "https://x/y", "--target", str(tmp_path / "mine"), "--json"
    )
    assert out.returncode == 1, out.stderr
    assert json.loads(out.stdout)["reason"] == "bad_location"
    out = _prism_tools("datalad", "open-from-server", "--location", "/srv/lab/x", "--target", "mine", "--json")
    assert out.returncode == 1, out.stderr
    refused = json.loads(out.stdout)
    assert refused["reason"] == "bad_target" and "full path" in refused["message"]  # Studio's 400 says the same
