"""Raw-file batch import uses the project's code maps (invented codes only)."""

import json
import subprocess
import sys
from pathlib import Path

import pytest

from src.batch_convert import batch_convert_folder
from src.code_maps import CodeMapError, UnknownCodeError
from src.conversion_to_project import save_physio_batch_to_project

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def world(tmp_path):
    project = tmp_path / "proj"
    (project / "code").mkdir(parents=True)
    (project / "project.json").write_text(
        json.dumps({"Basics": {"Name": "N", "Authors": ["A"], "Keywords": ["k"]},
                    "StudyDesign": {"Timepoints": "multiple"}}), encoding="utf-8")
    (project / "code" / "session_map.json").write_text(json.dumps({"1": "1", "2": "2"}), encoding="utf-8")
    source = tmp_path / "src"
    source.mkdir()
    return project, source, tmp_path / "staged"


def write_map(project, name, *rows):
    (project / "code" / name).write_text(
        "code\tparticipant_id\n" + "".join(f"{c}\t{p}\n" for c, p in rows), encoding="utf-8")


def run(world, *names, modality="eyetracking", **kwargs):
    project, source, out = world
    for name in names:
        (source / name).write_text(f"data of {name.split('_', 1)[1]}", encoding="utf-8")
    logs: list[str] = []
    result = batch_convert_folder(source, out, project_root=project, modality_filter=modality,
                                  log_callback=lambda message, level="info": logs.append(message), **kwargs)
    return result, "\n".join(logs + result.warnings)


def data_files(out):
    return sorted(p.relative_to(out).as_posix() for p in out.glob("sub-*/**/*.tsv"))


def everything(out):
    return "\n".join(f"{p.name}\n{p.read_text(errors='ignore')}" for p in out.rglob("*") if p.is_file()).lower()


def test_the_code_in_the_name_is_translated_and_appears_nowhere(world):
    write_map(world[0], "eyetracking_code_map.tsv", ("QQAA", "sub-001"))
    result, log = run(world, "sub-qqaa_ses-1_task-rest.tsv")
    assert data_files(world[2]) == ["sub-001/ses-1/eyetracking/sub-001_ses-1_task-rest_eyetracking.tsv"]
    assert "Applied code map eyetracking_code_map.tsv: 1 code(s)." in log
    assert "qqaa" not in log.lower() + everything(world[2])
    assert [c.subject for c in result.converted] == ["sub-001"]


def test_a_participant_number_stays(world):
    write_map(world[0], "eyetracking_code_map.tsv", ("QQAA", "sub-004"))
    run(world, "sub-004_ses-1_task-rest.tsv")
    assert data_files(world[2])[0].startswith("sub-004/")


def test_session_and_task_maps_follow_the_file_name(world):
    write_map(world[0], "eyetracking_code_map.tsv", ("QQAA", "sub-001"))
    write_map(world[0], "eyetracking_ses-2_code_map.tsv", ("QQAA", "sub-002"))
    write_map(world[0], "eyetracking_task-read_code_map.tsv", ("QQAA", "sub-003"))
    run(world, "sub-QQAA_ses-1_task-rest.tsv", "sub-QQAA_ses-2_task-rest.tsv", "sub-QQAA_ses-1_task-read.tsv")
    assert [f.split("/")[0] + "/" + f.split("/")[1] for f in data_files(world[2])] == [
        "sub-001/ses-1", "sub-002/ses-2", "sub-003/ses-1"]


@pytest.mark.parametrize("dry_run", [False, True])
def test_unknown_labels_stop_before_any_file_is_converted(world, dry_run):
    write_map(world[0], "eyetracking_code_map.tsv", ("QQAA", "sub-001"))
    with pytest.raises(UnknownCodeError) as error:
        run(world, "sub-QQAA_ses-1_task-rest.tsv", "sub-ZZZZ_ses-1_task-rest.tsv", "sub-ZZYY_ses-1_task-rest.tsv",
            dry_run=dry_run)
    assert error.value.codes == ["ZZYY", "ZZZZ"]
    assert not world[2].exists()


def test_two_files_for_one_participant_file_stop_instead_of_overwriting(world):
    write_map(world[0], "eyetracking_code_map.tsv", ("QQAA", "sub-001"), ("QQBB", "sub-001"))
    with pytest.raises(CodeMapError, match="sub-001_ses-1_task-rest.tsv"):
        run(world, "sub-QQAA_ses-1_task-rest.tsv", "sub-QQBB_ses-1_task-rest.tsv")
    assert not world[2].exists()


def test_physio_files_use_physio_maps_and_other_modalities_are_unchanged(world, make_edf, monkeypatch):
    import numpy as np

    monkeypatch.setitem(sys.modules, "pyedflib", None)
    project, source, out = world
    write_map(project, "physio_code_map.tsv", ("QQAA", "sub-001"))
    make_edf(source / "sub-QQAA_ses-1_recording-ecg.edf", {"ecg": (np.linspace(-1, 1, 8), 4)})
    result = batch_convert_folder(source, out, project_root=project)
    assert list(out.glob("sub-001/ses-1/physio/sub-001_*.edf")), result.skipped
    assert "qqaa" not in everything(out)


def test_a_modality_without_a_map_keeps_the_label(world):
    write_map(world[0], "physio_code_map.tsv", ("QQAA", "sub-001"))
    run(world, "sub-QQAA_ses-1_task-rest.tsv")
    assert data_files(world[2])[0].startswith("sub-QQAA/")


def test_saving_does_not_shorten_a_mapped_participant(world):
    project, _, out = world
    write_map(project, "eyetracking_code_map.tsv", ("QQAA", "sub-1004"))
    result, _ = run(world, "sub-QQAA_ses-1_task-rest.tsv")
    save_physio_batch_to_project(project_root=project, staged_root=out, converted=result.converted,
                                 dataset_name="d", dest_root="root", flat_structure=False,
                                 modality_filter="eyetracking", subject_rewrite_mode="last3")
    assert [p.name for p in project.glob("sub-*")] == ["sub-1004"]


def test_cli_saves_the_mapped_participant_and_stops_on_an_unknown_one(world):
    project, source, _ = world
    write_map(project, "eyetracking_code_map.tsv", ("QQAA", "sub-001"))

    def cli(name):
        (source / name).write_text("data", encoding="utf-8")
        return subprocess.run(
            [sys.executable, "prism_tools.py", "physio", "batch-convert", "--input", str(source),
             "--project", str(project), "--modality", "eyetracking"],
            cwd=ROOT, capture_output=True, text=True)

    done = cli("sub-QQAA_ses-1_task-rest.tsv")
    assert done.returncode == 0, done.stdout + done.stderr
    assert [p.name for p in project.glob("sub-*")] == ["sub-001"]
    assert "qqaa" not in (done.stdout + done.stderr).lower()

    stopped = cli("sub-ZZZZ_ses-1_task-rest.tsv")
    assert stopped.returncode == 2 and "missing in the mapping" in stopped.stderr, stopped.stdout + stopped.stderr


def test_every_studio_call_hands_over_the_project():
    source = (ROOT / "app/src/web/blueprints/conversion_physio_handlers.py").read_text(encoding="utf-8")
    assert source.count("project_root=") - source.count("project_root=current_project_root") \
        - source.count("project_root=base_project_root") == 3
