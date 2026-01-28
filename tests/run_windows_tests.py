#!/usr/bin/env python3
"""
Master test runner for all Windows-specific PRISM tests.
Runs all Windows compatibility, path handling, web upload, and dataset validation tests.
"""

import os
import sys
import subprocess
from datetime import datetime


def run_test_file(test_file, description):
    """Run a single test file and return results"""
    print(f"\n{'=' * 70}")
    print(f"🧪 {description}")
    print(f"{'=' * 70}")
    
    try:
        result = subprocess.run(
            [sys.executable, test_file],
            capture_output=True,
            text=True,
            timeout=300  # 5 minute timeout
        )
        
        print(result.stdout)
        if result.stderr:
            print("STDERR:", result.stderr)
        
        return result.returncode == 0
        
    except subprocess.TimeoutExpired:
        print(f"❌ Test timed out after 5 minutes")
        return False
    except Exception as e:
        print(f"❌ Error running test: {e}")
        return False


def main():
    """Run all Windows-specific tests"""
    print("=" * 70)
    print("🪟 PRISM WINDOWS TEST SUITE")
    print("=" * 70)
    print(f"Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Platform: {sys.platform}")
    print(f"Python: {sys.version}")
    
    if not sys.platform.startswith("win"):
        print("\n⚠️  WARNING: Not running on Windows!")
        print("These tests are designed for Windows but will run on any platform.")
        print("Results may differ from actual Windows behavior.\n")
    
    # Get tests directory
    tests_dir = os.path.dirname(os.path.abspath(__file__))
    
    # Define all test files
    test_suites = [
        ("test_windows_compatibility.py", "Core Windows Compatibility"),
        ("test_windows_paths.py", "Windows Path & Filename Handling"),
        ("test_windows_web_uploads.py", "Windows Web Interface Uploads"),
        ("test_windows_datasets.py", "Windows Dataset Validation"),
        ("test_github_signing.py", "GitHub Actions Code Signing"),
    ]
    
    results = {}
    
    # Run each test suite
    for test_file, description in test_suites:
        test_path = os.path.join(tests_dir, test_file)
        
        if not os.path.exists(test_path):
            print(f"\n⚠️  Test file not found: {test_file}")
            results[description] = False
            continue
        
        success = run_test_file(test_path, description)
        results[description] = success
    
    # Summary
    print("\n" + "=" * 70)
    print("📊 WINDOWS TEST SUITE SUMMARY")
    print("=" * 70)
    
    total_suites = len(results)
    passed_suites = sum(1 for v in results.values() if v)
    
    for description, success in results.items():
        status = "✅ PASS" if success else "❌ FAIL"
        print(f"{status} - {description}")
    
    print("-" * 70)
    print(f"Result: {passed_suites}/{total_suites} test suites passed")
    print(f"Finished: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    if passed_suites == total_suites:
        print("\n🎉 All Windows test suites passed!")
        return 0
    else:
        print(f"\n❌ {total_suites - passed_suites} test suite(s) failed")
        return 1


if __name__ == "__main__":
    sys.exit(main())
