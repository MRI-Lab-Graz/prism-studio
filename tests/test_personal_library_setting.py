"""The optional personal library: a folder of the user's own, laid out like a project's code/library."""

import json

from src import config


def _paths(tmp_path, folder):
    settings = config.AppSettings(personal_library_path=str(folder))
    return config.get_effective_library_paths(app_root=str(tmp_path), app_settings=settings)


def test_personal_library_is_unset_by_default(tmp_path):
    paths = config.get_effective_library_paths(app_root=str(tmp_path), app_settings=config.AppSettings())
    assert paths["personal_library_path"] is None


def test_personal_library_is_the_folder_with_the_modality_folders(tmp_path):
    mine = tmp_path / "mine"
    (mine / "survey").mkdir(parents=True)
    assert _paths(tmp_path, mine)["personal_library_path"] == str(mine)


def test_an_official_style_folder_is_read_through_its_library_subfolder(tmp_path):
    mine = tmp_path / "mine"
    (mine / "library" / "survey").mkdir(parents=True)
    assert _paths(tmp_path, mine)["personal_library_path"] == str(mine / "library")


def test_personal_library_path_is_saved_and_loaded(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "_get_user_app_settings_dir", lambda: tmp_path / "settings")
    saved = config.save_app_settings(config.AppSettings(personal_library_path="/me/lib"), app_root=str(tmp_path))
    assert json.loads(open(saved, encoding="utf-8").read())["personalLibraryPath"] == "/me/lib"
    assert config.load_app_settings(app_root=str(tmp_path)).personal_library_path == "/me/lib"
