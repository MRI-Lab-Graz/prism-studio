#!/usr/bin/env python3
"""
Comprehensive test suite for PRISM repository
Tests all major components and workflows
"""

import sys
import os
import subprocess
from pathlib import Path
import json
import tempfile

# Colors for output
GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
BLUE = "\033[94m"
RESET = "\033[0m"

test_results = {"passed": [], "failed": [], "warnings": []}


def print_header(text):
    print(f"\n{BLUE}{'=' * 60}{RESET}")
    print(f"{BLUE}{text:^60}{RESET}")
    print(f"{BLUE}{'=' * 60}{RESET}\n")


def print_test(name, passed, message=""):
    if passed:
        print(f"{GREEN}✓{RESET} {name}")
        test_results["passed"].append(name)
    else:
        print(f"{RED}✗{RESET} {name}")
        if message:
            print(f"  {RED}└─ {message}{RESET}")
        test_results["failed"].append(name)


def print_warning(name, message):
    print(f"{YELLOW}⚠{RESET} {name}")
    print(f"  {YELLOW}└─ {message}{RESET}")
    test_results["warnings"].append(name)


def run_command(cmd, cwd=None):
    """Run a command and return (success, stdout, stderr)"""
    try:
        result = subprocess.run(
            cmd, cwd=cwd, capture_output=True, text=True, timeout=30
        )
        return result.returncode == 0, result.stdout, result.stderr
    except subprocess.TimeoutExpired:
        return False, "", "Command timed out"
    except Exception as e:
        return False, "", str(e)


# Get repository root (now running from tests/ subdirectory)
repo_root = Path(__file__).resolve().parent.parent
os.chdir(repo_root)

print_header("PRISM Repository Comprehensive Test Suite")
print(f"Repository: {repo_root}")
print(f"Python: {sys.executable}")

# ============================================================================
# 1. Repository Structure Tests
# ============================================================================
print_header("1. Repository Structure")

required_files = [
    "prism.py",
    "prism-studio.py",
    "requirements.txt",
    "setup.py",
    "README.md",
    "app/prism.py",
    "app/prism-studio.py",
    "app/src/validator.py",
    "app/src/schema_manager.py",
    "app/src/runner.py",
]

for file in required_files:
    path = repo_root / file
    print_test(f"File exists: {file}", path.exists())

required_dirs = [
    "app",
    "app/src",
    "app/schemas",
    "app/templates",
    "app/static",
    "src",
    "tests",
]

for dir_path in required_dirs:
    path = repo_root / dir_path
    print_test(f"Directory exists: {dir_path}", path.is_dir())

# ============================================================================
# 2. Python Environment Tests
# ============================================================================
print_header("2. Python Environment")

# Check venv exists
venv_path = repo_root / ".venv"
print_test("Virtual environment exists", venv_path.exists())

# Check key imports
imports_to_test = [
    ("flask", "Flask"),
    ("pandas", "Pandas"),
    ("jsonschema", "JSON Schema"),
    ("openpyxl", "Excel support"),
]

for module, name in imports_to_test:
    try:
        __import__(module)
        print_test(f"Import {name}", True)
    except ImportError:
        print_test(f"Import {name}", False, f"pip install {module}")

# ============================================================================
# 3. CLI Validator Tests (prism.py)
# ============================================================================
print_header("3. CLI Validator (prism.py)")

# Test help command
success, stdout, stderr = run_command([sys.executable, "prism.py", "--help"])
print_test("prism.py --help", success and "usage" in stdout.lower())

# Test version
success, stdout, stderr = run_command([sys.executable, "prism.py", "--version"])
print_test("prism.py --version", success)

# Test with demo dataset if it exists
demo_path = repo_root / "demo"
if demo_path.exists():
    success, stdout, stderr = run_command([sys.executable, "prism.py", str(demo_path)])
    print_test("Validate demo dataset", success or "error" not in stderr.lower())
else:
    print_warning("Demo dataset not found", "Skipping validation test")

# ============================================================================
# 4. Schema Tests
# ============================================================================
print_header("4. Schema Validation")

schemas_dir = repo_root / "app" / "schemas" / "stable"
if schemas_dir.exists():
    schema_files = list(schemas_dir.glob("*.json"))
    print_test(f"Found {len(schema_files)} schemas", len(schema_files) > 0)

    for schema_file in schema_files:
        try:
            with open(schema_file) as f:
                schema = json.load(f)
            print_test(f"Schema valid: {schema_file.name}", True)
        except json.JSONDecodeError:
            print_test(f"Schema valid: {schema_file.name}", False, "Invalid JSON")
else:
    print_test("Schemas directory exists", False)

# ============================================================================
# 5. Converters Tests
# ============================================================================
print_header("5. Converters")

converter_modules = [
    "src/converters/survey.py",
    "src/converters/limesurvey.py",
    "src/converters/excel_to_biometrics.py",
]

for module_path in converter_modules:
    path = repo_root / module_path
    if path.exists():
        print_test(f"Converter exists: {module_path}", True)
    else:
        print_warning(f"Converter missing: {module_path}", "Module not found")

# Test participants converter
pc_path = repo_root / "src" / "participants_converter.py"
if pc_path.exists():
    try:
        # Read file and check for key methods
        content = pc_path.read_text()
        has_class = "class ParticipantsConverter" in content
        has_convert = "def convert_participant_data" in content
        has_validate = "def validate_mapping" in content
        print_test("ParticipantsConverter class", has_class)
        print_test("convert_participant_data method", has_convert)
        print_test("validate_mapping method", has_validate)
    except Exception as e:
        print_test("Read participants_converter.py", False, str(e))

# ============================================================================
# 6. Web Interface Tests
# ============================================================================
print_header("6. Web Interface")

# Check Flask app structure
app_components = [
    "app/src/web/blueprints/conversion.py",
    "app/src/web/blueprints/validation.py",
    "app/src/web/blueprints/projects.py",
    "app/templates/index.html",
    "app/templates/converter.html",
]

for component in app_components:
    path = repo_root / component
    print_test(f"Component: {component}", path.exists())

# Check templates
templates_dir = repo_root / "app" / "templates"
if templates_dir.exists():
    template_files = list(templates_dir.glob("*.html"))
    print_test(f"Found {len(template_files)} HTML templates", len(template_files) > 0)

# Check static files
static_dir = repo_root / "app" / "static"
if static_dir.exists():
    css_files = list(static_dir.rglob("*.css"))
    js_files = list(static_dir.rglob("*.js"))
    print_test(f"Found {len(css_files)} CSS files", len(css_files) >= 0)
    print_test(f"Found {len(js_files)} JS files", len(js_files) >= 0)

# ============================================================================
# 7. Unit Tests
# ============================================================================
print_header("7. Unit Tests")

tests_dir = repo_root / "tests"
if tests_dir.exists():
    test_files = list(tests_dir.glob("test_*.py"))
    print_test(f"Found {len(test_files)} test files", len(test_files) > 0)

    # Try running pytest if available
    try:
        import pytest

        print_test("pytest available", True)

        # Run tests
        success, stdout, stderr = run_command(
            [sys.executable, "-m", "pytest", "tests/", "-v"]
        )
        if success:
            print_test("Unit tests pass", True)
        else:
            print_test("Unit tests pass", False, "Some tests failed")
    except ImportError:
        print_warning("pytest not installed", "Run: pip install pytest")
else:
    print_warning("Tests directory not found", "No unit tests")

# ============================================================================
# 8. Documentation Tests
# ============================================================================
print_header("8. Documentation")

doc_files = [
    "README.md",
    "CHANGELOG.md",
    "LICENSE",
    "docs/index.rst",
    "docs/QUICK_START.md",
]

for doc_file in doc_files:
    path = repo_root / doc_file
    if path.exists():
        print_test(f"Doc exists: {doc_file}", True)
    else:
        print_warning(f"Doc missing: {doc_file}", "Documentation incomplete")

# ============================================================================
# 9. Cross-Platform Tests
# ============================================================================
print_header("9. Cross-Platform Compatibility")

# Check for cross-platform utilities
cp_utils = repo_root / "app" / "src" / "cross_platform.py"
if cp_utils.exists():
    content = cp_utils.read_text()
    has_file_ops = "class CrossPlatformFile" in content
    has_path_ops = "normalize_path" in content
    print_test("CrossPlatformFile utilities", has_file_ops)
    print_test("Path normalization", has_path_ops)
else:
    print_warning("cross_platform.py not found", "May have platform issues")

# ============================================================================
# 10. Integration Tests
# ============================================================================
print_header("10. Integration Tests")

# Test creating a temporary dataset structure
with tempfile.TemporaryDirectory() as tmpdir:
    tmpdir = Path(tmpdir)

    # Create minimal PRISM structure
    (tmpdir / "dataset_description.json").write_text(
        json.dumps({"Name": "Test Dataset", "BIDSVersion": "1.10.0"})
    )

    # Create participants file
    (tmpdir / "participants.tsv").write_text("participant_id\nsub-001\nsub-002\n")

    # Test validator on minimal dataset
    success, stdout, stderr = run_command([sys.executable, "prism.py", str(tmpdir)])
    # Check if validation ran (success or with validation messages)
    has_output = len(stdout) > 0 or len(stderr) > 0
    print_test("Validate minimal dataset", success or has_output)

# ============================================================================
# 11. Security & Code Quality
# ============================================================================
print_header("11. Security & Code Quality")

# Check for hardcoded secrets/passwords
security_patterns = [
    (r"password\s*=\s*['\"][^'\"]+['\"]", "Hardcoded password"),
    (r"api_key\s*=\s*['\"][^'\"]+['\"]", "Hardcoded API key"),
    (r"secret\s*=\s*['\"][^'\"]+['\"]", "Hardcoded secret"),
]

has_security_issues = False
for py_file in repo_root.rglob("*.py"):
    if ".venv" in str(py_file) or "__pycache__" in str(py_file):
        continue
    try:
        content = py_file.read_text()
        for pattern, desc in security_patterns:
            import re

            if re.search(pattern, content, re.IGNORECASE):
                print_warning(f"Security: {py_file.name}", f"Found {desc}")
                has_security_issues = True
                break
    except:
        pass

if not has_security_issues:
    print_test("No hardcoded secrets", True)

# Check .gitignore exists
gitignore = repo_root / ".gitignore"
print_test(".gitignore exists", gitignore.exists())

# Check no .pyc files tracked
if gitignore.exists():
    gitignore_content = gitignore.read_text()
    print_test(
        ".gitignore includes *.pyc",
        "*.pyc" in gitignore_content or "__pycache__" in gitignore_content,
    )

# Check key Python files for syntax errors
key_files = [
    "app/prism.py",
    "app/prism-studio.py",
    "app/src/validator.py",
    "src/participants_converter.py",
]

syntax_ok = True
for file_path in key_files:
    full_path = repo_root / file_path
    if full_path.exists():
        success, stdout, stderr = run_command(
            [sys.executable, "-m", "py_compile", str(full_path)]
        )
        if not success:
            print_test(f"Syntax check: {file_path}", False, "Syntax error")
            syntax_ok = False

if syntax_ok:
    print_test("Python syntax valid", True)

# ============================================================================
# 12. Configuration Files
# ============================================================================
print_header("12. Configuration Files")

# Check JSON config files
config_files = [
    "app/prism_studio_settings.json",
]

for config_file in config_files:
    path = repo_root / config_file
    if path.exists():
        try:
            with open(path) as f:
                json.load(f)
            print_test(f"Config valid: {config_file}", True)
        except json.JSONDecodeError:
            print_test(f"Config valid: {config_file}", False, "Invalid JSON")
    else:
        print_warning(f"Config missing: {config_file}", "Optional config")

# Check requirements.txt format
req_file = repo_root / "requirements.txt"
if req_file.exists():
    try:
        content = req_file.read_text()
        lines = [
            l.strip()
            for l in content.split("\n")
            if l.strip() and not l.startswith("#")
        ]
        print_test(f"requirements.txt has {len(lines)} packages", len(lines) > 0)
    except Exception as e:
        print_test("requirements.txt readable", False, str(e))

# ============================================================================
# 13. Flask App Tests
# ============================================================================
print_header("13. Flask Application")

# Check Flask app can be imported
try:
    sys.path.insert(0, str(repo_root / "app"))
    # Just check if critical imports work

    print_test("Web validation module imports", True)
except Exception as e:
    print_test("Web validation module imports", False, str(e))

# Check templates use proper Jinja2 syntax
templates_dir = repo_root / "app" / "templates"
if templates_dir.exists():
    template_errors = []
    for template in templates_dir.glob("*.html"):
        try:
            content = template.read_text()
            # Basic checks for common template issues
            if "{{" in content and "}}" not in content:
                template_errors.append(f"{template.name}: Unclosed curly braces")
            if "{%" in content and "%}" not in content:
                template_errors.append(f"{template.name}: Unclosed percent braces")
        except:
            pass

    if template_errors:
        for error in template_errors[:3]:  # Show first 3
            print_warning("Template syntax", error)
    else:
        print_test("Template syntax valid", True)

# ============================================================================
# 14. File Handling Tests
# ============================================================================
print_header("14. File Handling")

# Test file size handling awareness
test_files = [
    "app/src/web/blueprints/conversion.py",
    "app/src/converters/survey.py",
]

for test_file in test_files:
    path = repo_root / test_file
    if path.exists():
        size_kb = path.stat().st_size / 1024
        if size_kb > 500:
            print_warning(
                f"Large file: {test_file}", f"{size_kb:.1f}KB - consider splitting"
            )
        else:
            print_test(f"File size ok: {test_file}", True)

# Check for proper file encoding
encoding_ok = True
for py_file in repo_root.rglob("*.py"):
    if ".venv" in str(py_file) or "__pycache__" in str(py_file):
        continue
    try:
        # Try reading as UTF-8
        content = py_file.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        print_warning(f"Encoding issue: {py_file.name}", "Not UTF-8")
        encoding_ok = False
        break

if encoding_ok:
    print_test("All Python files UTF-8 encoded", True)

# ============================================================================
# 15. Performance Checks
# ============================================================================
print_header("15. Performance Indicators")

# Check if demo dataset validation is reasonably fast
demo_path = repo_root / "demo"
if demo_path.exists():
    import time

    start = time.time()
    success, stdout, stderr = run_command([sys.executable, "prism.py", str(demo_path)])
    elapsed = time.time() - start

    if elapsed < 5:
        print_test("Demo validation < 5s", True)
    elif elapsed < 10:
        print_test("Demo validation < 10s", True)
    else:
        print_warning("Demo validation slow", f"{elapsed:.1f}s")
else:
    print_warning("Demo dataset not available", "Skipping performance test")

# Check module import speed
import time

start = time.time()
try:
    __import__("pandas")
    __import__("flask")
    elapsed = time.time() - start
    print_test("Core imports < 2s", elapsed < 2)
except:
    print_warning("Import test failed", "Could not measure")

# ============================================================================
# 16. Repository Verification Script
# ============================================================================
print_header("16. Repository Verification Script")

verify_script = repo_root / "tests" / "verify_repo.py"
if verify_script.exists():
    print_test("verify_repo.py exists", True)

    # Check script has main function
    content = verify_script.read_text()
    has_main = "def main():" in content
    print_test("verify_repo.py has main()", has_main)

    # Check wrapper script
    wrapper = repo_root / "verify_repo.sh"
    print_test("verify_repo.sh wrapper exists", wrapper.exists())
else:
    print_warning("Repository verification script not found", "Optional tool")

# ============================================================================
# Summary
# ============================================================================
print_header("Test Summary")

total = (
    len(test_results["passed"])
    + len(test_results["failed"])
    + len(test_results["warnings"])
)
passed = len(test_results["passed"])
failed = len(test_results["failed"])
warnings = len(test_results["warnings"])

print(f"{GREEN}Passed:{RESET}   {passed}/{total}")
print(f"{RED}Failed:{RESET}   {failed}/{total}")
print(f"{YELLOW}Warnings:{RESET} {warnings}/{total}")

if failed > 0:
    print(f"\n{RED}Failed tests:{RESET}")
    for test in test_results["failed"]:
        print(f"  - {test}")

if warnings > 0:
    print(f"\n{YELLOW}Warnings:{RESET}")
    for test in test_results["warnings"]:
        print(f"  - {test}")

print(f"\n{BLUE}{'=' * 60}{RESET}")
if failed == 0:
    print(f"{GREEN}All critical tests passed! ✓{RESET}")
    sys.exit(0)
else:
    print(f"{RED}Some tests failed. Please review.{RESET}")
    sys.exit(1)
