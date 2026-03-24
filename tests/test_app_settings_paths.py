from __future__ import annotations

import importlib.util
import json
from pathlib import Path

CONFIG_FILE = Path(__file__).resolve().parents[1] / "app" / "src" / "config.py"


def _load_module_from_path(module_name: str, file_path: Path):
    spec = importlib.util.spec_from_file_location(module_name, str(file_path))
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_app_settings_loads_bundle_default_then_saves_to_user_dir(
    tmp_path: Path, monkeypatch
):
    config = _load_module_from_path("config_for_settings_paths", CONFIG_FILE)

    bundled_root = tmp_path / "bundle"
    bundled_root.mkdir(parents=True)
    bundled_settings = bundled_root / config.APP_SETTINGS_FILENAME
    bundled_settings.write_text(
        json.dumps({"globalLibraryRoot": "/bundled/library"}),
        encoding="utf-8",
    )

    user_settings_dir = tmp_path / "user-settings"
    monkeypatch.setattr(
        config,
        "_get_user_app_settings_dir",
        lambda: user_settings_dir,
    )

    loaded_default = config.load_app_settings(app_root=str(bundled_root))
    assert loaded_default.global_library_root == "/bundled/library"
    assert loaded_default.show_dedicated_terminal is True

    saved_path = Path(
        config.save_app_settings(
            config.AppSettings(global_library_root="/user/library"),
            app_root=str(bundled_root),
        )
    )
    assert saved_path == user_settings_dir / config.APP_SETTINGS_FILENAME

    saved_data = json.loads(saved_path.read_text(encoding="utf-8"))
    assert saved_data["showDedicatedTerminal"] is True

    reloaded = config.load_app_settings(app_root=str(bundled_root))
    assert reloaded.global_library_root == "/user/library"
    assert reloaded.show_dedicated_terminal is True
