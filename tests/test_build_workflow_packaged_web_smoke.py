from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
BUILD_WORKFLOW = REPO_ROOT / ".github" / "workflows" / "build.yml"


def test_build_workflow_smoke_tests_packaged_web_app() -> None:
    content = BUILD_WORKFLOW.read_text(encoding="utf-8")

    assert "bundle_executable:" in content
    assert "Smoke test packaged web app" in content
    assert "scripts/ci/smoke_packaged_web_app.py" in content
    assert "--app-path ${{ matrix.bundle_executable }}" in content