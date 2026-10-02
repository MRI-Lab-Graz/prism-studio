import os
import subprocess
from pathlib import Path

import pytest

import src.share_publish as sp

REPO_ROOT = Path(__file__).resolve().parents[1]
ENV_KEYS = (
    "PRISM_USER_NAME",
    "PRISM_USER_EMAIL",
    "GIT_AUTHOR_NAME",
    "GIT_AUTHOR_EMAIL",
    "GIT_COMMITTER_NAME",
    "GIT_COMMITTER_EMAIL",
)


@pytest.fixture
def clean_env(monkeypatch):
    # delenv first so monkeypatch teardown restores whatever was there
    for key in ENV_KEYS:
        monkeypatch.delenv(key, raising=False)
    return monkeypatch


def test_applies_only_when_both_prism_vars_are_set(clean_env):
    assert sp.apply_env_identity() is None and "GIT_AUTHOR_NAME" not in os.environ
    clean_env.setenv("PRISM_USER_NAME", "Ada")
    assert sp.apply_env_identity() is None
    clean_env.setenv("PRISM_USER_EMAIL", "ada@uni.at")
    assert sp.apply_env_identity() == sp.Identity("Ada", "ada@uni.at")
    assert os.environ["GIT_COMMITTER_EMAIL"] == "ada@uni.at"


def test_real_git_commit_is_attributed_via_env_path(clean_env, tmp_path):
    clean_env.setenv("PRISM_USER_NAME", "Ada Lovelace")
    clean_env.setenv("PRISM_USER_EMAIL", "ada@uni.at")
    sp.apply_env_identity()
    # isolate from the developer's global/system git config
    clean_env.setenv("GIT_CONFIG_GLOBAL", os.devnull)
    clean_env.setenv("GIT_CONFIG_NOSYSTEM", "1")
    repo = tmp_path / "r"
    subprocess.run(["git", "init", "-q", str(repo)], check=True)
    (repo / "f.txt").write_text("x")
    subprocess.run(["git", "-C", str(repo), "add", "f.txt"], check=True)
    subprocess.run(["git", "-C", str(repo), "commit", "-q", "-m", "m"], check=True)
    out = subprocess.run(
        ["git", "-C", str(repo), "log", "-1", "--format=%an|%ae|%cn|%ce"],
        check=True, capture_output=True, text=True,
    ).stdout.strip()
    assert out == "Ada Lovelace|ada@uni.at|Ada Lovelace|ada@uni.at"
    assert "[user]" not in (repo / ".git" / "config").read_text()


def test_cli_main_applies_env_identity(monkeypatch):
    import src.cli.entrypoint as ep

    calls = []
    monkeypatch.setattr(ep, "apply_env_identity", lambda: calls.append(1))
    monkeypatch.setattr("sys.argv", ["prism_tools", "publish", "--help"])
    with pytest.raises(SystemExit):
        ep.main()
    assert calls == [1]


def test_projects_page_has_publish_button_and_helper():
    section = (REPO_ROOT / "app/templates/includes/projects/push_server_section.html").read_text()
    page = (REPO_ROOT / "app/templates/projects.html").read_text()
    assert 'id="publishProjectBtn"' in section
    assert "js/publish.js" in page and "prismPublish" in page

    # path must come from the live project-state store, like the sync button
    start = page.index("publishProjectBtn")
    handler = page[start:page.index("</script>", start)]
    assert "resolveCurrentProjectPath" in handler
    assert "const projectPath = window.currentProjectPath;" not in handler
