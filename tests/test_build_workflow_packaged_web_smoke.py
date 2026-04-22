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
    assert "--require-pandas-support" in content
    assert "--require-limesurvey-exporter" in content
    assert "--require-project-export-defacing-import" in content


def test_build_workflow_smoke_tests_bundle_imports_on_linux() -> None:
    content = BUILD_WORKFLOW.read_text(encoding="utf-8")

    assert "Smoke test bundled imports (Linux)" in content
    assert "if: runner.os == 'Linux'" in content
    assert (
        "python scripts/ci/smoke_bundle_imports.py --bundle-root dist/PrismStudio/_internal"
        in content
    )


def test_packaged_web_smoke_can_require_pyreadstat_write_support() -> None:
    content = PACKAGED_WEB_SMOKE.read_text(encoding="utf-8")

    assert "--require-pyreadstat-write-support" in content
    assert "/api/runtime-capabilities" in content
    assert "pyreadstat_write_support" in content


def test_packaged_web_smoke_can_require_pandas_support() -> None:
    content = PACKAGED_WEB_SMOKE.read_text(encoding="utf-8")

    assert "--require-pandas-support" in content
    assert "pandas_dataframe_support" in content


def test_packaged_web_smoke_can_require_limesurvey_exporter() -> None:
    content = PACKAGED_WEB_SMOKE.read_text(encoding="utf-8")

    assert "--require-limesurvey-exporter" in content
    assert "/api/survey-customizer/export" in content
    assert "exporter not available" in content


def test_packaged_web_smoke_can_require_project_export_defacing_import() -> None:
    content = PACKAGED_WEB_SMOKE.read_text(encoding="utf-8")

    assert "--require-project-export-defacing-import" in content
    assert "/api/projects/export/defacing-report" in content
