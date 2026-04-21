"""
Unit tests for src/runner.py validation functions - uses demo folder
"""

import os
import sys
import tempfile
from pathlib import Path

# Add app/src to path for testing
sys.path.insert(
    0, os.path.join(os.path.dirname(os.path.dirname(__file__)), "app", "src")
)

import runner
from runner import validate_dataset
from stats import DatasetStats
from validator import DatasetValidator
import validator as validator_module

import pytest

# Path to demo folder for testing
REPO_ROOT = Path(__file__).resolve().parents[1]
DEMO_PRISM_DATASET = REPO_ROOT / "examples" / "demos" / "prism_structure_example"


class TestValidateDataset:
    """Test the main validate_dataset function using demo data"""

    @pytest.mark.skipif(
        not DEMO_PRISM_DATASET.exists(), reason="Demo dataset not found"
    )
    def test_validate_demo_dataset(self):
        """Test validation of the demo PRISM dataset"""
        issues, stats = validate_dataset(str(DEMO_PRISM_DATASET), verbose=False)

        # Should have stats
        assert stats is not None
        assert stats.total_files > 0

        # Demo dataset should be valid (no errors)
        errors = [issue for issue in issues if issue[0] == "ERROR"]
        assert len(errors) == 0, f"Expected no errors in demo dataset, got: {errors}"

    @pytest.mark.skipif(
        not DEMO_PRISM_DATASET.exists(), reason="Demo dataset not found"
    )
    def test_validate_demo_has_subjects(self):
        """Test that demo dataset stats include subjects"""
        issues, stats = validate_dataset(str(DEMO_PRISM_DATASET), verbose=False)

        assert "sub-001" in stats.subjects or "sub-002" in stats.subjects
        assert len(stats.subjects) >= 2

    @pytest.mark.skipif(
        not DEMO_PRISM_DATASET.exists(), reason="Demo dataset not found"
    )
    def test_validate_demo_has_modalities(self):
        """Test that demo dataset stats include modalities"""
        issues, stats = validate_dataset(str(DEMO_PRISM_DATASET), verbose=False)

        # Demo has eyetrack and physio
        assert len(stats.modalities) > 0

    def test_validate_nonexistent_dataset(self):
        """Test validation handles nonexistent directory gracefully"""
        nonexistent = "/tmp/does_not_exist_prism_test_12345"

        try:
            issues, stats = validate_dataset(nonexistent, verbose=False)
            assert False, "Should raise an error for nonexistent directory"
        except (FileNotFoundError, OSError, ValueError):
            pass  # Expected

    def test_validate_empty_dataset(self):
        """Test validation of an empty dataset"""
        with tempfile.TemporaryDirectory() as tmp_dir:
            issues, stats = validate_dataset(tmp_dir, verbose=False)

            # Should detect missing dataset_description.json
            error_messages = [issue[1] for issue in issues if issue[0] == "ERROR"]
            assert any("dataset_description.json" in msg for msg in error_messages)

            # Stats should show zero files
            assert stats.total_files == 0

    def test_invalid_citation_cff_is_prism_error(self, tmp_path, monkeypatch):
        """Malformed CITATION.cff should surface as a PRISM validation error."""
        (tmp_path / "dataset_description.json").write_text(
            '{"Name": "Demo", "BIDSVersion": "1.10.1", "DatasetType": "raw", "Authors": ["Demo Author"], "Keywords": ["one", "two", "three"]}',
            encoding="utf-8",
        )
        # Missing required keys like 'message' and 'authors' entries.
        (tmp_path / "CITATION.cff").write_text(
            'cff-version: 1.2.0\ntitle: "Demo"\n',
            encoding="utf-8",
        )

        def fake_validate_subject(
            _subject_dir,
            subject_id,
            _validator,
            stats,
            _root_dir,
            run_prism=True,
        ):
            stats.subjects.add(subject_id)
            return []

        monkeypatch.setattr(runner, "_validate_subject", fake_validate_subject)
        (tmp_path / "sub-01").mkdir(parents=True)

        issues, _stats = validate_dataset(
            str(tmp_path),
            verbose=False,
            run_prism=True,
            run_bids=False,
        )

        error_messages = [msg for level, msg, *_rest in issues if level == "ERROR"]
        assert any("PRISM303" in msg and "CITATION.cff" in msg for msg in error_messages)

    def test_invalid_citation_cff_is_ignored_in_bids_only_mode(
        self, tmp_path, monkeypatch
    ):
        """BIDS-only mode should not emit PRISM citation validation errors."""
        (tmp_path / "dataset_description.json").write_text(
            '{"Name": "Demo", "BIDSVersion": "1.10.1", "DatasetType": "raw"}',
            encoding="utf-8",
        )
        (tmp_path / "CITATION.cff").write_text(
            'cff-version: 1.2.0\ntitle: "Demo"\n',
            encoding="utf-8",
        )

        monkeypatch.setattr(runner, "_run_bids_validator", lambda *_args, **_kwargs: [])

        issues, _stats = validate_dataset(
            str(tmp_path),
            verbose=False,
            run_prism=False,
            run_bids=True,
        )

        messages = [msg for _level, msg, *_rest in issues]
        assert not any("PRISM303" in msg for msg in messages)

    def test_dataset_description_authors_not_required_when_citation_exists(
        self, tmp_path, monkeypatch
    ):
        """Authors requirement should be relaxed when CITATION.cff is present."""
        (tmp_path / "dataset_description.json").write_text(
            '{"Name": "Demo", "BIDSVersion": "1.10.1", "DatasetType": "raw", "Keywords": ["one", "two", "three"]}',
            encoding="utf-8",
        )
        (tmp_path / "CITATION.cff").write_text(
            "\n".join(
                [
                    "cff-version: 1.2.0",
                    'title: "Demo"',
                    'message: "Please cite."',
                    "authors:",
                    '  - family-names: "Author"',
                    '    given-names: "Demo"',
                    "",
                ]
            ),
            encoding="utf-8",
        )

        def fake_validate_subject(
            _subject_dir,
            subject_id,
            _validator,
            stats,
            _root_dir,
            run_prism=True,
        ):
            stats.subjects.add(subject_id)
            return []

        monkeypatch.setattr(runner, "_validate_subject", fake_validate_subject)
        (tmp_path / "sub-01").mkdir(parents=True)

        issues, _stats = validate_dataset(
            str(tmp_path),
            verbose=False,
            run_prism=True,
            run_bids=False,
        )

        error_messages = [msg for level, msg, *_rest in issues if level == "ERROR"]
        assert not any("'Authors' is a required property" in msg for msg in error_messages)

    def test_nested_derivative_dataset_description_is_accepted(self):
        """Variant subfolders under derivatives should satisfy metadata checks."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            (root / "dataset_description.json").write_text(
                '{"Name": "Root dataset", "BIDSVersion": "1.8.0"}',
                encoding="utf-8",
            )

            variant_dir = root / "derivatives" / "survey" / "wide_de"
            variant_dir.mkdir(parents=True)
            (variant_dir / "dataset_description.json").write_text(
                (
                    '{"Name": "Survey derivative", '
                    '"BIDSVersion": "1.8.0", '
                    '"DatasetType": "derivative"}'
                ),
                encoding="utf-8",
            )

            issues, stats = validate_dataset(tmp_dir, verbose=False)

            warning_messages = [issue[1] for issue in issues if issue[0] == "WARNING"]
            assert not any(
                "Derivatives dataset 'survey' is missing dataset_description.json"
                in msg
                for msg in warning_messages
            )

    def test_bids_only_mode_skips_prism_specific_checks(self, monkeypatch, tmp_path):
        """BIDS-only runs must not include PRISM-only consistency/derivative checks."""
        (tmp_path / "derivatives" / "pipeline").mkdir(parents=True)

        def fake_consistency(_self):
            return [
                (
                    "WARNING",
                    "Consistency warning from stats",
                    str(tmp_path),
                )
            ]

        monkeypatch.setattr(DatasetStats, "check_consistency", fake_consistency)
        monkeypatch.setattr(runner, "_run_bids_validator", lambda *_args, **_kwargs: [])

        issues, _stats = validate_dataset(
            str(tmp_path),
            verbose=False,
            run_bids=True,
            run_prism=False,
        )

        messages = [issue[1] for issue in issues]
        assert not any("Consistency warning from stats" in msg for msg in messages)
        assert not any("No subjects found in dataset" in msg for msg in messages)
        assert not any(
            "Derivatives dataset 'pipeline' is missing dataset_description.json" in msg
            for msg in messages
        )

    def test_prism_mode_keeps_prism_specific_checks(self, monkeypatch, tmp_path):
        """PRISM runs should continue to emit PRISM-only consistency/derivative checks."""
        (tmp_path / "derivatives" / "pipeline").mkdir(parents=True)

        def fake_consistency(_self):
            return [
                (
                    "WARNING",
                    "Consistency warning from stats",
                    str(tmp_path),
                )
            ]

        monkeypatch.setattr(DatasetStats, "check_consistency", fake_consistency)
        monkeypatch.setattr(runner, "_run_bids_validator", lambda *_args, **_kwargs: [])

        issues, _stats = validate_dataset(
            str(tmp_path),
            verbose=False,
            run_bids=False,
            run_prism=True,
        )

        messages = [issue[1] for issue in issues]
        assert any("Consistency warning from stats" in msg for msg in messages)
        assert any("No subjects found in dataset" in msg for msg in messages)
        assert any(
            "Derivatives dataset 'pipeline' is missing dataset_description.json" in msg
            for msg in messages
        )

    def test_bids_mri_files_skip_unneeded_sidecar_resolution(
        self, monkeypatch, tmp_path
    ):
        """MRI/BIDS files without task entities should not resolve sidecars for stats."""
        anat_dir = tmp_path / "sub-01" / "ses-01" / "anat"
        anat_dir.mkdir(parents=True)
        (anat_dir / "sub-01_ses-01_T1w.nii.gz").write_bytes(b"nifti")
        (anat_dir / "sub-01_ses-01_T1w.json").write_text(
            '{"Study": {"OriginalName": "Structural MRI"}}',
            encoding="utf-8",
        )

        def unexpected_resolve(*args, **kwargs):
            raise AssertionError("resolve_sidecar_path should not be called here")

        monkeypatch.setattr(runner, "resolve_sidecar_path", unexpected_resolve)

        issues = runner._validate_modality_dir(
            str(anat_dir),
            "sub-01",
            "ses-01",
            "anat",
            DatasetValidator(),
            DatasetStats(),
            str(tmp_path),
        )

        assert issues == []

    def test_sidecar_json_is_cached_across_validation_steps(
        self, monkeypatch, tmp_path
    ):
        """Repeated validation work should reuse the same parsed sidecar JSON."""
        survey_dir = tmp_path / "sub-01" / "ses-01" / "survey"
        survey_dir.mkdir(parents=True)

        data_file = survey_dir / "sub-01_ses-01_task-demo_survey.tsv"
        data_file.write_text("item1\n1\n", encoding="utf-8")

        sidecar_file = survey_dir / "sub-01_ses-01_task-demo_survey.json"
        sidecar_file.write_text(
            (
                '{"Study": {"OriginalName": "Demo Survey"}, '
                '"item1": {"DataType": "integer", "AllowedValues": [1, 2, 3]}}'
            ),
            encoding="utf-8",
        )

        validator = DatasetValidator()
        read_count = 0
        original_read_text = validator_module.CrossPlatformFile.read_text

        def counting_read_text(path):
            nonlocal read_count
            read_count += 1
            return original_read_text(path)

        monkeypatch.setattr(
            validator_module.CrossPlatformFile, "read_text", counting_read_text
        )

        assert (
            validator.get_sidecar_original_name(str(data_file), str(tmp_path))
            == "Demo Survey"
        )
        assert validator.validate_sidecar(str(data_file), "survey", str(tmp_path)) == []
        assert (
            validator.validate_data_content(str(data_file), "survey", str(tmp_path))
            == []
        )
        assert read_count == 1

    def test_json_sidecars_skip_data_content_validation(self, monkeypatch, tmp_path):
        """JSON sidecars should not be re-validated as tabular data content."""
        survey_dir = tmp_path / "sub-01" / "ses-01" / "survey"
        survey_dir.mkdir(parents=True)

        data_file = survey_dir / "sub-01_ses-01_task-demo_survey.tsv"
        data_file.write_text("item1\n1\n", encoding="utf-8")
        sidecar_file = survey_dir / "sub-01_ses-01_task-demo_survey.json"
        sidecar_file.write_text(
            '{"Study": {"OriginalName": "Demo Survey"}}',
            encoding="utf-8",
        )

        validator = DatasetValidator()
        seen_paths = []

        def fake_validate_filename(*args, **kwargs):
            return []

        def fake_validate_sidecar(*args, **kwargs):
            return []

        def fake_validate_data_content(file_path, modality, root_dir):
            seen_paths.append(Path(file_path).name)
            return []

        monkeypatch.setattr(validator, "validate_filename", fake_validate_filename)
        monkeypatch.setattr(validator, "validate_sidecar", fake_validate_sidecar)
        monkeypatch.setattr(
            validator, "validate_data_content", fake_validate_data_content
        )

        runner._validate_modality_dir(
            str(survey_dir),
            "sub-01",
            "ses-01",
            "survey",
            validator,
            DatasetStats(),
            str(tmp_path),
        )

        assert seen_paths == [data_file.name]


class TestSurveyRecipeCoverage:
    """Tests for _check_survey_recipe_coverage"""

    def test_no_survey_files_no_warning(self):
        """No warning when there are no survey data files."""
        from runner import _check_survey_recipe_coverage

        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            (root / "sub-001" / "ses-01" / "beh").mkdir(parents=True)
            (
                root / "sub-001" / "ses-01" / "beh" / "sub-001_ses-01_task-demo_beh.tsv"
            ).write_text("col1\tval1\n")

            issues = _check_survey_recipe_coverage(tmp_dir)
            assert issues == []

    def test_survey_files_without_recipes_raises_warning(self):
        """Warning is raised when survey TSV files exist but no recipe JSON."""
        from runner import _check_survey_recipe_coverage

        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            (root / "sub-001" / "ses-01" / "survey").mkdir(parents=True)
            (
                root
                / "sub-001"
                / "ses-01"
                / "survey"
                / "sub-001_ses-01_task-demo_survey.tsv"
            ).write_text("col1\tval1\n")

            issues = _check_survey_recipe_coverage(tmp_dir)
            assert len(issues) == 1
            assert issues[0][0] == "WARNING"
            assert "recipe" in issues[0][1].lower()

    def test_survey_files_with_recipes_no_warning(self):
        """No warning when both survey data files and recipe JSON exist."""
        from runner import _check_survey_recipe_coverage

        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            (root / "sub-001" / "ses-01" / "survey").mkdir(parents=True)
            (
                root
                / "sub-001"
                / "ses-01"
                / "survey"
                / "sub-001_ses-01_task-demo_survey.tsv"
            ).write_text("col1\tval1\n")
            recipe_dir = root / "code" / "recipes" / "survey"
            recipe_dir.mkdir(parents=True)
            (recipe_dir / "recipe-demo.json").write_text('{"RecipeVersion": "1.0"}')

            issues = _check_survey_recipe_coverage(tmp_dir)
            assert issues == []


if __name__ == "__main__":
    import traceback

    test_class = TestValidateDataset()
    test_methods = [m for m in dir(test_class) if m.startswith("test_")]

    passed = 0
    failed = 0

    print("Running tests for src/runner.py...")
    print("=" * 60)

    for method_name in test_methods:
        try:
            method = getattr(test_class, method_name)
            method()
            print(f"✅ {method_name}")
            passed += 1
        except Exception as e:
            print(f"❌ {method_name}")
            print(f"   {str(e)}")
            traceback.print_exc()
            failed += 1

    print("=" * 60)
    print(f"Results: {passed} passed, {failed} failed")
    sys.exit(0 if failed == 0 else 1)
