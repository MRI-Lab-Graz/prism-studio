#!/usr/bin/env python3
"""
Quick test to verify the reorganized structure works
"""

import os
import sys
import subprocess


def test_streamlined_version():
    """Test the main validator"""
    print("🧪 Testing main validator...")

    # Test from project root
    project_root = os.path.dirname(os.path.dirname(__file__))

    # Test help command
    try:
        result = subprocess.run(
            [
                sys.executable,
                os.path.join(project_root, "prism.py"),
                "--help",
            ],
            capture_output=True,
            text=True,
            timeout=10,
        )

        if result.returncode == 0 and "PRISM" in result.stdout:
            print("✅ Main validator help works")
            return True
        else:
            print("❌ Main validator help failed")
            print(f"Return code: {result.returncode}")
            print(f"Output: {result.stdout}")
            print(f"Error: {result.stderr}")
            return False

    except Exception as e:
        print(f"❌ Error testing main validator: {e}")
        return False


def test_module_imports():
    """Test that our modules can be imported"""
    print("🧪 Testing module imports...")

    # Add src to path
    current_dir = os.path.dirname(os.path.dirname(__file__))
    src_path = os.path.join(current_dir, "src")
    sys.path.insert(0, src_path)

    try:
        from validator import DatasetValidator, MODALITY_PATTERNS
        from schema_manager import load_all_schemas
        from stats import DatasetStats
        from reporting import print_dataset_summary

        print("✅ All core modules import successfully")
        print(f"   - Found {len(MODALITY_PATTERNS)} modality patterns")

        # Test basic functionality
        stats = DatasetStats()
        stats.add_file("sub-001", None, "image", "test", "test.png")

        if len(stats.subjects) == 1 and len(stats.modalities) == 1:
            print("✅ Basic stats functionality works")
            return True
        else:
            print("❌ Stats functionality failed")
            return False

    except ImportError as e:
        print(f"❌ Import error: {e}")
        return False
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        return False


def test_directory_structure():
    """Test that the reorganized structure is correct"""
    print("🧪 Testing directory structure...")

    # Test from project root, not tests directory
    project_root = os.path.dirname(os.path.dirname(__file__))
    os.chdir(project_root)

    expected_dirs = ["src", "scripts", "tests", "docs", "schemas"]
    expected_files = ["prism.py", "README.md", "requirements.txt", "setup.py"]

    missing_dirs = []
    missing_files = []

    for dir_name in expected_dirs:
        if not os.path.isdir(dir_name):
            missing_dirs.append(dir_name)

    for file_name in expected_files:
        if not os.path.isfile(file_name):
            missing_files.append(file_name)

    if not missing_dirs and not missing_files:
        print("✅ Directory structure is correct")
        return True
    else:
        if missing_dirs:
            print(f"❌ Missing directories: {missing_dirs}")
        if missing_files:
            print(f"❌ Missing files: {missing_files}")
        return False


def main():
    print("🔍 REORGANIZATION VERIFICATION")
    print("=" * 50)

    tests = [
        ("Directory Structure", test_directory_structure),
        ("Module Imports", test_module_imports),
        ("Main Validator", test_streamlined_version),
    ]

    passed = 0
    total = len(tests)

    for test_name, test_func in tests:
        print(f"\n📋 {test_name}")
        print("-" * 30)
        if test_func():
            passed += 1
        print()

    print("=" * 50)
    print(f"📊 RESULTS: {passed}/{total} tests passed")

    if passed == total:
        print("🎉 Reorganization successful!")
        return 0
    else:
        print("❌ Some tests failed - check the reorganization")
        return 1


if __name__ == "__main__":
    sys.exit(main())
