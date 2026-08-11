"""Regression test: pyedflib is declared optional (setup.py's "edf" extra,
requirements-optional.txt), but helpers.physio.convert_varioport used to
`import pyedflib` unconditionally at module scope. That module sits behind
app/src/cli/commands/convert.py's top-level import, which every prism_tools
CLI command (including ones unrelated to physio/EDF, e.g. wide-to-long)
loads via the shared entrypoint -- so a machine without pyedflib installed
had a completely broken CLI, not just broken physio conversion. The import
must now be deferred into convert_varioport() itself.
"""

import sys

import pytest


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
