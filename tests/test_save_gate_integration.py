import os
import shutil
import sys
from pathlib import Path

import pytest

import src.save_gate as sg
from src.share_publish import HookExistsError

_APP = str(Path(__file__).resolve().parents[1] / "app")
if _APP not in sys.path:
    sys.path.insert(0, _APP)

from src.project_manager import ProjectManager  # noqa: E402


def test_ensure_prism_tools_env_sets_the_repo_script(monkeypatch):
    monkeypatch.delenv("PRISM_TOOLS", raising=False)
    value = sg.ensure_prism_tools_env()
    assert value and os.path.basename(value) == "prism_tools.py"
    assert os.environ["PRISM_TOOLS"] == value
    assert os.access(value, os.X_OK)


def test_ensure_prism_tools_env_never_overrides(monkeypatch):
    monkeypatch.setenv("PRISM_TOOLS", "/custom/tool")
    assert sg.ensure_prism_tools_env() is None
    assert os.environ["PRISM_TOOLS"] == "/custom/tool"


def test_cli_main_exports_prism_tools(monkeypatch):
    import src.cli.entrypoint as ep

    called = []
    monkeypatch.setattr(ep, "ensure_prism_tools_env", lambda: called.append(1))
    monkeypatch.setattr(ep, "apply_env_identity", lambda: None)
    monkeypatch.setattr("sys.argv", ["prism_tools", "save-gate", "--help"])
    with pytest.raises(SystemExit):
        ep.main()
    assert called == [1]


def _ordered_manager(monkeypatch, order):
    """ProjectManager whose DataLad steps are fakes that record call order."""
    pm = ProjectManager()
    monkeypatch.setattr(
        pm,
        "_create_datalad_dataset",
        lambda *a, **k: {"initialized": True, "saved": False, "executable": "/x/datalad"},
    )
    monkeypatch.setattr(pm, "_create_nested_subdatasets", lambda *a, **k: {})

    def fake_save(*a, **k):
        order.append("save")
        return {"saved": True, "available": True}

    monkeypatch.setattr(pm, "_run_datalad_save", fake_save)
    return pm


def test_hooks_are_installed_after_the_creation_saves(monkeypatch, tmp_path):
    order = []
    pm = _ordered_manager(monkeypatch, order)
    monkeypatch.setattr(
        sg, "install_save_hooks", lambda root: order.append(("hooks", str(root))) or {"installed": [str(root)], "foreign": [], "errors": []}
    )
    project = tmp_path / "p"
    result = pm.create_project(str(project), {"name": "p", "use_datalad": True})
    assert result["success"], result
    assert order == ["save", ("hooks", str(project))]
    assert result["save_gate_hook"]["installed"] == [str(project)]


def test_creation_continues_when_hook_install_fails(monkeypatch, tmp_path):
    pm = _ordered_manager(monkeypatch, [])

    def boom(root):
        raise HookExistsError("foreign pre-commit")

    monkeypatch.setattr(sg, "install_save_hooks", boom)
    result = pm.create_project(str(tmp_path / "p"), {"name": "p", "use_datalad": True})
    assert result["success"], result
    assert "foreign pre-commit" in result["save_gate_hook"]["errors"][0]


def test_no_hooks_without_datalad(monkeypatch, tmp_path):
    called = []
    monkeypatch.setattr(sg, "install_save_hooks", lambda root: called.append(root))
    result = ProjectManager().create_project(str(tmp_path / "p"), {"name": "p", "use_datalad": False})
    assert result["success"], result
    assert called == []


def test_nested_dataset_gets_the_hook_after_its_creation_save(monkeypatch, tmp_path):
    order = []
    pm = _ordered_manager(monkeypatch, order)
    project = tmp_path / "p"
    sub = project / "sub-001"
    sub.mkdir(parents=True)
    monkeypatch.setattr(
        pm, "_run_datalad_create_with_lock_retry", lambda *a, **k: type("P", (), {"returncode": 0, "stdout": "", "stderr": ""})()
    )
    monkeypatch.setattr(pm, "_is_registered_nested_dataset", lambda *a, **k: True)
    monkeypatch.setattr(sg, "install_save_hook", lambda root: order.append(("hook", str(root))))
    result = pm._create_registered_nested_dataset(project, sub, "/x/datalad")
    assert result["success"], result
    assert order == ["save", ("hook", str(sub))]


def test_registered_existing_nested_dataset_gets_the_hook(monkeypatch, tmp_path):
    pm = ProjectManager()
    project = tmp_path / "p"
    sub = project / "sub-001"
    sub.mkdir(parents=True)
    monkeypatch.setattr(
        pm, "_run_datalad_create_with_lock_retry", lambda *a, **k: type("P", (), {"returncode": 0, "stdout": "", "stderr": ""})()
    )
    monkeypatch.setattr(pm, "_is_registered_nested_dataset", lambda *a, **k: True)
    seen = []
    monkeypatch.setattr(sg, "install_save_hook", lambda root: seen.append(str(root)))
    assert pm._register_existing_nested_dataset(project, sub, "/x/datalad")["success"]
    assert seen == [str(sub)]


def test_nested_creation_succeeds_when_hook_install_fails(monkeypatch, tmp_path):
    pm = _ordered_manager(monkeypatch, [])
    project = tmp_path / "p"
    sub = project / "sub-001"
    sub.mkdir(parents=True)
    monkeypatch.setattr(
        pm, "_run_datalad_create_with_lock_retry", lambda *a, **k: type("P", (), {"returncode": 0, "stdout": "", "stderr": ""})()
    )
    monkeypatch.setattr(pm, "_is_registered_nested_dataset", lambda *a, **k: True)

    def boom(root):
        raise HookExistsError("foreign")

    monkeypatch.setattr(sg, "install_save_hook", boom)
    assert pm._create_registered_nested_dataset(project, sub, "/x/datalad")["success"]


_NEEDS_DATALAD = pytest.mark.skipif(
    not (shutil.which("git") and shutil.which("git-annex") and shutil.which("datalad")),
    reason="datalad and git-annex required",
)


def _real_project(monkeypatch, tmp_path):
    monkeypatch.setenv("PRISM_TOOLS", str(Path(sg.__file__).resolve().parents[1] / "prism_tools.py"))
    project = tmp_path / "real"
    result = ProjectManager().create_project(str(project), {"name": "real", "use_datalad": True})
    assert result["success"], result
    return project, result


@_NEEDS_DATALAD
def test_real_create_flow_reports_hook_outcome_and_still_succeeds(monkeypatch, tmp_path):
    project, result = _real_project(monkeypatch, tmp_path)
    assert (project / "derivatives" / ".git").exists()
    assert result["save_gate_hook"]["errors"] == []


@_NEEDS_DATALAD
@pytest.mark.xfail(
    strict=True,
    reason="git-annex writes its own pre-commit hook ('git annex pre-commit .') into every "
    "DataLad dataset; install_save_hook treats it as foreign and refuses (Task 3 design gap).",
)
def test_real_create_flow_installs_hooks_in_project_and_nested_datasets(monkeypatch, tmp_path):
    project, _ = _real_project(monkeypatch, tmp_path)
    assert sg.has_save_hook(project)
    assert sg.has_save_hook(project / "derivatives")
