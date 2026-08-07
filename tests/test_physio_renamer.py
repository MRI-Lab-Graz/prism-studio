"""Unit tests for src.physio_renamer.

Extracted from app/src/web/blueprints/conversion_physio_handlers.py's
api_physio_rename (the Studio GUI's physio/eyetracking batch renamer),
which had no CLI equivalent despite being real business logic (regex
renaming, folder-path subject/session inference, BIDS-organized output
paths, subject-ID rewriting) — see
docs/_archive/GUI_BACKEND_AUDIT_2026-08-07.md, P2. The blueprint's own
existing tests (tests/test_web_blueprints_conversion.py) continue to cover
the same logic indirectly via the re-exported names.
"""

import re

from src.physio_renamer import (
    apply_folder_placeholders,
    compute_organized_relative_path,
    compute_renamed_filename,
    extract_subject_session_from_source_path,
    normalize_project_dest_root,
    normalize_subject_rewrite_mode,
    plan_rename,
    resolve_project_copy_root,
    rewrite_subject_in_filename,
    rewrite_subject_in_relative_path,
    rewrite_subject_label,
    sanitize_bids_label,
    should_use_flat_project_copy,
)


class TestSanitizeBidsLabel:
    def test_strips_non_alnum(self):
        assert sanitize_bids_label("sub_001!") == "sub001"

    def test_empty_returns_none(self):
        assert sanitize_bids_label("   ") is None
        assert sanitize_bids_label(None) is None


class TestExtractSubjectSessionFromSourcePath:
    def test_finds_literal_sub_ses_segments(self):
        # Only two folder parts (sub-07, ses-03) — the positional pass at
        # the default levels (2, 1) lands on the same parts as the literal
        # scan here, so both agree.
        subject, session = extract_subject_session_from_source_path(
            "sub-07/ses-03/VPDATA.RAW"
        )
        assert subject == "07"
        assert session == "03"

    def test_positional_fallback_without_literal_segments(self):
        subject, session = extract_subject_session_from_source_path(
            "VPDATA/135/t1/VPDATA.RAW",
            subject_level_from_end=2,
            session_level_from_end=1,
        )
        assert subject == "135"
        assert session == "t1"

    def test_example_guided_extraction(self):
        subject, session = extract_subject_session_from_source_path(
            "VPDATA/132/t3/VPDATA.RAW",
            subject_level_from_end=2,
            session_level_from_end=1,
            example_path="VPDATA/135/t1/VPDATA.RAW",
            subject_example_value="135",
            session_example_value="1",
        )
        assert subject == "132"


class TestApplyFolderPlaceholders:
    def test_substitutes_subject_and_session(self):
        name = apply_folder_placeholders(
            "{subject}_{session}_physio.vpd", "sub-006/ses-1/data.vpd"
        )
        assert name == "006_1_physio.vpd"

    def test_raises_when_subject_placeholder_unresolvable(self):
        import pytest

        with pytest.raises(ValueError):
            apply_folder_placeholders("{subject}_physio.vpd", "data.vpd")

    def test_drops_session_placeholder_cleanly_when_absent(self):
        name = apply_folder_placeholders(
            "sub-{subject}_ses-{session}_physio.vpd",
            "sub-006/data.vpd",
            session_level_from_end=1,
        )
        assert "ses-{session}" not in name
        assert name.startswith("sub-006")


class TestSubjectRewrite:
    def test_normalize_defaults_to_keep(self):
        assert normalize_subject_rewrite_mode(None) == "keep"
        assert normalize_subject_rewrite_mode("bogus") == "keep"
        assert normalize_subject_rewrite_mode("LAST3") == "last3"

    def test_rewrite_label_keeps_last_three_digits(self):
        assert rewrite_subject_label("sub-1291003", "last3") == "sub-003"

    def test_rewrite_label_noop_in_keep_mode(self):
        assert rewrite_subject_label("sub-1291003", "keep") == "sub-1291003"

    def test_rewrite_in_filename(self):
        assert (
            rewrite_subject_in_filename("sub-1291003_task-rest_physio.vpd", "last3")
            == "sub-003_task-rest_physio.vpd"
        )

    def test_rewrite_in_relative_path(self):
        from pathlib import Path

        result = rewrite_subject_in_relative_path(
            Path("sub-1291003/sub-1291003_physio.vpd"), "last3"
        )
        assert result == Path("sub-003/sub-003_physio.vpd")


class TestProjectDestRoot:
    def test_root_alias_maps_to_prism(self):
        assert normalize_project_dest_root("root") == "prism"

    def test_invalid_falls_back_to_prism(self):
        assert normalize_project_dest_root("bogus") == "prism"

    def test_resolve_appends_subfolder_for_rawdata(self, tmp_path):
        result = resolve_project_copy_root(tmp_path, "rawdata")
        assert result == tmp_path / "rawdata"

    def test_resolve_stays_at_root_for_prism(self, tmp_path):
        result = resolve_project_copy_root(tmp_path, "prism")
        assert result == tmp_path

    def test_flat_copy_only_for_rawdata_sourcedata(self):
        assert should_use_flat_project_copy("rawdata", True) is True
        assert should_use_flat_project_copy("prism", True) is False
        assert should_use_flat_project_copy("rawdata", False) is False


class TestComputeOrganizedRelativePath:
    def test_returns_filename_unchanged_when_not_organizing(self):
        assert (
            compute_organized_relative_path("sub-001_task-rest.vpd", modality="physio", organize=False)
            == "sub-001_task-rest.vpd"
        )

    def test_builds_bids_path_when_organizing(self):
        def _fake_parse_bids_filename(name):
            return {"sub": "sub-001", "ses": "ses-1"}

        result = compute_organized_relative_path(
            "sub-001_ses-1_task-rest.vpd",
            modality="physio",
            organize=True,
            parse_bids_filename=_fake_parse_bids_filename,
        )
        assert result == "sub-001/ses-1/physio/sub-001_ses-1_task-rest.vpd"

    def test_returns_filename_when_parse_fails(self):
        result = compute_organized_relative_path(
            "not-bids.vpd",
            modality="physio",
            organize=True,
            parse_bids_filename=lambda name: None,
        )
        assert result == "not-bids.vpd"


class TestComputeRenamedFilename:
    def test_applies_regex_and_normalization(self):
        pattern = re.compile(r"^raw_")
        result = compute_renamed_filename(
            "raw_café.vpd", pattern=pattern, replacement="clean_"
        )
        assert result == "clean_cafe.vpd"

    def test_folder_id_source_applies_placeholders(self):
        pattern = re.compile(r"^VPDATA\.RAW$")
        result = compute_renamed_filename(
            "sub-07/ses-03/VPDATA.RAW",
            pattern=pattern,
            replacement="sub-{subject}_ses-{session}_physio.raw",
            id_source="folder",
        )
        assert result == "sub-07_ses-03_physio.raw"


class TestPlanRename:
    def test_previews_multiple_entries(self):
        results, warnings = plan_rename(
            [("raw_a.vpd", "raw_a.vpd"), ("raw_b.vpd", "raw_b.vpd")],
            pattern=r"^raw_",
            replacement="clean_",
        )
        assert warnings == []
        assert [r["new"] for r in results] == ["clean_a.vpd", "clean_b.vpd"]
        assert all(r["success"] for r in results)

    def test_invalid_regex_raises(self):
        import pytest

        with pytest.raises(ValueError):
            plan_rename([("a.vpd", "a.vpd")], pattern="(unclosed", replacement="x")

    def test_failed_entry_reports_error_without_raising(self):
        # No folder structure at all -> {subject} placeholder can't resolve,
        # which apply_folder_placeholders raises ValueError for; plan_rename
        # must catch it per-entry rather than letting the whole batch fail.
        results, _ = plan_rename(
            [("data.vpd", "data.vpd")],
            pattern=r"^data\.vpd$",
            replacement="{subject}_physio.vpd",
            id_source="folder",
        )
        assert results[0]["success"] is False
        assert "subject" in results[0]["new"].lower()

    def test_organize_uses_bids_parser_when_provided(self):
        def _fake_parse_bids_filename(name):
            return {"sub": "sub-001", "ses": None}

        results, _ = plan_rename(
            [("sub-001_task-rest.vpd", "sub-001_task-rest.vpd")],
            pattern=r"^sub-001",
            replacement="sub-001",
            modality="physio",
            organize=True,
            parse_bids_filename=_fake_parse_bids_filename,
        )
        assert results[0]["path"] == "sub-001/physio/sub-001_task-rest.vpd"
