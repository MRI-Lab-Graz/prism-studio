"""Unit tests for src.validation_library_resolution.

Extracted from app/src/web/blueprints/validation.py so the CLI's bare
`prism <dataset>` validate could resolve a default template library the
same way the Studio GUI's Validate Dataset page already did, instead of
leaving library_path=None (docs/_archive/GUI_BACKEND_AUDIT_2026-08-07.md,
P1-6).
"""

from __future__ import annotations

from src.validation_library_resolution import (
    default_global_validation_library_path,
    default_validation_library_path,
)


class TestDefaultGlobalValidationLibraryPath:
    def test_falls_back_to_app_root_survey_library_when_nothing_configured(
        self, tmp_path, monkeypatch
    ):
        import src.validation_library_resolution as mod

        monkeypatch.setattr(
            mod,
            "get_effective_library_paths",
            lambda app_root: {"global_library_path": None},
        )
        result = default_global_validation_library_path(str(tmp_path))
        assert result == str((tmp_path / "survey_library").resolve())

    def test_uses_configured_global_library_when_it_exists(self, tmp_path, monkeypatch):
        import src.validation_library_resolution as mod

        configured = tmp_path / "official_library"
        configured.mkdir()
        monkeypatch.setattr(
            mod,
            "get_effective_library_paths",
            lambda app_root: {"global_library_path": str(configured)},
        )
        result = default_global_validation_library_path(str(tmp_path))
        assert result == str(configured.resolve())

    def test_falls_back_when_configured_path_does_not_exist(
        self, tmp_path, monkeypatch
    ):
        import src.validation_library_resolution as mod

        monkeypatch.setattr(
            mod,
            "get_effective_library_paths",
            lambda app_root: {"global_library_path": str(tmp_path / "does-not-exist")},
        )
        result = default_global_validation_library_path(str(tmp_path))
        assert result == str((tmp_path / "survey_library").resolve())


class TestDefaultValidationLibraryPath:
    def test_prefers_project_library_directory(self, tmp_path, monkeypatch):
        import src.validation_library_resolution as mod

        monkeypatch.setattr(
            mod,
            "get_effective_library_paths",
            lambda app_root: {"global_library_path": None},
        )
        project = tmp_path / "project"
        (project / "library").mkdir(parents=True)

        result = default_validation_library_path(
            str(tmp_path), project_path=str(project)
        )
        assert result == str((project / "library").resolve())

    def test_falls_back_to_project_code_library(self, tmp_path, monkeypatch):
        import src.validation_library_resolution as mod

        monkeypatch.setattr(
            mod,
            "get_effective_library_paths",
            lambda app_root: {"global_library_path": None},
        )
        project = tmp_path / "project"
        (project / "code" / "library").mkdir(parents=True)

        result = default_validation_library_path(
            str(tmp_path), project_path=str(project)
        )
        assert result == str((project / "code" / "library").resolve())

    def test_falls_back_to_global_when_project_has_no_library(
        self, tmp_path, monkeypatch
    ):
        import src.validation_library_resolution as mod

        monkeypatch.setattr(
            mod,
            "get_effective_library_paths",
            lambda app_root: {"global_library_path": None},
        )
        project = tmp_path / "project"
        project.mkdir()

        result = default_validation_library_path(
            str(tmp_path), project_path=str(project)
        )
        assert result == str((tmp_path / "survey_library").resolve())

    def test_accepts_a_file_path_and_uses_its_parent_directory(
        self, tmp_path, monkeypatch
    ):
        import src.validation_library_resolution as mod

        monkeypatch.setattr(
            mod,
            "get_effective_library_paths",
            lambda app_root: {"global_library_path": None},
        )
        project = tmp_path / "project"
        (project / "library").mkdir(parents=True)
        dataset_description = project / "dataset_description.json"
        dataset_description.write_text("{}", encoding="utf-8")

        result = default_validation_library_path(
            str(tmp_path), project_path=str(dataset_description)
        )
        assert result == str((project / "library").resolve())

    def test_no_project_path_goes_straight_to_global(self, tmp_path, monkeypatch):
        import src.validation_library_resolution as mod

        monkeypatch.setattr(
            mod,
            "get_effective_library_paths",
            lambda app_root: {"global_library_path": None},
        )
        result = default_validation_library_path(str(tmp_path), project_path=None)
        assert result == str((tmp_path / "survey_library").resolve())
