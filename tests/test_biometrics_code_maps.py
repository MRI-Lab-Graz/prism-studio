"""Biometrics import uses the project's code maps (invented codes only)."""

import json
import subprocess
import sys
from pathlib import Path

import pytest

from src.code_maps import CodeMapError, UnknownCodeError
from src.converters.biometrics import convert_biometrics_table_to_prism_dataset

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def project(tmp_path):
    root = tmp_path / "proj"
    library = root / "code" / "library" / "biometrics"
    library.mkdir(parents=True)
    for task, item in (("grip", "grip_strength"), ("jump", "jump_height")):
        (library / f"biometrics-{task}.json").write_text(
            json.dumps({"Technical": {"Device": "D"}, "Study": {"TaskName": task},
                        "Metadata": {"SchemaVersion": "1.2.0"}, item: {"Description": item}}),
            encoding="utf-8",
        )
    (root / "project.json").write_text(
        json.dumps({"Basics": {"Name": "N", "Authors": ["A"], "Keywords": ["k"]},
                    "StudyDesign": {"Timepoints": "multiple"}}),
        encoding="utf-8",
    )
    (root / "code" / "session_map.json").write_text(json.dumps({"pre": "1", "post": "2"}), encoding="utf-8")
    return root


def write_map(project, name, *rows):
    (project / "code" / name).write_text(
        "code\tparticipant_id\n" + "".join(f"{c}\t{p}\n" for c, p in rows), encoding="utf-8"
    )


def table(project, text):
    path = project.parent / "data.csv"
    path.write_text(text, encoding="utf-8")
    return path


ONE_ROW = "participant_id,session,grip_strength,jump_height\nQQAA,pre,40,30\n"


def convert(project, text=ONE_ROW, **overrides):
    out = project.parent / "staged"
    kwargs = dict(input_path=table(project, text), library_dir=project / "code" / "library" / "biometrics",
                  output_root=out, project_root=project, force=True)
    kwargs.update(overrides)
    return out, convert_biometrics_table_to_prism_dataset(**kwargs)


def folders(root):
    return sorted(p.relative_to(root).as_posix() for p in root.glob("sub-*/ses-*"))


def test_the_general_map_is_applied_and_no_code_is_written_or_reported(project):
    write_map(project, "biometrics_code_map.tsv", ("qqaa", "sub-001"))
    out, result = convert(project)
    assert folders(out) == ["sub-001/ses-1"]
    assert (out / "participants.tsv").read_text(encoding="utf-8").split() == ["participant_id", "sub-001"]
    assert "Applied code map biometrics_code_map.tsv: 1 code(s)." in result.notes
    assert "qqaa" not in "\n".join(result.notes).lower()
    assert not any("qqaa" in p.read_text(encoding="utf-8").lower() for p in out.rglob("*") if p.is_file())


def test_the_session_map_uses_the_written_session(project):
    write_map(project, "biometrics_code_map.tsv", ("QQAA", "sub-001"))
    write_map(project, "biometrics_ses-2_code_map.tsv", ("QQAA", "sub-002"))
    out, _ = convert(project, "participant_id,session,grip_strength\nQQAA,pre,40\nQQAA,post,41\n")
    assert folders(out) == ["sub-001/ses-1", "sub-002/ses-2"]


@pytest.mark.parametrize("tasks_to_export", [None, ["grip"]])
def test_a_task_map_that_splits_a_row_stops_also_when_the_task_is_not_exported(project, tasks_to_export):
    write_map(project, "biometrics_code_map.tsv", ("QQAA", "sub-001"))
    write_map(project, "biometrics_task-jump_code_map.tsv", ("QQAA", "sub-002"))
    with pytest.raises(CodeMapError, match="different participants"):
        convert(project, tasks_to_export=tasks_to_export)
    assert not (project.parent / "staged").exists()


@pytest.mark.parametrize("rows", [(), (("QQBB", "sub-001"),)])
def test_an_unlisted_code_stops_and_nothing_is_written(project, rows):
    write_map(project, "biometrics_code_map.tsv", *rows)
    with pytest.raises(UnknownCodeError):
        convert(project)
    assert not (project.parent / "staged").exists()


def test_a_mapped_participant_is_not_matched_to_another_existing_one(project):
    write_map(project, "biometrics_code_map.tsv", ("QQAA", "sub-1"))
    out, _ = convert(project, existing_participant_ids={"sub-001"})
    assert folders(out) == ["sub-1/ses-1"]


def test_the_single_timepoint_rule_applies_to_a_staged_conversion(project):
    (project / "project.json").write_text(json.dumps({"StudyDesign": {"Timepoints": "single"}}), encoding="utf-8")
    out, _ = convert(project)
    assert folders(out) == ["sub-QQAA/ses-1"]


def test_cli_writes_the_mapped_participant_into_the_project(project):
    write_map(project, "biometrics_code_map.tsv", ("QQAA", "sub-001"))
    done = subprocess.run(
        [sys.executable, "prism_tools.py", "biometrics", "convert", "--input", str(table(project, ONE_ROW)),
         "--library", str(project / "code" / "library" / "biometrics"), "--output", str(project)],
        cwd=ROOT, capture_output=True, text=True,
    )
    assert done.returncode == 0, done.stdout + done.stderr
    assert folders(project) == ["sub-001/ses-1"]
    assert "qqaa" not in (done.stdout + done.stderr).lower()
    assert "qqaa" not in (project / "participants.tsv").read_text(encoding="utf-8").lower()


def test_cli_stops_on_an_unlisted_code(project):
    write_map(project, "biometrics_code_map.tsv", ("QQBB", "sub-001"))
    done = subprocess.run(
        [sys.executable, "prism_tools.py", "biometrics", "convert", "--input", str(table(project, ONE_ROW)),
         "--library", str(project / "code" / "library" / "biometrics"), "--output", str(project)],
        cwd=ROOT, capture_output=True, text=True,
    )
    assert done.returncode != 0
    assert "missing in the mapping" in done.stdout + done.stderr
    assert folders(project) == []


def test_studio_passes_the_project_to_the_converter():
    """Parity: both Studio calls hand the converter the project, as the CLI does."""
    source = (ROOT / "app/src/web/blueprints/conversion_biometrics_handlers.py").read_text(encoding="utf-8")
    assert source.count("project_root=participants_source_root,") == 2
