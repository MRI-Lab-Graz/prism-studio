from __future__ import annotations

import json

import pytest

from src.session_code_rewriter import SessionCodeRewriter


def test_session_code_rewriter_rewrites_existing_names_and_json_links(tmp_path):
    project_root = tmp_path / "project"
    func_dir = project_root / "sub-001" / "ses-baseline1" / "func"
    fmap_dir = project_root / "sub-001" / "ses-baseline1" / "fmap"
    func_dir.mkdir(parents=True)
    fmap_dir.mkdir(parents=True)

    bold_file = func_dir / "sub-001_ses-baseline1_task-rest_bold.nii.gz"
    bold_file.write_bytes(b"nii")

    fmap_json = fmap_dir / "sub-001_ses-baseline1_dir-ap_epi.json"
    fmap_json.write_text(
        json.dumps(
            {
                "IntendedFor": [
                    "sub-001/ses-baseline1/func/sub-001_ses-baseline1_task-rest_bold.nii.gz"
                ],
            },
            indent=2,
        ),
        encoding="utf-8",
    )

    rewriter = SessionCodeRewriter(project_root)
    preview = rewriter.preview(
        mode="example_keep",
        example_session="ses-baseline1",
        keep_fragment="baseline",
    )

    assert preview["mapping"]["ses-baseline1"] == "ses-baseline"
    assert preview["directory_rename_count"] >= 1
    assert preview["file_rename_count"] >= 2
    assert not preview["conflicts"]

    result = rewriter.apply(
        mode="example_keep",
        example_session="ses-baseline1",
        keep_fragment="baseline",
    )
    assert result["mapping_count"] == 1

    assert not (project_root / "sub-001" / "ses-baseline1").exists()
    assert (
        project_root
        / "sub-001"
        / "ses-baseline"
        / "func"
        / "sub-001_ses-baseline_task-rest_bold.nii.gz"
    ).exists()

    rewritten_json = (
        project_root
        / "sub-001"
        / "ses-baseline"
        / "fmap"
        / "sub-001_ses-baseline_dir-ap_epi.json"
    ).read_text(encoding="utf-8")
    assert "ses-baseline/func/sub-001_ses-baseline_task-rest_bold.nii.gz" in rewritten_json
    assert "ses-baseline1" not in rewritten_json


def test_session_code_rewriter_add_only_applies_to_every_subject_with_that_session(tmp_path):
    """A session-label rewrite is a global rule, same as subject rewrite:
    every subject carrying the affected session gets the same mapping."""
    project_root = tmp_path / "project"
    (project_root / "sub-001" / "ses-1").mkdir(parents=True)
    (project_root / "sub-002" / "ses-1").mkdir(parents=True)

    rewriter = SessionCodeRewriter(project_root)
    result = rewriter.apply(
        mode="example_keep",
        example_session="ses-1",
        add_text="visit",
        add_position="prepend",
    )

    assert result["mapping"] == {"ses-1": "ses-visit1"}
    assert (project_root / "sub-001" / "ses-visit1").exists()
    assert (project_root / "sub-002" / "ses-visit1").exists()


def test_session_code_rewriter_detects_collisions(tmp_path):
    project_root = tmp_path / "project"
    (project_root / "sub-001" / "ses-pre1").mkdir(parents=True)
    (project_root / "sub-001" / "ses-post1").mkdir(parents=True)

    rewriter = SessionCodeRewriter(project_root)
    preview = rewriter.preview(
        mode="example_keep",
        example_session="ses-pre1",
        keep_fragment="1",
    )

    assert preview["mapping"]["ses-pre1"] == "ses-1"
    assert preview["mapping"]["ses-post1"] == "ses-1"
    assert preview["conflicts"]

    with pytest.raises(ValueError):
        rewriter.apply(mode="example_keep", example_session="ses-pre1", keep_fragment="1")


def test_session_code_rewriter_allows_many_to_one_when_paths_are_unique(tmp_path):
    project_root = tmp_path / "project"
    (project_root / "sub-001" / "ses-pre1").mkdir(parents=True)
    (project_root / "sub-002" / "ses-post1").mkdir(parents=True)

    rewriter = SessionCodeRewriter(project_root)
    result = rewriter.apply(
        mode="example_keep",
        example_session="ses-pre1",
        keep_fragment="1",
        allow_many_to_one=True,
    )

    assert result["mapping"] == {"ses-pre1": "ses-1", "ses-post1": "ses-1"}
    assert (project_root / "sub-001" / "ses-1").exists()
    assert (project_root / "sub-002" / "ses-1").exists()


def test_session_code_rewriter_explicit_mapping_bypasses_derivation(tmp_path):
    project_root = tmp_path / "project"
    (project_root / "sub-001" / "ses-1").mkdir(parents=True)

    rewriter = SessionCodeRewriter(project_root)
    result = rewriter.apply(explicit_mapping={"ses-1": "ses-baseline"})

    assert result["mapping_count"] == 1
    assert (project_root / "sub-001" / "ses-baseline").exists()


def test_session_code_rewriter_never_pads_or_coerces_session_labels(tmp_path):
    """CLAUDE.md invariant: session labels are free-form strings. '1' and
    '01' must stay distinct, independent labels -- never coerced into each
    other. The "add" rule applies uniformly to every session token found
    (same documented behavior as SubjectCodeRewriter's strip rule), but
    each token is rewritten from its own literal label, so '1' and '01'
    land on distinct results rather than being unified into one."""
    project_root = tmp_path / "project"
    (project_root / "sub-001" / "ses-1").mkdir(parents=True)
    (project_root / "sub-001" / "ses-01").mkdir(parents=True)

    rewriter = SessionCodeRewriter(project_root)
    preview = rewriter.preview(
        mode="example_keep",
        example_session="ses-1",
        add_text="visit",
        add_position="prepend",
    )

    assert preview["mapping"] == {"ses-1": "ses-visit1", "ses-01": "ses-visit01"}


def test_session_code_rewriter_list_session_ids_scans_whole_tree(tmp_path):
    project_root = tmp_path / "project"
    (project_root / "sub-001" / "ses-pre").mkdir(parents=True)
    (project_root / "sub-002" / "ses-post").mkdir(parents=True)

    rewriter = SessionCodeRewriter(project_root)
    assert rewriter.list_session_ids() == ["ses-post", "ses-pre"]


def test_session_code_rewriter_rejects_ambiguous_example(tmp_path):
    project_root = tmp_path / "project"
    (project_root / "sub-001" / "ses-103103").mkdir(parents=True)

    rewriter = SessionCodeRewriter(project_root)
    with pytest.raises(ValueError, match="Pattern is not unique"):
        rewriter.preview(
            mode="example_keep",
            example_session="ses-103103",
            keep_fragment="103",
        )


def test_session_code_rewriter_requires_keep_or_add(tmp_path):
    project_root = tmp_path / "project"
    (project_root / "sub-001" / "ses-1").mkdir(parents=True)

    rewriter = SessionCodeRewriter(project_root)
    with pytest.raises(ValueError, match="part to keep and/or a part to add"):
        rewriter.preview(mode="example_keep", example_session="ses-1")
