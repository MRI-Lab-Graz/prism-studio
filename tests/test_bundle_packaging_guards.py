from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
BUILD_SCRIPT = REPO_ROOT / "scripts" / "build" / "build_app.py"
BUNDLE_SMOKE = REPO_ROOT / "scripts" / "ci" / "smoke_bundle_imports.py"


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
