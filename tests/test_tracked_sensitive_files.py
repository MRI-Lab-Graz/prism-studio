"""Older projects may already have the pseudonym map (secret key + reverse map)
or session logs committed. They are not rewritten out of history automatically,
but saving a snapshot must say so, plainly."""

import subprocess

from src.git_exclude import tracked_sensitive_files


def git(root, *args):
    subprocess.run(["git", "-c", "user.name=a", "-c", "user.email=a@b.c", "-C", str(root), *args], check=True, capture_output=True)


def test_lists_tracked_map_and_logs_only(tmp_path):
    git(tmp_path, "init", "-q")
    (tmp_path / "code" / "logs").mkdir(parents=True)
    (tmp_path / "code" / "anonymization_map.json").write_text("{}")
    (tmp_path / "code" / "logs" / "prism_session_1.log").write_text("x")
    (tmp_path / "code" / "analysis.R").write_text("x")
    git(tmp_path, "add", "-A")
    git(tmp_path, "commit", "-q", "-m", "x")
    assert sorted(tracked_sensitive_files(tmp_path)) == [
        "code/anonymization_map.json",
        "code/logs/prism_session_1.log",
    ]


def test_nothing_tracked_and_non_repos_give_empty_list(tmp_path):
    assert tracked_sensitive_files(tmp_path) == []  # not a repo
    git(tmp_path, "init", "-q")
    assert tracked_sensitive_files(tmp_path) == []


def test_snapshot_message_warns_when_sensitive_files_are_tracked():
    from src.git_exclude import sensitive_files_warning

    assert sensitive_files_warning([]) == ""
    text = sensitive_files_warning(["code/anonymization_map.json"])
    assert "anonymization_map.json" in text and "do not share" in text.lower()
