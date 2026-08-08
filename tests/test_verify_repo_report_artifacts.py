import importlib.util
from types import SimpleNamespace
from pathlib import Path


def _load_verify_repo_module():
    module_path = Path(__file__).with_name("verify_repo.py")
    spec = importlib.util.spec_from_file_location("verify_repo", module_path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_report_artifact_check_rejects_tracked_reports_directory(
    tmp_path: Path, monkeypatch, capsys
) -> None:
    verify_repo = _load_verify_repo_module()
    (tmp_path / ".git").mkdir()

    def fake_run_command(command, cwd=None, **_kwargs):
        assert command == 'git ls-files -- "*_report_*.txt" "reports/**"'
        assert cwd == str(tmp_path)
        return SimpleNamespace(
            returncode=0,
            stdout="reports/session_assignment_audit.csv\n",
        )

    monkeypatch.setattr(verify_repo, "run_command", fake_run_command)

    verify_repo.check_report_artifacts(str(tmp_path))

    output = capsys.readouterr().out
    assert "reports/ files are tracked" in output
    assert "reports/session_assignment_audit.csv" in output