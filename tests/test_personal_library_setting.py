"""The optional personal library: a folder of the user's own, laid out like the global one."""

import json

from src import config


def test_personal_library_is_unset_by_default(tmp_path):
    paths = config.get_effective_library_paths(app_root=str(tmp_path), app_settings=config.AppSettings())
    assert paths["personal_library_path"] is None


def test_personal_library_root_has_library_and_recipe_folders(tmp_path):
    mine = tmp_path / "mine"
    settings = config.AppSettings(personal_library_root=str(mine))
    paths = config.get_effective_library_paths(app_root=str(tmp_path), app_settings=settings)
    assert paths["personal_library_root"] == str(mine)
    assert paths["personal_library_path"] == str(mine / "library")
    assert paths["personal_recipe_path"] == str(mine / "recipe")


def test_personal_root_may_name_the_library_folder_itself(tmp_path):
    settings = config.AppSettings(personal_library_root=str(tmp_path / "mine" / "library"))
    paths = config.get_effective_library_paths(app_root=str(tmp_path), app_settings=settings)
    assert paths["personal_library_root"] == str(tmp_path / "mine")
    assert paths["personal_library_path"] == str(tmp_path / "mine" / "library")


def test_personal_library_root_is_saved_and_loaded(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "_get_user_app_settings_dir", lambda: tmp_path / "settings")
    saved = config.save_app_settings(config.AppSettings(personal_library_root="/me/lib"), app_root=str(tmp_path))
    assert json.loads(open(saved, encoding="utf-8").read())["personalLibraryRoot"] == "/me/lib"
    assert config.load_app_settings(app_root=str(tmp_path)).personal_library_root == "/me/lib"
