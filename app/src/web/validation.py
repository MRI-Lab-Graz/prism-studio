"""
Validation module for prism web interface.
Provides unified validation function and progress tracking.
"""

import os
import re
import sys
import subprocess
import threading
import time
from typing import Optional, Callable, Tuple, Any, List


def _resolve_participants_mapping():
    """Resolve optional participants mapping function lazily."""
    candidates = [
        "src.derivatives.participants_mapping",
        "derivatives.participants_mapping",
    ]

    for module_name in candidates:
        try:
            module = __import__(module_name, fromlist=["apply_participants_mapping"])
            fn = getattr(module, "apply_participants_mapping", None)
            if callable(fn):
                return fn
        except Exception:
            continue

    return None


def _apply_participants_mapping(
    dataset_path: str, progress_callback: Optional[Callable] = None
):
    """Delegate participants mapping to derivatives workflow layer."""
    apply_participants_mapping = _resolve_participants_mapping()
    if apply_participants_mapping is None:
        return
    apply_participants_mapping(dataset_path, progress_callback)


# Progress tracking for validation jobs
_validation_progress: dict[str, dict[str, Any]] = {}
_validation_progress_lock = threading.Lock()
_PROGRESS_TTL_SECONDS = 2 * 60 * 60


def _purge_expired_progress_locked() -> None:
    """Drop stale progress entries. Must be called under lock."""
    now = time.time()
    expired = [
        job_id
        for job_id, payload in _validation_progress.items()
        if now - payload.get("updated_at", now) > _PROGRESS_TTL_SECONDS
    ]
    for job_id in expired:
        _validation_progress.pop(job_id, None)


def update_progress(
    job_id: str,
    progress: int,
    message: str,
    *,
    status: Optional[str] = None,
    phase: Optional[str] = None,
    progress_mode: Optional[str] = None,
    result_id: Optional[str] = None,
    redirect_url: Optional[str] = None,
    error: Optional[str] = None,
):
    """Update progress for a validation job."""
    normalized_progress = max(0, min(100, int(progress)))
    with _validation_progress_lock:
        _purge_expired_progress_locked()
        payload = dict(_validation_progress.get(job_id, {}))
        payload.update(
            {
                "progress": normalized_progress,
                "message": message,
                "status": status
                or payload.get("status")
                or ("running" if normalized_progress < 100 else "complete"),
                "phase": phase or payload.get("phase") or "validation",
                "progress_mode": progress_mode
                or payload.get("progress_mode")
                or "determinate",
                "updated_at": time.time(),
            }
        )
        if result_id is not None:
            payload["result_id"] = result_id
        if redirect_url is not None:
            payload["redirect_url"] = redirect_url
        if error is not None:
            payload["error"] = error
        _validation_progress[job_id] = payload


def complete_progress(
    job_id: str,
    message: str = "Validation complete",
    *,
    result_id: Optional[str] = None,
    redirect_url: Optional[str] = None,
) -> None:
    """Mark a validation job as complete."""
    update_progress(
        job_id,
        100,
        message,
        status="complete",
        phase="complete",
        progress_mode="determinate",
        result_id=result_id,
        redirect_url=redirect_url,
        error=None,
    )


def fail_progress(job_id: str, message: str, *, error: Optional[str] = None) -> None:
    """Mark a validation job as failed."""
    current = get_progress(job_id)
    progress = current.get("progress", 0)
    update_progress(
        job_id,
        progress,
        message,
        status="error",
        phase="error",
        progress_mode="determinate",
        error=error or message,
    )


def get_progress(job_id: str) -> dict:
    """Get progress for a validation job."""
    with _validation_progress_lock:
        _purge_expired_progress_locked()
        payload = _validation_progress.get(job_id)
        if payload is None:
            return {
                "progress": 0,
                "message": "Starting...",
                "status": "pending",
                "phase": "pending",
                "progress_mode": "determinate",
            }
        return dict(payload)


def clear_progress(job_id: str):
    """Clear progress for a completed job."""
    with _validation_progress_lock:
        _validation_progress.pop(job_id, None)


# Alias removed — use get_progress() / update_progress() / clear_progress() directly


class SimpleStats:
    """Simple stats class to hold validation statistics."""

    def __init__(self):
        self.total_files = 0
        self.subjects = set()
        self.sessions = set()
        self.tasks = set()
        self.modalities = {}  # modality -> file count
        self.surveys = set()
        self.biometrics = set()
        self.sidecar_files = 0


def _get_core_validator():
    """Try to import core validator function."""
    try:
        from src.core.validation import validate_dataset

        return validate_dataset
    except ImportError:
        pass

    try:
        from core.validation import validate_dataset

        return validate_dataset
    except ImportError:
        pass

    # NOTE: Do not fall back to importing runner.validate_dataset directly here
    # as that bypasses the src.core.validation boundary layer.
    return None


def _strip_ansi(text: str) -> str:
    """Remove ANSI escape codes from text."""
    ansi_escape = re.compile(r"\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])")
    return ansi_escape.sub("", text)


def run_validation(
    dataset_path: str,
    verbose: bool = False,
    schema_version: Optional[str] = None,
    run_bids: bool = False,
    run_prism: bool = True,
    library_path: Optional[str] = None,
    project_path: Optional[str] = None,
    progress_callback: Optional[Callable[[int, str], None]] = None,
) -> Tuple[List, Any]:
    """
    Run dataset validation using core validator or subprocess fallback.

    Args:
        dataset_path: Path to the dataset to validate
        verbose: Enable verbose output
        schema_version: Schema version to use (default: 'stable')
        run_bids: Also run standard BIDS validator
        run_prism: Also run PRISM-specific validation
        library_path: Optional path to a template library for sidecar resolution
        progress_callback: Optional callback for progress updates

    Returns:
        Tuple of (issues list, stats object)
    """
    # Canonical PRISM location: BIDS root is the provided project folder.
    dataset_path = os.path.abspath(dataset_path)

    # Auto-apply participants mapping only when PRISM checks are enabled
    if run_prism:
        _apply_participants_mapping(dataset_path, progress_callback)

    core_validate = _get_core_validator()

    # Try to use core validator directly first
    if core_validate:
        try:
            # Wrap progress_callback to handle 4 arguments if it only expects 2
            wrapped_callback = None
            if progress_callback:

                def wrapped_callback(*args, **kwargs):
                    try:
                        # runner.py calls with (current, total, message, file_path=None)
                        # we want to call progress_callback(progress_pct, message)
                        if len(args) >= 3:
                            current, total, message = args[0], args[1], args[2]
                            progress_pct = (
                                int((current / total) * 100) if total > 0 else current
                            )
                            progress_callback(progress_pct, message)
                        elif (
                            "current" in kwargs
                            and "total" in kwargs
                            and "message" in kwargs
                        ):
                            current, total, message = (
                                kwargs["current"],
                                kwargs["total"],
                                kwargs["message"],
                            )
                            progress_pct = (
                                int((current / total) * 100) if total > 0 else current
                            )
                            progress_callback(progress_pct, message)
                        elif len(args) == 2:
                            progress_callback(args[0], args[1])
                    except Exception as cb_err:
                        # Fallback or ignore if it fails
                        print(f"DEBUG: Callback error: {cb_err}")

            issues, stats = core_validate(
                dataset_path,
                verbose=verbose,
                schema_version=schema_version,
                run_bids=run_bids,
                run_prism=run_prism,
                library_path=library_path,
                project_path=project_path,
                progress_callback=wrapped_callback,
            )

            # Convert issues to web format if needed
            # core_validate_dataset returns list of tuples.
            # If they are (level, msg), we need to add path.
            web_issues = []
            for issue in issues:
                if len(issue) == 2:
                    web_issues.append((issue[0], issue[1], dataset_path))
                else:
                    web_issues.append(issue)

            return web_issues, stats
        except Exception as e:
            print(f"⚠️  Error running core validator directly: {e}")
            # Fall through to subprocess

    # Fallback to subprocess
    return _run_validator_subprocess(
        dataset_path, verbose=verbose, schema_version=schema_version, run_bids=run_bids
    )


def _run_validator_subprocess(
    dataset_path: str,
    verbose: bool = False,
    schema_version: Optional[str] = None,
    run_bids: bool = False,
    run_prism: bool = True,
) -> Tuple[List, SimpleStats]:
    """Run validation via subprocess (fallback method)."""

    try:
        # Build command
        cmd = [sys.executable, "prism.py", dataset_path]
        if verbose:
            cmd.append("--verbose")
        if schema_version:
            cmd.extend(["--schema-version", schema_version])
        if run_bids:
            cmd.append("--bids")
        if not run_prism:
            cmd.append("--no-prism")

        # Get script directory
        script_dir = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))

        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            cwd=script_dir,
            timeout=300,
        )

        # Parse results
        if result.returncode in [0, 1]:
            return _parse_subprocess_output(result, dataset_path)
        else:
            error_msg = result.stderr or "Validation failed"
            print(
                f"❌ Validator subprocess failed (code {result.returncode}): {error_msg}"
            )
            stats = SimpleStats()
            issues = [
                ("ERROR", f"Validation process failed: {error_msg}", dataset_path)
            ]
            return issues, stats

    except subprocess.TimeoutExpired:
        error_msg = "Validation timed out after 300 seconds"
        print(f"❌ {error_msg}")
        stats = SimpleStats()
        return [("ERROR", error_msg, dataset_path)], stats

    except FileNotFoundError:
        error_msg = "prism.py script not found"
        print(f"❌ {error_msg}")
        stats = SimpleStats()
        issues = [("ERROR", error_msg, dataset_path)]
        return issues, stats

    except Exception as e:
        error_msg = f"Failed to run validator: {str(e)}"
        print(f"❌ {error_msg}")
        stats = SimpleStats()
        issues = [("ERROR", error_msg, dataset_path)]
        return issues, stats


def _parse_subprocess_output(result, dataset_path: str) -> Tuple[List, SimpleStats]:
    """Parse validator subprocess output."""
    stdout = result.stdout
    stderr = result.stderr

    stats = SimpleStats()
    issues = []

    # Parse output for file counts and issues
    for line in stdout.split("\n") + stderr.split("\n"):
        clean_line = _strip_ansi(line).strip()

        # Parse file count
        if "Total files:" in clean_line:
            match = re.search(r"Total files:\s*(\d+)", clean_line)
            if match:
                stats.total_files = int(match.group(1))
        elif "📊 Found" in clean_line and "files" in clean_line:
            match = re.search(r"Found (\d+) files", clean_line)
            if match:
                stats.total_files = int(match.group(1))

            # Also try to parse subjects and sessions from this line
            # Format: 📊 Found 15 files across 1 subjects and 1 sessions
            sub_match = re.search(r"across (\d+) subjects", clean_line)
            if sub_match:
                # We can't get the IDs, but we can fill the set with dummy IDs to get the count right
                count = int(sub_match.group(1))
                stats.subjects = {f"sub-{i:02d}" for i in range(1, count + 1)}

            ses_match = re.search(r"and (\d+) sessions", clean_line)
            if ses_match:
                count = int(ses_match.group(1))
                stats.sessions = {f"ses-{i:02d}" for i in range(1, count + 1)}

        # Parse subject count from summary
        elif "👥 Subjects:" in clean_line:
            match = re.search(r"Subjects:\s*(\d+)", clean_line)
            if match:
                count = int(match.group(1))
                stats.subjects = {f"sub-{i:02d}" for i in range(1, count + 1)}

        # Parse session count from summary
        elif "📋 Sessions:" in clean_line:
            match = re.search(r"Sessions:\s*(\d+)", clean_line)
            if match:
                count = int(match.group(1))
                stats.sessions = {f"ses-{i:02d}" for i in range(1, count + 1)}

        # Parse specific error messages (bullet style)
        elif clean_line.startswith("•") and (
            "\u274c" in clean_line or "ERROR" in clean_line
        ):
            issues.append(("ERROR", clean_line.replace("•", "").strip(), dataset_path))
        # Parse numbered error messages
        elif re.search(r"^\d+\.\s+", clean_line) and (
            "\u274c" in clean_line or "ERROR" in clean_line
        ):
            msg = re.sub(r"^\d+\.\s+", "", clean_line).strip()
            issues.append(("ERROR", msg, dataset_path))
        elif clean_line.startswith("•") and (
            "\u26a0" in clean_line or "WARNING" in clean_line
        ):
            issues.append(
                ("WARNING", clean_line.replace("•", "").strip(), dataset_path)
            )
        elif re.search(r"^\d+\.\s+", clean_line) and (
            "\u26a0" in clean_line or "WARNING" in clean_line
        ):
            msg = re.sub(r"^\d+\.\s+", "", clean_line).strip()
            issues.append(("WARNING", msg, dataset_path))

    # Add generic error if validation failed but no specific issues found
    if "✅ Dataset is valid!" in stdout:
        pass  # No issues
    elif "❌ Dataset has validation errors" in stdout:
        if not issues:
            issues.append(
                (
                    "ERROR",
                    "Dataset validation failed - see terminal output for details",
                    dataset_path,
                )
            )
    elif result.returncode != 0 and not issues:
        issues.append(("ERROR", "Dataset validation failed", dataset_path))

    return issues, stats
