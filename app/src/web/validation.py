"""
Validation module for prism web interface.
Provides unified validation function and progress tracking.
"""

import sys
import os
import re
import subprocess
from typing import Optional, Callable, Tuple, Any, List
from pathlib import Path


def _apply_participants_mapping(
    dataset_path: str, progress_callback: Optional[Callable] = None
):
    """
    Auto-detect and apply participants mapping if present.

    This is called automatically during validation.
    If participants_mapping.json exists in code/library/ or sourcedata/, it will be applied
    to generate/update participants.tsv.
    """
    # Look for mapping in standard locations
    mapping_file = None
    search_paths = [
        Path(dataset_path).parent / "code" / "library" / "participants_mapping.json",
        Path(dataset_path).parent / "sourcedata" / "participants_mapping.json",
        Path(dataset_path).parent.parent
        / "code"
        / "library"
        / "participants_mapping.json",  # If in rawdata/
    ]

    for candidate in search_paths:
        if candidate.exists():
            mapping_file = candidate
            break

    if not mapping_file:
        return  # No mapping file, skip

    try:
        if progress_callback:
            progress_callback(
                0, "Detected participants_mapping.json - applying transformations..."
            )

        from src.participants_converter import ParticipantsConverter

        converter = ParticipantsConverter(dataset_path)
        mapping = converter.load_mapping_from_file(mapping_file)

        if not mapping:
            if progress_callback:
                progress_callback(5, "⚠ Could not load participants mapping")
            return

        # Validate mapping
        is_valid, errors = converter.validate_mapping(mapping)
        if not is_valid:
            if progress_callback:
                progress_callback(
                    5, f"⚠ Mapping validation failed: {'; '.join(errors[:3])}"
                )
            return

        # Try to find source file (usually first TSV in raw_data/)
        source_file = None
        raw_data_dir = Path(dataset_path).parent / "raw_data"

        # If we're in rawdata/, look for source in parent's raw_data/
        if not raw_data_dir.exists():
            raw_data_dir = Path(dataset_path).parent.parent / "raw_data"

        # Also check sourcedata/
        if not raw_data_dir.exists():
            raw_data_dir = Path(dataset_path).parent / "sourcedata"

        if raw_data_dir.exists():
            for tsv_file in raw_data_dir.glob("**/*.tsv"):
                # Skip hidden files and system files
                if not tsv_file.name.startswith("."):
                    source_file = tsv_file
                    break

        if not source_file:
            if progress_callback:
                progress_callback(
                    5, "ℹ No source participant data file found - skipping mapping"
                )
            return

        # Apply conversion
        success, df, messages = converter.convert_participant_data(
            source_file, mapping, output_file=Path(dataset_path) / "participants.tsv"
        )

        if success:
            if progress_callback:
                progress_callback(
                    15, f"✓ Applied participants mapping ({len(df)} rows transformed)"
                )
        else:
            if progress_callback:
                progress_callback(10, "⚠ Participants mapping partially failed")

    except Exception as e:
        # Silently fail - don't break validation
        if progress_callback:
            progress_callback(5, f"ℹ Participants mapping skipped: {str(e)[:50]}")


# Progress tracking for validation jobs
_validation_progress = {}  # job_id -> {progress, message, status}


def update_progress(job_id: str, progress: int, message: str):
    """Update progress for a validation job."""
    _validation_progress[job_id] = {
        "progress": progress,
        "message": message,
        "status": "running" if progress < 100 else "complete",
    }


def get_progress(job_id: str) -> dict:
    """Get progress for a validation job."""
    return _validation_progress.get(
        job_id, {"progress": 0, "message": "Starting...", "status": "pending"}
    )


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
        self.modalities = {}  # modality -> file count
        self.surveys = set()
        self.biometrics = set()
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
    run_prism: bool = True,
    library_path: Optional[str] = None,
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

    # Auto-apply participants mapping if present
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

        result = subprocess.run(cmd, capture_output=True, text=True, cwd=script_dir)

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
        elif clean_line.startswith("•") and ("❌" in stdout or "ERROR" in stdout):
            issues.append(("ERROR", clean_line.replace("•", "").strip(), dataset_path))
        # Parse numbered error messages
        elif re.search(r"^\d+\.\s+", clean_line) and (
            "❌" in stdout or "ERROR" in stdout
        ):
            msg = re.sub(r"^\d+\.\s+", "", clean_line).strip()
            issues.append(("ERROR", msg, dataset_path))
        elif clean_line.startswith("•") and ("⚠️" in stdout or "WARNING" in stdout):
            issues.append(
                ("WARNING", clean_line.replace("•", "").strip(), dataset_path)
            )
        elif re.search(r"^\d+\.\s+", clean_line) and (
            "⚠️" in stdout or "WARNING" in stdout
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
