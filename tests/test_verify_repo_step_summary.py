import importlib.util
from pathlib import Path


def _load_verify_repo_module():
    module_path = Path(__file__).with_name("verify_repo.py")
    spec = importlib.util.spec_from_file_location("verify_repo", module_path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_step_summary_lists_failed_checks(tmp_path: Path, monkeypatch) -> None:
    verify_repo = _load_verify_repo_module()
    summary = tmp_path / "summary.md"
    monkeypatch.setenv("GITHUB_STEP_SUMMARY", str(summary))

    verify_repo.write_step_summary(["dependencies", "unsafe-patterns"])

    text = summary.read_text(encoding="utf-8")
    assert "dependencies" in text and "unsafe-patterns" in text


def test_step_summary_is_noop_outside_github(monkeypatch) -> None:
    verify_repo = _load_verify_repo_module()
    monkeypatch.delenv("GITHUB_STEP_SUMMARY", raising=False)

    verify_repo.write_step_summary(["dependencies"])  # must not raise


def test_step_summary_silent_when_nothing_failed(tmp_path: Path, monkeypatch) -> None:
    verify_repo = _load_verify_repo_module()
    summary = tmp_path / "summary.md"
    monkeypatch.setenv("GITHUB_STEP_SUMMARY", str(summary))

    verify_repo.write_step_summary([])

    assert not summary.exists()
