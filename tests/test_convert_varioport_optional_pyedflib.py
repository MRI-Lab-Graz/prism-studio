"""Regression test: pyedflib is declared optional (setup.py's "edf" extra,
requirements-optional.txt), but helpers.physio.convert_varioport used to
`import pyedflib` unconditionally at module scope. That module sits behind
app/src/cli/commands/convert.py's top-level import, which every prism_tools
CLI command (including ones unrelated to physio/EDF, e.g. wide-to-long)
loads via the shared entrypoint -- so a machine without pyedflib installed
had a completely broken CLI, not just broken physio conversion. The import
must now be deferred into convert_varioport() itself.

Also covers the vendor/pyedflib/ fallback: on machines where pip's pyedflib
can't be installed (historically some Windows setups without a C compiler),
_import_pyedflib() must try the pre-compiled copy bundled at vendor/pyedflib/
before giving up. This is a from-source-only safety net -- both PyInstaller
.spec files deliberately exclude pyedflib from the frozen app builds, so it
intentionally does not apply there.
"""

import sys

import pytest


def test_import_pyedflib_falls_back_to_vendored_copy_when_pip_unavailable(
    monkeypatch, tmp_path
):
    """On this test machine pip's pyedflib genuinely isn't installed, so the
    first-attempt import is real. The vendor fallback itself is exercised
    against a fake package rather than the real vendor/pyedflib/ -- that
    directory's compiled extension is pinned to one platform/Python version
    (vendor/pyedflib/_extensions/_pyedflib.cp312-win_amd64.pyd) and can't
    load on arbitrary CI/dev machines, so a fake stand-in is what makes this
    test deterministic everywhere."""
    monkeypatch.delitem(sys.modules, "pyedflib", raising=False)
    monkeypatch.delitem(sys.modules, "helpers.physio.convert_varioport", raising=False)

    fake_vendor = tmp_path / "vendor"
    fake_pyedflib = fake_vendor / "pyedflib"
    fake_pyedflib.mkdir(parents=True)
    (fake_pyedflib / "__init__.py").write_text("EdfWriter = object()\n", encoding="utf-8")

    import helpers.physio.convert_varioport as module

    monkeypatch.setattr(module, "_VENDOR_DIR", fake_vendor)

    try:
        result = module._import_pyedflib()

        assert result is not None
        assert hasattr(result, "EdfWriter")
    finally:
        sys.modules.pop("pyedflib", None)
        if str(fake_vendor) in sys.path:
            sys.path.remove(str(fake_vendor))


def test_convert_varioport_module_imports_without_pyedflib(monkeypatch):
    monkeypatch.setitem(sys.modules, "pyedflib", None)
    monkeypatch.delitem(sys.modules, "helpers.physio.convert_varioport", raising=False)

    import helpers.physio.convert_varioport as module

    assert hasattr(module, "convert_varioport")


def test_convert_varioport_raises_clear_error_without_pyedflib(monkeypatch, tmp_path):
    monkeypatch.setitem(sys.modules, "pyedflib", None)
    monkeypatch.delitem(sys.modules, "helpers.physio.convert_varioport", raising=False)

    import helpers.physio.convert_varioport as module

    with pytest.raises(ImportError, match="pyedflib"):
        module.convert_varioport(
            str(tmp_path / "does-not-matter.raw"),
            str(tmp_path / "out.edf"),
            str(tmp_path / "out.json"),
        )
