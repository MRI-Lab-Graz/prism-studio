"""The pseudonym map (with its secret key) and session logs (absolute paths,
usernames) must stay on this machine: not in git/DataLad pushes, not in ZIPs,
and the map must not be world-readable."""

import os
import subprocess
import sys
import zipfile
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "app"))

from src.git_exclude import ensure_git_excluded
from src.project_session_logging import ProjectSessionLogger
from src.web.export_project import export_project


def _git_project(tmp_path: Path) -> Path:
    p = tmp_path / "study"
    (p / "sub-001").mkdir(parents=True)
    (p / "participants.tsv").write_text("participant_id\nsub-001\n", encoding="utf-8")
    subprocess.run(["git", "init", "-q", str(p)], check=True)
    return p


def _ignored(project: Path, rel: str) -> bool:
    return subprocess.run(["git", "-C", str(project), "check-ignore", "-q", rel]).returncode == 0


def test_ensure_git_excluded_is_idempotent_and_skips_non_repos(tmp_path):
    p = _git_project(tmp_path)
    ensure_git_excluded(p, "a/b.json")
    ensure_git_excluded(p, "a/b.json", "c/")
    lines = (p / ".git" / "info" / "exclude").read_text().splitlines()
    assert lines.count("a/b.json") == 1 and "c/" in lines
    ensure_git_excluded(tmp_path / "not-a-repo", "x")  # no .git: silently nothing


def test_export_keeps_map_out_of_git_and_owner_only(tmp_path):
    p = _git_project(tmp_path)
    export_project(p, tmp_path / "o.zip", anonymize=True, include_derivatives=False, include_code=True)
    assert _ignored(p, "code/anonymization_map.json")
    if os.name == "posix":
        assert (p / "code" / "anonymization_map.json").stat().st_mode & 0o077 == 0


def test_session_logs_are_git_ignored(tmp_path):
    p = _git_project(tmp_path)
    ProjectSessionLogger().activate_project(p)
    assert _ignored(p, "code/logs/prism_session_x.log")


def test_zip_export_leaves_out_session_logs(tmp_path):
    p = _git_project(tmp_path)
    (p / "code" / "logs").mkdir(parents=True)
    (p / "code" / "logs" / "prism_session_1.log").write_text("# project_root: /Users/me/x\n")
    (p / "code" / "analysis.R").write_text("x <- 1\n")
    export_project(p, tmp_path / "o.zip", anonymize=False, include_derivatives=False, include_code=True)
    with zipfile.ZipFile(tmp_path / "o.zip") as z:
        names = z.namelist()
    assert "code/analysis.R" in names
    assert not any("code/logs/" in n for n in names)
