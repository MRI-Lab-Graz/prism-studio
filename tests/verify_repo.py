import os
import sys
import argparse
import subprocess
import re
import fnmatch
from pathlib import Path
from datetime import datetime
from colorama import init, Fore, Style

# Initialize colorama
init()

IGNORED_DIRS = {
    ".venv",
    "venv",
    "env",
    ".git",
    "node_modules",
    "__pycache__",
    ".idea",
    ".vscode",
    "build",
    "dist",
    "eggs",
    ".eggs",
    "*_report_*.txt",
}
IGNORED_PATHS = []
MISSING_TOOLS = {}
TARGET_VENV_BIN = None
TARGET_PYTHON = None
CURRENT_CHECK = None
CURRENT_CHECK_WARNINGS = 0
CURRENT_CHECK_ERRORS = 0

# ANSI escape code stripper
ansi_escape = re.compile(r"\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])")

_GIT_FILES_CACHE = None


class Tee:
    """Writes to both stdout and a file, stripping ANSI codes for the file."""

    def __init__(self, file, stdout):
        self.file = file
        self.stdout = stdout

    def write(self, obj):
        self.stdout.write(obj)
        # Strip ANSI codes for the file
        clean_obj = ansi_escape.sub("", obj)
        self.file.write(clean_obj)
        self.file.flush()  # Ensure immediate write

    def flush(self):
        self.stdout.flush()
        self.file.flush()


def print_header(msg):
    print(f"\n{Fore.CYAN}{'=' * 60}")
    print(f" {msg}")
    print(f"{'=' * 60}{Style.RESET_ALL}")


def print_success(msg):
    print(f"{Fore.GREEN}[✓] {msg}{Style.RESET_ALL}")


def print_warning(msg):
    global CURRENT_CHECK_WARNINGS
    if CURRENT_CHECK:
        CURRENT_CHECK_WARNINGS += 1
    print(f"{Fore.YELLOW}[!] {msg}{Style.RESET_ALL}")


def print_error(msg):
    global CURRENT_CHECK_ERRORS
    if CURRENT_CHECK:
        CURRENT_CHECK_ERRORS += 1
    print(f"{Fore.RED}[✗] {msg}{Style.RESET_ALL}")


def print_info(msg):
    print(f"{Fore.BLUE}[i] {msg}{Style.RESET_ALL}")


def run_command(command, cwd=None, capture_output=True):
    """Runs a shell command and returns the result."""
    try:
        # Ensure we use the tools from the current python environment
        env = os.environ.copy()

        # Priority: Target Venv > Current Venv > System Path
        paths = []
        if TARGET_VENV_BIN:
            paths.append(TARGET_VENV_BIN)

        python_bin = os.path.dirname(sys.executable)
        paths.append(python_bin)

        existing_path = env.get("PATH", "")
        if existing_path:
            paths.append(existing_path)

        env["PATH"] = os.pathsep.join(paths)

        if capture_output:
            result = subprocess.run(
                command,
                cwd=cwd,
                shell=True,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                env=env,
            )
        else:
            result = subprocess.run(command, cwd=cwd, shell=True, text=True, env=env)
        return result
    except Exception:
        return None


def check_tool(tool_name, install_cmd):
    """Checks if a tool is installed, otherwise adds to MISSING_TOOLS."""
    cmd = "where" if os.name == "nt" else "which"
    result = run_command(f"{cmd} {tool_name}")
    if result and result.returncode == 0:
        return True
    MISSING_TOOLS[tool_name] = install_cmd
    return False


def parse_gitignore(repo_path):
    """Parses .gitignore and adds patterns to IGNORED_DIRS."""
    gitignore_path = os.path.join(repo_path, ".gitignore")
    if os.path.exists(gitignore_path):
        print_info("Parsing .gitignore to exclude ignored files...")
        try:
            with open(gitignore_path, "r") as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith("#"):
                        # Handle directory entries like 'dir/'
                        if line.endswith("/"):
                            IGNORED_DIRS.add(line.rstrip("/"))
                        else:
                            IGNORED_DIRS.add(line)
        except Exception as e:
            print_warning(f"Failed to parse .gitignore: {e}")


def detect_venvs(repo_path):
    """Scans for and adds virtual environment directories to IGNORED_DIRS."""
    global TARGET_VENV_BIN, TARGET_PYTHON
    print_info("Scanning for virtual environments...")
    found_venvs = []

    for root, dirs, files in os.walk(repo_path):
        # First filter known ignores to avoid traversing them
        dirs[:] = [d for d in dirs if d not in IGNORED_DIRS]

        venvs_in_current_root = []
        for d in dirs:
            dir_path = os.path.join(root, d)
            # Check for venv indicators
            if (
                os.path.exists(os.path.join(dir_path, "pyvenv.cfg"))
                or os.path.exists(os.path.join(dir_path, "bin", "activate"))
                or os.path.exists(os.path.join(dir_path, "Scripts", "activate"))
                or os.path.exists(os.path.join(dir_path, "conda-meta"))
            ):
                venvs_in_current_root.append(d)

        for venv in venvs_in_current_root:
            IGNORED_DIRS.add(venv)
            rel_path = os.path.relpath(os.path.join(root, venv), repo_path)
            IGNORED_PATHS.append(rel_path)
            found_venvs.append(rel_path)

            # Set target venv if not already set
            if not TARGET_VENV_BIN:
                venv_full_path = os.path.join(root, venv)
                bin_dir = os.path.join(venv_full_path, "bin")
                if not os.path.exists(bin_dir):
                    bin_dir = os.path.join(venv_full_path, "Scripts")

                if os.path.exists(bin_dir):
                    TARGET_VENV_BIN = bin_dir
                    python_exe = os.path.join(bin_dir, "python")
                    if not os.path.exists(python_exe):
                        python_exe = os.path.join(bin_dir, "python.exe")
                    if os.path.exists(python_exe):
                        TARGET_PYTHON = python_exe
                    print_info(f"Detected target virtual environment: {rel_path}")

            if venv in dirs:
                dirs.remove(venv)  # Prevent os.walk from entering

    if found_venvs:
        print_success(
            f"Auto-detected ignored virtual environments: {', '.join(found_venvs)}"
        )


def should_ignore(path, repo_path):
    """Check if a path should be ignored based on IGNORED_DIRS."""
    rel_path = os.path.relpath(path, repo_path)
    parts = rel_path.split(os.sep)

    # Check against IGNORED_DIRS (which now contains globs too)
    for part in parts:
        for ignored in IGNORED_DIRS:
            if fnmatch.fnmatch(part, ignored):
                return True
    return False


def is_binary(file_path):
    """Check if a file is binary."""
    try:
        with open(file_path, "rb") as f:
            chunk = f.read(1024)
            return b"\0" in chunk
    except Exception:
        return True


def get_git_files(repo_path):
    """Get list of all files tracked by git or untracked but not ignored."""
    global _GIT_FILES_CACHE
    if _GIT_FILES_CACHE is not None:
        return _GIT_FILES_CACHE

    if os.path.isdir(os.path.join(repo_path, ".git")):
        try:
            result = run_command("git ls-files -c -o --exclude-standard", cwd=repo_path)
            if result and result.returncode == 0:
                _GIT_FILES_CACHE = [
                    os.path.join(repo_path, f) for f in result.stdout.splitlines()
                ]
                return _GIT_FILES_CACHE
        except Exception:
            pass
    return None


def get_files(repo_path, pattern):
    """Generator that yields files matching pattern, respecting gitignore if possible."""
    git_files = get_git_files(repo_path)

    if git_files is not None:
        for file_path in git_files:
            # Check should_ignore even for git files (to handle our custom ignores like report files)
            if should_ignore(file_path, repo_path):
                continue

            if fnmatch.fnmatch(os.path.basename(file_path), pattern):
                yield Path(file_path)
    else:
        # Fallback
        for path in Path(repo_path).rglob(pattern):
            if not should_ignore(path, repo_path) and path.is_file():
                yield path


def check_secrets(repo_path, fix=False):
    print_header("Checking for Secrets (API Keys, Tokens, etc.)")

    # Method 1: Check for .env files
    env_files = list(get_files(repo_path, ".env*"))
    if env_files:
        print_warning("Found .env files (ensure these are in .gitignore):")
        for f in env_files:
            print(f"  - {f.relative_to(repo_path)}")
    else:
        print_success("No .env files found.")

    # Method 2: detect-secrets (if installed)
    print_info("Running detect-secrets...")
    if check_tool("detect-secrets", "pip install detect-secrets"):
        # Construct exclude regex from IGNORED_DIRS
        ignored_regex = "|".join([re.escape(d) for d in IGNORED_DIRS])
        known_false_positive_paths = [
            r"app/static/js/jszip\.min\.js",
            r"docs/WINDOWS_SETUP\.md",
            r"vendor/pyedflib/version\.py",
        ]
        known_false_positive_regex = "|".join(known_false_positive_paths)
        exclude_arg = (
            f'--exclude-files "(({ignored_regex})/|({known_false_positive_regex}))"'
        )

        result = run_command(f"detect-secrets scan {exclude_arg}", cwd=repo_path)
        if result and result.returncode == 0:
            if '"results": {}' in result.stdout:
                print_success("detect-secrets found no obvious secrets.")
            else:
                print_warning(
                    "detect-secrets found potential secrets. Please review output or run 'detect-secrets scan' manually."
                )
        else:
            print_warning("detect-secrets failed to run.")
    else:
        print_warning("detect-secrets not installed. Skipping deep secret scan.")


def check_gitignore(repo_path, fix=False):
    print_header("Checking .gitignore")
    gitignore_path = os.path.join(repo_path, ".gitignore")
    critical_ignores = [
        ".env",
        "node_modules",
        "__pycache__",
        ".DS_Store",
        ".venv",
        "venv",
        "env",
    ]

    if not os.path.exists(gitignore_path):
        if fix:
            print_info("Creating .gitignore with default ignores...")
            try:
                with open(gitignore_path, "w") as f:
                    f.write("\n".join(critical_ignores) + "\n")
                print_success("Created .gitignore")
            except Exception as e:
                print_error(f"Failed to create .gitignore: {e}")
        else:
            print_error("No .gitignore found! This is critical.")
            return

    # Read existing
    try:
        with open(gitignore_path, "r") as f:
            content = f.read()

        missing = []
        for item in critical_ignores:
            if item in content:
                print_success(f"'{item}' is ignored.")
            else:
                print_warning(f"'{item}' NOT found in .gitignore.")
                missing.append(item)

        if fix and missing:
            print_info(f"Adding missing items to .gitignore: {', '.join(missing)}")
            try:
                with open(gitignore_path, "a") as f:
                    if not content.endswith("\n"):
                        f.write("\n")
                    f.write("\n".join(missing) + "\n")
                print_success("Updated .gitignore")
            except Exception as e:
                print_error(f"Failed to update .gitignore: {e}")
    except Exception as e:
        print_error(f"Error reading .gitignore: {e}")


def check_large_files(repo_path, threshold_mb=10):
    print_header(f"Checking for Large Files (>{threshold_mb}MB)")
    found_large = False
    # Use get_files with '*' to check all files
    for file_path in get_files(repo_path, "*"):
        try:
            size_mb = os.path.getsize(file_path) / (1024 * 1024)
            if size_mb > threshold_mb:
                print_warning(
                    f"Large file found: {file_path.relative_to(repo_path)} ({size_mb:.2f} MB)"
                )
                found_large = True
        except Exception:
            pass

    if not found_large:
        print_success(f"No files larger than {threshold_mb}MB found.")


def check_sensitive_files(repo_path):
    print_header("Checking for Sensitive Filenames")
    sensitive_patterns = [
        "*.pem",
        "*.key",
        "*.crt",
        "*.p12",
        "*.pfx",  # Certificates/Keys
        "id_rsa",
        "id_dsa",
        "id_ecdsa",
        "id_ed25519",  # SSH keys
        "*.db",
        "*.sqlite",
        "*.sqlite3",  # Databases
        "credentials.json",
        "client_secret.json",  # Cloud credentials
        "*.aws/credentials",
        "*.aws/config",  # AWS
        "*.tfstate",
        "*.tfstate.backup",  # Terraform state
        "*.log",
        "npm-debug.log*",
        "yarn-error.log*",  # Logs
        ".history",
        ".bash_history",
        ".zsh_history",  # Shell history
    ]

    found_sensitive = False
    for pattern in sensitive_patterns:
        for file_path in get_files(repo_path, pattern):
            print_error(f"Sensitive file found: {file_path.relative_to(repo_path)}")
            found_sensitive = True

    if not found_sensitive:
        print_success("No sensitive filenames detected.")


def check_git_status(repo_path):
    print_header("Checking Git Status")
    if not os.path.isdir(os.path.join(repo_path, ".git")):
        print_info("Not a git repository.")
        return

    result = run_command("git status --porcelain", cwd=repo_path)
    if result and result.stdout.strip():
        print_warning("You have uncommitted changes or untracked files:")
        print(result.stdout)
        print_info(
            "Recommendation: Commit or stash changes before making the repo public."
        )
    else:
        print_success("Git working directory is clean.")

    # Check for large files in history (optional but good to mention)
    print_info(
        "Note: This script only checks the current state. Use 'trufflehog' or 'gitleaks' to scan full git history for secrets."
    )


def check_python_security(repo_path, fix=False):
    print_header("Running Python Security Scan (Bandit)")
    # Check if there are python files
    py_files = list(get_files(repo_path, "*.py"))
    if not py_files:
        print_info("No Python files found (excluding .venv). Skipping Bandit.")
        return

    if check_tool("bandit", "pip install bandit"):
        # Focus on application code to avoid test-only noise
        extra_excludes = ["tests", "tests/*", "tests/**", "docs", "examples"]
        excludes = ",".join(list(IGNORED_DIRS) + IGNORED_PATHS + extra_excludes)
        target_paths = "src app/src app/prism_tools.py app/prism-studio.py"
        result = run_command(
            f"bandit -r {target_paths} -ll -f custom --exclude {excludes}",
            cwd=repo_path,
        )
        if result and result.returncode == 0:
            print_success("Bandit passed with no issues.")
        else:
            print_warning("Bandit found potential security issues:")
            if result:
                print(result.stdout)
    else:
        print_warning("Bandit not installed. Skipping.")


def check_unsafe_patterns(repo_path, fix=False):
    print_header("Checking for Unsafe Patterns (eval, exec, etc.)")

    def is_risky_innerhtml(line):
        """Return True only for potentially unsafe innerHTML assignments.

        This avoids flagging benign reads (e.g., `const x = el.innerHTML`) or
        simple static assignments used for icons/spinners/placeholders.
        """
        if ".innerHTML" not in line:
            return False

        assignment = re.search(r"\.innerHTML\s*=\s*(.+)", line)
        if not assignment:
            return False

        rhs = assignment.group(1).strip().rstrip(";")
        if not rhs:
            return False

        # Empty clear is benign
        if rhs in {"''", '""', "``"}:
            return False

        # Static quoted strings without concatenation/interpolation are benign
        if re.fullmatch(r"'[^']*'", rhs) or re.fullmatch(r'"[^"]*"', rhs):
            return False

        # Template literals are only risky when interpolated
        if re.fullmatch(r"`[^`]*`", rhs):
            return "${" in rhs

        # For expressions/variables/concatenation, treat as risky
        return True

    unsafe_patterns = {
        "python": [
            (r"eval\(", "eval() can execute arbitrary code"),
            (r"exec\(", "exec() can execute arbitrary code"),
            (
                r"subprocess\.call\(.*shell=True",
                "subprocess with shell=True is a security risk",
            ),
            (r"os\.system\(", "os.system() is insecure, use subprocess instead"),
            (r"pickle\.load\(", "pickle.load() is unsafe for untrusted data"),
            (r"yaml\.load\(", "yaml.load() is unsafe, use yaml.safe_load()"),
            (r"http://", "Insecure HTTP connection, use HTTPS"),
            (r"\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}", "Hardcoded IP address found"),
        ],
        "javascript": [
            (r"eval\(", "eval() is a security risk"),
            (r"\.innerHTML", "innerHTML assignment can lead to XSS"),
            (r"document\.write\(", "document.write() is a security risk"),
            (r"http://", "Insecure HTTP connection, use HTTPS"),
        ],
        "bash": [
            (r"eval ", "eval can execute arbitrary code"),
            (r"rm -rf /", "Extremely dangerous command"),
            (r"http://", "Insecure HTTP connection, use HTTPS"),
        ],
    }

    extensions = {"python": ".py", "javascript": ".js", "bash": ".sh"}

    found_issues = False
    for lang, patterns in unsafe_patterns.items():
        ext = extensions[lang]
        files = list(get_files(repo_path, f"*{ext}"))
        for file_path in files:
            try:
                with open(file_path, "r", errors="ignore") as f:
                    for i, line in enumerate(f, 1):
                        for pattern, reason in patterns:
                            if re.search(pattern, line):
                                if pattern == r"\.innerHTML" and not is_risky_innerhtml(
                                    line
                                ):
                                    continue

                                # Filter out common false positives for IPs
                                if pattern == r"\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}":
                                    # Skip if it looks like a version number or common local IP
                                    if (
                                        re.search(r"v?\d+\.\d+\.\d+", line)
                                        or "127.0.0.1" in line
                                    ):
                                        continue

                                # Local development URLs are acceptable
                                if pattern == r"http://":
                                    if "127.0.0.1" in line or "localhost" in line:
                                        continue

                                print_warning(
                                    f"Potential unsafe pattern in {file_path.relative_to(repo_path)}:{i}"
                                )
                                print(f"  Pattern: {pattern} ({reason})")
                                print(f"  Line: {line.strip()}")
                                found_issues = True
            except Exception as e:
                print_error(f"Could not read {file_path}: {e}")

    if not found_issues:
        print_success("No obvious unsafe patterns found.")


def check_github_actions(repo_path):
    print_header("Checking GitHub Actions Workflows")
    workflow_dir = os.path.join(repo_path, ".github", "workflows")
    if not os.path.exists(workflow_dir):
        print_info("No GitHub Actions workflows found.")
        return

    found_issues = False
    for workflow_file in Path(workflow_dir).glob("*.yml"):
        try:
            with open(workflow_file, "r") as f:
                content = f.read()
                # Check for hardcoded secrets (basic check)
                if re.search(r"password:|token:|secret:", content, re.IGNORECASE):
                    # Check if it's using ${{ secrets. }}
                    if not re.search(r"\$\{\{\s*secrets\..*\}\}", content):
                        print_warning(
                            f"Potential hardcoded secret in {workflow_file.relative_to(repo_path)}"
                        )
                        found_issues = True

                # Check for 'pull_request_target' which can be risky
                if "pull_request_target" in content:
                    print_warning(
                        f"Found 'pull_request_target' in {workflow_file.relative_to(repo_path)}. Ensure it's used securely."
                    )
                    found_issues = True
        except Exception as e:
            print_error(f"Could not read {workflow_file}: {e}")

    if not found_issues:
        print_success("GitHub Actions workflows look okay (basic check).")


def check_linting(repo_path, fix=False):
    print_header("Code Quality & Linting (Black, Flake8)")

    excludes = ",".join(IGNORED_DIRS)

    # Black regex for exclusion
    # Only include simple directory names/files, skip globs for regex generation
    # Black respects .gitignore natively, so we mainly need to add things NOT in gitignore (like detected venvs)
    # But IGNORED_DIRS now has everything.
    # We filter out items with *, ?, [ to avoid breaking regex or creating invalid paths
    safe_ignores = [d for d in IGNORED_DIRS if not any(c in d for c in "*?[]")]
    ignored_regex = "|".join([re.escape(d) for d in safe_ignores])
    black_exclude = f"/({ignored_regex})/"

    # Black
    if check_tool("black", "pip install black"):
        if fix:
            print_info("Running Black (fixing mode)...")
            result_black = run_command(
                f"black . --exclude '{black_exclude}'", cwd=repo_path
            )
            if result_black and result_black.returncode == 0:
                print_success("Black: Code formatted.")
            else:
                print_warning("Black failed to format some files.")
        else:
            print_info("Running Black (check mode)...")
            result_black = run_command(
                f"black --check . --exclude '{black_exclude}'", cwd=repo_path
            )
            if result_black and result_black.returncode == 0:
                print_success("Black: Code is formatted correctly.")
            else:
                print_warning(
                    "Black: Code is NOT formatted correctly. Run 'black .' or use --fix"
                )
    else:
        print_warning("Black not installed.")

    # Flake8
    print_info("Running Flake8...")
    if check_tool("flake8", "pip install flake8"):
        excludes = ",".join(list(IGNORED_DIRS) + IGNORED_PATHS)
        result_flake = run_command(
            f"flake8 . --count --select=E9,F63,F7,F82 --show-source --statistics --exclude={excludes}",
            cwd=repo_path,
        )
        if result_flake and result_flake.returncode == 0:
            print_success("Flake8: No critical syntax errors or undefined names found.")
        else:
            print_warning("Flake8 found issues:")
            if result_flake:
                print(result_flake.stdout)
    else:
        print_warning("Flake8 not installed.")


def check_ruff(repo_path, fix=False):
    print_header("Running Ruff (Linting & Formatting)")
    if check_tool("ruff", "pip install ruff"):
        if fix:
            print_info("Running Ruff check --fix...")
            run_command("ruff check --fix .", cwd=repo_path)
            print_info("Running Ruff format...")
            run_command("ruff format .", cwd=repo_path)
            print_success("Ruff fixes applied.")
        else:
            print_info("Running Ruff check...")
            result = run_command("ruff check .", cwd=repo_path)
            if result and result.returncode == 0:
                print_success("Ruff check passed.")
            else:
                print_warning("Ruff found issues:")
                if result:
                    print(result.stdout)
                print_info("Note: Run with --fix to automatically resolve some issues.")
    else:
        print_warning("Ruff not installed.")


def check_mypy(repo_path, fix=False):
    print_header("Running MyPy (Type Checking)")
    if check_tool("mypy", "pip install mypy"):
        print_info("Running MyPy...")

        # Construct exclude regex from IGNORED_DIRS
        # Convert globs to regex approximation
        exclude_patterns = []
        for d in IGNORED_DIRS:
            # Escape special chars, then restore * and ? as regex wildcards
            pattern = re.escape(d).replace(r"\*", ".*").replace(r"\?", ".")
            exclude_patterns.append(pattern)

        exclude_arg = ""
        if exclude_patterns:
            full_exclude = "|".join(exclude_patterns)
            exclude_arg = f"--exclude '({full_exclude})'"

        # MyPy can be noisy, so we just run it and report success/fail
        # Using --explicit-package-bases to handle duplicate module names in different subdirectories
        # Using --python-executable to ensure MyPy sees the target repo's installed packages
        python_arg = f"--python-executable '{TARGET_PYTHON}'" if TARGET_PYTHON else ""
        result = run_command(
            f"mypy . --ignore-missing-imports --explicit-package-bases {python_arg} {exclude_arg}",
            cwd=repo_path,
        )
        if result and result.returncode == 0:
            print_success("MyPy passed.")
        else:
            print_warning("MyPy found type issues:")
            if result:
                print(result.stdout)
    else:
        print_warning("MyPy not installed.")


def check_semgrep(repo_path, fix=False):
    print_header("Running Semgrep (Security Scan)")
    if check_tool("semgrep", "pip install semgrep"):
        print_info("Running Semgrep...")
        # Use --no-git-ignore to ensure we scan everything, but we might want to respect it.
        # Actually, semgrep respects gitignore by default.
        result = run_command("semgrep scan --config=auto --quiet", cwd=repo_path)
        if result and result.returncode == 0:
            print_success("Semgrep passed.")
        else:
            print_warning("Semgrep found issues:")
            if result:
                print(result.stdout)
    else:
        print_warning("Semgrep not installed.")


def check_pip_audit(repo_path, fix=False):
    print_header("Running Pip-Audit (Dependency Vulnerabilities)")
    if check_tool("pip-audit", "pip install pip-audit"):
        req_file = os.path.join(repo_path, "requirements.txt")
        if os.path.exists(req_file):
            print_info("Auditing requirements.txt...")
            result = run_command("pip-audit -r requirements.txt", cwd=repo_path)
            if result and result.returncode == 0:
                print_success("Pip-audit passed.")
            else:
                if result and (
                    "Cannot install" in result.stdout
                    or "RuntimeError" in result.stdout
                    or "ensurepip" in result.stdout
                    or "SIGABRT" in result.stdout
                ):
                    print_warning(
                        "Pip-audit failed to resolve requirements (environment issue)."
                    )
                    print_info("Retrying with local environment audit...")
                    local_result = run_command("pip-audit -l", cwd=repo_path)
                    if local_result and local_result.returncode == 0:
                        print_success("Pip-audit (local) passed.")
                    else:
                        print_warning(
                            "Pip-audit (local) found vulnerabilities or failed:"
                        )
                        if local_result:
                            print(local_result.stdout)
                else:
                    print_warning("Pip-audit found vulnerabilities or failed:")
                    if result:
                        print(result.stdout)
        else:
            print_info("No requirements.txt found for pip-audit.")
    else:
        print_warning("Pip-audit not installed.")


def check_codespell(repo_path, fix=False):
    print_header("Running Codespell (Typos)")
    if check_tool("codespell", "pip install codespell"):
        # Build skip list
        default_skips = [
            "*.git",
            "*.venv",
            "*.lock",
            "*.json",
            "*.csv",
            "*.ipynb",
            "*.svg",
            "*.map",
            "*.js",
            "*.css",
            "*.pdf",
        ]
        skips = set(default_skips)

        # Add patterns from IGNORED_DIRS
        for item in IGNORED_DIRS:
            skips.add(item)

        # Clean up skips (remove empty strings, strip whitespace)
        skips = {s.strip() for s in skips if s and s.strip()}

        skip_str = ",".join(skips)

        ignore_file = os.path.join(repo_path, ".codespellignore")
        ignore_arg = f" -I '{ignore_file}'" if os.path.exists(ignore_file) else ""

        if fix:
            print_info("Running Codespell --write-changes...")
            result = run_command(
                f"codespell --write-changes --skip='{skip_str}'{ignore_arg}",
                cwd=repo_path,
            )
            if result and result.returncode == 0:
                print_success("Codespell passed/fixed.")
            else:
                print_warning(
                    "Codespell found issues it couldn't fix automatically (or just fixed them):"
                )
                if result:
                    print(result.stdout)
        else:
            print_info("Running Codespell...")
            result = run_command(
                f"codespell --skip='{skip_str}'{ignore_arg}", cwd=repo_path
            )
            if result and result.returncode == 0:
                print_success("Codespell passed.")
            else:
                print_warning("Codespell found typos:")
                if result:
                    print(result.stdout)
    else:
        print_warning("Codespell not installed.")


def check_dependencies(repo_path, fix=False):
    print_header("Verifying Dependencies")

    # Python
    req_file = os.path.join(repo_path, "requirements.txt")
    if os.path.exists(req_file):
        print_success("Found requirements.txt")
        print_info("Running 'safety check' on requirements.txt...")
        if check_tool("safety", "pip install safety"):
            result = run_command("safety check -r requirements.txt", cwd=repo_path)
            if result and result.returncode == 0:
                print_success("Safety check passed.")
            else:
                print_warning("Safety check found vulnerabilities or failed to run.")
                if result:
                    print(result.stdout)
        else:
            print_warning("Safety not installed.")
    else:
        print_warning("No requirements.txt found (Python).")

    # Node.js
    package_json = os.path.join(repo_path, "package.json")
    if os.path.exists(package_json):
        print_success("Found package.json")
        if check_tool("npm", "Install Node.js from https://nodejs.org/"):
            if fix:
                print_info("Running 'npm audit fix'...")
                result = run_command("npm audit fix", cwd=repo_path)
                if result and result.returncode == 0:
                    print_success("npm audit fix completed.")
                else:
                    print_warning("npm audit fix had issues.")
                    if result:
                        print(result.stdout)
            else:
                print_info("Running 'npm audit'...")
                result = run_command("npm audit", cwd=repo_path)
                if result and result.returncode == 0:
                    print_success("npm audit passed.")
                else:
                    print_warning("npm audit found issues.")
                    if result:
                        print(result.stdout)
        else:
            print_warning("npm not installed.")


def check_licensing(repo_path, fix=False):
    print_header("Checking Licensing")
    license_files = list(Path(repo_path).glob("LICENSE*")) + list(
        Path(repo_path).glob("COPYING*")
    )
    if license_files:
        license_file = license_files[0]
        print_success(f"Found License file: {license_file.name}")
        if license_file.stat().st_size < 100:
            print_warning(
                "License file seems very short. Ensure it contains the full license text."
            )
    else:
        print_error(
            "No LICENSE or COPYING file found. Please add a license before making the repo public."
        )


def check_todos(repo_path, fix=False):
    print_header("Checking for TODOs and FIXMEs")
    todo_pattern = re.compile(r"(TODO|FIXME)", re.IGNORECASE)
    found_todos = False

    # Use get_files to respect gitignore
    files = get_files(repo_path, "*")

    for file_path in files:
        # Skip binary files
        if is_binary(file_path):
            continue

        try:
            with open(file_path, "r", errors="ignore") as f:
                for i, line in enumerate(f, 1):
                    if todo_pattern.search(line):
                        print_info(
                            f"Found {line.strip()} in {os.path.relpath(file_path, repo_path)}:{i}"
                        )
                        found_todos = True
        except Exception:
            pass

    if not found_todos:
        print_success("No TODOs or FIXMEs found.")
    else:
        print_warning("Review the above TODOs/FIXMEs before publishing.")


def check_testing(repo_path, fix=False):
    print_header("Checking for Tests")
    # Use get_files to avoid finding tests in venv
    tests_dir = []
    for root, dirs, files in os.walk(repo_path):
        dirs[:] = [d for d in dirs if not d.startswith(".") and d not in IGNORED_DIRS]
        if "tests" in dirs:
            tests_dir.append(os.path.join(root, "tests"))

    test_files = list(get_files(repo_path, "test_*.py"))

    if tests_dir or test_files:
        print_success(
            f"Found tests: {len(test_files)} test files, {len(tests_dir)} test directories."
        )
        print_info("Recommendation: Run your tests locally before pushing.")
    else:
        print_warning("No obvious tests found (tests/ folder or test_*.py files).")


def check_documentation(repo_path, fix=False):
    print_header("Checking Documentation")
    readme_files = list(Path(repo_path).glob("README*"))
    if readme_files:
        readme_file = readme_files[0]
        print_success(f"Found README: {readme_file.name}")
        if readme_file.stat().st_size < 50:
            print_warning("README seems very short. Please add detailed documentation.")

        try:
            with open(readme_file, "r") as f:
                content = f.read()
                if (
                    "Project description goes here" in content
                    or "Add usage instructions" in content
                ):
                    print_warning("README contains placeholder text. Please update it.")
        except Exception:
            pass
    else:
        if fix:
            print_info("Creating basic README.md...")
            readme_path = os.path.join(repo_path, "README.md")
            try:
                with open(readme_path, "w") as f:
                    f.write(
                        f"# {os.path.basename(repo_path)}\n\nProject description goes here.\n\n## Usage\n\n```bash\n# Add usage instructions\n```\n"
                    )
                print_success("Created README.md")
            except Exception as e:
                print_error(f"Failed to create README.md: {e}")
        else:
            print_error("No README found! Please add one.")


CHECKS = {
    "git-status": check_git_status,
    "sensitive-files": check_sensitive_files,
    "large-files": check_large_files,
    "github-actions": check_github_actions,
    "secrets": check_secrets,
    "gitignore": check_gitignore,
    "python-security": check_python_security,
    "unsafe-patterns": check_unsafe_patterns,
    "linting": check_linting,
    "ruff": check_ruff,
    "mypy": check_mypy,
    "semgrep": check_semgrep,
    "codespell": check_codespell,
    "dependencies": check_dependencies,
    "pip-audit": check_pip_audit,
    "licensing": check_licensing,
    "testing": check_testing,
    "todos": check_todos,
    "documentation": check_documentation,
}


CHECKS_SUPPORT_FIX = {
    "secrets",
    "gitignore",
    "python-security",
    "unsafe-patterns",
    "linting",
    "ruff",
    "mypy",
    "semgrep",
    "codespell",
    "dependencies",
    "pip-audit",
    "licensing",
    "testing",
    "todos",
    "documentation",
}


def parse_selected_checks(check_args):
    """Parse --check args that can be repeated and/or comma-separated."""
    selected = []
    for raw_value in check_args or []:
        parts = [item.strip() for item in raw_value.split(",") if item.strip()]
        selected.extend(parts)

    # De-duplicate while preserving order
    seen = set()
    deduped = []
    for check_name in selected:
        if check_name not in seen:
            seen.add(check_name)
            deduped.append(check_name)
    return deduped


def run_check(check_name, check_fn, repo_path, fix):
    """Run a single check function with the proper signature.

    Returns:
        bool: True if check passed without warnings/errors, False otherwise.
    """
    global CURRENT_CHECK, CURRENT_CHECK_WARNINGS, CURRENT_CHECK_ERRORS
    CURRENT_CHECK = check_name
    CURRENT_CHECK_WARNINGS = 0
    CURRENT_CHECK_ERRORS = 0

    if check_name in CHECKS_SUPPORT_FIX:
        check_fn(repo_path, fix)
    else:
        check_fn(repo_path)

    passed = CURRENT_CHECK_WARNINGS == 0 and CURRENT_CHECK_ERRORS == 0
    CURRENT_CHECK = None
    return passed


def main():
    parser = argparse.ArgumentParser(
        description="AI Code Safety & Pre-Upload Checklist"
    )
    parser.add_argument(
        "path", nargs="?", default=".", help="Path to the repository to check"
    )
    parser.add_argument(
        "--fix",
        action="store_true",
        default=True,
        help="Attempt to automatically fix issues (gitignore, formatting, etc.) (default: True)",
    )
    parser.add_argument(
        "--no-fix", action="store_false", dest="fix", help="Disable automatic fixes"
    )
    parser.add_argument(
        "--check",
        action="append",
        default=[],
        help=(
            "Run only specific checks (repeatable or comma-separated), "
            "e.g. --check git-status --check linting,mypy"
        ),
    )
    parser.add_argument(
        "--list-checks",
        action="store_true",
        help="List available checks and exit",
    )
    parser.add_argument(
        "--spellcheck",
        action="store_true",
        help="Enable codespell check (disabled by default)",
    )
    args = parser.parse_args()

    if args.list_checks:
        print("Available checks:")
        for check_name in CHECKS:
            print(f"  - {check_name}")
        sys.exit(0)

    requested_checks = parse_selected_checks(args.check)
    if requested_checks:
        invalid = [name for name in requested_checks if name not in CHECKS]
        if invalid:
            print_error(f"Unknown check(s): {', '.join(invalid)}")
            print_info("Run with --list-checks to see valid names.")
            sys.exit(1)

    repo_path = os.path.abspath(args.path)

    if not os.path.exists(repo_path):
        print_error(f"Path does not exist: {repo_path}")
        sys.exit(1)

    # Setup logging to file
    repo_name = os.path.basename(repo_path) or os.path.basename(
        os.path.dirname(repo_path)
    )
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    log_filename = f"{repo_name}_report_{timestamp}.txt"

    print(f"Starting verification for: {repo_path}")
    print(f"Report will be saved to: {log_filename}")

    try:
        with open(log_filename, "w", encoding="utf-8") as log_file:
            # Redirect stdout to Tee
            original_stdout = sys.stdout
            sys.stdout = Tee(log_file, original_stdout)

            try:
                parse_gitignore(repo_path)
                detect_venvs(repo_path)

                if args.fix:
                    print_info("Fix mode enabled. Will attempt to auto-fix issues.")

                if requested_checks:
                    checks_to_run = requested_checks
                else:
                    checks_to_run = [name for name in CHECKS if name != "codespell"]

                if args.spellcheck and "codespell" not in checks_to_run:
                    checks_to_run.append("codespell")

                print_info(
                    f"Running checks: {', '.join(checks_to_run) if checks_to_run else 'none'}"
                )

                failed_check = None
                for check_name in checks_to_run:
                    check_passed = run_check(
                        check_name, CHECKS[check_name], repo_path, args.fix
                    )
                    if not check_passed:
                        failed_check = check_name
                        print_error(
                            f"Check '{check_name}' has unresolved issues. Fix this check before proceeding to the next one."
                        )
                        break

                print_header("Summary")
                if MISSING_TOOLS:
                    print_warning(
                        "Some tools were missing. Install them for better results:"
                    )
                    for tool, cmd in MISSING_TOOLS.items():
                        print(f"  - {tool}: {cmd}")
                    print()

                print_info("Please manually review:")
                print("  ☐ Manual code review for personal info/comments")
                print("  ☐ Run the code once to ensure it works")
                print("\nDone.")

                if failed_check:
                    print_warning(
                        "Verification stopped early due to unresolved issues in the current check."
                    )
                    sys.exit(1)
            finally:
                # Restore stdout
                sys.stdout = original_stdout

        print(f"\n{Fore.GREEN}Full report saved to: {log_filename}{Style.RESET_ALL}")

    except Exception as e:
        print_error(f"Failed to write log file: {e}")


if __name__ == "__main__":
    main()
