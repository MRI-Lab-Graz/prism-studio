"""BIDS validator integration for PRISM: runs the bids-validator-deno engine and filters its report."""

import importlib.metadata
import json
import os
import shutil
import subprocess
import sys
import sysconfig
from functools import lru_cache
from pathlib import Path
from typing import List, Optional, Set, Tuple

BIDS_ENGINE_COMMAND = "bids-validator-deno"
BIDS_ENGINE_PACKAGE = "bids-validator-deno"
# ponytail: fixed 30 min ceiling, make it configurable if a real dataset needs more
BIDS_ENGINE_TIMEOUT_SECONDS = 1800


def find_bids_engine() -> Optional[str]:
    """The bids-validator-deno program: next to the running Python, in the
    interpreter's and the user's scripts folders (non-venv installs), then on PATH."""
    name = BIDS_ENGINE_COMMAND + (".exe" if sys.platform == "win32" else "")
    user_scheme = (
        sysconfig.get_preferred_scheme("user")
        if hasattr(sysconfig, "get_preferred_scheme")
        else ("nt_user" if os.name == "nt" else "posix_user")
    )
    for folder in (
        Path(sys.executable).parent,
        sysconfig.get_path("scripts"),
        sysconfig.get_path("scripts", scheme=user_scheme),
    ):
        candidate = Path(folder) / name
        if candidate.is_file():
            return str(candidate)
    return shutil.which(BIDS_ENGINE_COMMAND)


def bids_engine_version() -> str:
    try:
        return importlib.metadata.version(BIDS_ENGINE_PACKAGE)
    except importlib.metadata.PackageNotFoundError:
        return "unknown"


# Recommended-key warnings are often produced by upstream converters
# (for example BIDScoin) and are not required for BIDS validity.
SUPPRESSED_RECOMMENDED_WARNING_CODES = {
    "SIDECAR_KEY_RECOMMENDED",
    "JSON_KEY_RECOMMENDED",
}


def _is_citation_precedence_conflict(code_or_key: str | None) -> bool:
    token = str(code_or_key or "").strip().upper()
    if not token:
        return False
    return "AUTHORS_AND_CITATION_FILE_MUTUALLY_EXCLUSIVE" in token


def _is_citation_precedence_warning(
    code_or_key: str | None, location: str | None = None
) -> bool:
    token = str(code_or_key or "").strip().upper()
    if not token:
        return False

    if _is_citation_precedence_conflict(token):
        return True

    if token == "SINGLE_SOURCE_CITATION_FIELDS":  # noqa: S105 - validation-code string, not a credential
        return True

    if token == "TOO_FEW_AUTHORS":  # noqa: S105 - validation-code string, not a credential
        loc = str(location or "").replace("\\", "/").strip().lower()
        if loc.startswith("/"):
            loc = loc[1:]
        return loc.endswith("dataset_description.json")

    return False


def run_bids_validator(
    root_dir: str,
    verbose: bool = False,
    placeholders: Optional[Set[str]] = None,
    structure_only: bool = False,
    check_nifti_headers: bool = False,
    backend_info: Optional[dict] = None,
) -> List[Tuple[str, str, str]]:
    """
    Run the standard BIDS validator CLI and return issues.

    Args:
        root_dir: Path to the dataset root
        verbose: Enable verbose output
        placeholders: Set of relative paths to placeholder files to ignore content errors for
        structure_only: Whether this is a structure-only upload (suppress content errors)
        check_nifti_headers: Whether to validate NIfTI headers (off by default to
            avoid remote-storage content reads)
        backend_info: Optional dict to fill in with which backend actually ran
            ({"engine": "bids-validator-deno", "version": ..., "spec": ...}), so callers
            can report the BIDS validator version alongside PRISM's own.

    Returns:
        List of (severity, message, file_path) tuples
    """
    issues = []
    silenced_not_included_count = 0
    silenced_not_included_examples: list[str] = []
    silenced_recommended_count = 0
    silenced_citation_precedence_count = 0
    print("\n🤖 Running standard BIDS Validator...")

    placeholders = placeholders or set()
    placeholder_basenames = {os.path.basename(p) for p in placeholders}
    citation_cff_exists = os.path.exists(os.path.join(root_dir, "CITATION.cff"))

    # Content-related issues that are expected in structure-only validation.
    content_error_codes = {
        "EMPTY_FILE",
        "NIFTI_HEADER_UNREADABLE",
        "QUICK_TEST_FAILED",
        "FILE_READ",
    }

    # PRISM-only modalities that should be ignored by BIDS
    prism_ignore_folders = {
        "physiological",
        "physio",
        "survey",
        "biometrics",
        "metadata",
        "environment",
        "events",
    }
    standard_bids_folders = {
        "anat",
        "func",
        "dwi",
        "fmap",
        "beh",
        "eeg",
        "ieeg",
        "meg",
        "pet",
        "micr",
        "nirs",
        "motion",
    }

    def _looks_like_content_file(location: str) -> bool:
        if not location:
            return False
        loc = location.replace("\\", "/").lower()
        return loc.endswith(
            (
                ".nii",
                ".nii.gz",
                ".eeg",
                ".fif",
                ".dat",
                ".tsv.gz",
            )
        )

    def _is_unfetched_annex_content(file_path: Optional[str]) -> bool:
        """A broken symlink is the on-disk signature of a DataLad/git-annex
        file whose content hasn't been fetched yet (e.g. `datalad install`
        without a following `datalad get`). Once fetched, the symlink
        resolves to real content in .git/annex/objects/ and this is False.
        """
        if not file_path:
            return False
        try:
            return os.path.islink(file_path) and not os.path.exists(file_path)
        except OSError:
            return False

    def _is_placeholder_location(location: str) -> bool:
        if not placeholders or not location:
            return False
        loc = location.replace("\\", "/").lstrip("/")
        if loc in placeholders:
            return True
        # The engine sometimes reports only the filename.
        if os.path.basename(loc) in placeholder_basenames:
            return True
        # And sometimes reports a path prefix/suffix; handle partial match.
        return any(loc.endswith(p) or p.endswith(loc) for p in placeholders)

    # A PRISM-only subject/session folder draws one NOT_INCLUDED issue per
    # file inside it, and answering each one used to re-walk the whole subtree.
    # The answer only depends on the folder, so compute it once per folder.
    @lru_cache(maxsize=None)
    def _is_prism_only_container_location(location: str) -> bool:
        if not location:
            return False

        rel_path = location.replace("\\", "/").strip("/")
        if not rel_path:
            return False

        abs_path = os.path.join(root_dir, rel_path)
        if not os.path.isdir(abs_path):
            return False

        node_name = os.path.basename(os.path.normpath(abs_path)).lower()
        if not (node_name.startswith("sub-") or node_name.startswith("ses-")):
            return False

        saw_prism_modality = False
        for dirpath, _, _ in os.walk(abs_path):
            folder_name = os.path.basename(dirpath).lower()
            if folder_name in standard_bids_folders:
                return False
            if folder_name in prism_ignore_folders:
                saw_prism_modality = True

        return saw_prism_modality

    if verbose and structure_only:
        print(
            "   ℹ️  Detected structure-only upload. Will suppress BIDS data-content checks."
        )

    if placeholders and verbose:
        print(
            f"   ℹ️  Found {len(placeholders)} placeholder files. Will suppress content errors for these."
        )

    participants_tsv = os.path.join(root_dir, "participants.tsv")
    if os.path.exists(participants_tsv):
        try:
            with open(participants_tsv, "r", encoding="utf-8") as f:
                has_non_empty_line = any(line.strip() for line in f)
            if not has_non_empty_line:
                issues.append(
                    (
                        "ERROR",
                        "[BIDS] participants.tsv is empty. Remove the file or add at least a 'participant_id' header.",
                        participants_tsv,
                    )
                )
                return issues
        except Exception:
            pass

    def _fail(reason: str) -> List[Tuple[str, str, str]]:
        issues.append(
            ("ERROR", f"PRISM902 BIDS validator requested but {reason}", root_dir)
        )
        return issues

    engine = find_bids_engine()
    if engine is None:
        return _fail(
            "not available: the bids-validator-deno program was not found next to "
            "Python or on PATH. Reinstall prism-validator (it depends on "
            "bids-validator-deno) or run with --no-bids"
        )

    version = bids_engine_version()
    print(f"   Using bids-validator-deno {version}")
    if backend_info is not None:
        backend_info.update(
            {
                "engine": "bids-validator-deno",
                "version": version,
                "spec": f"bids-validator-deno@{version}",
            }
        )

    command = [engine, root_dir, "--format", "json"]
    if not check_nifti_headers:
        command.append("--ignoreNiftiHeaders")
    try:
        process = subprocess.run(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            encoding="utf-8",
            errors="replace",
            env={**os.environ, "NO_COLOR": "1"},
            timeout=BIDS_ENGINE_TIMEOUT_SECONDS,
        )
    except subprocess.TimeoutExpired:
        return _fail(
            "did not finish within 30 minutes. Reinstall prism-validator or run with --no-bids"
        )
    except OSError as exc:
        return _fail(f"could not be started: {exc}")

    if not process.stdout:
        stderr_msg = (process.stderr or "").strip()
        detail = f" Stderr: {stderr_msg}" if stderr_msg else ""
        return _fail(
            f"produced no output (exit code {process.returncode}).{detail} "
            "Reinstall prism-validator or run with --no-bids"
        )
    hint = "Reinstall prism-validator or run with --no-bids"
    try:
        bids_report = json.loads(process.stdout)
    except json.JSONDecodeError:
        return _fail(
            f"its output could not be parsed (exit code {process.returncode}). {hint}"
        )

    # The engine exits 0 (no errors) or 16 (errors found) and always prints a
    # report; anything else means the report cannot be trusted.
    issue_list = (
        bids_report.get("issues", {}).get("issues")
        if isinstance(bids_report, dict) and isinstance(bids_report.get("issues"), dict)
        else None
    )
    if not isinstance(issue_list, list):
        return _fail(f"its output is not a BIDS report (exit code {process.returncode}). {hint}")
    if process.returncode not in (0, 16):
        return _fail(f"exited with unexpected code {process.returncode}. {hint}")
    has_raw_error = any(
        isinstance(i, dict) and str(i.get("severity", "")).lower() == "error"
        for i in issue_list
    )
    if process.returncode == 16 and not has_raw_error:
        return _fail(f"exited with code 16 (errors found) but its report lists no error. {hint}")
    if process.returncode == 0 and has_raw_error:
        return _fail(f"exited with code 0 (no errors) but its report lists an error. {hint}")

    for issue in issue_list:
        code = issue.get("code", "UNKNOWN_CODE")
        location = issue.get("location", "")

        # PRISM citation-precedence: when CITATION.cff exists, suppress
        # BIDS citation overlap guidance and dataset_description-only
        # author-count warnings.
        if citation_cff_exists and _is_citation_precedence_warning(code, location):
            silenced_citation_precedence_count += 1
            continue

        # These are non-required recommendation hints and can dominate
        # warning output for externally converted datasets.
        if code in SUPPRESSED_RECOMMENDED_WARNING_CODES:
            silenced_recommended_count += 1
            continue

        # Try to extract a specific file path from the location
        issue_file: Optional[str] = None
        if location:
            # Engine location starts with /
            if location.startswith("/"):
                issue_file = os.path.join(root_dir, location.lstrip("/"))
            else:
                issue_file = os.path.join(root_dir, location)

        annex_unfetched = code in content_error_codes and (
            _is_unfetched_annex_content(issue_file)
        )

        # Suppress content-related errors for placeholders (and for structure-only uploads).
        if code in content_error_codes and not annex_unfetched:
            if _is_placeholder_location(location):
                continue
            if structure_only and _looks_like_content_file(location):
                continue

        # Filter out NOT_INCLUDED for known PRISM modalities
        if code == "NOT_INCLUDED":
            is_prism_modality = False
            loc_lower = location.lower()
            for folder in prism_ignore_folders:
                if f"/{folder}/" in loc_lower or loc_lower.endswith(f"/{folder}/"):
                    is_prism_modality = True
                    break
            if is_prism_modality:
                silenced_not_included_count += 1
                if location and len(silenced_not_included_examples) < 3:
                    silenced_not_included_examples.append(location)
                continue
            if _is_prism_only_container_location(location):
                silenced_not_included_count += 1
                if location and len(silenced_not_included_examples) < 3:
                    silenced_not_included_examples.append(location)
                continue

        severity = issue.get("severity", "warning").upper()
        level = "ERROR" if severity == "ERROR" else "WARNING"

        sub_code = issue.get("subCode", "")
        issue_msg = issue.get("issueMessage", "")

        msg = f"[BIDS] {code}"
        if sub_code:
            msg += f".{sub_code}"

        if issue_msg:
            msg += f": {issue_msg}"

        if location:
            msg += f"\n    Location: {location}"

        if annex_unfetched:
            level = "WARNING"
            msg += (
                "\n    Note: file content not yet fetched from "
                "git-annex/DataLad. Run `datalad get -r .` in the "
                "dataset root to download the actual data."
            )

        if issue_file:
            issues.append((level, msg, issue_file))
        else:
            issues.append((level, msg, root_dir))

    if verbose and silenced_not_included_count:
        sample = ", ".join(silenced_not_included_examples)
        if silenced_not_included_count > len(silenced_not_included_examples):
            remaining = silenced_not_included_count - len(
                silenced_not_included_examples
            )
            sample = f"{sample}, +{remaining} more" if sample else f"+{remaining} more"
        if sample:
            print(
                "   ℹ️  Silenced "
                f"{silenced_not_included_count} NOT_INCLUDED issue(s) for PRISM paths: {sample}"
            )
        else:
            print(
                "   ℹ️  Silenced "
                f"{silenced_not_included_count} NOT_INCLUDED issue(s) for PRISM paths"
            )

    if verbose and silenced_recommended_count:
        print(
            "   ℹ️  Silenced "
            f"{silenced_recommended_count} recommended-key warning(s) "
            "(SIDECAR/JSON_KEY_RECOMMENDED)"
        )

    if verbose and silenced_citation_precedence_count:
        print(
            "   ℹ️  Silenced "
            f"{silenced_citation_precedence_count} citation-precedence issue(s) "
            "(AUTHORS/CITATION overlap and dataset_description-only author hints)"
        )

    return issues
