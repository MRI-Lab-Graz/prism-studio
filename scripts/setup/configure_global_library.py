#!/usr/bin/env python3
"""Point the app-level global library at the repo's official/ folder.

Individual projects can still override it via templateLibraryPath in
.prismrc.json. Check the result with scripts/setup/verify_global_library.py.
"""

import sys
from pathlib import Path

app_root = Path(__file__).resolve().parent.parent.parent / "app"
sys.path.insert(0, str(app_root))

from src.config import AppSettings, save_app_settings  # noqa: E402

official_root = app_root.parent / "official"
if not official_root.exists():
    sys.exit(f"Error: official folder not found at: {official_root}")

settings_path = save_app_settings(
    AppSettings(
        global_library_root=str(official_root),
        default_modalities=["survey", "biometrics"],
    ),
    app_root=str(app_root),
)
print(f"Global library root: {official_root}\nSettings saved to:   {settings_path}")
