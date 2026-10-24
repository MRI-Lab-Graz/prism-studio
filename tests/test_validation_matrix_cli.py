"""prism_tools dataset validation-matrix: builds the control project and prints what the validator caught."""

import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

APP_ROOT = Path(__file__).resolve().parents[1] / "app"
if str(APP_ROOT) not in sys.path:
    sys.path.insert(0, str(APP_ROOT))

from src.cli.commands.validation_matrix import cmd_dataset_validation_matrix  # noqa: E402
from src.validation_matrix import DEFECTS, KNOWN_GAPS  # noqa: E402


def test_json_output_lists_every_defect_and_exits_cleanly(tmp_path, capsys):
    cmd_dataset_validation_matrix(SimpleNamespace(output=str(tmp_path / "control"), json=True))

    payload = json.loads(capsys.readouterr().out)
    assert [r["id"] for r in payload["rows"]] == [d.id for d in DEFECTS]
    assert {r["id"] for r in payload["rows"] if r["status"] != "detected"} == set(KNOWN_GAPS)
    assert payload["control_problems"] == [] and payload["problems"] == []
    assert (tmp_path / "control" / "project.json").is_file()  # the clean control stays for hands-on use


def test_a_non_empty_output_folder_is_refused(tmp_path, capsys):
    (tmp_path / "x").write_text("data")
    with pytest.raises(SystemExit) as info:
        cmd_dataset_validation_matrix(SimpleNamespace(output=str(tmp_path), json=False))
    assert info.value.code == 2
