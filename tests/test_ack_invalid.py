"""An acknowledged invalid save or push (--allow-invalid / "Save anyway") gets through both git hooks.

One environment variable (PRISM_ACK_INVALID), set only for the one acknowledged command; the hooks inherit it.
"""

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "app"))

import src.save_gate as sg  # noqa: E402
from tests.test_save_gate_check import calls, repo  # noqa: E402,F401

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(autouse=True)
def _no_ack(monkeypatch):
    monkeypatch.delenv(sg.ACK_INVALID_ENV, raising=False)


def test_the_save_check_passes_an_invalid_dataset_only_when_acknowledged(tmp_path, calls, monkeypatch):  # noqa: F811
    calls["full_result"] = ["PRISM101 bad"]
    project = repo(tmp_path / "p", commits=2)
    assert sg.check_save(project) == sg.SaveCheck(False, ["PRISM101 bad"], "validation_errors")
    monkeypatch.setenv(sg.ACK_INVALID_ENV, "1")
    assert sg.check_save(project) == sg.SaveCheck(True, ["PRISM101 bad"], "acknowledged")


def test_the_acknowledgement_is_only_in_the_child_environment(monkeypatch):
    monkeypatch.setenv("SOME_OTHER", "kept")
    env = sg.ack_env()
    assert env[sg.ACK_INVALID_ENV] == "1" and env["SOME_OTHER"] == "kept"
    assert sg.ACK_INVALID_ENV not in os.environ  # never this process: other threads' commits stay gated


def test_an_acknowledged_save_hands_the_variable_to_its_datalad_save_only(tmp_path, monkeypatch):
    from src.project_manager import ProjectManager

    pm = ProjectManager()
    seen = {}
    monkeypatch.setattr(pm, "get_datalad_status", lambda p: {"enabled": True, "available": True, "executable": "datalad"})
    monkeypatch.setattr("src.share_publish.validate_for_publish", lambda p: ["a"])
    monkeypatch.setattr(pm, "_ensure_datalad_editable_metadata_policy", lambda p: False)
    monkeypatch.setattr(pm, "_fix_annexed_text_files", lambda p: {})

    def fake_save(path, **kw):
        seen["process"] = os.environ.get(sg.ACK_INVALID_ENV)
        seen["child"] = (kw.get("env") or {}).get(sg.ACK_INVALID_ENV)
        return {"saved": True, "message": "ok"}

    monkeypatch.setattr(pm, "_run_datalad_save", fake_save)
    assert pm.save_datalad_snapshot(tmp_path, message="m", allow_invalid=True)["success"]
    assert seen == {"process": None, "child": "1"}


@pytest.mark.skipif(not shutil.which("datalad") or not shutil.which("git-annex"), reason="needs DataLad and git-annex")
@pytest.mark.slow
def test_a_real_acknowledged_save_gets_through_the_installed_hook(tmp_path, monkeypatch):
    from src.project_manager import ProjectManager

    cfg = tmp_path / "gitconfig"
    cfg.write_text("[user]\n\tname = Ada\n\temail = ada@example.org\n")
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", str(cfg))
    monkeypatch.setenv("GIT_CONFIG_NOSYSTEM", "1")
    monkeypatch.setenv("PRISM_TOOLS", str(ROOT / "prism_tools.py"))
    root = tmp_path / "study"
    root.mkdir()
    (root / "project.json").write_text(json.dumps({"Basics": {"Name": "Ack"}}) + "\n", encoding="utf-8")
    (root / "dataset_description.json").write_text(
        json.dumps({"Name": "Ack", "BIDSVersion": "1.10.0", "DatasetType": "raw"}) + "\n", encoding="utf-8"
    )
    pm = ProjectManager()
    enabled = pm.enable_datalad_for_project(root, message="start")
    assert enabled["success"] and enabled["save_gate_hook"]["installed"], enabled

    survey = root / "sub-01" / "survey"
    survey.mkdir(parents=True)
    (survey / "sub-01_task-x_wrongsuffix.tsv").write_text("a\n", encoding="utf-8")
    saved = pm.save_datalad_snapshot(root, message="anyway", allow_invalid=True)
    assert saved["success"], saved
    log = subprocess.run(["git", "-C", str(root), "log", "-1", "--format=%s"], capture_output=True, text=True).stdout
    assert log.strip().startswith("anyway [saved with ") and log.strip().endswith("validation error(s)]")
    assert sg.ACK_INVALID_ENV not in os.environ

    # the next commit without the acknowledgement is refused by the hook again
    (survey / "sub-01_task-y_wrongsuffix.tsv").write_text("b\n", encoding="utf-8")
    subprocess.run(["git", "-C", str(root), "add", "."], check=True, capture_output=True)
    commit = subprocess.run(["git", "-C", str(root), "commit", "-m", "sneak"], capture_output=True, text=True)
    assert commit.returncode != 0 and "save gate" in commit.stderr.lower()
