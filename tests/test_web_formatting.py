"""
Unit tests for web formatting functions
"""

import os
import sys

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from src.web.utils import (
    format_validation_results,
    get_error_description,
    get_error_documentation_url,
    shorten_path,
    get_filename_from_path,
)


class MockDatasetStats:
    """Mock DatasetStats for testing"""

    def __init__(self, total_files=0):
        self.total_files = total_files


class TestFormatValidationResults:
    """Test the format_validation_results function"""

    def test_format_with_tuple_issues(self):
        """Test formatting with tuple-based issues (level, message)"""
        issues = [
            ("ERROR", "Invalid BIDS filename format: sub-01_task-test.tsv"),
            ("ERROR", "Missing sidecar for sub-01_task-test.tsv"),
            ("WARNING", "Inconsistent session structure"),
        ]
        stats = MockDatasetStats(total_files=10)

        results = format_validation_results(issues, stats, "/test/dataset")

        assert results["summary"]["total_files"] == 10
        assert results["summary"]["total_errors"] == 2
        assert results["summary"]["total_warnings"] == 1
        assert not results["valid"]
        # New PRISM error code system
        assert "PRISM101" in results["error_groups"]

    def test_format_with_dict_issues(self):
        """Test formatting with dict-based issues"""
        issues = [
            {
                "type": "ERROR",
                "message": "Invalid filename",
                "file": "/path/to/file.tsv",
            },
            {
                "level": "WARNING",
                "message": "Pattern mismatch",
                "file": "/path/to/other.json",
            },
        ]
        stats = MockDatasetStats(total_files=5)

        results = format_validation_results(issues, stats, "/test/dataset")

        assert results["summary"]["total_errors"] == 1
        assert results["summary"]["total_warnings"] == 1
        assert len(results["errors"]) == 1
        assert len(results["warnings"]) == 1

    def test_format_with_no_issues(self):
        """Test formatting with no issues (valid dataset)"""
        issues = []
        stats = MockDatasetStats(total_files=20)

        results = format_validation_results(issues, stats, "/test/dataset")

        assert results["valid"]
        assert results["summary"]["total_errors"] == 0
        assert results["summary"]["total_warnings"] == 0
        assert results["summary"]["total_files"] == 20

    def test_format_with_path_extraction(self):
        """Test that file paths are extracted from messages"""
        issues = [
            ("ERROR", "Invalid BIDS filename format: task-recognition_stim.json"),
            ("ERROR", "Missing dataset_description.json"),
        ]
        stats = MockDatasetStats(total_files=0)

        results = format_validation_results(issues, stats, "/test/dataset")

        # Should extract filenames and count them
        assert results["summary"]["invalid_files"] == 2

    def test_error_code_grouping(self):
        """Test that errors are grouped by error code"""
        issues = [
            ("ERROR", "Invalid BIDS filename format: file1.tsv"),
            ("ERROR", "Invalid BIDS filename format: file2.tsv"),
            ("ERROR", "Missing sidecar for file3.nii.gz"),
        ]
        stats = MockDatasetStats(total_files=5)

        results = format_validation_results(issues, stats, "/test/dataset")

        # New PRISM error codes: PRISM101 for filename, PRISM201 for sidecar
        assert "PRISM101" in results["error_groups"]
        assert "PRISM201" in results["error_groups"]
        assert results["error_groups"]["PRISM101"]["count"] == 2
        assert results["error_groups"]["PRISM201"]["count"] == 1


class TestErrorDescriptionFunctions:
    """Test error description and documentation URL functions"""

    def test_get_error_description(self):
        """Test getting error descriptions"""
        # New PRISM error codes
        desc = get_error_description("PRISM101")
        assert "BIDS naming convention" in desc or "filename" in desc.lower()

        desc = get_error_description("PRISM201")
        assert "sidecar" in desc.lower()

        # Unknown code should return default
        desc = get_error_description("UNKNOWN_CODE")
        assert desc is not None

    def test_get_error_documentation_url(self):
        """Test getting documentation URLs"""
        url = get_error_documentation_url("PRISM101")
        # URL now points to ReadTheDocs HTML
        assert "ERROR_CODES" in url.upper() or "error" in url.lower()
        assert "prism101" in url.lower()

        url = get_error_documentation_url("UNKNOWN_CODE")
        assert "ERROR_CODES" in url.upper() or "error" in url.lower()


class TestPathUtilities:
    """Test path shortening and filename extraction"""

    def test_shorten_path_long(self):
        """Test shortening a long path"""
        path = "/very/long/path/to/dataset/sub-01/ses-01/func/sub-01_ses-01_task-test_bold.nii.gz"
        short = shorten_path(path, max_parts=3)

        assert short.startswith(".../")
        assert "bold.nii.gz" in short
        assert len(short) < len(path)

    def test_shorten_path_short(self):
        """Test shortening a path that's already short"""
        path = "sub-01/file.tsv"
        short = shorten_path(path, max_parts=3)

        assert short == path
        assert not short.startswith(".../")

    def test_shorten_path_none(self):
        """Test shortening None/empty path"""
        assert shorten_path(None) == "General"
        assert shorten_path("") == "General"

    def test_get_filename_from_path(self):
        """Test extracting filename from path"""
        path = "/path/to/sub-01_task-test_bold.nii.gz"
        filename = get_filename_from_path(path)

        assert filename == "sub-01_task-test_bold.nii.gz"
        assert "/" not in filename

    def test_get_filename_from_path_none(self):
        """Test extracting filename from None/empty"""
        assert get_filename_from_path(None) == "General"
        assert get_filename_from_path("") == "General"


if __name__ == "__main__":
    # Simple test runner
    import traceback

    test_classes = [
        TestFormatValidationResults,
        TestErrorDescriptionFunctions,
        TestPathUtilities,
    ]

    passed = 0
    failed = 0

    print("Running tests for web_interface.py formatting...")
    print("=" * 60)

    for test_class in test_classes:
        test_instance = test_class()
        test_methods = [m for m in dir(test_instance) if m.startswith("test_")]

        for method_name in test_methods:
            try:
                method = getattr(test_instance, method_name)
                method()
                print(f"✅ {test_class.__name__}.{method_name}")
                passed += 1
            except Exception as e:
                print(f"❌ {test_class.__name__}.{method_name}")
                print(f"   {str(e)}")
                traceback.print_exc()
                failed += 1

    print("=" * 60)
    print(f"Results: {passed} passed, {failed} failed")
    sys.exit(0 if failed == 0 else 1)
