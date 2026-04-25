from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.subject_code_rewriter import SubjectCodeRewriter


def test_subject_code_rewriter_rewrites_existing_names_and_json_links(tmp_path):
    project_root = tmp_path / "project"
    func_dir = project_root / "sub-1293167" / "ses-01" / "func"
    fmap_dir = project_root / "sub-1293167" / "ses-01" / "fmap"
    func_dir.mkdir(parents=True)
    fmap_dir.mkdir(parents=True)

    bold_file = func_dir / "sub-1293167_ses-01_task-rest_bold.nii.gz"
    bold_file.write_bytes(b"nii")

    fmap_json = fmap_dir / "sub-1293167_ses-01_dir-ap_epi.json"
    fmap_json.write_text(
        json.dumps(
            {
                "IntendedFor": [
                    "sub-1293167/ses-01/func/sub-1293167_ses-01_task-rest_bold.nii.gz"
                ],
                "Description": "link to sub-1293167",
            },
            indent=2,
        ),
        encoding="utf-8",
    )

    participants_tsv = project_root / "participants.tsv"
    participants_tsv.write_text(
        "participant_id\tage\nsub-1293167\t30\n", encoding="utf-8"
    )

    rewriter = SubjectCodeRewriter(project_root)
    preview = rewriter.preview(mode="last3")

    assert preview["mapping"]["sub-1293167"] == "sub-167"
    assert preview["directory_rename_count"] >= 1
    assert preview["file_rename_count"] >= 2
    assert preview["text_update_count"] >= 2
    assert not preview["conflicts"]

    result = rewriter.apply(mode="last3")
    assert result["directory_rename_count"] >= 1
    assert result["file_rename_count"] >= 2

    assert not (project_root / "sub-1293167").exists()
    assert (project_root / "sub-167" / "ses-01" / "func").exists()
    assert (
        project_root
        / "sub-167"
        / "ses-01"
        / "func"
        / "sub-167_ses-01_task-rest_bold.nii.gz"
    ).exists()
    assert (
        project_root
        / "sub-167"
        / "ses-01"
        / "fmap"
        / "sub-167_ses-01_dir-ap_epi.json"
    ).exists()

    rewritten_json = (
        project_root
        / "sub-167"
        / "ses-01"
        / "fmap"
        / "sub-167_ses-01_dir-ap_epi.json"
    ).read_text(encoding="utf-8")
    assert "sub-167/ses-01/func/sub-167_ses-01_task-rest_bold.nii.gz" in rewritten_json
    assert "sub-1293167" not in rewritten_json

    rewritten_participants = participants_tsv.read_text(encoding="utf-8")
    assert "sub-167" in rewritten_participants
    assert "sub-1293167" not in rewritten_participants


def test_subject_code_rewriter_detects_collisions(tmp_path):
    project_root = tmp_path / "project"
    (project_root / "sub-1293167").mkdir(parents=True)
    (project_root / "sub-999167").mkdir(parents=True)

    rewriter = SubjectCodeRewriter(project_root)
    preview = rewriter.preview(mode="last3")

    assert preview["mapping"]["sub-1293167"] == "sub-167"
    assert preview["mapping"]["sub-999167"] == "sub-167"
    assert preview["conflicts"]
    assert "sub-1293167" in preview["subject_token_sources"]
    assert "sub-999167" in preview["subject_token_sources"]
    assert preview["subject_token_sources"]["sub-1293167"]
    assert preview["subject_token_sources"]["sub-999167"]

    with pytest.raises(ValueError):
        rewriter.apply(mode="last3")


def test_subject_code_rewriter_allows_many_to_one_when_paths_are_unique(tmp_path):
    project_root = tmp_path / "project"
    first_func = project_root / "sub-1293167" / "ses-01" / "func"
    second_func = project_root / "sub-999167" / "ses-02" / "func"
    first_func.mkdir(parents=True)
    second_func.mkdir(parents=True)

    (first_func / "sub-1293167_ses-01_task-rest_bold.json").write_text(
        "{}", encoding="utf-8"
    )
    (second_func / "sub-999167_ses-02_task-rest_bold.json").write_text(
        "{}", encoding="utf-8"
    )

    participants_tsv = project_root / "participants.tsv"
    participants_tsv.write_text(
        "participant_id\tage\nsub-1293167\t30\nsub-999167\t31\n",
        encoding="utf-8",
    )

    rewriter = SubjectCodeRewriter(project_root)
    preview = rewriter.preview(mode="last3", allow_many_to_one=True)

    assert preview["mapping"]["sub-1293167"] == "sub-167"
    assert preview["mapping"]["sub-999167"] == "sub-167"
    assert preview["allow_many_to_one"] is True
    assert preview["conflicts"] == []

    result = rewriter.apply(mode="last3", allow_many_to_one=True)
    assert result["mapping_count"] == 2
    assert (
        project_root
        / "sub-167"
        / "ses-01"
        / "func"
        / "sub-167_ses-01_task-rest_bold.json"
    ).exists()
    assert (
        project_root
        / "sub-167"
        / "ses-02"
        / "func"
        / "sub-167_ses-02_task-rest_bold.json"
    ).exists()
    assert not (project_root / "sub-1293167").exists()
    assert not (project_root / "sub-999167").exists()

    rewritten_participants = participants_tsv.read_text(encoding="utf-8")
    assert "sub-167" in rewritten_participants
    assert "sub-1293167" not in rewritten_participants
    assert "sub-999167" not in rewritten_participants


def test_subject_code_rewriter_many_to_one_blocks_file_path_collisions(tmp_path):
    project_root = tmp_path / "project"
    first_func = project_root / "sub-1293167" / "ses-01" / "func"
    second_func = project_root / "sub-999167" / "ses-01" / "func"
    first_func.mkdir(parents=True)
    second_func.mkdir(parents=True)

    (first_func / "sub-1293167_ses-01_task-rest_bold.json").write_text(
        "{}", encoding="utf-8"
    )
    (second_func / "sub-999167_ses-01_task-rest_bold.json").write_text(
        "{}", encoding="utf-8"
    )

    rewriter = SubjectCodeRewriter(project_root)
    preview = rewriter.preview(mode="last3", allow_many_to_one=True)

    assert any(
        "Final file path collision after harmonization" in message
        for message in preview["conflicts"]
    )

    with pytest.raises(ValueError, match="Final file path collision after harmonization"):
        rewriter.apply(mode="last3", allow_many_to_one=True)


def test_subject_code_rewriter_noop_when_no_rewrite_needed(tmp_path):
    project_root = tmp_path / "project"
    (project_root / "sub-167" / "ses-01" / "func").mkdir(parents=True)
    (project_root / "sub-167" / "ses-01" / "func" / "sub-167_ses-01_task-rest_bold.json").write_text(
        "{}", encoding="utf-8"
    )

    rewriter = SubjectCodeRewriter(project_root)
    preview = rewriter.preview(mode="last3")

    assert preview["mapping_count"] == 0
    assert preview["directory_rename_count"] == 0
    assert preview["file_rename_count"] == 0
    assert preview["text_update_count"] == 0
    assert preview["conflicts"] == []


def test_subject_code_rewriter_example_keep_preview_and_apply(tmp_path):
    project_root = tmp_path / "project"
    (project_root / "sub-1291003" / "ses-01" / "func").mkdir(parents=True)
    (project_root / "sub-7777002" / "ses-01" / "func").mkdir(parents=True)

    file_one = (
        project_root
        / "sub-1291003"
        / "ses-01"
        / "func"
        / "sub-1291003_ses-01_task-rest_bold.json"
    )
    file_one.write_text('{"participant_id": "sub-1291003"}', encoding="utf-8")

    file_two = (
        project_root
        / "sub-7777002"
        / "ses-01"
        / "func"
        / "sub-7777002_ses-01_task-rest_bold.json"
    )
    file_two.write_text('{"participant_id": "sub-7777002"}', encoding="utf-8")

    rewriter = SubjectCodeRewriter(project_root)
    preview = rewriter.preview(
        mode="example_keep",
        example_subject="sub-1291003",
        keep_fragment="003",
    )

    assert preview["mode"] == "example_keep"
    assert preview["rule"]["strategy"] == "suffix"
    assert preview["mapping"]["sub-1291003"] == "sub-003"
    assert preview["mapping"]["sub-7777002"] == "sub-002"

    result = rewriter.apply(
        mode="example_keep",
        example_subject="sub-1291003",
        keep_fragment="003",
    )
    assert result["mapping_count"] == 2
    assert (project_root / "sub-003").exists()
    assert (project_root / "sub-002").exists()


def test_subject_code_rewriter_example_keep_rejects_ambiguous_example(tmp_path):
    project_root = tmp_path / "project"
    (project_root / "sub-103103" / "ses-01" / "func").mkdir(parents=True)

    rewriter = SubjectCodeRewriter(project_root)

    with pytest.raises(ValueError, match="Pattern is not unique"):
        rewriter.preview(
            mode="example_keep",
            example_subject="sub-103103",
            keep_fragment="103",
        )


def test_subject_code_rewriter_list_root_subject_ids_only(tmp_path):
    project_root = tmp_path / "project"
    (project_root / "sub-101").mkdir(parents=True)
    (project_root / "sub-202").mkdir(parents=True)
    (project_root / "sourcedata").mkdir(parents=True)
    (project_root / "sourcedata" / "sub-999").mkdir(parents=True)

    rewriter = SubjectCodeRewriter(project_root)
    assert rewriter.list_root_subject_ids() == ["sub-101", "sub-202"]
