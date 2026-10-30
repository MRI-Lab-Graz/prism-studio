"""Changing Studio's settings: one function for ``prism_tools.py settings set`` and the Settings page's routes."""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any

from src.config import (
    AppSettings,
    library_folder_error,
    load_app_settings,
    normalize_export_defacing_confirmation_mode,
    recipes_folder_error,
    save_app_settings,
)


class SettingsError(ValueError):
    """A setting was refused; the message says why."""


@dataclass(frozen=True)
class Setting:
    kind: str  # library_folder | recipes_folder | folder | list | choice | bool
    help: str


# AppSettings field -> what it is. The command's flags and the page's routes both come from here.
SETTINGS: dict[str, Setting] = {
    "global_template_library_path": Setting("library_folder", "Global survey template library: a folder with a survey/ subfolder ('' for the default)"),
    "global_recipes_path": Setting("recipes_folder", "Global recipe library folder ('' for the default)"),
    "personal_library_path": Setting("folder", "Your personal template library, used by every project ('' to turn it off)"),
    "default_modalities": Setting("list", "Modalities a new project starts with, comma separated (e.g. survey,biometrics)"),
    "export_defacing_confirmation_mode": Setting("choice", "When the defacing export asks for confirmation: risk or always"),
    "backend_monitoring": Setting("bool", "Show backend actions in the terminal: on or off"),
    "backend_monitoring_verbose": Setting("bool", "Show them in detail: on or off"),
    "show_dedicated_terminal": Setting("bool", "Open Studio's own terminal window at start: on or off"),
    "enable_study_application_import": Setting("bool", "Show the MRI-Lab Graz study application import: on or off"),
}


def _truthy(value: Any) -> bool:
    return value if isinstance(value, bool) else str(value).strip().lower() in {"1", "true", "yes", "on"}


def _checked(name: str, value: Any) -> Any:
    kind = SETTINGS[name].kind
    if kind == "bool":
        return _truthy(value)
    if kind == "list":
        items = value.split(",") if isinstance(value, str) else list(value or [])
        return [str(item).strip() for item in items if str(item).strip()]
    if kind == "choice":
        if str(value or "").strip().lower() not in {"risk", "always"}:
            raise SettingsError(f"Invalid {name}. Use 'risk' or 'always'.")
        return normalize_export_defacing_confirmation_mode(value)
    path = str(value or "").strip()
    if not path:
        return None  # cleared: back to the default
    if not (os.path.isdir(path) if kind == "folder" else os.path.exists(path)):
        raise SettingsError(f"Path does not exist: {path}")
    problem = {"library_folder": library_folder_error, "recipes_folder": recipes_folder_error}.get(kind, lambda _p: None)(path)
    if problem:
        raise SettingsError(problem)
    return path


def update_app_settings(app_root, changes: dict[str, Any]) -> AppSettings:
    """Validate ``changes`` (AppSettings field -> value) as a whole, then apply and save them."""
    unknown = sorted(set(changes) - set(SETTINGS))
    if unknown:
        raise SettingsError(f"Unknown setting: {', '.join(unknown)}")
    checked = {name: _checked(name, value) for name, value in changes.items()}
    settings = load_app_settings(app_root=str(app_root))
    for name, value in checked.items():
        setattr(settings, name, value)
    save_app_settings(settings, str(app_root))
    return settings


def settings_as_dict(settings: AppSettings) -> dict[str, Any]:
    return {name: getattr(settings, name) for name in SETTINGS}
