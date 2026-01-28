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

from runner import validate_dataset

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
