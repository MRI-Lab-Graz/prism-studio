"""The validator CLI (`prism.py`) does not carry Studio commands.

`file-management` and `wide-to-long` live in prism_tools; prism.py only points
there instead of importing the Studio CLI tree (the PyPI validator has none).
"""

from __future__ import annotations

import importlib.util
import os
import sys
from pathlib import Path

import pytest

APP_ROOT = Path(__file__).resolve().parents[1] / "app"

os.environ.setdefault("PRISM_SKIP_VENV_CHECK", "1")


def _load_prism_module():
    spec = importlib.util.spec_from_file_location(
        "prism_cli_pointer_under_test", APP_ROOT / "prism.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


prism = _load_prism_module()


@pytest.mark.parametrize("command", ["file-management", "wide-to-long"])
def test_studio_command_points_to_prism_tools(monkeypatch, capsys, command):
    monkeypatch.setattr(sys, "argv", ["prism.py", command, "--project", "/x"])

    with pytest.raises(SystemExit) as exc:
        prism.main()

    assert exc.value.code == 2
    out = capsys.readouterr().out
    assert "not part of the validator" in out
    assert f"prism_tools.py {command}" in out
