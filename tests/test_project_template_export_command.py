from __future__ import annotations

import sys
import zipfile
from argparse import Namespace
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
APP_PATH = PROJECT_ROOT / "app"
if str(APP_PATH) not in sys.path:
    sys.path.insert(0, str(APP_PATH))

from src.cli.commands.template_export import cmd_template_export


def _snapshot_tree(root: Path) -> dict[str, bytes | None]:
    snapshot: dict[str, bytes | None] = {}
    for path in sorted(root.rglob("*")):
        rel = path.relative_to(root).as_posix()
        if path.is_dir():
            snapshot[f"{rel}/"] = None
        else:
            snapshot[rel] = path.read_bytes()
    return snapshot


def test_template_export_command_skips_subject_data_without_modifying_project(tmp_path):
    project_dir = tmp_path / "study"
    project_dir.mkdir()

    (project_dir / "dataset_description.json").write_text(
        '{"Name": "Demo"}\n', encoding="utf-8"
    )
    (project_dir / ".prismrc.json").write_text('{"schemaVersion": "stable"}\n', encoding="utf-8")
    (project_dir / "participants.tsv").write_text(
        "participant_id\tage\nsub-001\t30\n", encoding="utf-8"
    )
    (project_dir / "participants.json").write_text("{}\n", encoding="utf-8")
    (project_dir / "participants_mapping.json").write_text("{}\n", encoding="utf-8")

    sub_dir = project_dir / "sub-001" / "ses-01" / "survey"
    sub_dir.mkdir(parents=True)
    (sub_dir / "sub-001_ses-01_task-demo_survey.tsv").write_text(
        "participant_id\tvalue\nsub-001\t5\n", encoding="utf-8"
    )

    derivatives_sub = project_dir / "derivatives" / "sub-001" / "func"
    derivatives_sub.mkdir(parents=True)
    (derivatives_sub / "sub-001_task-rest_bold.nii.gz").write_bytes(b"dummy")

    (project_dir / "code").mkdir()
    (project_dir / "code" / "pipeline.py").write_text("print('ok')\n", encoding="utf-8")

    before_snapshot = _snapshot_tree(project_dir)

    output_zip = tmp_path / "study_template.zip"
    args = Namespace(project=str(project_dir), output=str(output_zip), json=True)
    cmd_template_export(args)

    assert output_zip.exists()

    after_snapshot = _snapshot_tree(project_dir)
    assert after_snapshot == before_snapshot

    with zipfile.ZipFile(output_zip, "r") as archive:
        names = set(archive.namelist())

    assert "dataset_description.json" in names
    assert ".prismrc.json" in names
    assert "code/pipeline.py" in names

    assert "participants.tsv" not in names
    assert "participants.json" not in names
    assert "participants_mapping.json" not in names
    assert all(not name.startswith("sub-") for name in names)
    assert all("/sub-" not in name for name in names)
