"""On Windows git-annex puts a new dataset on an adjusted branch and adds two bookkeeping
commits, so a brand-new dataset has 3 commits. Its first save must still be exempt."""
import subprocess

from src import save_gate as sg

GIT = ["git", "-c", "user.name=t", "-c", "user.email=t@t.t"]


def _commit(repo, message):
    subprocess.run([*GIT, "commit", "--allow-empty", "-q", "-m", message], cwd=repo, check=True)


def _repo(tmp_path, *messages):
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    for message in messages:
        _commit(tmp_path, message)
    return tmp_path


def test_annex_adjusted_branch_bookkeeping_does_not_count_as_history(tmp_path):
    repo = _repo(
        tmp_path,
        "commit before entering adjusted branch",
        "[DATALAD] new dataset",
        "git-annex adjusted branch",
    )
    assert sg._is_initial_save(repo) == (True, "")


def test_a_real_commit_on_top_of_the_bookkeeping_is_gated(tmp_path):
    repo = _repo(
        tmp_path,
        "commit before entering adjusted branch",
        "[DATALAD] new dataset",
        "git-annex adjusted branch",
        "scaffold",
    )
    assert sg._is_initial_save(repo) == (False, "")
