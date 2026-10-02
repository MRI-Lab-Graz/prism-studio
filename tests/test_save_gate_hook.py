import os
import shutil
import stat
import subprocess

import pytest

import src.save_gate as sg
from src.share_publish import HookExistsError, NotAGitRepoError


def run(*args, cwd, env=None, check=True):
    return subprocess.run(list(args), cwd=cwd, capture_output=True, text=True, check=check, env=env)


@pytest.fixture
def repo(tmp_path):
    root = tmp_path / "ds"
    run("git", "init", "-q", str(root), cwd=tmp_path)
    (root / "f").write_text("x")
    run("git", "add", "f", cwd=root)
    return root


def fake_tool(tmp_path, exit_code):
    tool = tmp_path / f"prism_tools_{exit_code}"
    tool.write_text(f"#!/bin/sh\necho 'PRISM save gate: fake' \nexit {exit_code}\n")
    tool.chmod(tool.stat().st_mode | stat.S_IEXEC)
    return tool


def commit(root, tool=None):
    env = {**os.environ}
    env.pop("PRISM_TOOLS", None)
    if tool:
        env["PRISM_TOOLS"] = str(tool)
    return run("git", "-c", "user.name=t", "-c", "user.email=t@t.t", "commit", "-q", "-m", "m",
               cwd=root, env=env, check=False)


def test_hook_blocks_commit_when_check_fails(repo, tmp_path):
    sg.install_save_hook(repo)
    result = commit(repo, fake_tool(tmp_path, 1))
    assert result.returncode != 0 and "PRISM save gate" in result.stderr


def test_hook_allows_commit_when_check_passes(repo, tmp_path):
    sg.install_save_hook(repo)
    assert commit(repo, fake_tool(tmp_path, 0)).returncode == 0


def test_hook_fails_closed_when_tool_is_missing(repo):
    if shutil.which("prism_tools"):
        pytest.skip("prism_tools is on PATH here")
    sg.install_save_hook(repo)
    result = commit(repo, tool=None)
    assert result.returncode != 0
    assert "PRISM save gate" in result.stderr and "PRISM_TOOLS" in result.stderr


def test_foreign_hook_is_never_overwritten(repo):
    hook = repo / ".git" / "hooks" / "pre-commit"
    hook.write_text("#!/bin/sh\necho mine\n")
    with pytest.raises(HookExistsError):
        sg.install_save_hook(repo)
    assert "mine" in hook.read_text()


def test_dangling_symlink_hook_is_foreign(repo):
    hook = repo / ".git" / "hooks" / "pre-commit"
    hook.parent.mkdir(exist_ok=True)
    hook.symlink_to(repo / "nowhere")
    with pytest.raises(HookExistsError):
        sg.install_save_hook(repo)


def test_install_is_idempotent_and_executable(repo):
    sg.install_save_hook(repo)
    hook = sg.install_save_hook(repo)
    assert sg.SAVE_HOOK_MARKER in hook.read_text()
    assert hook.stat().st_mode & stat.S_IXUSR
    assert sg.has_save_hook(repo)


def test_install_on_a_plain_folder_writes_nothing(tmp_path):
    plain = tmp_path / "plain"
    plain.mkdir()
    with pytest.raises(NotAGitRepoError):
        sg.install_save_hook(plain)
    assert list(plain.iterdir()) == []


def test_install_save_hooks_covers_every_dataset_root_and_reports_foreign(tmp_path, monkeypatch):
    roots = []
    for name in ("a", "b", "c"):
        r = tmp_path / name
        run("git", "init", "-q", str(r), cwd=tmp_path)
        roots.append(r)
    (roots[2] / ".git" / "hooks" / "pre-commit").write_text("#!/bin/sh\nexit 0\n")
    monkeypatch.setattr(sg, "_dataset_roots", lambda p: roots)
    result = sg.install_save_hooks(tmp_path)
    assert sorted(result["installed"]) == sorted(str(r) for r in roots[:2])
    assert result["foreign"] == [str(roots[2])]
    assert [sg.has_save_hook(r) for r in roots] == [True, True, False]


def test_install_save_hooks_reports_non_git_root_as_error_without_raising(tmp_path, monkeypatch):
    good = tmp_path / "good"
    run("git", "init", "-q", str(good), cwd=tmp_path)
    plain = tmp_path / "plain"
    plain.mkdir()
    monkeypatch.setattr(sg, "_dataset_roots", lambda p: [plain, good])
    result = sg.install_save_hooks(tmp_path)
    assert result["installed"] == [str(good)]
    assert result["foreign"] == []
    assert len(result["errors"]) == 1 and result["errors"][0].startswith(f"{plain}: ")


def _bad_hook_dir(repo):
    hook = repo / ".git" / "hooks" / "pre-commit"
    hook.parent.mkdir(exist_ok=True)
    hook.mkdir()
    return hook


def _unreadable_hook(repo):
    if os.geteuid() == 0:
        pytest.skip("root can read anything")
    hook = repo / ".git" / "hooks" / "pre-commit"
    hook.parent.mkdir(exist_ok=True)
    hook.write_text("#!/bin/sh\n")
    hook.chmod(0)
    return hook


@pytest.mark.parametrize("make", [_bad_hook_dir, _unreadable_hook])
def test_unreadable_or_directory_hook_is_foreign_not_a_crash(repo, tmp_path, monkeypatch, make):
    hook = make(repo)
    try:
        with pytest.raises(HookExistsError):
            sg.install_save_hook(repo)
        assert sg.has_save_hook(repo) is False
        monkeypatch.setattr(sg, "_dataset_roots", lambda p: [repo])
        assert sg.install_save_hooks(tmp_path) == {"installed": [], "foreign": [str(repo)], "errors": []}
    finally:
        if hook.is_file():
            hook.chmod(0o644)


def test_has_save_hook_false_for_symlink(repo):
    real = repo / "real"
    real.write_text(sg._save_hook_script())
    hook = repo / ".git" / "hooks" / "pre-commit"
    hook.parent.mkdir(exist_ok=True)
    hook.symlink_to(real)
    assert sg.has_save_hook(repo) is False


def test_hook_scrubs_git_index_env_for_the_tool(repo, tmp_path):
    out = tmp_path / "seen"
    tool = tmp_path / "prism_tools_env"
    tool.write_text(f'#!/bin/sh\necho "${{GIT_INDEX_FILE-unset}}" > {out}\nexit 0\n')
    tool.chmod(tool.stat().st_mode | stat.S_IEXEC)
    sg.install_save_hook(repo)
    run("git", "-c", "user.name=t", "-c", "user.email=t@t.t", "commit", "-q", "-m", "0", cwd=repo,
        env={**os.environ, "PRISM_TOOLS": str(tool)})
    (repo / "f").write_text("y")
    env = {**os.environ, "PRISM_TOOLS": str(tool)}
    r = run("git", "-c", "user.name=t", "-c", "user.email=t@t.t", "commit", "-q", "-o", "f", "-m", "m",
            cwd=repo, env=env, check=False)
    assert r.returncode == 0, r.stderr
    assert out.read_text().strip() == "unset"


def test_hook_works_in_a_real_submodule(tmp_path):
    sub = tmp_path / "sub"
    run("git", "init", "-q", str(sub), cwd=tmp_path)
    (sub / "f").write_text("x")
    run("git", "add", "f", cwd=sub)
    run("git", "-c", "user.name=t", "-c", "user.email=t@t.t", "commit", "-q", "-m", "i", cwd=sub)
    sup = tmp_path / "sup"
    run("git", "init", "-q", str(sup), cwd=tmp_path)
    run("git", "-c", "protocol.file.allow=always", "submodule", "add", "-q", str(sub), "s", cwd=sup)
    nested = sup / "s"
    hook = sg.install_save_hook(nested)
    assert sg.has_save_hook(nested) and hook.is_file()
    (nested / "g").write_text("z")
    run("git", "add", "g", cwd=nested)
    assert commit(nested, fake_tool(tmp_path, 1)).returncode != 0
