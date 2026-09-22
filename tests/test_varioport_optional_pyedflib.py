"""pyedflib is optional: everything but EDF writing must work without it."""

import importlib
import sys
from pathlib import Path
from unittest.mock import patch

project_root = Path(__file__).resolve().parents[1]
app_path = project_root / "app"
if str(app_path) not in sys.path:
    sys.path.insert(0, str(app_path))


def test_module_imports_without_pyedflib():
    """A missing pyedflib must not break importing the module (nor the CLI,
    which imports it eagerly via src.cli.commands.convert)."""
    with patch.dict(sys.modules, {"pyedflib": None}):
        module = importlib.reload(
            importlib.import_module("helpers.physio.convert_varioport")
        )
        assert module.read_varioport_header is not None
