"""Regression test for scripts/build/build_app.py::_build_pyinstaller_args.

cmath is a compiled stdlib extension pandas/numpy need at runtime. It used to
be discovered incidentally via static analysis of the pandas.tests suite
pulled in by --collect-submodules=pandas; excluding pandas.tests (see
hook-pandas.py) silently dropped cmath from Linux/macOS builds (Windows is
unaffected since cmath is built into python3.dll there), breaking every
Flask blueprint that imports it transitively. Assert it stays explicit.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts" / "build"))

from build_app import _build_pyinstaller_args  # noqa: E402 (PyInstaller import is now lazy, so this doesn't require it installed)


def test_cmath_is_an_explicit_hidden_import():
    args = _build_pyinstaller_args("PrismStudio", Path("/fake/scripts/build"))
    assert "--hidden-import=cmath" in args


def test_name_is_applied():
    args = _build_pyinstaller_args("PrismStudio", Path("/fake/scripts/build"))
    assert "--name=PrismStudio" in args
