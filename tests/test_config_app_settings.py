from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from types import SimpleNamespace

# Ensure app/src is importable as `src.*` for direct module tests.
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(current_dir)
app_path = os.path.join(project_root, "app")
if app_path not in sys.path:
    sys.path.insert(0, app_path)

from src.config import (  # noqa: E402
    AppSettings,
    PrismConfig,
    find_config_file,
    get_effective_library_paths,
    get_effective_template_library_path,
    load_app_settings,
    load_config,
    merge_cli_args,
    save_app_settings,
    save_config,
)


def test_prism_config_should_ignore_patterns():
    config = PrismConfig(ignore_paths=["derivatives/**", "*.tmp"])

    assert config.should_ignore("derivatives/sub-01/file.nii.gz") is True
    assert config.should_ignore("./derivatives/sub-01/file.nii.gz") is True
    assert config.should_ignore("notes.tmp") is True
    assert config.should_ignore("rawdata/sub-01/file.nii.gz") is False


def test_find_config_file_prefers_hidden_then_visible(tmp_path):
    dataset = tmp_path / "dataset"
    dataset.mkdir(parents=True)

    visible = dataset / "prism.config.json"
    hidden = dataset / ".prismrc.json"

    visible.write_text("{}", encoding="utf-8")
    assert find_config_file(str(dataset)) == str(visible)

    hidden.write_text("{}", encoding="utf-8")
    assert find_config_file(str(dataset)) == str(hidden)


def test_load_config_invalid_json_returns_defaults(tmp_path):
    dataset = tmp_path / "dataset"
    dataset.mkdir(parents=True)
    (dataset / ".prismrc.json").write_text("{invalid", encoding="utf-8")

    config = load_config(str(dataset))

    assert config.schema_version == "stable"
    assert config.run_bids is False
    assert config.template_library_path is None


def test_save_and_load_config_roundtrip(tmp_path):
    dataset = tmp_path / "dataset"
    dataset.mkdir(parents=True)

    original = PrismConfig(
        schema_version="v0.1",
        ignore_paths=["derivatives/**"],
        strict_mode=True,
        run_bids=True,
        show_bids_warnings=True,
        custom_modalities={"beh": "beh$"},
        default_output_format="json",
        max_file_size_mb=5,
        parallel_validation=True,
        template_library_path=str(tmp_path / "shared" / "templates"),
        neurobagel_participant_filter={"minRepeatedPrefixCount": 3},
        project_preferences={"projects": {"layout": "compact"}},
    )

    saved_path = save_config(original, str(dataset), filename=".prismrc.json")
    assert Path(saved_path).exists()

    loaded = load_config(str(dataset))
    assert loaded.schema_version == "v0.1"
    assert loaded.ignore_paths == ["derivatives/**"]
    assert loaded.strict_mode is True
    assert loaded.run_bids is True
    assert loaded.show_bids_warnings is True
    assert loaded.custom_modalities == {"beh": "beh$"}
    assert loaded.default_output_format == "json"
    assert loaded.max_file_size_mb == 5
    assert loaded.parallel_validation is True
    assert loaded.template_library_path == str(tmp_path / "shared" / "templates")
    assert loaded.neurobagel_participant_filter == {"minRepeatedPrefixCount": 3}
    assert loaded.project_preferences == {"projects": {"layout": "compact"}}


def test_merge_cli_args_overrides_loaded_config():
    config = PrismConfig(schema_version="stable", run_bids=False, show_bids_warnings=False)
    args = SimpleNamespace(
        schema_version="v0.2",
        bids=True,
        bids_warnings=True,
        json=True,
        json_pretty=False,
    )

    merged = merge_cli_args(config, args)

    assert merged.schema_version == "v0.2"
    assert merged.run_bids is True
    assert merged.show_bids_warnings is True
    assert merged.default_output_format == "json"


def test_load_app_settings_defaults_when_missing(tmp_path, monkeypatch):
    from src import config as config_module

    monkeypatch.setattr(config_module, "_get_user_app_settings_dir", lambda: tmp_path)

    settings = load_app_settings(app_root=str(tmp_path))

    assert settings.backend_monitoring is True
    assert settings.backend_monitoring_verbose is False
    assert settings.show_dedicated_terminal is False
    assert settings.connected_to_server is False


def test_save_and_load_app_settings_roundtrip(tmp_path, monkeypatch):
    from src import config as config_module

    monkeypatch.setattr(config_module, "_get_user_app_settings_dir", lambda: tmp_path)

    settings = AppSettings(
        global_library_root=str(tmp_path / "official"),
        global_template_library_path=str(tmp_path / "official" / "library"),
        global_recipes_path=str(tmp_path / "official" / "recipe"),
        default_modalities=["survey"],
        last_project_path=str(tmp_path / "project"),
        last_project_name="project",
        backend_monitoring=False,
        backend_monitoring_verbose=True,
        show_dedicated_terminal=True,
        connected_to_server=True,
    )

    saved_path = save_app_settings(settings, app_root=str(tmp_path))
    assert Path(saved_path).exists()

    loaded = load_app_settings(app_root=str(tmp_path))
    assert loaded.global_library_root == str(tmp_path / "official")
    assert loaded.default_modalities == ["survey"]
    assert loaded.last_project_name == "project"
    assert loaded.backend_monitoring is False
    assert loaded.backend_monitoring_verbose is True
    assert loaded.show_dedicated_terminal is True
    assert loaded.connected_to_server is True


def test_get_effective_library_paths_from_configured_root(tmp_path):
    official_root = tmp_path / "official"
    (official_root / "library").mkdir(parents=True)
    (official_root / "recipe").mkdir(parents=True)

    settings = AppSettings(global_library_root=str(official_root))
    paths = get_effective_library_paths(app_root=str(tmp_path), app_settings=settings)

    assert paths["source"] == "configured"
    assert paths["global_library_root"] == str(official_root)
    assert paths["global_library_path"] == str(official_root / "library")
    assert paths["global_recipe_path"] == str(official_root / "recipe")


def test_get_effective_library_paths_from_legacy_paths(tmp_path):
    library_path = tmp_path / "legacy-library"
    recipe_path = tmp_path / "legacy-recipe"

    settings = AppSettings(
        global_template_library_path=str(library_path),
        global_recipes_path=str(recipe_path),
    )
    paths = get_effective_library_paths(app_root=str(tmp_path), app_settings=settings)

    assert paths["source"] == "configured-legacy"
    assert paths["global_library_path"] == str(library_path)
    assert paths["global_recipe_path"] == str(recipe_path)


def test_get_effective_library_paths_defaults_to_official_folder(tmp_path):
    official_root = tmp_path / "official"
    (official_root / "library").mkdir(parents=True)
    (official_root / "recipe").mkdir(parents=True)

    paths = get_effective_library_paths(
        app_root=str(tmp_path),
        app_settings=AppSettings(),
    )

    assert paths["source"] == "default"
    assert paths["global_library_root"] == str(official_root)


def test_get_effective_template_library_path_prefers_project_override(tmp_path):
    project = tmp_path / "project"
    (project / "code" / "library").mkdir(parents=True)

    # Provide project-level external template library override.
    project_config = {
        "templateLibraryPath": str(tmp_path / "external" / "templates"),
    }
    (project / ".prismrc.json").write_text(json.dumps(project_config), encoding="utf-8")

    settings = AppSettings(global_library_root=str(tmp_path / "official"))
    paths = get_effective_template_library_path(
        project_path=str(project),
        app_settings=settings,
        app_root=str(tmp_path),
    )

    assert paths["project_library_path"] == str(project / "code" / "library")
    assert paths["effective_external_path"] == str(tmp_path / "external" / "templates")
    assert paths["source"] == "project"


def test_get_effective_template_library_path_uses_global_when_no_override(tmp_path):
    project = tmp_path / "project"
    project.mkdir(parents=True)

    official_root = tmp_path / "official"
    (official_root / "library").mkdir(parents=True)
    (official_root / "recipe").mkdir(parents=True)

    settings = AppSettings(global_library_root=str(official_root))
    paths = get_effective_template_library_path(
        project_path=str(project),
        app_settings=settings,
        app_root=str(tmp_path),
    )

    assert paths["effective_external_path"] == str(official_root / "library")
    assert paths["source"] == "configured"
