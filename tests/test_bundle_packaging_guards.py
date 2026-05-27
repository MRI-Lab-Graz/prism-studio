from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
BUILD_SCRIPT = REPO_ROOT / "scripts" / "build" / "build_app.py"
BUNDLE_SMOKE = REPO_ROOT / "scripts" / "ci" / "smoke_bundle_imports.py"
PRISM_STUDIO_SPEC = REPO_ROOT / "PrismStudio.spec"
PRISM_VALIDATOR_SPEC = REPO_ROOT / "PrismValidator.spec"
CI_WORKFLOW = REPO_ROOT / ".github" / "workflows" / "ci.yml"


def test_build_script_explicitly_includes_pandas() -> None:
    content = BUILD_SCRIPT.read_text(encoding="utf-8")

    assert '"--hidden-import=pandas"' in content
    assert '"--collect-submodules=pandas"' in content
    assert '"--collect-data=pandas"' in content
    assert '"--collect-binaries=pandas"' in content


def test_build_script_explicitly_includes_pyreadstat() -> None:
    content = BUILD_SCRIPT.read_text(encoding="utf-8")

    assert '"--hidden-import=pyreadstat"' in content
    assert '"--collect-submodules=pyreadstat"' in content
    assert '"--collect-data=pyreadstat"' in content
    assert '"--collect-binaries=pyreadstat"' in content


def test_build_script_explicitly_includes_pyreadr() -> None:
    content = BUILD_SCRIPT.read_text(encoding="utf-8")

    assert '"--hidden-import=pyreadr"' in content
    assert '"--collect-submodules=pyreadr"' in content
    assert '"--collect-data=pyreadr"' in content
    assert '"--collect-binaries=pyreadr"' in content


def test_bundle_smoke_isolates_runner_site_packages() -> None:
    content = BUNDLE_SMOKE.read_text(encoding="utf-8")

    assert "site-packages" in content
    assert "dist-packages" in content
    assert "sys.path[:] = _build_isolated_sys_path(bundle_root)" in content


def test_bundle_smoke_checks_pandas_api_shape() -> None:
    content = BUNDLE_SMOKE.read_text(encoding="utf-8")

    assert "_prepare_pandas_for_plain_python_import(bundle_root)" in content
    assert "_install_pandas_smoke_stub()" in content
    assert "deferring real pandas validation to the packaged web smoke" in content
    assert "bundle_entries=" in content


def test_bundle_smoke_checks_pyreadstat_write_support() -> None:
    content = BUNDLE_SMOKE.read_text(encoding="utf-8")

    assert (
        "def _prepare_pyreadstat_for_plain_python_import(bundle_root: Path)" in content
    )
    assert "_prepare_pyreadstat_for_plain_python_import(bundle_root)" in content
    assert "_install_pyreadstat_smoke_stub()" in content
    assert "namespace-style bundle stub under plain Python" in content
    assert "deferring real pyreadstat validation to the packaged web smoke" in content
    assert "write_sav" in content


def test_bundle_smoke_checks_limesurvey_exporter_import() -> None:
    content = BUNDLE_SMOKE.read_text(encoding="utf-8")

    assert '"src.limesurvey_exporter"' in content


def test_validator_spec_includes_backend_bundle_and_optional_excludes() -> None:
    studio_content = PRISM_STUDIO_SPEC.read_text(encoding="utf-8")
    validator_content = PRISM_VALIDATOR_SPEC.read_text(encoding="utf-8")

    assert "('src', 'backend_bundle/src')" in studio_content
    assert "('src', 'backend_bundle/src')" in validator_content
    assert "excludes=[]" not in validator_content
    for excluded_pkg in (
        "'pyarrow'",
        "'nibabel'",
        "'pydicom'",
        "'authlib'",
        "'nltk'",
        "'beautifulsoup4'",
        "'bs4'",
        "'pyedflib'",
        "'sphinx'",
        "'sphinx_rtd_theme'",
        "'myst_parser'",
        "'babel'",
        "'docutils'",
        "'pygments'",
    ):
        assert excluded_pkg in studio_content
        assert excluded_pkg in validator_content


def test_ci_workflow_runs_coverage_on_python_310_and_311() -> None:
    content = CI_WORKFLOW.read_text(encoding="utf-8")

    assert 'name: Coverage Report (Python ${{ matrix.python-version }})' in content
    assert 'python-version: ["3.10", "3.11"]' in content
    assert 'python-version: ${{ matrix.python-version }}' in content
    assert "if: matrix.python-version == '3.10'" in content
