"""Tests for the CLI validate-flow helpers extracted from app/prism.py's main().

docs/_archive/GUI_BACKEND_AUDIT_2026-08-07.md found two behavioral gaps
between the Studio GUI's Validate Dataset page and the CLI's bare
`prism <dataset>` validate:

- P1-5: the GUI auto-applies a previously-saved participants_mapping.json
  before validating; the CLI didn't.
- P1-6: the GUI resolves a default template library (project library ->
  project code/library -> global library) when none is specified; the CLI
  left library_path=None, which falls back to a much narrower search
  inside the validator.

apply_participants_mapping_before_validation and
resolve_effective_library_path close both gaps. Per this repo's convention
of extracting testable functions out of app/prism.py's monolithic main()
rather than growing it in place, these are tested directly here instead of
via a full CLI subprocess run.
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
        "prism_cli_under_test", APP_ROOT / "prism.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


prism = _load_prism_module()


class TestResolveEffectiveLibraryPath:
    def test_explicit_library_path_passes_through_unchanged(self, tmp_path):
        result = prism.resolve_effective_library_path(
            "/some/explicit/library", str(tmp_path), machine_output=False
        )
        assert result == "/some/explicit/library"

    def test_falls_back_to_default_when_omitted(self, tmp_path, monkeypatch):
        monkeypatch.setattr(
            prism,
            "default_validation_library_path",
            lambda app_root, project_path=None: "/resolved/default/library",
        )
        result = prism.resolve_effective_library_path(
            None, str(tmp_path), machine_output=False
        )
        assert result == "/resolved/default/library"

    def test_falls_back_to_default_when_empty_string(self, tmp_path, monkeypatch):
        monkeypatch.setattr(
            prism,
            "default_validation_library_path",
            lambda app_root, project_path=None: "/resolved/default/library",
        )
        result = prism.resolve_effective_library_path(
            "", str(tmp_path), machine_output=False
        )
        assert result == "/resolved/default/library"

    def test_passes_dataset_path_and_app_root_through(self, tmp_path, monkeypatch):
        captured = {}

        def _fake_default(app_root, project_path=None):
            captured["app_root"] = app_root
            captured["project_path"] = project_path
            return "/resolved"

        monkeypatch.setattr(prism, "default_validation_library_path", _fake_default)
        prism.resolve_effective_library_path(
            None, str(tmp_path), machine_output=False
        )
        assert captured["project_path"] == str(tmp_path)
        assert captured["app_root"] == str(APP_ROOT)

    def test_prints_resolved_library_unless_machine_output(
        self, tmp_path, capsys, monkeypatch
    ):
        monkeypatch.setattr(
            prism,
            "default_validation_library_path",
            lambda app_root, project_path=None: "/resolved/default/library",
        )
        prism.resolve_effective_library_path(
            None, str(tmp_path), machine_output=False
        )
        assert "/resolved/default/library" in capsys.readouterr().out

        prism.resolve_effective_library_path(
            None, str(tmp_path), machine_output=True
        )
        assert capsys.readouterr().out == ""
