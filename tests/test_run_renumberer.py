from __future__ import annotations

from src.run_renumberer import RunRenumberer


def _touch(path):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"data")


def test_run_renumberer_detects_no_gap_as_nothing_to_do(tmp_path):
    project_root = tmp_path / "project"
    func = project_root / "sub-001" / "ses-01" / "func"
    _touch(func / "sub-001_ses-01_task-rest_run-01_bold.nii.gz")
    _touch(func / "sub-001_ses-01_task-rest_run-02_bold.nii.gz")

    renumberer = RunRenumberer(project_root)
    preview = renumberer.preview()

    assert preview["groups"] == []
    assert preview["skipped_groups"] == []
    assert preview["rename_count"] == 0


def test_run_renumberer_detects_and_closes_a_simple_gap(tmp_path):
    project_root = tmp_path / "project"
    func = project_root / "sub-001" / "ses-01" / "func"
    _touch(func / "sub-001_ses-01_task-rest_run-01_bold.nii.gz")
    _touch(func / "sub-001_ses-01_task-rest_run-03_bold.nii.gz")

    renumberer = RunRenumberer(project_root)
    preview = renumberer.preview()

    assert preview["rename_count"] == 1
    assert len(preview["groups"]) == 1
    group = preview["groups"][0]
    assert group["current_runs"] == ["01", "03"]
    assert group["proposed_runs"] == ["01", "02"]
    assert group["renames"] == [
        {
            "from": "sub-001/ses-01/func/sub-001_ses-01_task-rest_run-03_bold.nii.gz",
            "to": "sub-001/ses-01/func/sub-001_ses-01_task-rest_run-02_bold.nii.gz",
        }
    ]

    result = renumberer.apply()
    assert result["rename_count"] == 1
    assert not (func / "sub-001_ses-01_task-rest_run-03_bold.nii.gz").exists()
    assert (func / "sub-001_ses-01_task-rest_run-02_bold.nii.gz").exists()
    assert (func / "sub-001_ses-01_task-rest_run-01_bold.nii.gz").exists()


def test_run_renumberer_closes_a_chained_gap_without_collision(tmp_path):
    """Regression guard: closing [01,03,04] -> [01,02,03] requires 03->02
    AND 04->03 in the same batch. 04->03 would collide with the original
    (not-yet-renamed) run-03 file if processed out of order."""
    project_root = tmp_path / "project"
    func = project_root / "sub-001" / "ses-01" / "func"
    for run in ("01", "03", "04"):
        _touch(func / f"sub-001_ses-01_task-rest_run-{run}_bold.nii.gz")
        _touch(func / f"sub-001_ses-01_task-rest_run-{run}_bold.json")

    renumberer = RunRenumberer(project_root)
    preview = renumberer.preview()
    assert preview["rename_count"] == 4  # 03->02 and 04->03, x2 files each

    result = renumberer.apply()
    assert result["rename_count"] == 4

    remaining = sorted(p.name for p in func.iterdir())
    assert remaining == [
        "sub-001_ses-01_task-rest_run-01_bold.json",
        "sub-001_ses-01_task-rest_run-01_bold.nii.gz",
        "sub-001_ses-01_task-rest_run-02_bold.json",
        "sub-001_ses-01_task-rest_run-02_bold.nii.gz",
        "sub-001_ses-01_task-rest_run-03_bold.json",
        "sub-001_ses-01_task-rest_run-03_bold.nii.gz",
    ]
    # Content survived the chain (not overwritten/lost along the way).
    for name in remaining:
        assert (func / name).read_bytes() == b"data"


def test_run_renumberer_skips_group_with_non_numeric_run_value(tmp_path):
    project_root = tmp_path / "project"
    func = project_root / "sub-001" / "ses-01" / "func"
    _touch(func / "sub-001_ses-01_task-rest_run-01_bold.nii.gz")
    _touch(func / "sub-001_ses-01_task-rest_run-01b_bold.nii.gz")

    renumberer = RunRenumberer(project_root)
    preview = renumberer.preview()

    assert preview["groups"] == []
    assert preview["rename_count"] == 0
    assert len(preview["skipped_groups"]) == 1
    assert "non-numeric" in preview["skipped_groups"][0]["reason"].lower()


def test_run_renumberer_skips_group_with_inconsistent_padding(tmp_path):
    project_root = tmp_path / "project"
    func = project_root / "sub-001" / "ses-01" / "func"
    _touch(func / "sub-001_ses-01_task-rest_run-1_bold.nii.gz")
    _touch(func / "sub-001_ses-01_task-rest_run-03_bold.nii.gz")

    renumberer = RunRenumberer(project_root)
    preview = renumberer.preview()

    assert preview["groups"] == []
    assert len(preview["skipped_groups"]) == 1
    assert "padding" in preview["skipped_groups"][0]["reason"].lower()


def test_run_renumberer_keeps_different_tasks_as_separate_groups(tmp_path):
    project_root = tmp_path / "project"
    func = project_root / "sub-001" / "ses-01" / "func"
    _touch(func / "sub-001_ses-01_task-rest_run-01_bold.nii.gz")
    _touch(func / "sub-001_ses-01_task-nback_run-01_bold.nii.gz")
    _touch(func / "sub-001_ses-01_task-nback_run-03_bold.nii.gz")

    renumberer = RunRenumberer(project_root)
    preview = renumberer.preview()

    assert preview["rename_count"] == 1
    assert len(preview["groups"]) == 1
    assert "task-nback" in preview["groups"][0]["renames"][0]["from"]


def test_run_renumberer_keeps_different_subjects_as_separate_groups(tmp_path):
    project_root = tmp_path / "project"
    func1 = project_root / "sub-001" / "ses-01" / "func"
    func2 = project_root / "sub-002" / "ses-01" / "func"
    _touch(func1 / "sub-001_ses-01_task-rest_run-01_bold.nii.gz")
    _touch(func2 / "sub-002_ses-01_task-rest_run-01_bold.nii.gz")
    _touch(func2 / "sub-002_ses-01_task-rest_run-03_bold.nii.gz")

    renumberer = RunRenumberer(project_root)
    preview = renumberer.preview()

    assert preview["rename_count"] == 1
    assert "sub-002" in preview["groups"][0]["renames"][0]["from"]
