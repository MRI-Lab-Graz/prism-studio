"""A file named like an option (e.g. `-f.tsv`) must not be read by `git annex
unannex` as an option: paths go after `--`."""

import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).parent.parent / "app"))

import src.project_manager as pm


def test_unannex_command_puts_paths_after_double_dash(tmp_path, monkeypatch):
    manager = pm.ProjectManager()
    calls = []

    def fake_run(cmd, **kwargs):
        calls.append(cmd)
        out = "-f.tsv\nsub-01/a.tsv\n" if "find" in cmd else ""
        return SimpleNamespace(returncode=0, stdout=out, stderr="")

    monkeypatch.setattr(pm.shutil, "which", lambda name: f"/usr/bin/{name}")
    monkeypatch.setattr(pm.subprocess, "run", fake_run)
    monkeypatch.setattr(manager, "_iter_datalad_dataset_roots", lambda p: [tmp_path])
    monkeypatch.setattr(manager, "_text_policy_glob_patterns", lambda: [])
    monkeypatch.setattr(manager, "_derivatives_only_glob_patterns", lambda: [])
    monkeypatch.setattr(manager, "_matches_text_policy", lambda *a, **k: True)

    result = manager._fix_annexed_text_files(tmp_path)

    unannex = next(c for c in calls if "unannex" in c)
    assert unannex[unannex.index("unannex") + 1] == "--"
    assert unannex[-2:] == ["-f.tsv", "sub-01/a.tsv"]
    assert result["fixed_count"] == 2
