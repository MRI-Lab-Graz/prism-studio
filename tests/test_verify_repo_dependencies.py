import importlib.util
from pathlib import Path
from types import SimpleNamespace


def _load_verify_repo_module():
    module_path = Path(__file__).with_name("verify_repo.py")
    spec = importlib.util.spec_from_file_location("verify_repo", module_path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_check_dependencies_uses_lockfile_only_npm_audit(
    tmp_path: Path, monkeypatch
) -> None:
    verify_repo = _load_verify_repo_module()

    (tmp_path / "requirements.txt").write_text("", encoding="utf-8")
    (tmp_path / "package.json").write_text("{}\n", encoding="utf-8")

    commands = []

    def fake_check_tool(tool_name, _install_hint):
        return tool_name == "npm"

    def fake_run_command(command, cwd=None):
        commands.append((command, cwd))
        return SimpleNamespace(returncode=0, stdout="")

    monkeypatch.setattr(verify_repo, "check_tool", fake_check_tool)
    monkeypatch.setattr(verify_repo, "run_command", fake_run_command)

    verify_repo.check_dependencies(str(tmp_path))

    assert (f'"{verify_repo.sys.executable}" -m pip check', str(tmp_path)) in commands
    assert ("npm audit --package-lock-only", str(tmp_path)) in commands


def test_check_dependencies_fix_uses_lockfile_only_npm_audit(
    tmp_path: Path, monkeypatch
) -> None:
    verify_repo = _load_verify_repo_module()

    (tmp_path / "package.json").write_text("{}\n", encoding="utf-8")

    commands = []

    def fake_check_tool(tool_name, _install_hint):
        return tool_name == "npm"

    def fake_run_command(command, cwd=None):
        commands.append((command, cwd))
        return SimpleNamespace(returncode=0, stdout="")

    monkeypatch.setattr(verify_repo, "check_tool", fake_check_tool)
    monkeypatch.setattr(verify_repo, "run_command", fake_run_command)

    verify_repo.check_dependencies(str(tmp_path), fix=True)

    assert ("npm audit --package-lock-only --fix", str(tmp_path)) in commands