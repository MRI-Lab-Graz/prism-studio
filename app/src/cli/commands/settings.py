"""``prism_tools.py settings show|set``: Studio's Settings page as commands."""

from __future__ import annotations

import json
import sys
from pathlib import Path

from src.config import load_app_settings
from src.settings_update import SETTINGS, SettingsError, settings_as_dict, update_app_settings

_APP_ROOT = Path(__file__).resolve().parents[3]


def cmd_settings_show(args) -> None:
    values = settings_as_dict(load_app_settings(app_root=str(_APP_ROOT)))
    if getattr(args, "json", False):
        print(json.dumps(values, indent=2, ensure_ascii=False))
        return
    for name, value in values.items():
        print(f"{name}: {value if value not in (None, []) else '(default)'}")


def cmd_settings_set(args) -> None:
    changes = {name: getattr(args, name) for name in SETTINGS if getattr(args, name, None) is not None}
    if not changes:
        print("Error: nothing to set. Give at least one setting, e.g. --personal-library-path /path (see --help).")
        sys.exit(2)
    try:
        update_app_settings(_APP_ROOT, changes)
    except SettingsError as exc:
        print(f"Error: {exc}")
        sys.exit(1)
    print(f"✅ Saved: {', '.join(changes)}")
