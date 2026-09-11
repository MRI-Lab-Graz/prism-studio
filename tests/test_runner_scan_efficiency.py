"""Guards for the single-pass dataset walk.

Validation of a network-mounted project is bound by filesystem round trips,
not CPU, so these tests pin the two things that made it slow: probing sidecar
candidates with one stat() each, and walking the whole tree a second time for
procedure validation. They assert behaviour is unchanged *and* that the round
trips stay gone.
"""

import json
import os
from collections import Counter

import pytest

from src.runner import _scan_dir, validate_dataset
from src.stats import DatasetStats
from src.validator import _dir_contains
from src.procedure_validator import validate_procedure


def _write(path, text=""):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _build_dataset(root, subjects=("sub-01", "sub-02"), sessions=("ses-01",)):
    _write(
        root / "dataset_description.json",
        json.dumps(
            {
                "Name": "scan",
                "BIDSVersion": "1.8.0",
                "DatasetType": "raw",
                "Authors": ["A B"],
            }
        ),
    )
    _write(
        root / "project.json",
        json.dumps(
            {
                "Sessions": [
                    {"id": s, "tasks": [{"task": "rest"}, {"task": "well-being"}]}
                    for s in sessions
                ],
                "TaskDefinitions": {"rest": {}, "well-being": {}},
            }
        ),
    )
    _write(
        root / "task-well-being_survey.json",
        json.dumps({"Study": {"OriginalName": "WB"}, "a": {"Description": "a"}}),
    )
    _write(root / "participants.tsv", "participant_id\n" + "\n".join(subjects) + "\n")
    for sub in subjects:
        for ses in sessions:
            _write(
                root / sub / ses / "survey" / f"{sub}_{ses}_task-well-being_survey.tsv",
                "a\n1\n",
            )
            # A standard BIDS modality: the walk hands these to the BIDS
            # validator, but procedure checks still need to see the task.
            _write(root / sub / ses / "anat" / f"{sub}_{ses}_task-rest_T1w.nii.gz", "x")


def test_dir_contains_reads_each_directory_once(tmp_path):
    _write(tmp_path / "a.json", "{}")
    cache = {}
    listdir_calls = []
    real_listdir = os.listdir

    def counting_listdir(path):
        listdir_calls.append(path)
        return real_listdir(path)

    os.listdir = counting_listdir
    try:
        assert _dir_contains(str(tmp_path), "a.json", cache) is True
        assert _dir_contains(str(tmp_path), "b.json", cache) is False
        assert _dir_contains(str(tmp_path), "c.json", cache) is False
    finally:
        os.listdir = real_listdir

    assert len(listdir_calls) == 1, "each extra probe must be a cache hit, not a stat"


def test_dir_contains_without_cache_falls_back_to_stat(tmp_path):
    _write(tmp_path / "a.json", "{}")
    assert _dir_contains(str(tmp_path), "a.json", None) is True
    assert _dir_contains(str(tmp_path), "missing.json", None) is False


def test_scan_dir_seeds_the_probe_cache(tmp_path):
    _write(tmp_path / "one.tsv", "x")
    (tmp_path / "sub-01").mkdir()
    cache = {}

    entries = _scan_dir(str(tmp_path), cache)

    assert set(entries) == {"one.tsv", "sub-01"}
    assert entries["one.tsv"].is_file()
    assert entries["sub-01"].is_dir()
    # The listing the walk already paid for answers later sidecar probes.
    assert _dir_contains(str(tmp_path), "one.tsv", cache) is True
    assert _dir_contains(str(tmp_path), "nope.tsv", cache) is False


def test_scan_dir_propagates_missing_directory(tmp_path):
    with pytest.raises(OSError):
        _scan_dir(str(tmp_path / "does-not-exist"))


def test_add_procedure_tasks_keeps_hyphenated_task_labels():
    stats = DatasetStats()
    stats.add_procedure_tasks(
        "ses-01",
        ["sub-01_ses-01_task-well-being_survey.tsv", "sub-01_ses-01_notes.txt"],
    )
    # The procedure validator's own pattern keeps the hyphen; the stricter
    # pattern behind stats.tasks would truncate this to "well".
    assert stats.procedure_tasks == {("ses-01", "well-being")}


def test_add_procedure_tasks_ignores_missing_session():
    stats = DatasetStats()
    stats.add_procedure_tasks("", ["sub-01_task-rest_bold.nii.gz"])
    assert stats.procedure_tasks == set()


def test_supplied_disk_index_matches_a_fresh_scan(tmp_path):
    _build_dataset(tmp_path)

    scanned = validate_procedure(tmp_path, tmp_path)
    _issues, stats = validate_dataset(str(tmp_path), run_prism=True, run_bids=False)
    supplied = validate_procedure(
        tmp_path,
        tmp_path,
        disk_index=(stats.disk_sessions, stats.procedure_tasks),
    )

    assert supplied == scanned


def test_bids_modalities_still_count_as_data_on_disk(tmp_path):
    """PRISM704 must not fire for a task whose only data sits in anat/.

    In combined mode the walk skips standard BIDS modality folders, so their
    filenames have to be collected before that skip — otherwise every
    MRI-only task is falsely reported as declared-but-missing.
    """
    _build_dataset(tmp_path)

    issues, _stats = validate_dataset(str(tmp_path), run_prism=True, run_bids=False)
    combined, _stats = validate_dataset(str(tmp_path), run_prism=True, run_bids=True)

    for result in (issues, combined):
        assert not [i for i in result if "PRISM704" in str(i[1])], result


def test_walk_does_not_grow_with_repeated_sidecar_probes(tmp_path):
    """One directory read per directory, and no second pass over the tree."""
    _build_dataset(tmp_path, subjects=("sub-01", "sub-02", "sub-03"))

    reads = []
    real_scandir, real_listdir = os.scandir, os.listdir

    def counting_scandir(path):
        reads.append(str(path))
        return real_scandir(path)

    def counting_listdir(path):
        reads.append(str(path))
        return real_listdir(path)

    os.scandir, os.listdir = counting_scandir, counting_listdir
    try:
        validate_dataset(str(tmp_path), run_prism=True, run_bids=False)
    finally:
        os.scandir, os.listdir = real_scandir, real_listdir

    dataset_reads = [r for r in reads if r.startswith(str(tmp_path))]
    duplicates = [r for r, n in Counter(dataset_reads).items() if n > 1]
    assert duplicates == [], f"directory read more than once: {duplicates}"

    # 1 root + 3 subjects + 3 sessions + 6 modality folders, plus the handful of
    # legacy dataset-level sidecar locations probed once each.
    real_dirs = {str(tmp_path)} | {
        str(p) for p in tmp_path.rglob("*") if p.is_dir()
    }
    assert set(dataset_reads) >= real_dirs
    assert len(dataset_reads) - len(real_dirs) <= 5, sorted(dataset_reads)
