# PRISM Test Suite

## Running All Tests

```bash
# From repository root - comprehensive test suite
./run_tests.sh

# Repository security & quality verification
./verify_repo.sh

# With automatic fixes enabled (default)
./verify_repo.sh --fix

# Without automatic fixes
./verify_repo.sh --no-fix
```

## Test Scripts

### `run_all_tests.py` - Comprehensive Test Suite
Runs a comprehensive test suite covering:
- Repository structure
- Python environment
- CLI validator
- Schema validation
- Converters
- Web interface
- Unit tests
- Documentation
- Cross-platform compatibility
- Integration tests
- Security & code quality
- Configuration files
- Flask application
- File handling
- Performance indicators

### `verify_repo.py` - AI-Safe Code Verification
Comprehensive security and quality checks before sharing code:
- Git status and uncommitted changes
- Sensitive files detection (API keys, credentials, .env files)
- Large files (>10MB) detection
- GitHub Actions workflow validation
- Secret scanning (with detect-secrets if installed)
- .gitignore completeness
- Python security scan (with Bandit if installed)
- Unsafe patterns (eval, exec, pickle.load, yaml.load)
- Code linting (with flake8/ruff if installed)
- Type checking (with mypy if installed)
- Dependency vulnerabilities (with pip-audit if installed)
- License compliance
- Test coverage
- TODO/FIXME comments
- Documentation completeness

**Generates a timestamped report file** with all findings.

## Running Unit Tests Only

```bash
# With pytest
source .venv/bin/activate
python3 -m pytest tests/ -v

# With specific test file
python3 -m pytest tests/test_validator.py -v
```

## Test Files

- `run_all_tests.py` - Comprehensive test suite (all components)
- `verify_repo.py` - Security & quality verification (AI-safe checklist)
- `test_validator.py` - Core validation logic tests
- `test_runner.py` - Validation runner tests  
- `test_unit.py` - Unit tests for various modules
- `test_reorganization.py` - File organization tests
- `test_windows_compatibility.py` - Cross-platform tests (legacy)
- `test_web_*.py` - Web interface tests
- `test_participants_mapping.py` - Participants converter tests

### Windows-Specific Tests

Comprehensive test suite for Windows compatibility (since repo was built on macOS):

- `test_windows_compatibility.py` - Core cross-platform utilities
- `test_windows_paths.py` - Path handling (drive letters, UNC, long paths, reserved names)
- `test_windows_web_uploads.py` - Web upload functionality on Windows
- `test_windows_datasets.py` - Dataset validation on Windows filesystems
- `github_signing_check.py` - GitHub Actions code signing configuration
- `run_windows_tests.py` - Master test runner (Python)
- `run_windows_tests.ps1` - Master test runner (PowerShell)

**Run Windows tests:**
```powershell
# PowerShell (recommended on Windows)
.\tests\run_windows_tests.ps1

# Or with Python
python tests/run_windows_tests.py

# Individual tests
python tests/test_windows_paths.py
```

See [WINDOWS_TESTING.md](../docs/WINDOWS_TESTING.md) for detailed documentation.

## Stress Testing

Test files for manual stress testing:
- `/tmp/test_stress.csv` - 100 participants (CSV)
- `/tmp/test_stress.xlsx` - 100 participants (Excel)
- `/tmp/test_participants_stress.csv` - 20 participants with rich metadata

Generate new test data:
```bash
python3 /tmp/create_test.py
```

## Expected Results

**Typical test run:** 73/73 tests passing
- All core functionality working
- Zero warnings
- All security checks pass

**Repository verification:** Clean report with recommendations only
- No secrets exposed
- No unsafe patterns in production code
- All dependencies secure

