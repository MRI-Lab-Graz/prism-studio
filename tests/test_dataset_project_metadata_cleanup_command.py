from __future__ import annotations

import json
import sys
from argparse import Namespace
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
APP_PATH = PROJECT_ROOT / "app"
if str(APP_PATH) not in sys.path:
    sys.path.insert(0, str(APP_PATH))

from src.cli.commands.dataset import cmd_dataset_cleanup_project_metadata


def test_cleanup_project_metadata_command_can_drop_task_definitions(
    tmp_path: Path, capsys
) -> None:
    project_root = tmp_path / "study"
    project_root.mkdir()
    project_json_path = project_root / "project.json"
    project_json_path.write_text(
        json.dumps(
            {
                "name": "demo",
                "Sessions": [{"id": "ses-1", "tasks": [{"task": "ads"}]}],
                "TaskDefinitions": {"ads": {"modality": "survey"}},
                "Basics": {"Name": "demo"},
            }
        ),
        encoding="utf-8",
    )

    args = Namespace(
        project=str(project_json_path),
        dry_run=False,
        drop_task_definitions=True,
        json=True,
    )

    cmd_dataset_cleanup_project_metadata(args)

    payload = json.loads(project_json_path.read_text(encoding="utf-8"))
    output = json.loads(capsys.readouterr().out)
    assert output["success"] is True
    assert output["removed_sessions"] == 1
    assert output["removed_task_definitions"] == 1
    assert "Sessions" not in payload
    assert "TaskDefinitions" not in payload
    assert payload["Basics"] == {"Name": "demo"}