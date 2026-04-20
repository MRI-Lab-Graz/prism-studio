from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
BUILD_WORKFLOW = REPO_ROOT / ".github" / "workflows" / "build.yml"
PACKAGED_WEB_SMOKE = REPO_ROOT / "scripts" / "ci" / "smoke_packaged_web_app.py"


def test_build_workflow_smoke_tests_packaged_web_app() -> None:
    content = BUILD_WORKFLOW.read_text(encoding="utf-8")

    assert "bundle_executable:" in content
    assert "Smoke test packaged web app" in content
    assert "scripts/ci/smoke_packaged_web_app.py" in content
    assert "--app-path ${{ matrix.bundle_executable }}" in content
    assert "--probe-path /converter" in content
    assert "--require-pyreadstat-write-support" in content


def test_packaged_web_smoke_can_require_pyreadstat_write_support() -> None:
    content = PACKAGED_WEB_SMOKE.read_text(encoding="utf-8")

    assert "--require-pyreadstat-write-support" in content
    assert "/api/runtime-capabilities" in content
    assert "pyreadstat_write_support" in content
