"""`prism_tools.py library share-template`: same mail as the Studio share offer."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from types import SimpleNamespace

APP_ROOT = Path(__file__).resolve().parents[1] / "app"
if str(APP_ROOT) not in sys.path:
    sys.path.insert(0, str(APP_ROOT))

from src.cli.commands.library import cmd_library_share_template  # noqa: E402


def test_prints_address_subject_and_mailto(tmp_path, capsys):
    path = tmp_path / "survey-x.json"
    path.write_text(json.dumps({"Study": {"OriginalName": "X"}}), encoding="utf-8")
    cmd_library_share_template(SimpleNamespace(input=str(path)))
    out = capsys.readouterr().out
    assert "mri-lab@uni-graz.at" in out and "PRISM template share: X" in out and "mailto:" in out
