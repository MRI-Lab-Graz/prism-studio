from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
BUILD_SCRIPT = REPO_ROOT / "scripts" / "build" / "build_app.py"
BUNDLE_SMOKE = REPO_ROOT / "scripts" / "ci" / "smoke_bundle_imports.py"


def test_build_script_explicitly_includes_pandas() -> None:
    content = BUILD_SCRIPT.read_text(encoding="utf-8")

    assert '"--hidden-import=pandas"' in content


def test_bundle_smoke_isolates_runner_site_packages() -> None:
    content = BUNDLE_SMOKE.read_text(encoding="utf-8")

    assert "site-packages" in content
    assert "dist-packages" in content
    assert "sys.path[:] = _build_isolated_sys_path(bundle_root)" in content