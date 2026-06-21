from __future__ import annotations

from pathlib import Path

import pytest

from src.bids_entity_rewriter import BidsEntityRewriter


def _touch_file(path: Path, content: bytes = b"data") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)


def test_bids_entity_rewriter_lists_modalities_entities_and_previews_rename(tmp_path):
    project_root = tmp_path / "project"
    func_dir = project_root / "sub-006" / "ses-1" / "func"
    _touch_file(func_dir / "sub-006_ses-1_task-RS_acq-Fs2_run-01_bold.nii.gz")
    _touch_file(func_dir / "sub-006_ses-1_task-RS_acq-Fs2_run-01_bold.json", b"{}")

    rewriter = BidsEntityRewriter(project_root)

    modalities = rewriter.list_modalities()
    assert "func" in modalities

    entities = rewriter.list_entities("func")
    assert "sub" not in entities
    assert "task" in entities
    assert "acq" in entities
    assert "run" in entities

    entity_values = rewriter.list_entity_values("func")
    assert entity_values.get("_task") == ["RS"]
    assert entity_values.get("_acq") == ["Fs2"]
    assert entity_values.get("_run") == ["01"]

    preview = rewriter.preview(
        modality="func",
        entity="_task",
        operation="rename",
        replacement="rest",
    )

    assert preview["modality"] == "func"
    assert preview["entity"] == "_task"
    assert preview["operation"] == "rename"
    assert preview["replacement"] == "rest"
    assert preview["rename_count"] == 2
    assert preview["conflicts"] == []
    assert any("task-rest" in entry["to"] for entry in preview["renames"])


def test_bids_entity_rewriter_does_not_expose_project_root_as_modality(tmp_path):
    project_root = tmp_path / "pk01"
    project_root.mkdir(parents=True)

    # Root-level BIDS-like filename should never make the project root name
    # appear as a modality option.
    _touch_file(project_root / "sub-006_task-RS_bold.nii.gz")

    func_dir = project_root / "sub-006" / "ses-1" / "func"
    _touch_file(func_dir / "sub-006_ses-1_task-RS_acq-Fs2_run-01_bold.nii.gz")

    rewriter = BidsEntityRewriter(project_root)
    modalities = rewriter.list_modalities()

    assert "func" in modalities
    assert "pk01" not in modalities


def test_bids_entity_rewriter_apply_delete_updates_subject_relative_text_links(tmp_path):
    project_root = tmp_path / "project"
    func_dir = project_root / "sub-006" / "ses-1" / "func"
    fmap_dir = project_root / "sub-006" / "ses-1" / "fmap"

    _touch_file(func_dir / "sub-006_ses-1_task-RS_acq-Fs2_run-01_bold.nii.gz")
    _touch_file(func_dir / "sub-006_ses-1_task-RS_acq-Fs2_run-01_bold.json", b"{}")
    fmap_json = fmap_dir / "sub-006_ses-1_dir-ap_epi.json"
    fmap_json.parent.mkdir(parents=True, exist_ok=True)
    fmap_json.write_text(
        (
            "{"
            '"IntendedFor": ['
            '"ses-1/func/sub-006_ses-1_task-RS_acq-Fs2_run-01_bold.nii.gz", '
            '"func/sub-006_ses-1_task-RS_acq-Fs2_run-01_bold.nii.gz", '
            '"bids::sub-006/ses-1/func/sub-006_ses-1_task-RS_acq-Fs2_run-01_bold.nii.gz"'
            "]"
            "}"
        ),
        encoding="utf-8",
    )

    rewriter = BidsEntityRewriter(project_root)
    result = rewriter.apply(
        modality="func",
        entity="_acq",
        operation="delete",
    )

    assert result["rename_count"] == 2
    assert result["text_update_count"] >= 1
    assert (
        func_dir / "sub-006_ses-1_task-RS_run-01_bold.nii.gz"
    ).exists()
    assert not (
        func_dir / "sub-006_ses-1_task-RS_acq-Fs2_run-01_bold.nii.gz"
    ).exists()

    rewritten_fmap = fmap_json.read_text(encoding="utf-8")
    assert "task-RS_run-01_bold.nii.gz" in rewritten_fmap
    assert "task-RS_acq-Fs2_run-01_bold.nii.gz" not in rewritten_fmap
    assert "func/sub-006_ses-1_task-RS_run-01_bold.nii.gz" in rewritten_fmap
    assert (
        "bids::sub-006/ses-1/func/sub-006_ses-1_task-RS_run-01_bold.nii.gz"
        in rewritten_fmap
    )


def test_bids_entity_rewriter_delete_detects_target_collisions(tmp_path):
    project_root = tmp_path / "project"
    func_dir = project_root / "sub-006" / "ses-1" / "func"

    _touch_file(func_dir / "sub-006_ses-1_task-rest_acq-A_run-01_bold.nii.gz")
    _touch_file(func_dir / "sub-006_ses-1_task-rest_run-01_bold.nii.gz")

    rewriter = BidsEntityRewriter(project_root)
    preview = rewriter.preview(
        modality="func",
        entity="_acq",
        current_value="A",
        operation="delete",
    )

    assert preview["conflicts"]
    with pytest.raises(ValueError, match="Entity rewrite cannot be applied"):
        rewriter.apply(
            modality="func",
            entity="_acq",
            current_value="A",
            operation="delete",
        )


def test_bids_entity_rewriter_requires_current_value_when_entity_has_multiple_values(
    tmp_path,
):
    project_root = tmp_path / "project"
    func_dir = project_root / "sub-006" / "ses-1" / "func"
    _touch_file(func_dir / "sub-006_ses-1_task-A_run-01_bold.nii.gz")
    _touch_file(func_dir / "sub-006_ses-1_task-B_run-01_bold.nii.gz")

    rewriter = BidsEntityRewriter(project_root)

    with pytest.raises(ValueError, match="Select the current value"):
        rewriter.preview(
            modality="func",
            entity="_task",
            operation="rename",
            replacement="rest",
        )


def test_bids_entity_rewriter_can_target_specific_current_value(tmp_path):
    project_root = tmp_path / "project"
    func_dir = project_root / "sub-006" / "ses-1" / "func"
    _touch_file(func_dir / "sub-006_ses-1_task-A_run-01_bold.nii.gz")
    _touch_file(func_dir / "sub-006_ses-1_task-B_run-01_bold.nii.gz")

    rewriter = BidsEntityRewriter(project_root)
    result = rewriter.apply(
        modality="func",
        entity="_task",
        operation="rename",
        current_value="A",
        replacement="rest",
    )

    assert result["rename_count"] == 1
    assert (func_dir / "sub-006_ses-1_task-rest_run-01_bold.nii.gz").exists()
    assert (func_dir / "sub-006_ses-1_task-B_run-01_bold.nii.gz").exists()
    assert not (func_dir / "sub-006_ses-1_task-A_run-01_bold.nii.gz").exists()


def test_bids_entity_rewriter_explicit_renames_survive_value_becoming_ambiguous_mid_batch(
    tmp_path,
):
    """Regression guard: when a multi-subject batch applies one subject's
    rename at a time, re-deriving current_value validity from a live scan
    breaks once an earlier subject's rename changes the set of distinct
    values left for this entity (e.g. introduces a second value where there
    used to be only one, making current_value=None suddenly ambiguous).
    explicit_renames must bypass that re-derivation entirely."""
    project_root = tmp_path / "project"
    func_a = project_root / "sub-006" / "ses-1" / "func"
    func_b = project_root / "sub-007" / "ses-1" / "func"
    _touch_file(func_a / "sub-006_ses-1_task-A_run-01_bold.nii.gz")
    _touch_file(func_b / "sub-007_ses-1_task-A_run-01_bold.nii.gz")

    rewriter = BidsEntityRewriter(project_root)

    # Simulate sub-006 having already been renamed to task-rest by an
    # earlier subject's mutation in the same batch — now there are two
    # distinct _task values (A, rest), so re-deriving with current_value
    # unset fails, exactly like the bug report.
    (func_a / "sub-006_ses-1_task-A_run-01_bold.nii.gz").rename(
        func_a / "sub-006_ses-1_task-rest_run-01_bold.nii.gz"
    )
    with pytest.raises(ValueError, match="Select the current value"):
        rewriter.apply(
            modality="func",
            entity="_task",
            operation="rename",
            replacement="rest",
            subjects=["sub-007"],
        )

    # The pre-resolved rename (computed once, before any subject in the
    # batch was renamed) must apply cleanly regardless.
    result = rewriter.apply(
        modality="func",
        entity="_task",
        operation="rename",
        replacement="rest",
        subjects=["sub-007"],
        explicit_renames=[
            {
                "from": "sub-007/ses-1/func/sub-007_ses-1_task-A_run-01_bold.nii.gz",
                "to": "sub-007/ses-1/func/sub-007_ses-1_task-rest_run-01_bold.nii.gz",
            }
        ],
    )

    assert result["rename_count"] == 1
    assert (func_b / "sub-007_ses-1_task-rest_run-01_bold.nii.gz").exists()
    assert not (func_b / "sub-007_ses-1_task-A_run-01_bold.nii.gz").exists()


def test_bids_entity_rewriter_case_only_rename_is_not_a_conflict(tmp_path):
    """Regression guard: on case-insensitive filesystems (macOS/Windows),
    Path.exists() returns True for a target that only differs in case from
    the source, since they're the same file on disk. A pure case-change
    rename (task-SST -> task-sst) must not be misreported as a collision
    with itself."""
    project_root = tmp_path / "project"
    func_dir = project_root / "sub-006" / "ses-1" / "func"
    _touch_file(func_dir / "sub-006_ses-1_task-SST_run-01_bold.nii.gz")
    _touch_file(func_dir / "sub-006_ses-1_task-SST_run-01_bold.json", b"{}")

    rewriter = BidsEntityRewriter(project_root)

    preview = rewriter.preview(
        modality="func",
        entity="_task",
        operation="rename",
        replacement="sst",
    )

    assert preview["conflicts"] == []
    assert preview["rename_count"] == 2

    result = rewriter.apply(
        modality="func",
        entity="_task",
        operation="rename",
        replacement="sst",
    )

    assert result["rename_count"] == 2
    assert (func_dir / "sub-006_ses-1_task-sst_run-01_bold.nii.gz").exists()
    assert (func_dir / "sub-006_ses-1_task-sst_run-01_bold.json").exists()


def test_bids_entity_rewriter_renames_broken_symlink_binary_files(tmp_path):
    """Regression guard: a DataLad-tracked .nii.gz is normally a symlink
    into .git/annex/objects/. Before content has been fetched, that
    symlink is broken — Path.is_file() returns False for it. The entity
    rewriter must still discover and rename it; renaming a symlink doesn't
    require its target to be resolvable. Previously this silently left
    the .nii.gz on its old entity value while a sibling .tsv got renamed,
    producing a dataset where two files for the same logical run disagree
    on the run entity, with no error reported."""
    project_root = tmp_path / "project"
    func_dir = project_root / "sub-02" / "func"
    func_dir.mkdir(parents=True)

    _touch_file(func_dir / "sub-02_task-rest_run-01_events.tsv", content=b"onset\n")
    broken_bold = func_dir / "sub-02_task-rest_run-01_bold.nii.gz"
    broken_bold.symlink_to(project_root / ".git" / "annex" / "objects" / "missing.nii.gz")
    assert not broken_bold.exists()
    assert broken_bold.is_symlink()

    rewriter = BidsEntityRewriter(project_root)
    result = rewriter.apply(
        modality="func",
        entity="run",
        current_value="01",
        operation="rename",
        replacement="A",
    )

    assert result["conflicts"] == []
    assert result["rename_count"] == 2
    renamed_bold = func_dir / "sub-02_task-rest_run-A_bold.nii.gz"
    assert renamed_bold.is_symlink()
    assert (func_dir / "sub-02_task-rest_run-A_events.tsv").exists()
    assert not (func_dir / "sub-02_task-rest_run-01_bold.nii.gz").is_symlink()


def test_bids_entity_rewriter_detects_collision_against_broken_symlink_target(tmp_path):
    """A broken symlink occupying the rename target filename is still a
    real collision (renaming into it would clobber an unrelated file),
    even though plain Path.exists() reports the target as absent."""
    project_root = tmp_path / "project"
    func_dir = project_root / "sub-03" / "func"
    func_dir.mkdir(parents=True)

    _touch_file(func_dir / "sub-03_task-rest_run-01_bold.nii.gz")
    target = func_dir / "sub-03_task-rest_run-02_bold.nii.gz"
    target.symlink_to(project_root / ".git" / "annex" / "objects" / "missing.nii.gz")

    rewriter = BidsEntityRewriter(project_root)
    preview = rewriter.preview(
        modality="func",
        entity="run",
        current_value="01",
        operation="rename",
        replacement="02",
    )

    assert preview["conflicts"]
