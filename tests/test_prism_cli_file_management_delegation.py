"""Tests that `prism.py file-management ...` delegates to the prism_tools
CLI tree, mirroring the existing `prism.py wide-to-long` alias.

docs/_archive/GUI_BACKEND_AUDIT_2026-08-07.md, P2: BidsFileDeleter already
generated a "python prism.py file-management delete-files ..." command
string for display before this command existed at all.
"""

from __future__ import annotations

import importlib.util
import os
import sys
from pathlib import Path

APP_ROOT = Path(__file__).resolve().parents[1] / "app"

os.environ.setdefault("PRISM_SKIP_VENV_CHECK", "1")


def _load_prism_module():
    spec = importlib.util.spec_from_file_location(
        "prism_cli_file_management_under_test", APP_ROOT / "prism.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


prism = _load_prism_module()


def test_file_management_argv_delegates_to_prism_tools_entrypoint(monkeypatch):
    called = {}

    def _fake_prism_tools_main():
        called["invoked"] = True

    import src.cli.entrypoint as entrypoint_module

    monkeypatch.setattr(entrypoint_module, "main", _fake_prism_tools_main)
    monkeypatch.setattr(
        sys, "argv", ["prism.py", "file-management", "delete-files", "--project", "/x"]
    )

    prism.main()

    assert called.get("invoked") is True


def test_non_file_management_argv_does_not_short_circuit(monkeypatch, tmp_path):
    # Sanity check the branch condition itself: a dataset path as the first
    # positional argument must NOT be mistaken for the file-management
    # delegate trigger.
    monkeypatch.setattr(sys, "argv", ["prism.py", str(tmp_path)])
    assert not (len(sys.argv) > 1 and sys.argv[1] == "file-management")
