"""
Validation module for prism-validator web interface.
Provides unified validation function and progress tracking.
"""

import sys
import os
import re
import subprocess
from pathlib import Path
from typing import Optional, Callable, Tuple, Any, List

# Progress tracking for validation jobs
_validation_progress = {}  # job_id -> {progress, message, status}


def update_progress(job_id: str, progress: int, message: str):
    """Update progress for a validation job."""
    _validation_progress[job_id] = {
        "progress": progress,
        "message": message,
        "status": "running" if progress < 100 else "complete"
    }


def get_progress(job_id: str) -> dict:
    """Get progress for a validation job."""
    return _validation_progress.get(job_id, {
        "progress": 0, 
        "message": "Starting...", 
        "status": "pending"
    })


def clear_progress(job_id: str):
    """Clear progress for a completed job."""
    _validation_progress.pop(job_id, None)


# Alias for backwards compatibility
validation_progress = _validation_progress


class SimpleStats:
    """Simple stats class to hold validation statistics."""

    def __init__(self, *args):
        self.total_files = 0
        self.subjects = set()
        self.sessions = set()
        self.tasks = set()
        self.modalities = set()
        self.sidecar_files = 0


def _get_core_validator():
    """Try to import core validator function."""
    try:
        from runner import validate_dataset
        return validate_dataset
    except ImportError:
        pass
    
    # Try src.runner
    try:
        from src.runner import validate_dataset
        return validate_dataset
    except ImportError:
        pass
    
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
    progress_callback: Optional[Callable[[int, str], None]] = None,
) -> Tuple[List, Any]:
    """
    Run dataset validation using core validator or subprocess fallback.
    
    Args:
        dataset_path: Path to the dataset to validate
        verbose: Enable verbose output
        schema_version: Schema version to use (default: 'stable')
        run_bids: Also run standard BIDS validator
        progress_callback: Optional callback for progress updates
        
    Returns:
        Tuple of (issues list, stats object)
    """
    core_validate = _get_core_validator()
    
    # Try to use core validator directly first
    if core_validate:
        try:
            issues, stats = core_validate(
                dataset_path, 
                verbose=verbose, 
                schema_version=schema_version,
                run_bids=run_bids,
                progress_callback=progress_callback,
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
        dataset_path, 
        verbose=verbose, 
        schema_version=schema_version, 
        run_bids=run_bids
    )


def _run_validator_subprocess(
    dataset_path: str,
    verbose: bool = False,
    schema_version: Optional[str] = None,
    run_bids: bool = False,
) -> Tuple[List, SimpleStats]:
    """Run validation via subprocess (fallback method)."""
    
    try:
        # Build command
        cmd = [sys.executable, "prism-validator.py", dataset_path]
        if verbose:
            cmd.append("--verbose")
        if schema_version:
            cmd.extend(["--schema-version", schema_version])
        if run_bids:
            cmd.append("--bids")

        # Get script directory
        script_dir = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
        
        result = subprocess.run(
            cmd, capture_output=True, text=True, cwd=script_dir
        )

        # Parse results
        if result.returncode in [0, 1]:
            return _parse_subprocess_output(result, dataset_path)
        else:
            error_msg = result.stderr or "Validation failed"
            print(f"❌ Validator subprocess failed (code {result.returncode}): {error_msg}")
            stats = SimpleStats()
            issues = [("ERROR", f"Validation process failed: {error_msg}", dataset_path)]
            return issues, stats

    except FileNotFoundError:
        error_msg = "prism-validator.py script not found"
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
        # Parse specific error messages (bullet style)
        elif clean_line.startswith("•") and ("❌" in stdout or "ERROR" in stdout):
            issues.append(
                ("ERROR", clean_line.replace("•", "").strip(), dataset_path)
            )
        # Parse numbered error messages
        elif re.search(r"^\d+\.\s+", clean_line) and ("❌" in stdout or "ERROR" in stdout):
            msg = re.sub(r"^\d+\.\s+", "", clean_line).strip()
            issues.append(("ERROR", msg, dataset_path))
        elif clean_line.startswith("•") and ("⚠️" in stdout or "WARNING" in stdout):
            issues.append(
                ("WARNING", clean_line.replace("•", "").strip(), dataset_path)
            )
        elif re.search(r"^\d+\.\s+", clean_line) and ("⚠️" in stdout or "WARNING" in stdout):
            msg = re.sub(r"^\d+\.\s+", "", clean_line).strip()
            issues.append(("WARNING", msg, dataset_path))

    # Add generic error if validation failed but no specific issues found
    if "✅ Dataset is valid!" in stdout:
        pass  # No issues
    elif "❌ Dataset has validation errors" in stdout:
        if not issues:
            issues.append((
                "ERROR",
                "Dataset validation failed - see terminal output for details",
                dataset_path,
            ))
    elif result.returncode != 0 and not issues:
        issues.append(("ERROR", "Dataset validation failed", dataset_path))

    return issues, stats
