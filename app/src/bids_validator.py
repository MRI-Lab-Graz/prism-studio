"""
BIDS validator integration for PRISM.
Handles running both modern (Deno) and legacy (Node/Python) BIDS validators.
"""

import os
import json
import subprocess
from typing import List, Tuple, Set, Optional

DENO_BIDS_VALIDATOR_SPEC = "jsr:@bids/validator@2.4.1"

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

    if token == "SINGLE_SOURCE_CITATION_FIELDS":
        return True

    if token == "TOO_FEW_AUTHORS":
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
) -> List[Tuple[str, str, str]]:
    """
    Run the standard BIDS validator CLI and return issues.

    Args:
        root_dir: Path to the dataset root
        verbose: Enable verbose output
        placeholders: Set of relative paths to placeholder files to ignore content errors for
        structure_only: Whether this is a structure-only upload (suppress content errors)

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
        # Deno validator sometimes reports only the filename.
        if os.path.basename(loc) in placeholder_basenames:
            return True
        # And sometimes reports a path prefix/suffix; handle partial match.
        return any(loc.endswith(p) or p.endswith(loc) for p in placeholders)

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

    deno_failure_message = None

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

    # 1. Try Deno-based validator (modern)
    try:
        # Check if deno is installed
        subprocess.run(
            ["deno", "--version"],
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        print(f"   Using Deno-based validator ({DENO_BIDS_VALIDATOR_SPEC})")

        # Run Deno validator
        process = subprocess.run(
            [
                "deno",
                "run",
                "-ERWN",
                "--allow-sys",
                DENO_BIDS_VALIDATOR_SPEC,
                root_dir,
                "--json",
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )

        if process.stdout:
            try:
                bids_report = json.loads(process.stdout)

                # Handle Deno validator structure
                issue_list = []
                if "issues" in bids_report:
                    if (
                        isinstance(bids_report["issues"], dict)
                        and "issues" in bids_report["issues"]
                    ):
                        issue_list = bids_report["issues"]["issues"]
                    elif isinstance(bids_report["issues"], list):
                        issue_list = bids_report["issues"]

                for issue in issue_list:
                    code = issue.get("code", "UNKNOWN_CODE")
                    location = issue.get("location", "")

                    # PRISM citation-precedence: when CITATION.cff exists, suppress
                    # BIDS citation overlap guidance and dataset_description-only
                    # author-count warnings.
                    if citation_cff_exists and _is_citation_precedence_warning(
                        code, location
                    ):
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
                        # Deno location starts with /
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
                            if f"/{folder}/" in loc_lower or loc_lower.endswith(
                                f"/{folder}/"
                            ):
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
                    if silenced_not_included_count > len(
                        silenced_not_included_examples
                    ):
                        remaining = silenced_not_included_count - len(
                            silenced_not_included_examples
                        )
                        sample = (
                            f"{sample}, +{remaining} more"
                            if sample
                            else f"+{remaining} more"
                        )
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

            except json.JSONDecodeError:
                deno_failure_message = (
                    "Deno validator output could not be parsed as JSON"
                )
        else:
            stderr_msg = (process.stderr or "").strip()
            if stderr_msg:
                deno_failure_message = (
                    f"Deno validator produced no output. Stderr: {stderr_msg}"
                )
            else:
                deno_failure_message = f"Deno validator produced no output (exit code {process.returncode})"

    except (subprocess.CalledProcessError, FileNotFoundError):
        # Deno not found, fall back to legacy
        pass

    # 2. Try legacy Python/Node CLI validator
    if deno_failure_message:
        print(f"   ⚠️  Deno validator failed: {deno_failure_message}")
    print("   ⚠️  Falling back to legacy 'bids-validator' CLI...")
    try:
        # Check if bids-validator is installed
        subprocess.run(
            ["bids-validator", "--version"],
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )

        # Run validation
        process = subprocess.run(
            ["bids-validator", root_dir, "--json"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )

        if process.stdout:
            try:
                bids_report = json.loads(process.stdout)

                # Map BIDS issues to our format ("LEVEL", "Message")
                for issue_type in ["errors", "warnings"]:
                    base_level = "ERROR" if issue_type == "errors" else "WARNING"
                    for issue in bids_report.get("issues", {}).get(issue_type, []):
                        level = base_level
                        key = issue.get("key", "")
                        issue_locations: list[str] = []
                        for file in issue.get("files", []):
                            file_obj = file.get("file")
                            if file_obj:
                                issue_locations.append(
                                    str(file_obj.get("relativePath", "") or "")
                                )

                        if citation_cff_exists and (
                            _is_citation_precedence_warning(key)
                            or any(
                                _is_citation_precedence_warning(key, location)
                                for location in issue_locations
                            )
                        ):
                            silenced_citation_precedence_count += 1
                            continue

                        if key in SUPPRESSED_RECOMMENDED_WARNING_CODES:
                            silenced_recommended_count += 1
                            continue

                        # Filter files for this issue
                        filtered_files = []
                        any_annex_unfetched = False
                        for file in issue.get("files", []):
                            file_obj = file.get("file")
                            if file_obj:
                                file_path = file_obj.get("relativePath", "")
                                abs_file_path = os.path.join(
                                    root_dir, file_path.lstrip("/")
                                )
                                file_annex_unfetched = (
                                    key in content_error_codes
                                    and _is_unfetched_annex_content(abs_file_path)
                                )
                                if file_annex_unfetched:
                                    any_annex_unfetched = True
                                # Suppress content-related errors for placeholders
                                if (
                                    key in content_error_codes
                                    and not file_annex_unfetched
                                    and file_path.lstrip("/") in placeholders
                                ):
                                    continue
                                if (
                                    structure_only
                                    and not file_annex_unfetched
                                    and key == "EMPTY_FILE"
                                    and file_path.lower().endswith(
                                        (".nii", ".nii.gz", ".tsv.gz")
                                    )
                                ):
                                    continue
                                filtered_files.append(file_path)

                        if not filtered_files and issue.get("files"):
                            continue

                        if any_annex_unfetched:
                            level = "WARNING"

                        # Filter out NOT_INCLUDED for known PRISM modalities
                        if key == "NOT_INCLUDED":
                            is_prism_folder = False
                            for f_path in filtered_files:
                                for prism_folder in prism_ignore_folders:
                                    if (
                                        f"/{prism_folder}/" in f_path.lower()
                                        or f_path.lower().endswith(f"/{prism_folder}/")
                                    ):
                                        is_prism_folder = True
                                        break
                                if _is_prism_only_container_location(f_path):
                                    is_prism_folder = True
                                    break
                            if is_prism_folder:
                                continue

                        msg = f"[BIDS] {issue.get('reason')} ({key})"
                        first_file = None
                        for f_path in filtered_files:
                            msg += f"\n    File: {f_path}"
                            if not first_file:
                                first_file = os.path.join(root_dir, f_path.lstrip("/"))

                        if any_annex_unfetched:
                            msg += (
                                "\n    Note: file content not yet fetched from "
                                "git-annex/DataLad. Run `datalad get -r .` in the "
                                "dataset root to download the actual data."
                            )

                        if first_file:
                            issues.append((level, msg, first_file))
                        else:
                            issues.append((level, msg, root_dir))

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

            except json.JSONDecodeError:
                if verbose:
                    print("Warning: Could not parse BIDS validator JSON output.")
                issues.append(
                    (
                        "INFO",
                        "BIDS Validator ran but output could not be parsed. See console for details if verbose.",
                        root_dir,
                    )
                )

        if process.returncode != 0 and not issues:
            issues.append(
                ("ERROR", f"BIDS Validator failed to run: {process.stderr}", root_dir)
            )

    except (subprocess.CalledProcessError, FileNotFoundError):
        if deno_failure_message:
            issues.append(
                (
                    "WARNING",
                    f"BIDS Validator (Deno) failed: {deno_failure_message}",
                    root_dir,
                )
            )
        issues.append(
            (
                "WARNING",
                "bids-validator not found or failed to run. Is it installed?",
                root_dir,
            )
        )

    return issues
