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


def test_cleanup_project_metadata_command_supports_recursive_folder_cleanup(
    tmp_path: Path, capsys
) -> None:
    first_root = tmp_path / "legacy-a"
    second_root = tmp_path / "legacy-b" / "rawdata"
    first_root.mkdir(parents=True)
    second_root.mkdir(parents=True)
    (first_root / "project.json").write_text(
        json.dumps(
            {
                "Sessions": [{"id": "ses-1", "tasks": [{"task": "ads"}]}],
                "TaskDefinitions": {"ads": {"modality": "survey"}},
            }
        ),
        encoding="utf-8",
    )
    (second_root / "project.json").write_text(
        json.dumps(
            {
                "Sessions": [{"id": "ses-2", "tasks": [{"task": "stai"}]}],
                "TaskDefinitions": {"stai": {"modality": "survey"}},
            }
        ),
        encoding="utf-8",
    )

    args = Namespace(
        project=str(tmp_path),
        dry_run=False,
        drop_task_definitions=True,
        recursive=True,
        json=True,
    )

    cmd_dataset_cleanup_project_metadata(args)

    first_payload = json.loads((first_root / "project.json").read_text(encoding="utf-8"))
    second_payload = json.loads((second_root / "project.json").read_text(encoding="utf-8"))
    output = json.loads(capsys.readouterr().out)
    assert output["success"] is True
    assert output["recursive"] is True
    assert output["processed_projects"] == 2
    assert output["changed_projects"] == 2
    assert output["removed_task_definitions"] == 2
    assert "Sessions" not in first_payload
    assert "TaskDefinitions" not in first_payload
    assert "Sessions" not in second_payload
    assert "TaskDefinitions" not in second_payload