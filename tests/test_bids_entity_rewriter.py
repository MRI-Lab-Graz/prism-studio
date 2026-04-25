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
