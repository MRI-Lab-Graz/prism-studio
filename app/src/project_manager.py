"""
Project Manager for PRISM Studio.

Provides functionality to:
- Create new PRISM/BIDS-compatible project structures
- Validate existing project folder structures
- Apply fixes to repair invalid structures

Usage:
    from src.project_manager import ProjectManager
    pm = ProjectManager()

    # Create new project
    result = pm.create_project("/path/to/project", {
        "name": "My Study",
        "sessions": 2,
        "modalities": ["survey", "biometrics"],
    })

    # Validate existing project
    result = pm.validate_structure("/path/to/project")

    # Apply fixes
    result = pm.apply_fixes("/path/to/project")
"""

import json
import os
import re
import stat
import shutil
import subprocess
import tempfile
import time
from pathlib import Path
from datetime import date
from typing import Dict, List, Any, Optional, Set, Union
from urllib.parse import urlparse

from src.fixer import DatasetFixer
from src.project_export_helpers import (
    _extract_export_task_label,
    _extract_terminal_suffix_label,
    _matches_excluded_acq_label,
)
from src.constants import DEFAULT_BIDS_VERSION
from src.cross_platform import CrossPlatformFile
from src.issues import get_fix_hint, infer_code_from_message
from src.schema_manager import load_schema
from src.readme_generator import ReadmeGenerator
from src.project_icons import choose_random_project_icon, normalize_project_icon
from src.system_files import filter_system_files
from jsonschema import Draft7Validator

# Available PRISM modalities
PRISM_MODALITIES = [
    "survey",
    "biometrics",
    "environment",
    "physio",
    "eyetracking",
    "events",
]

# Modalities that remain available in PRISM tooling but are validated as BIDS
# pass-through instead of PRISM-specific extensions.
BIDS_PASSTHROUGH_MODALITIES = {"eyetracking"}

# Valid project name pattern (no spaces, filesystem-safe)
PROJECT_NAME_PATTERN = re.compile(r"^[a-zA-Z0-9_-]+$")
VALID_DATASET_TYPES = {"raw", "derivative"}
DATALAD_REPAIR_STEP_TIMEOUT_SECONDS = 120
REGISTERED_SUBDATASET_QUERY_TIMEOUT_SECONDS = 30
DATALAD_EXPORT_STEP_TIMEOUT_SECONDS = 60 * 60
DATALAD_DOCS_URL = "https://www.datalad.org/"
DATALAD_INSTALL_HINT = "Install with: uv tool install datalad git-annex"
DATALAD_TEXT_POLICY_REQUIRED_LINES = (
    "*.cfg annex.largefiles=nothing",
    "*.csv annex.largefiles=nothing",
    "*.ini annex.largefiles=nothing",
    "*.json annex.largefiles=nothing",
    "*.jsonl annex.largefiles=nothing",
    "*.md annex.largefiles=nothing",
    "*.ndjson annex.largefiles=nothing",
    "*.toml annex.largefiles=nothing",
    "*.tsv annex.largefiles=nothing",
    "*.txt annex.largefiles=nothing",
    "*.xml annex.largefiles=nothing",
    "*.yaml annex.largefiles=nothing",
    "*.yml annex.largefiles=nothing",
    ".gitattributes annex.largefiles=nothing",
    ".bidsignore annex.largefiles=nothing",
    ".prismrc.json annex.largefiles=nothing",
    "CHANGES annex.largefiles=nothing",
    "CITATION.cff annex.largefiles=nothing",
    "README.md annex.largefiles=nothing",
    "dataset_description.json annex.largefiles=nothing",
    "project.json annex.largefiles=nothing",
)
EXPORT_TEMP_WORKSPACE_PREFIX = ".prism-folder-export-"
EXPORT_TEMP_WORKSPACE_LOCKFILE = ".prism-export-active.json"
EXPORT_TEMP_WORKSPACE_STALE_SECONDS = 15 * 60
EXPORT_TEMP_WORKSPACE_LOW_FREE_BYTES = 20 * 1024 * 1024 * 1024
EXPORT_TEMP_WORKSPACE_LOW_FREE_RATIO = 0.10
REMOTE_DATASET_ACQUIRE_TIMEOUT_SECONDS = 60 * 60
MRI_SUFFIX_LABEL_MODALITIES = {"anat", "dwi", "fmap", "perf"}


class ProjectManager:
    """
    Manages PRISM project creation and validation.
    """

    def __init__(self):
        """Initialize the project manager."""
        # Path to template files
        self.template_dir = Path(__file__).parent.parent / "demo"

    def create_project(self, path: str, config: Dict[str, Any]) -> Dict[str, Any]:
        """
        Create a new PRISM project with proper folder structure.

        Args:
            path: Path where project should be created
            config: Project configuration:
                - name: Project name (required)
                - sessions: Number of sessions (0 = no sessions)
                - modalities: List of modalities to include

        Returns:
            Dict with success status and created files list
        """
        project_path = Path(path)

        # Extract config
        name = config.get("name", project_path.name)

        # Validate project name
        if not PROJECT_NAME_PATTERN.match(name):
            return {
                "success": False,
                "error": f"Invalid project name '{name}'. Only letters, numbers, underscores and hyphens allowed.",
            }

        # Validate path doesn't exist or is empty
        if project_path.exists():
            existing_entries = filter_system_files(
                [entry.name for entry in project_path.iterdir()]
            )
            if existing_entries:
                return {
                    "success": False,
                    "error": (
                        f"Directory '{path}' already exists and is not empty. "
                        "Project Location must be the parent folder where the new "
                        "project directory will be created. Choose a different "
                        "project name or parent folder, or use Open Existing Project "
                        "if this project already exists."
                    ),
                }

        # In the new YODA layout, sessions and modalities are not pre-selected.
        # We always create a standard structure that is populated later.
        sessions = 0  # Default to 0, since it's for later import
        modalities = ["survey", "biometrics"]  # Default core modalities for folders

        created_files = []
        datalad_result: Optional[Dict[str, Any]] = None

        try:
            # Create project root
            project_path.mkdir(parents=True, exist_ok=True)

            datalad_result = self._create_datalad_dataset(
                project_path,
                enabled=config.get("use_datalad", False),
            )
            gitattributes_created = self._ensure_datalad_editable_metadata_policy(
                project_path,
                datalad_result,
            )
            if gitattributes_created:
                created_files.append(".gitattributes")

            # 1. Create dataset_description.json in root (BIDS standard)
            desc_path = project_path / "dataset_description.json"
            desc_content = self._create_dataset_description(name, config)
            CrossPlatformFile.write_text(
                str(desc_path), json.dumps(desc_content, indent=2)
            )
            created_files.append("dataset_description.json")

            # 2. Create .bidsignore in root
            bidsignore_path = project_path / ".bidsignore"
            bidsignore_content = self._create_bidsignore(modalities)
            CrossPlatformFile.write_text(str(bidsignore_path), bidsignore_content)
            created_files.append(".bidsignore")

            # 3. Create .prismrc.json in root (controls project-wide validation)
            prismrc_path = project_path / ".prismrc.json"
            prismrc_content = self._create_prismrc()
            CrossPlatformFile.write_text(
                str(prismrc_path), json.dumps(prismrc_content, indent=2)
            )
            created_files.append(".prismrc.json")

            # 4. Create README.md in root
            readme_path = project_path / "README.md"
            # Use the new generator to create a proper structured README
            try:
                generator = ReadmeGenerator(project_path)
                readme_content = generator.generate()
                CrossPlatformFile.write_text(str(readme_path), readme_content)
                created_files.append("README.md")
            except Exception:
                # Fallback to basic README if generator fails
                readme_content = self._create_readme(name, sessions, modalities)
                CrossPlatformFile.write_text(str(readme_path), readme_content)
                created_files.append("README.md")

            # 5. Create project governance files in root
            project_metadata_path = project_path / "project.json"
            project_metadata = self._create_project_metadata(name, config)
            CrossPlatformFile.write_text(
                str(project_metadata_path),
                json.dumps(project_metadata, indent=2, ensure_ascii=False),
            )
            created_files.append("project.json")

            citation_path = project_path / "CITATION.cff"
            citation_content = self._create_citation_cff(name, config)
            CrossPlatformFile.write_text(str(citation_path), citation_content)
            created_files.append("CITATION.cff")

            # 6. Create CHANGES file in root (BIDS standard)
            changes_path = project_path / "CHANGES"
            changes_content = f"1.0.0 {date.today().isoformat()}\n  - Initial dataset structure created and validated via PRISM.\n"
            CrossPlatformFile.write_text(str(changes_path), changes_content)
            created_files.append("CHANGES")

            # 7. Create essential folders only (sourcedata, derivatives)
            # sourcedata/
            sourcedata_path = project_path / "sourcedata"
            sourcedata_path.mkdir(exist_ok=True)
            created_files.append("sourcedata/")

            # derivatives/
            derivatives_path = project_path / "derivatives"
            derivatives_path.mkdir(exist_ok=True)
            created_files.append("derivatives/")

            # code/ - for user scripts and project library (YODA-compliant)
            code_path = project_path / "code"
            code_path.mkdir(exist_ok=True)
            created_files.append("code/")

            # Create library structure under code/ (YODA-compliant)
            library_files = self._create_library_structure(project_path, modalities)
            created_files.extend(library_files)

            if datalad_result is not None:
                datalad_result.update(
                    self._create_nested_subdatasets(
                        project_path,
                        str(datalad_result.get("executable") or ""),
                    )
                )
                datalad_result = self._save_datalad_changes(
                    project_path,
                    datalad_result,
                    message="Initialize PRISM dataset structure",
                )

            result = {
                "success": True,
                "path": str(project_path),
                "created_files": created_files,
                "message": f"Project '{name}' created successfully with {len(created_files)} files",
            }
            if datalad_result is not None:
                result["datalad"] = datalad_result
            return result

        except Exception as e:
            result = {"success": False, "error": str(e), "created_files": created_files}
            if datalad_result is not None:
                result["datalad"] = datalad_result
            return result

    def init_on_existing_bids(
        self, path: str, config: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Initialise PRISM Studio on top of an *existing* BIDS root.

        The folder must already contain ``dataset_description.json``; all
        other BIDS files are left untouched.  Only missing PRISM artefacts
        are created (existing files are never overwritten).

        Args:
            path: Absolute path to the existing BIDS dataset root.
            config: Optional study metadata (same keys as create_project).

        Returns:
            Dict with ``success``, ``path``, ``created_files``, ``message``.
        """
        if config is None:
            config = {}

        project_path = Path(path)
        source_result: Optional[Dict[str, Any]] = None

        remote_url = self._normalize_remote_dataset_url(config.get("remote_url"))
        if remote_url:
            source_result = self._acquire_remote_bids_dataset(
                project_path,
                remote_url=remote_url,
            )
            if not source_result.get("success"):
                return source_result

        if not project_path.exists() or not project_path.is_dir():
            return {
                "success": False,
                "error": f"Path does not exist or is not a directory: {path}",
            }

        if not (project_path / "dataset_description.json").exists():
            return {
                "success": False,
                "error": (
                    "No dataset_description.json found.  "
                    "The selected folder does not look like a BIDS root."
                ),
            }

        name = config.get("name") or project_path.name
        modalities = [
            modality
            for modality in PRISM_MODALITIES
            if modality not in BIDS_PASSTHROUGH_MODALITIES
        ]
        created_files: List[str] = []
        datalad_result: Optional[Dict[str, Any]] = None

        try:
            datalad_result = self._create_datalad_dataset(
                project_path,
                enabled=config.get("use_datalad", False),
            )
            gitattributes_created = self._ensure_datalad_editable_metadata_policy(
                project_path,
                datalad_result,
            )
            if gitattributes_created:
                created_files.append(".gitattributes")

            # --- .bidsignore ------------------------------------------------
            bidsignore_path = project_path / ".bidsignore"
            if not bidsignore_path.exists():
                CrossPlatformFile.write_text(
                    str(bidsignore_path), self._create_bidsignore(modalities)
                )
                created_files.append(".bidsignore")

            # --- Sanitize existing dataset_description.json -----------------
            # Strip empty HEDVersion (invalid per BIDS schema — must match hed_version format)
            desc_path = project_path / "dataset_description.json"
            try:
                desc_raw = CrossPlatformFile.read_text(str(desc_path))
                desc_data = json.loads(desc_raw)
                if "HEDVersion" in desc_data and not desc_data.get("HEDVersion"):
                    del desc_data["HEDVersion"]
                    CrossPlatformFile.write_text(
                        str(desc_path),
                        json.dumps(desc_data, indent=2, ensure_ascii=False),
                    )
                    created_files.append(
                        "dataset_description.json (sanitized: removed empty HEDVersion)"
                    )
            except Exception:
                pass  # leave untouched if unreadable

            # --- .prismrc.json ----------------------------------------------
            prismrc_path = project_path / ".prismrc.json"
            if not prismrc_path.exists():
                CrossPlatformFile.write_text(
                    str(prismrc_path),
                    json.dumps(self._create_prismrc(), indent=2),
                )
                created_files.append(".prismrc.json")

            # --- project.json -----------------------------------------------
            project_json_path = project_path / "project.json"
            if not project_json_path.exists():
                CrossPlatformFile.write_text(
                    str(project_json_path),
                    json.dumps(
                        self._create_project_metadata(name, config),
                        indent=2,
                        ensure_ascii=False,
                    ),
                )
                created_files.append("project.json")

            # --- CITATION.cff -----------------------------------------------
            citation_path = project_path / "CITATION.cff"
            if not citation_path.exists():
                CrossPlatformFile.write_text(
                    str(citation_path), self._create_citation_cff(name, config)
                )
                created_files.append("CITATION.cff")

            # --- CHANGES (BIDS standard) ------------------------------------
            changes_path = project_path / "CHANGES"
            if not changes_path.exists():
                CrossPlatformFile.write_text(
                    str(changes_path),
                    f"1.0.0 {date.today().isoformat()}\n"
                    "  - PRISM Studio initialised on existing BIDS dataset.\n",
                )
                created_files.append("CHANGES")

            # --- Standard YODA/BIDS folders ---------------------------------
            for folder in ("sourcedata", "derivatives", "code"):
                folder_path = project_path / folder
                if not folder_path.exists():
                    folder_path.mkdir(exist_ok=True)
                    created_files.append(f"{folder}/")

            if datalad_result is not None:
                datalad_result.update(
                    self._create_nested_subdatasets(
                        project_path,
                        str(datalad_result.get("executable") or ""),
                    )
                )
                datalad_result = self._save_datalad_changes(
                    project_path,
                    datalad_result,
                    message="Initialize PRISM on existing BIDS dataset",
                )

            skipped = (
                "  (existing files were not modified)" if not created_files else ""
            )
            msg = (
                f"PRISM initialised on '{name}': "
                f"{len(created_files)} file(s) added.{skipped}"
            )
            result = {
                "success": True,
                "path": str(project_path),
                "created_files": created_files,
                "message": msg,
            }
            if source_result is not None:
                result["source"] = source_result
            if datalad_result is not None:
                result["datalad"] = datalad_result
            return result

        except Exception as exc:
            result = {"success": False, "error": str(exc), "created_files": created_files}
            if source_result is not None:
                result["source"] = source_result
            if datalad_result is not None:
                result["datalad"] = datalad_result
            return result

    def _normalize_remote_dataset_url(self, remote_url: Any) -> str:
        """Return a supported remote dataset URL or an empty string."""
        normalized = str(remote_url or "").strip()
        if not normalized:
            return ""

        if normalized.startswith("git@"):
            after_at = normalized.split("@", 1)[1] if "@" in normalized else ""
            host, separator, path = after_at.partition(":")
            if host and separator and path:
                return normalized
            return ""

        parsed = urlparse(normalized)
        if parsed.scheme.lower() not in {"http", "https", "ssh", "git"}:
            return ""
        if not parsed.netloc or not parsed.path:
            return ""
        return normalized

    def inspect_remote_dataset_source(self, remote_url: Any) -> Dict[str, Any]:
        """Classify a remote dataset URL for UI preflight and backend routing."""
        normalized_remote_url = self._normalize_remote_dataset_url(remote_url)
        if not normalized_remote_url:
            return {
                "active": bool(str(remote_url or "").strip()),
                "valid": False,
                "remote_url": "",
                "remote_kind": "",
                "requires_datalad": False,
                "clone_method": "",
                "message": (
                    "Git/DataLad URL is invalid. Provide a full https://, ssh://, git:// or git@ URL."
                ),
            }

        remote_info = self._classify_remote_dataset_url(normalized_remote_url)
        requires_datalad = bool(remote_info.get("prefer_datalad"))
        clone_method = "datalad_install" if requires_datalad else "git_clone"
        return {
            "active": True,
            "valid": True,
            "remote_url": normalized_remote_url,
            "remote_kind": str(remote_info.get("kind") or "git"),
            "requires_datalad": requires_datalad,
            "clone_method": clone_method,
            "message": (
                "This OpenNeuro/DataLad dataset will be installed with DataLad."
                if requires_datalad
                else "This remote dataset can be cloned with Git."
            ),
        }

    def _classify_remote_dataset_url(self, remote_url: str) -> Dict[str, Any]:
        """Classify a remote dataset URL for clone/install strategy selection."""
        normalized = str(remote_url or "").strip()
        host = ""
        path = ""

        if normalized.startswith("git@"):
            after_at = normalized.split("@", 1)[1] if "@" in normalized else ""
            host, _, ssh_path = after_at.partition(":")
            path = f"/{ssh_path.lstrip('/')}"
        else:
            parsed = urlparse(normalized)
            host = parsed.netloc
            path = parsed.path or ""

        normalized_host = host.strip().lower()
        normalized_path = path.strip()
        lowered_path = normalized_path.lower()
        is_openneuro_remote = (
            (
                normalized_host in {"openneuro.org", "www.openneuro.org"}
                and lowered_path.startswith("/git/")
            )
            or (
                normalized_host == "github.com"
                and lowered_path.startswith("/openneurodatasets/")
            )
        )

        return {
            "kind": "openneuro" if is_openneuro_remote else "git",
            "host": normalized_host,
            "path": normalized_path,
            "prefer_datalad": is_openneuro_remote,
        }

    def _acquire_remote_bids_dataset(
        self,
        destination_path: Path,
        *,
        remote_url: str,
    ) -> Dict[str, Any]:
        """Clone or install a remote BIDS dataset into a local destination."""
        remote_status = self.inspect_remote_dataset_source(remote_url)
        if not remote_status.get("valid"):
            return {
                "success": False,
                "error": str(
                    remote_status.get("message") or "Remote dataset URL is invalid."
                ),
            }

        normalized_remote_url = str(remote_status.get("remote_url") or "").strip()

        if destination_path.exists():
            if not destination_path.is_dir():
                return {
                    "success": False,
                    "error": (
                        f"Clone destination exists but is not a directory: {destination_path}"
                    ),
                }

            existing_entries = filter_system_files(
                [entry.name for entry in destination_path.iterdir()]
            )
            if existing_entries:
                return {
                    "success": False,
                    "error": (
                        f"Clone destination '{destination_path}' already exists and is not empty. "
                        "Choose an empty folder or a new destination path."
                    ),
                }
        else:
            destination_path.parent.mkdir(parents=True, exist_ok=True)

        clone_method = str(remote_status.get("clone_method") or "git_clone")
        command: List[str]
        step_label = "Git clone"
        datalad_executable_text = ""

        if remote_status.get("requires_datalad"):
            datalad_executable = shutil.which("datalad")
            git_annex_executable = shutil.which("git-annex")
            missing_tools = [
                tool_name
                for tool_name, executable in (
                    ("DataLad", datalad_executable),
                    ("git-annex", git_annex_executable),
                )
                if not executable
            ]
            if missing_tools:
                missing_text = ", ".join(missing_tools)
                return {
                    "success": False,
                    "error": (
                        "This remote looks like an OpenNeuro/DataLad dataset and should "
                        f"be installed with DataLad first. Missing: {missing_text}."
                    ),
                }

            clone_method = "datalad_install"
            step_label = "DataLad install"
            datalad_executable_text = str(datalad_executable or "")
            command = [
                datalad_executable_text,
                "install",
                "-s",
                normalized_remote_url,
                str(destination_path),
            ]
        else:
            command = ["git", "clone", normalized_remote_url, str(destination_path)]

        try:
            process = subprocess.run(
                command,
                capture_output=True,
                text=True,
                check=False,
                timeout=REMOTE_DATASET_ACQUIRE_TIMEOUT_SECONDS,
            )
        except subprocess.TimeoutExpired:
            return {
                "success": False,
                "error": (
                    f"{step_label} timed out after {REMOTE_DATASET_ACQUIRE_TIMEOUT_SECONDS} "
                    "seconds."
                ),
            }
        except Exception as exc:
            return {
                "success": False,
                "error": f"{step_label} failed ({type(exc).__name__}: {exc}).",
            }

        if process.returncode != 0:
            detail = (process.stderr or process.stdout or f"Unknown {step_label} error.").strip()
            summary = (
                self._summarize_datalad_error(detail)
                if clone_method == "datalad_install"
                else detail.splitlines()[0].strip() if detail else f"Unknown {step_label} error."
            )
            return {
                "success": False,
                "error": f"{step_label} failed: {summary}",
            }

        if clone_method == "datalad_install":
            resolve_nested_step_label = "DataLad nested dataset structure sync"
            resolve_nested_command = [
                datalad_executable_text,
                "-C",
                str(destination_path),
                "get",
                "-n",
                "-r",
                ".",
            ]
            try:
                resolve_nested_process = subprocess.run(
                    resolve_nested_command,
                    capture_output=True,
                    text=True,
                    check=False,
                    timeout=REMOTE_DATASET_ACQUIRE_TIMEOUT_SECONDS,
                )
            except subprocess.TimeoutExpired:
                return {
                    "success": False,
                    "error": (
                        f"{resolve_nested_step_label} timed out after "
                        f"{REMOTE_DATASET_ACQUIRE_TIMEOUT_SECONDS} seconds."
                    ),
                }
            except Exception as exc:
                return {
                    "success": False,
                    "error": (
                        f"{resolve_nested_step_label} failed "
                        f"({type(exc).__name__}: {exc})."
                    ),
                }

            if resolve_nested_process.returncode != 0:
                detail = (
                    resolve_nested_process.stderr
                    or resolve_nested_process.stdout
                    or f"Unknown {resolve_nested_step_label} error."
                ).strip()
                return {
                    "success": False,
                    "error": (
                        f"{resolve_nested_step_label} failed: "
                        f"{self._summarize_datalad_error(detail)}"
                    ),
                }

        if clone_method == "datalad_install":
            message = (
                f'Installed OpenNeuro/DataLad dataset from "{normalized_remote_url}" '
                "and resolved nested dataset structure locally."
            )
        else:
            message = f'Cloned remote dataset from "{normalized_remote_url}".'

        return {
            "success": True,
            "path": str(destination_path),
            "remote_url": normalized_remote_url,
            "remote_kind": str(remote_status.get("remote_kind") or "git"),
            "clone_method": clone_method,
            "message": message,
        }

    def validate_structure(self, path: str) -> Dict[str, Any]:
        """
        Validate an existing project's folder structure.

        Args:
            path: Path to the project

        Returns:
            Dict with validation results:
                - valid: Whether structure is valid
                - issues: List of issues found
                - runner_warnings: Non-blocking warnings from canonical validator
                - fixable_issues: List of auto-fixable issues
                - stats: Basic project statistics
        """
        project_path = Path(path)

        if not project_path.exists():
            return {
                "valid": False,
                "error": f"Path does not exist: {path}",
                "issues": [],
                "fixable_issues": [],
            }

        if not project_path.is_dir():
            return {
                "valid": False,
                "error": f"Path is not a directory: {path}",
                "issues": [],
                "fixable_issues": [],
            }

        issues: List[Dict[str, Any]] = []
        runner_warnings: List[Dict[str, Any]] = []
        fixable_issues: List[str] = []
        subject_count = 0
        sessions: set[str] = set()
        modalities: set[str] = set()
        has_dataset_description = False
        has_participants_tsv = False
        has_participants_json = False
        has_bidsignore = False
        participants_tsv_required = False

        # Require project.json at the project root
        project_json_path = project_path / "project.json"
        if not project_json_path.exists():
            code = "PRISM010"
            msg = "Missing project.json at project root"
            issues.append(
                {
                    "code": code,
                    "message": msg,
                    "fix_hint": get_fix_hint(code, msg),
                    "fixable": False,
                }
            )

        # Canonical PRISM location: project folder is the BIDS root.
        bids_root = project_path

        # Check root files (in the identified BIDS root)
        if (bids_root / "dataset_description.json").exists():
            has_dataset_description = True
        else:
            code = "PRISM001"
            msg = "Missing dataset_description.json"
            issues.append(
                {
                    "code": code,
                    "message": msg,
                    "fix_hint": get_fix_hint(code, msg),
                    "fixable": True,
                }
            )
            fixable_issues.append(code)

        if (bids_root / "participants.json").exists():
            has_participants_json = True

        if (bids_root / ".bidsignore").exists():
            has_bidsignore = True

        # Scan for subjects in BIDS root
        for item in bids_root.iterdir():
            if item.is_dir() and item.name.startswith("sub-"):
                subject_count += 1

                # Check for sessions
                for sub_item in item.iterdir():
                    if sub_item.is_dir():
                        if sub_item.name.startswith("ses-"):
                            sessions.add(sub_item.name)
                            # Check modalities in session
                            for mod_item in sub_item.iterdir():
                                if mod_item.is_dir() and not mod_item.name.startswith(
                                    "."
                                ):
                                    modalities.add(mod_item.name)
                        elif not sub_item.name.startswith("."):
                            # Direct modality folder (no session)
                            modalities.add(sub_item.name)

        # participants.tsv is only required after subject folders are present.
        participants_tsv_required = subject_count > 0
        participants_tsv_exists = (bids_root / "participants.tsv").exists()
        has_participants_tsv = participants_tsv_exists or not participants_tsv_required

        if participants_tsv_required and not participants_tsv_exists:
            code = "PRISM004"
            msg = "Missing participants.tsv"
            issues.append(
                {
                    "code": code,
                    "message": msg,
                    "fix_hint": get_fix_hint(code, msg),
                    "fixable": False,
                }
            )

        # Pull canonical validator errors so project-page issues and validator output
        # stay aligned without introducing warning noise into the quick project check.
        try:
            from src.core.validation import validate_dataset as run_dataset_validation

            runner_issues, _runner_stats = run_dataset_validation(
                path,
                verbose=False,
                run_bids=False,
                run_prism=True,
                project_path=path,
            )

            existing_issue_keys = {
                (i.get("code"), i.get("message"), i.get("file_path")) for i in issues
            }
            existing_warning_keys = set()
            for runner_issue in runner_issues:
                if not isinstance(runner_issue, (list, tuple)) or len(runner_issue) < 2:
                    continue

                level = str(runner_issue[0]).upper()
                message = str(runner_issue[1])

                file_path = None
                if len(runner_issue) > 2 and runner_issue[2]:
                    file_path = str(runner_issue[2])

                code = infer_code_from_message(message)

                if level == "WARNING":
                    warning_key = (code, message, file_path)
                    if warning_key in existing_warning_keys:
                        continue

                    runner_warnings.append(
                        {
                            "code": code,
                            "message": message,
                            "fix_hint": get_fix_hint(code, message),
                            "file_path": file_path,
                        }
                    )
                    existing_warning_keys.add(warning_key)
                    continue

                if level != "ERROR":
                    continue

                if "No subjects found in dataset" in message:
                    # Project creation/open workflows allow empty projects.
                    continue

                issue_key = (code, message, file_path)
                if issue_key in existing_issue_keys:
                    continue

                issues.append(
                    {
                        "code": code,
                        "message": message,
                        "fix_hint": get_fix_hint(code, message),
                        "fixable": False,
                        "file_path": file_path,
                    }
                )
                existing_issue_keys.add(issue_key)
        except Exception:
            pass

        stats = {
            "subjects": subject_count,
            "sessions": sorted(sessions),
            "modalities": sorted(modalities),
            "has_dataset_description": has_dataset_description,
            "has_participants_tsv": has_participants_tsv,
            "participants_tsv_required": participants_tsv_required,
            "has_participants_json": has_participants_json,
            "has_bidsignore": has_bidsignore,
            "is_yoda": False,
        }

        # Use DatasetFixer to find additional fixable issues
        try:
            fixer = DatasetFixer(path, dry_run=True)
            fixes = fixer.analyze()
            for fix in fixes:
                if fix.issue_code not in fixable_issues:
                    fixable_issues.append(fix.issue_code)
                    # Add to issues if not already present
                    if not any(i.get("code") == fix.issue_code for i in issues):
                        issues.append(
                            {
                                "code": fix.issue_code,
                                "message": fix.description,
                                "fix_hint": get_fix_hint(
                                    fix.issue_code, fix.description
                                ),
                                "fixable": True,
                                "file_path": fix.file_path,
                            }
                        )
        except Exception:
            pass  # Fixer analysis failed, continue with basic checks

        return {
            "valid": len([i for i in issues if not i.get("fixable", False)]) == 0,
            "issues": issues,
            "runner_warnings": runner_warnings,
            "fixable_issues": fixable_issues,
            "stats": stats,
        }

    def get_fixable_issues(self, path: str) -> List[Dict[str, Any]]:
        """
        Get list of auto-fixable issues for a project.

        Args:
            path: Path to the project

        Returns:
            List of fixable issues with details
        """
        try:
            fixer = DatasetFixer(path, dry_run=True)
            fixes = fixer.analyze()
            return [fix.to_dict() for fix in fixes]
        except Exception as e:
            return [{"error": str(e)}]

    def apply_fixes(
        self, path: str, fix_codes: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        Apply fixes to a project.

        Args:
            path: Path to the project
            fix_codes: Specific fix codes to apply (None = all)

        Returns:
            Dict with results of fix application
        """
        try:
            fixer = DatasetFixer(path, dry_run=False)
            fixer.analyze()
            applied = fixer.apply_fixes(fix_codes)

            return {
                "success": True,
                "applied_fixes": [fix.to_dict() for fix in applied],
                "count": len(applied),
            }
        except Exception as e:
            return {"success": False, "error": str(e), "applied_fixes": []}

    def validate_dataset_description(
        self, description: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """
        Validate a dataset_description dictionary against the schema.

        Args:
            description: The dataset_description content as a dict

        Returns:
            List of issue dicts, empty if valid
        """
        issues = []

        # Load the schema
        schema_dir = Path(__file__).parent.parent / "schemas"
        schema = load_schema("dataset_description", str(schema_dir), version="stable")

        if not schema:
            return [
                {
                    "code": "SCHEMA_ERROR",
                    "message": "Could not load dataset_description schema",
                    "level": "ERROR",
                }
            ]

        try:
            # Use Draft7Validator to get all errors
            validator = Draft7Validator(schema)
            errors = sorted(validator.iter_errors(description), key=lambda e: e.path)

            for error in errors:
                # Format the field path for better reporting
                field_path = " -> ".join([str(p) for p in error.path])
                msg = f"{field_path}: {error.message}" if field_path else error.message

                # Check for specific hints from issues.py
                code = "PRISM301"  # General schema error
                if (
                    "too short" in error.message.lower()
                    or "minlength" in error.message.lower()
                    or "minitems" in error.message.lower()
                ):
                    code = "PRISM301"

                issues.append(
                    {
                        "code": code,
                        "message": msg,
                        "fix_hint": get_fix_hint(code, msg),
                        "level": "ERROR",
                    }
                )
        except Exception as e:
            issues.append(
                {"code": "VALIDATION_ERROR", "message": str(e), "level": "ERROR"}
            )

        return issues

    # =========================================================================
    # Private helper methods
    # =========================================================================

    def _create_dataset_description(
        self, name: str, config: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Create dataset_description.json content following BIDS v1.10.1."""
        if config is None:
            config = {}

        normalized_doi = self._normalize_doi(config.get("doi", ""))

        return {
            "Name": name,
            "BIDSVersion": DEFAULT_BIDS_VERSION,
            "DatasetType": self._normalize_dataset_type(config.get("dataset_type")),
            "Description": config.get("description")
            or "A PRISM-compatible dataset for psychological research.",
            "Acknowledgements": config.get("acknowledgements", ""),
            "Funding": config.get("funding", []),
            "DatasetDOI": normalized_doi,
            "EthicsApprovals": config.get("ethics_approvals", []),
            "Keywords": config.get("keywords", ["psychology", "experiment", "PRISM"]),
            "DatasetLinks": config.get("dataset_links", {}),
            "GeneratedBy": [
                {
                    "Name": "PRISM Validator",
                    "Version": "1.1.1",
                    "Description": "Dataset initialized and managed via PRISM Studio",
                }
            ],
            "SourceDatasets": config.get("source_datasets", []),
        }

    def _normalize_dataset_type(self, dataset_type: Any) -> str:
        """Normalize DatasetType to BIDS-compatible values."""
        value = str(dataset_type or "").strip().lower()
        if value in VALID_DATASET_TYPES:
            return value
        return "raw"

    def _create_participants_tsv(self) -> str:
        """Create participants.tsv header (no sample rows)."""
        return "participant_id\tage\tsex\n"

    def _normalize_feature_toggle(self, value: Any, default: bool = True) -> bool:
        """Normalize optional boolean-style configuration values."""
        if value is None:
            return default
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            normalized = value.strip().lower()
            if normalized in {"0", "false", "no", "off"}:
                return False
            if normalized in {"1", "true", "yes", "on"}:
                return True
        return bool(value)

    def get_datalad_status(self, path: Union[str, Path, None]) -> Dict[str, Any]:
        """Return lightweight DataLad status for a project path."""
        project_path = Path(path) if path else None
        datalad_executable = shutil.which("datalad")
        git_annex_executable = shutil.which("git-annex")
        available = bool(datalad_executable)
        annex_available = bool(git_annex_executable)

        result: Dict[str, Any] = {
            "enabled": False,
            "available": available,
            "annex_available": annex_available,
            "can_save": False,
            "can_enable": False,
            "message": "",
            "path": str(project_path) if project_path else "",
            "subdatasets_total_count": 0,
            "subdatasets_registered_count": 0,
            "subdatasets_remaining_count": 0,
            "subdatasets_progress_percent": 0,
            "next_missing_subdataset": "",
            "subdatasets_topology_mode": "",
            "text_policy_complete": True,
            "text_policy_dataset_count": 0,
            "text_policy_missing_count": 0,
            "text_policy_missing_examples": [],
        }

        if not project_path:
            result["message"] = "Load a project to see DataLad status."
            return result

        if not project_path.exists() or not project_path.is_dir():
            result["message"] = "Current project path is unavailable."
            return result

        if not (project_path / ".datalad").exists():
            if not available:
                result["message"] = (
                    "DataLad is not installed in this environment. "
                    f"{DATALAD_INSTALL_HINT}. Learn more: {DATALAD_DOCS_URL}"
                )
                return result
            if not annex_available:
                result["message"] = (
                    "git-annex is not installed, so new DataLad projects cannot be initialized. "
                    f"{DATALAD_INSTALL_HINT}. Learn more: {DATALAD_DOCS_URL}"
                )
                return result

            result["can_enable"] = True
            result["message"] = "Current project is not a DataLad dataset."
            return result

        result["enabled"] = True
        result.update(self._summarize_nested_subdatasets(project_path))
        result.update(self._summarize_datalad_text_policy(project_path))

        missing_text_policy_count = int(result.get("text_policy_missing_count", 0) or 0)
        text_policy_warning = ""
        if missing_text_policy_count > 0:
            text_policy_warning = (
                " Text-file Git tracking policy is missing in "
                f"{missing_text_policy_count} dataset(s). Use Save DataLad Snapshot "
                "to apply .gitattributes policy across nested datasets."
            )

        if not available:
            result["message"] = (
                "Current project is a DataLad dataset, but the datalad executable "
                "is not available in this environment. "
                f"{DATALAD_INSTALL_HINT}. Learn more: {DATALAD_DOCS_URL}"
            ) + text_policy_warning
            return result

        result["can_save"] = True
        if annex_available:
            if result.get("subdatasets_total_count"):
                if result.get("subdatasets_topology_mode") == "openneuro-registered":
                    result["message"] = (
                        "Current project is tracked by DataLad. "
                        f"OpenNeuro nested subdatasets: {result.get('subdatasets_registered_count', 0)}/"
                        f"{result.get('subdatasets_total_count', 0)} registered "
                        "(this is not the subject count)."
                    )
                else:
                    result["message"] = (
                        "Current project is tracked by DataLad. "
                        f"Nested datasets: {result.get('subdatasets_registered_count', 0)}/"
                        f"{result.get('subdatasets_total_count', 0)} registered."
                    )
            else:
                result["message"] = "Current project is tracked by DataLad."
        else:
            result["message"] = (
                "Current project is tracked by DataLad, but git-annex is not "
                "available in this environment. "
                f"{DATALAD_INSTALL_HINT}. Learn more: {DATALAD_DOCS_URL}"
            )
        if text_policy_warning:
            result["message"] = f"{result['message']}{text_policy_warning}"
        result["executable"] = datalad_executable
        if git_annex_executable:
            result["annex_executable"] = git_annex_executable
        return result

    def save_datalad_snapshot(
        self,
        path: Union[str, Path],
        *,
        message: str,
    ) -> Dict[str, Any]:
        """Persist current project changes into DataLad with a user-supplied message."""
        project_path = Path(path)
        status = self.get_datalad_status(project_path)
        result: Dict[str, Any] = {
            "success": False,
            "path": str(project_path),
            "datalad": dict(status),
        }

        if not project_path.exists() or not project_path.is_dir():
            result["error"] = f"Path does not exist or is not a directory: {project_path}"
            return result

        if not status.get("enabled"):
            result["error"] = status.get("message") or "Current project is not a DataLad dataset."
            return result

        if not status.get("available"):
            result["error"] = status.get("message") or "DataLad is not available in this environment."
            return result

        gitattributes_policy_updated = self._ensure_datalad_editable_metadata_policy(
            project_path,
            {"initialized": True},
        )
        if gitattributes_policy_updated:
            result["datalad"]["gitattributes_policy_updated"] = True

        save_result = self._run_datalad_save(
            project_path,
            message=message,
            datalad_executable=status.get("executable"),
            recursive=True,
        )
        refreshed_status = self.get_datalad_status(project_path)
        save_result.update(refreshed_status)
        if gitattributes_policy_updated:
            save_result["gitattributes_policy_updated"] = True
            save_result["message"] = (
                (save_result.get("message") or "DataLad save completed.")
                + " Updated DataLad text-file tracking policy across dataset roots."
            )
        result["datalad"] = save_result
        if save_result.get("saved") or save_result.get("no_changes"):
            result["success"] = True
            result["message"] = save_result.get("message", "DataLad save completed.")
            return result

        result["error"] = save_result.get("message") or "DataLad save failed."
        return result

    def reapply_datalad_text_policy(
        self,
        path: Union[str, Path],
        *,
        message: str = "Reapply DataLad text-file tracking policy",
    ) -> Dict[str, Any]:
        """Reapply .gitattributes text policy recursively and persist changes."""
        project_path = Path(path)
        status = self.get_datalad_status(project_path)
        result: Dict[str, Any] = {
            "success": False,
            "path": str(project_path),
            "datalad": dict(status),
            "policy_updated": False,
        }

        if not project_path.exists() or not project_path.is_dir():
            result["error"] = f"Path does not exist or is not a directory: {project_path}"
            return result

        if not status.get("enabled"):
            result["error"] = status.get("message") or "Current project is not a DataLad dataset."
            return result

        if not status.get("available"):
            result["error"] = status.get("message") or "DataLad is not available in this environment."
            return result

        policy_updated = self._ensure_datalad_editable_metadata_policy(
            project_path,
            {"initialized": True},
        )
        result["policy_updated"] = bool(policy_updated)

        if not policy_updated:
            refreshed_status = self.get_datalad_status(project_path)
            result["datalad"] = refreshed_status
            result["success"] = True
            result["message"] = "DataLad text-file tracking policy is already up to date."
            return result

        save_result = self._run_datalad_save(
            project_path,
            message=message,
            datalad_executable=status.get("executable"),
            recursive=True,
        )
        refreshed_status = self.get_datalad_status(project_path)
        save_result.update(refreshed_status)
        save_result["gitattributes_policy_updated"] = True
        result["datalad"] = save_result

        if save_result.get("saved") or save_result.get("no_changes"):
            result["success"] = True
            result["message"] = (
                save_result.get("message")
                or "DataLad text-file tracking policy reapplied successfully."
            )
            return result

        result["error"] = save_result.get("message") or "Could not persist DataLad policy updates."
        return result

    def unannex_datalad_text_patterns(
        self,
        path: Union[str, Path],
        *,
        patterns: List[str],
        message: str = "Unannex selected text patterns for Git tracking",
    ) -> Dict[str, Any]:
        """Unannex selected text patterns across nested datasets and save recursively."""
        project_path = Path(path)
        status = self.get_datalad_status(project_path)
        normalized_patterns = self._normalize_datalad_text_patterns(patterns)
        result: Dict[str, Any] = {
            "success": False,
            "path": str(project_path),
            "patterns": normalized_patterns,
            "datalad": dict(status),
            "dataset_roots_scanned": 0,
            "matched_files_count": 0,
            "unannexed_files_count": 0,
            "failure_count": 0,
            "failures": [],
        }

        if not project_path.exists() or not project_path.is_dir():
            result["error"] = f"Path does not exist or is not a directory: {project_path}"
            return result

        if not status.get("enabled"):
            result["error"] = status.get("message") or "Current project is not a DataLad dataset."
            return result

        if not status.get("available"):
            result["error"] = status.get("message") or "DataLad is not available in this environment."
            return result

        if not status.get("annex_available"):
            result["error"] = (
                status.get("message")
                or "git-annex is not available in this environment."
            )
            return result

        if not normalized_patterns:
            result["error"] = "Provide at least one file pattern to unannex."
            return result

        failures: List[Dict[str, str]] = []
        matched_files_count = 0
        unannexed_files_count = 0

        dataset_roots = self._iter_datalad_dataset_roots(project_path)
        result["dataset_roots_scanned"] = len(dataset_roots)

        for dataset_root in dataset_roots:
            find_command = ["git", "annex", "find", "--json"]
            for pattern in normalized_patterns:
                find_command.extend(["--include", pattern])

            try:
                find_process = subprocess.run(
                    find_command,
                    cwd=str(dataset_root),
                    capture_output=True,
                    text=True,
                    check=False,
                    timeout=DATALAD_REPAIR_STEP_TIMEOUT_SECONDS,
                )
            except subprocess.TimeoutExpired:
                failures.append(
                    {
                        "dataset": str(dataset_root),
                        "file": "",
                        "error": self._format_repair_timeout_message(
                            f'git annex find for "{dataset_root.name}"'
                        ),
                    }
                )
                continue
            except Exception as exc:
                failures.append(
                    {
                        "dataset": str(dataset_root),
                        "file": "",
                        "error": f"git annex find failed ({type(exc).__name__}: {exc}).",
                    }
                )
                continue

            if find_process.returncode != 0:
                detail = (find_process.stderr or find_process.stdout or "Unknown git-annex error.").strip()
                failures.append(
                    {
                        "dataset": str(dataset_root),
                        "file": "",
                        "error": f"git annex find failed: {detail}",
                    }
                )
                continue

            annexed_paths: List[str] = []
            seen_paths: set[str] = set()
            for line in (find_process.stdout or "").splitlines():
                record_line = line.strip()
                if not record_line:
                    continue
                try:
                    payload = json.loads(record_line)
                except Exception:
                    continue
                relative_path = str(payload.get("file") or "").strip()
                if not relative_path or relative_path in seen_paths:
                    continue
                seen_paths.add(relative_path)
                annexed_paths.append(relative_path)

            if not annexed_paths:
                continue

            matched_files_count += len(annexed_paths)
            chunk_size = 200
            for offset in range(0, len(annexed_paths), chunk_size):
                chunk = annexed_paths[offset : offset + chunk_size]
                unannex_command = ["git", "annex", "unannex", "--", *chunk]

                try:
                    unannex_process = subprocess.run(
                        unannex_command,
                        cwd=str(dataset_root),
                        capture_output=True,
                        text=True,
                        check=False,
                        timeout=DATALAD_REPAIR_STEP_TIMEOUT_SECONDS,
                    )
                except subprocess.TimeoutExpired:
                    for relative_path in chunk:
                        failures.append(
                            {
                                "dataset": str(dataset_root),
                                "file": relative_path,
                                "error": self._format_repair_timeout_message(
                                    f'git annex unannex for "{relative_path}"'
                                ),
                            }
                        )
                    continue
                except Exception as exc:
                    for relative_path in chunk:
                        failures.append(
                            {
                                "dataset": str(dataset_root),
                                "file": relative_path,
                                "error": f"git annex unannex failed ({type(exc).__name__}: {exc}).",
                            }
                        )
                    continue

                if unannex_process.returncode == 0:
                    unannexed_files_count += len(chunk)
                    continue

                # Retry single files to maximize successful migrations.
                for relative_path in chunk:
                    single_command = ["git", "annex", "unannex", "--", relative_path]
                    try:
                        single_process = subprocess.run(
                            single_command,
                            cwd=str(dataset_root),
                            capture_output=True,
                            text=True,
                            check=False,
                            timeout=DATALAD_REPAIR_STEP_TIMEOUT_SECONDS,
                        )
                    except subprocess.TimeoutExpired:
                        failures.append(
                            {
                                "dataset": str(dataset_root),
                                "file": relative_path,
                                "error": self._format_repair_timeout_message(
                                    f'git annex unannex for "{relative_path}"'
                                ),
                            }
                        )
                        continue
                    except Exception as exc:
                        failures.append(
                            {
                                "dataset": str(dataset_root),
                                "file": relative_path,
                                "error": f"git annex unannex failed ({type(exc).__name__}: {exc}).",
                            }
                        )
                        continue

                    if single_process.returncode == 0:
                        unannexed_files_count += 1
                    else:
                        detail = (
                            single_process.stderr
                            or single_process.stdout
                            or "Unknown git-annex error."
                        ).strip()
                        failures.append(
                            {
                                "dataset": str(dataset_root),
                                "file": relative_path,
                                "error": f"git annex unannex failed: {detail}",
                            }
                        )

        result["matched_files_count"] = matched_files_count
        result["unannexed_files_count"] = unannexed_files_count
        result["failure_count"] = len(failures)
        result["failures"] = failures[:25]

        if matched_files_count == 0:
            refreshed_status = self.get_datalad_status(project_path)
            result["datalad"] = refreshed_status
            result["success"] = True
            result["message"] = "No annexed files matched the selected text patterns."
            return result

        save_result = self._run_datalad_save(
            project_path,
            message=message,
            datalad_executable=status.get("executable"),
            recursive=True,
        )
        refreshed_status = self.get_datalad_status(project_path)
        save_result.update(refreshed_status)
        result["datalad"] = save_result

        if not (save_result.get("saved") or save_result.get("no_changes")):
            result["error"] = save_result.get("message") or "DataLad save failed after unannex."
            return result

        result["success"] = True
        message_parts = [
            (
                f"Unannexed {unannexed_files_count} file(s) matching "
                f"{len(normalized_patterns)} pattern(s) across {len(dataset_roots)} dataset root(s)."
            )
        ]
        if failures:
            message_parts.append(
                f"{len(failures)} file(s) could not be unannexed; see failures for details."
            )
        result["message"] = " ".join(message_parts)
        return result

    def export_project_to_plain_folder(
        self,
        path: Union[str, Path],
        *,
        output_root: Union[str, Path, None] = None,
        scrub_mri_json: bool = False,
        scrub_mri_json_groups: Optional[Set[str]] = None,
        include_derivatives: bool = True,
        include_sourcedata: bool = False,
        include_code: bool = True,
        include_analysis: bool = True,
        exclude_subjects: Optional[set[str]] = None,
        exclude_sessions: Optional[set[str]] = None,
        exclude_modalities: Optional[set[str]] = None,
        exclude_acq: Optional[Dict[str, set[str]]] = None,
        exclude_tasks: Optional[Dict[str, set[str]]] = None,
        materialize_annex_content: bool = False,
    ) -> Dict[str, Any]:
        """Export a project to a plain folder copy without Git/DataLad metadata."""
        project_path = Path(path)
        status = self.get_datalad_status(project_path)
        result: Dict[str, Any] = {
            "success": False,
            "path": str(project_path),
            "datalad": dict(status),
        }

        if not project_path.exists() or not project_path.is_dir():
            result["error"] = f"Path does not exist or is not a directory: {project_path}"
            return result

        destination_root = (
            Path(output_root).expanduser() if output_root else project_path.parent
        ).resolve()

        if destination_root.exists() and not destination_root.is_dir():
            result["error"] = (
                f"Export destination is not a folder: {destination_root}"
            )
            return result

        destination_root.mkdir(parents=True, exist_ok=True)

        def _workspace_lock_file(path: Path) -> Path:
            return path / EXPORT_TEMP_WORKSPACE_LOCKFILE

        def _is_pid_alive(pid: int) -> bool:
            if pid <= 0:
                return False
            try:
                os.kill(pid, 0)
            except ProcessLookupError:
                return False
            except PermissionError:
                return True
            except OSError:
                return False
            return True

        def _workspace_is_active(path: Path) -> bool:
            lock_file = _workspace_lock_file(path)
            if not lock_file.exists():
                return False
            try:
                lock_data = json.loads(lock_file.read_text(encoding="utf-8"))
            except Exception:
                return False

            pid_value = lock_data.get("pid")
            try:
                pid_int = int(pid_value)
            except (TypeError, ValueError):
                return False
            return _is_pid_alive(pid_int)

        def _mark_workspace_active(path: Path) -> None:
            lock_file = _workspace_lock_file(path)
            payload = {
                "pid": os.getpid(),
                "started_at": time.time(),
            }
            try:
                lock_file.write_text(json.dumps(payload), encoding="utf-8")
            except Exception:
                # Best effort only; cleanup logic still falls back to mtime checks.
                pass

        def _cleanup_workspace(path: Optional[Path]) -> bool:
            if path is None:
                return True

            def _onerror(func, target, _exc_info):
                target_path = Path(str(target))
                try:
                    if target_path.is_dir():
                        os.chmod(target_path, stat.S_IRUSR | stat.S_IWUSR | stat.S_IXUSR)
                    else:
                        os.chmod(target_path, stat.S_IRUSR | stat.S_IWUSR)
                except Exception:
                    pass
                try:
                    func(target)
                except Exception:
                    pass

            try:
                if not path.exists():
                    return True

                shutil.rmtree(path, onerror=_onerror)
                if not path.exists():
                    return True

                shutil.rmtree(path, onerror=_onerror)
                return not path.exists()
            except FileNotFoundError:
                return True
            except Exception:
                return False

        def _cleanup_stale_workspaces(root: Path, *, min_age_seconds: int) -> int:
            # Best-effort cleanup for interrupted exports from prior runs.
            removed_count = 0
            stale_cutoff = time.time() - max(0, int(min_age_seconds))
            for candidate in root.glob(f"{EXPORT_TEMP_WORKSPACE_PREFIX}*"):
                if not candidate.is_dir():
                    continue
                if _workspace_is_active(candidate):
                    continue
                try:
                    if candidate.stat().st_mtime > stale_cutoff:
                        continue
                except OSError:
                    continue
                if _cleanup_workspace(candidate):
                    removed_count += 1
            return removed_count

        def _cleanup_stale_workspaces_on_low_space(root: Path) -> int:
            try:
                usage = shutil.disk_usage(root)
            except Exception:
                return 0

            if usage.total <= 0:
                return 0
            low_space = usage.free <= EXPORT_TEMP_WORKSPACE_LOW_FREE_BYTES or (
                usage.free / usage.total
            ) <= EXPORT_TEMP_WORKSPACE_LOW_FREE_RATIO
            if low_space:
                return _cleanup_stale_workspaces(root, min_age_seconds=0)
            return 0

        stale_cleanup_count = _cleanup_stale_workspaces(
            destination_root,
            min_age_seconds=EXPORT_TEMP_WORKSPACE_STALE_SECONDS,
        )
        low_space_cleanup_count = _cleanup_stale_workspaces_on_low_space(destination_root)
        total_cleanup_count = stale_cleanup_count + low_space_cleanup_count
        if total_cleanup_count > 0:
            self._emit_backend_progress(
                (
                    f"Cleaned up {total_cleanup_count} stale temporary export workspace(s) "
                    f"in {destination_root}."
                ),
                command=f'find "{destination_root}" -maxdepth 1 -type d -name "{EXPORT_TEMP_WORKSPACE_PREFIX}*"',
            )

        target_name = f"{project_path.name}_folder_export"
        export_path = destination_root / target_name
        suffix = 2
        while export_path.exists():
            export_path = destination_root / f"{target_name}_{suffix}"
            suffix += 1

        self._emit_backend_progress(
            f'Starting plain folder export for "{project_path.name}".',
            command=(
                f'python prism.py projects export-folder --project "{project_path}" '
                f'--output "{export_path}"'
            ),
        )

        copy_source_path = project_path
        materialized_export = False
        materialization_warnings: List[str] = []
        materialization_workspace: Optional[Path] = None
        workspace_cleanup_error: Optional[str] = None

        materialization_included_top_level_folders = {
            "derivatives": include_derivatives,
            "sourcedata": include_sourcedata,
            "code": include_code,
            "analysis": include_analysis,
        }
        materialization_exclude_subjects = {
            str(label).strip()
            for label in (exclude_subjects or set())
            if str(label).strip()
        }
        materialization_exclude_sessions = {
            str(label).strip()
            for label in (exclude_sessions or set())
            if str(label).strip()
        }
        materialization_exclude_modalities = {
            str(label).strip()
            for label in (exclude_modalities or set())
            if str(label).strip()
        }
        materialization_exclude_acq = {
            str(modality).strip(): {
                str(label).strip() for label in labels if str(label).strip()
            }
            for modality, labels in (exclude_acq or {}).items()
            if str(modality).strip() and labels
        }
        materialization_exclude_tasks = {
            str(modality).strip(): {
                str(label).strip() for label in labels if str(label).strip()
            }
            for modality, labels in (exclude_tasks or {}).items()
            if str(modality).strip() and labels
        }

        def _materialization_should_exclude_entry(
            rel_parts: tuple[str, ...], *, is_dir: bool
        ) -> bool:
            if not rel_parts:
                return False

            if rel_parts[0].startswith("sub-") and rel_parts[0] in materialization_exclude_subjects:
                return True

            if len(rel_parts) == 1:
                root_name = rel_parts[0]
                if root_name in materialization_included_top_level_folders:
                    return not materialization_included_top_level_folders[root_name]
                if not is_dir:
                    survey_task_filters = materialization_exclude_tasks.get("survey", set())
                    if survey_task_filters:
                        task_match = re.search(
                            r"^task-([A-Za-z0-9]+)_survey\\.json$", root_name
                        )
                        if task_match and task_match.group(1) in survey_task_filters:
                            return True
                return False

            if not rel_parts[0].startswith("sub-"):
                return False

            part_index = 1
            if (
                part_index < len(rel_parts)
                and rel_parts[part_index].startswith("ses-")
            ):
                session_label = rel_parts[part_index]
                if session_label in materialization_exclude_sessions:
                    return True
                part_index += 1

            if part_index >= len(rel_parts):
                return False

            modality = rel_parts[part_index]
            if modality in materialization_exclude_modalities:
                return True

            if is_dir:
                return False

            filename = rel_parts[-1]
            excluded_acq_labels = materialization_exclude_acq.get(modality, set())
            if excluded_acq_labels:
                if modality in MRI_SUFFIX_LABEL_MODALITIES:
                    if _matches_excluded_acq_label(filename, excluded_acq_labels):
                        return True
                elif _matches_excluded_acq_label(filename, excluded_acq_labels):
                    return True

            excluded_task_labels = materialization_exclude_tasks.get(modality, set())
            if excluded_task_labels:
                task_label = _extract_export_task_label(filename, modality)
                if task_label and task_label in excluded_task_labels:
                    return True

            return False

        def _collect_materialization_targets(dataset_root: Path) -> List[str]:
            selected_files: List[str] = []
            ignored_names_for_materialization = {
                ".git",
                ".datalad",
                ".gitattributes",
                ".gitignore",
                ".gitmodules",
                "CHANGES",
            }

            for current_dir_raw, dirnames, filenames in os.walk(dataset_root):
                current_dir = Path(current_dir_raw)

                non_system_dirs = set(filter_system_files(dirnames))
                kept_dirs: List[str] = []
                for dirname in dirnames:
                    if dirname not in non_system_dirs:
                        continue
                    if dirname in ignored_names_for_materialization:
                        continue
                    candidate_dir = current_dir / dirname
                    try:
                        rel_parts = candidate_dir.relative_to(dataset_root).parts
                    except ValueError:
                        continue
                    if _materialization_should_exclude_entry(rel_parts, is_dir=True):
                        continue
                    kept_dirs.append(dirname)
                dirnames[:] = kept_dirs

                non_system_files = set(filter_system_files(filenames))
                for filename in filenames:
                    if filename not in non_system_files:
                        continue
                    if filename in ignored_names_for_materialization:
                        continue
                    candidate_file = current_dir / filename
                    try:
                        rel_parts = candidate_file.relative_to(dataset_root).parts
                    except ValueError:
                        continue
                    if _materialization_should_exclude_entry(rel_parts, is_dir=False):
                        continue
                    selected_files.append(Path(*rel_parts).as_posix())

            return sorted(set(selected_files))

        def _collect_materialization_recursive_scope_dirs(dataset_root: Path) -> List[str]:
            # Prefer modality-level roots for scoped recursion. Fall back to session/subject
            # roots only when deeper scope roots are not discoverable pre-materialization.
            subject_dirs: Set[str] = set()
            session_dirs: Set[str] = set()
            modality_dirs: Set[str] = set()

            subject_has_children: Dict[str, bool] = {}
            session_has_modalities: Dict[str, bool] = {}
            ignored_names_for_materialization = {
                ".git",
                ".datalad",
                ".gitattributes",
                ".gitignore",
                ".gitmodules",
                "CHANGES",
            }

            for current_dir_raw, dirnames, _filenames in os.walk(dataset_root):
                current_dir = Path(current_dir_raw)

                non_system_dirs = set(filter_system_files(dirnames))
                kept_dirs: List[str] = []
                for dirname in dirnames:
                    if dirname not in non_system_dirs:
                        continue
                    if dirname in ignored_names_for_materialization:
                        continue
                    candidate_dir = current_dir / dirname
                    try:
                        rel_parts = candidate_dir.relative_to(dataset_root).parts
                    except ValueError:
                        continue
                    if _materialization_should_exclude_entry(rel_parts, is_dir=True):
                        continue
                    kept_dirs.append(dirname)

                    if not rel_parts or not rel_parts[0].startswith("sub-"):
                        continue

                    rel_path = Path(*rel_parts).as_posix()
                    subject_key = rel_parts[0]

                    if len(rel_parts) == 1:
                        subject_dirs.add(rel_path)
                        subject_has_children.setdefault(subject_key, False)
                        continue

                    subject_has_children[subject_key] = True

                    part_index = 1
                    session_key: Optional[str] = None
                    if rel_parts[part_index].startswith("ses-"):
                        session_key = Path(*rel_parts[:2]).as_posix()
                        session_dirs.add(session_key)
                        session_has_modalities.setdefault(session_key, False)
                        part_index += 1

                    if part_index >= len(rel_parts):
                        continue

                    if len(rel_parts) == part_index + 1:
                        modality_dirs.add(rel_path)
                        if session_key:
                            session_has_modalities[session_key] = True
                dirnames[:] = kept_dirs

            selected_dirs: Set[str] = set(modality_dirs)

            for session_dir in sorted(session_dirs):
                if not session_has_modalities.get(session_dir, False):
                    selected_dirs.add(session_dir)

            for subject_dir in sorted(subject_dirs):
                if not subject_has_children.get(subject_dir, False):
                    selected_dirs.add(subject_dir)

            return sorted(selected_dirs)

        if materialize_annex_content:
            if not status.get("enabled"):
                materialization_warnings.append(
                    "Materialized DataLad export was requested, but this project is not tracked by DataLad. "
                    "PRISM exported directly from the current folder."
                )
            else:
                resolved_datalad = str(
                    status.get("executable") or shutil.which("datalad") or ""
                ).strip()
                if not resolved_datalad:
                    result["error"] = (
                        "Materialized DataLad-free folder export requires the datalad executable."
                    )
                    return result

                materialization_workspace = Path(
                    tempfile.mkdtemp(
                        prefix=EXPORT_TEMP_WORKSPACE_PREFIX,
                        dir=str(destination_root),
                    )
                )
                _mark_workspace_active(materialization_workspace)
                clone_source_path = materialization_workspace / project_path.name

                def _run_materialization_step(
                    command: List[str],
                    *,
                    cwd: Optional[Path],
                    step_label: str,
                ) -> tuple[bool, str]:
                    self._emit_backend_progress(
                        f"{step_label} for DataLad-free folder export.",
                        command=" ".join(str(part) for part in command),
                    )
                    try:
                        process = subprocess.run(
                            command,
                            cwd=str(cwd) if cwd else None,
                            capture_output=True,
                            text=True,
                            check=False,
                            timeout=DATALAD_EXPORT_STEP_TIMEOUT_SECONDS,
                        )
                    except subprocess.TimeoutExpired:
                        return (
                            False,
                            f"{step_label} timed out after {DATALAD_EXPORT_STEP_TIMEOUT_SECONDS} seconds.",
                        )
                    except Exception as exc:
                        return (
                            False,
                            f"{step_label} failed ({type(exc).__name__}: {exc}).",
                        )

                    if process.returncode == 0:
                        return True, ""

                    detail = (process.stderr or process.stdout or "").strip()
                    return (
                        False,
                        f"{step_label} failed: {self._summarize_datalad_error(detail)}",
                    )

                clone_ok, clone_error = _run_materialization_step(
                    [
                        resolved_datalad,
                        "clone",
                        str(project_path),
                        str(clone_source_path),
                    ],
                    cwd=None,
                    step_label="DataLad clone",
                )
                if not clone_ok:
                    if not _cleanup_workspace(materialization_workspace):
                        clone_error = (
                            f"{clone_error} Temporary export workspace could not be deleted: "
                            f"{materialization_workspace}"
                        )
                    result["error"] = clone_error
                    return result

                def _run_datalad_get_chunks(
                    target_chunks: List[List[str]],
                    *,
                    recursive: bool,
                    no_data: bool,
                    step_label_prefix: str,
                ) -> bool:
                    get_failed_local = False
                    base_command = [resolved_datalad, "get"]
                    if recursive:
                        base_command.append("-r")
                    if no_data:
                        # Install/resolve nested dataset structure without pulling full file payloads.
                        base_command.append("-n")

                    def _without_no_data_flag(command: List[str]) -> List[str]:
                        return [part for part in command if part != "-n"]

                    for chunk_index, chunk in enumerate(target_chunks, start=1):
                        active_base_command = list(base_command)
                        get_ok, get_error = _run_materialization_step(
                            [*active_base_command, "--on-failure", "ignore", *chunk],
                            cwd=clone_source_path,
                            step_label=(
                                f"{step_label_prefix} "
                                f"({chunk_index}/{len(target_chunks)})"
                            ),
                        )

                        if (
                            not get_ok
                            and no_data
                            and any(
                                fragment in str(get_error or "").lower()
                                for fragment in [
                                    "unknown argument: -n",
                                    "unrecognized arguments: -n",
                                    "unknown option: -n",
                                ]
                            )
                        ):
                            active_base_command = _without_no_data_flag(active_base_command)
                            get_ok, get_error = _run_materialization_step(
                                [*active_base_command, "--on-failure", "ignore", *chunk],
                                cwd=clone_source_path,
                                step_label=(
                                    f"{step_label_prefix} "
                                    f"({chunk_index}/{len(target_chunks)}) no-data compatibility fallback"
                                ),
                            )

                        if (
                            not get_ok
                            and "--on-failure" in str(get_error or "").lower()
                            and (
                                "unknown argument" in str(get_error or "").lower()
                                or "unrecognized arguments" in str(get_error or "").lower()
                            )
                        ):
                            get_ok, get_error = _run_materialization_step(
                                [*active_base_command, *chunk],
                                cwd=clone_source_path,
                                step_label=(
                                    f"{step_label_prefix} "
                                    f"({chunk_index}/{len(target_chunks)}) compatibility fallback"
                                ),
                            )
                        if not get_ok:
                            get_failed_local = True
                            if str(get_error or "").strip():
                                materialization_warnings.append(get_error)

                    return get_failed_local

                selected_recursive_scope_dirs = _collect_materialization_recursive_scope_dirs(
                    clone_source_path
                )
                if selected_recursive_scope_dirs:
                    scope_chunks = [
                        selected_recursive_scope_dirs[index:index + 200]
                        for index in range(0, len(selected_recursive_scope_dirs), 200)
                    ]
                    scope_get_failed = _run_datalad_get_chunks(
                        scope_chunks,
                        recursive=True,
                        no_data=True,
                        step_label_prefix="DataLad get selected scope metadata recursively",
                    )
                    if scope_get_failed:
                        materialization_warnings.append(
                            "DataLad get could not fully recurse selected scope metadata; "
                            "continuing with locally available files."
                        )

                selected_materialization_targets = _collect_materialization_targets(
                    clone_source_path
                )

                has_subject_scope_dirs = any(
                    str(path).startswith("sub-")
                    for path in selected_recursive_scope_dirs
                )
                has_subject_materialization_targets = any(
                    str(path).startswith("sub-")
                    for path in selected_materialization_targets
                )

                if has_subject_scope_dirs and not has_subject_materialization_targets:
                    scope_chunks = [
                        selected_recursive_scope_dirs[index:index + 200]
                        for index in range(0, len(selected_recursive_scope_dirs), 200)
                    ]
                    scope_data_get_failed = _run_datalad_get_chunks(
                        scope_chunks,
                        recursive=True,
                        no_data=False,
                        step_label_prefix="DataLad get selected scope data recursively fallback",
                    )
                    if scope_data_get_failed:
                        materialization_warnings.append(
                            "DataLad fallback recursion could not materialize all selected scope data; "
                            "continuing with locally available files."
                        )
                    selected_materialization_targets = _collect_materialization_targets(
                        clone_source_path
                    )

                if not selected_materialization_targets:
                    materialization_warnings.append(
                        "No files matched the current folder export scope after materialization preflight; "
                        "continuing with folder structure only."
                    )

                target_chunks = [
                    selected_materialization_targets[index:index + 200]
                    for index in range(0, len(selected_materialization_targets), 200)
                ]

                get_failed = _run_datalad_get_chunks(
                    target_chunks,
                    recursive=False,
                    no_data=False,
                    step_label_prefix="DataLad get selected export content",
                )

                if get_failed:
                    materialization_warnings.append(
                        "DataLad get could not retrieve all selected export content from remotes; "
                        "continuing with locally available files."
                    )

                resolved_annex = str(
                    status.get("annex_executable") or shutil.which("git-annex") or ""
                ).strip()
                if not resolved_annex and target_chunks:
                    materialization_warnings.append(
                        "git-annex executable is unavailable; continuing without unlock."
                    )
                if resolved_annex:
                    unlock_failed = False
                    for chunk_index, chunk in enumerate(target_chunks, start=1):
                        unlock_ok, unlock_error = _run_materialization_step(
                            [resolved_annex, "unlock", *chunk],
                            cwd=clone_source_path,
                            step_label=(
                                "git annex unlock selected export content "
                                f"({chunk_index}/{len(target_chunks)})"
                            ),
                        )
                        if not unlock_ok:
                            unlock_failed = True
                            if str(unlock_error or "").strip():
                                materialization_warnings.append(unlock_error)

                    if unlock_failed:
                        materialization_warnings.append(
                            "git annex unlock could not unlock all selected export files. "
                            "Continuing with symlink-following copy."
                        )

                selected_subject_scope_dirs = [
                    scope_dir
                    for scope_dir in selected_recursive_scope_dirs
                    if str(scope_dir).startswith("sub-")
                ]

                def _has_visible_files_in_selected_scopes(
                    dataset_root: Path,
                    scope_dirs: List[str],
                ) -> bool:
                    ignored_names_for_visibility_scan = {
                        ".git",
                        ".datalad",
                        ".gitattributes",
                        ".gitignore",
                        ".gitmodules",
                        "CHANGES",
                    }

                    for scope_dir in scope_dirs:
                        scope_path = dataset_root / scope_dir
                        if not scope_path.exists() or not scope_path.is_dir():
                            continue

                        for current_dir_raw, dirnames, filenames in os.walk(scope_path):
                            current_dir = Path(current_dir_raw)

                            non_system_dirs = set(filter_system_files(dirnames))
                            dirnames[:] = [
                                dirname
                                for dirname in dirnames
                                if dirname in non_system_dirs
                                and dirname not in ignored_names_for_visibility_scan
                            ]

                            non_system_files = set(filter_system_files(filenames))
                            for filename in filenames:
                                if filename not in non_system_files:
                                    continue
                                if filename in ignored_names_for_visibility_scan:
                                    continue

                                candidate_file = current_dir / filename
                                try:
                                    rel_parts = candidate_file.relative_to(dataset_root).parts
                                except ValueError:
                                    continue

                                if _materialization_should_exclude_entry(
                                    rel_parts,
                                    is_dir=False,
                                ):
                                    continue

                                if candidate_file.exists() and candidate_file.is_file():
                                    return True
                    return False

                clone_has_visible_subject_files = _has_visible_files_in_selected_scopes(
                    clone_source_path,
                    selected_subject_scope_dirs,
                )
                source_has_visible_subject_files = _has_visible_files_in_selected_scopes(
                    project_path,
                    selected_subject_scope_dirs,
                )

                if (
                    selected_subject_scope_dirs
                    and not clone_has_visible_subject_files
                    and source_has_visible_subject_files
                ):
                    materialization_warnings.append(
                        "Temporary clone did not expose selected subject files in the working tree; "
                        "exporting selected scope directly from the source project files."
                    )
                    copy_source_path = project_path
                else:
                    copy_source_path = clone_source_path
                materialized_export = True

        ignored_names = {
            ".git",
            ".datalad",
            ".gitattributes",
            ".gitignore",
            ".gitmodules",
            "CHANGES",
        }

        included_top_level_folders = {
            "derivatives": include_derivatives,
            "sourcedata": include_sourcedata,
            "code": include_code,
            "analysis": include_analysis,
        }

        normalized_exclude_subjects = {
            str(label).strip()
            for label in (exclude_subjects or set())
            if str(label).strip()
        }

        normalized_exclude_sessions = {
            str(label).strip()
            for label in (exclude_sessions or set())
            if str(label).strip()
        }
        normalized_exclude_modalities = {
            str(label).strip()
            for label in (exclude_modalities or set())
            if str(label).strip()
        }
        normalized_exclude_acq = {
            str(modality).strip(): {
                str(label).strip() for label in labels if str(label).strip()
            }
            for modality, labels in (exclude_acq or {}).items()
            if str(modality).strip() and labels
        }
        normalized_exclude_tasks = {
            str(modality).strip(): {
                str(label).strip() for label in labels if str(label).strip()
            }
            for modality, labels in (exclude_tasks or {}).items()
            if str(modality).strip() and labels
        }
        missing_source_paths: List[str] = []

        def _should_exclude_export_entry(rel_parts: tuple[str, ...], *, is_dir: bool) -> bool:
            if not rel_parts:
                return False

            if rel_parts[0].startswith("sub-") and rel_parts[0] in normalized_exclude_subjects:
                return True

            if len(rel_parts) == 1:
                root_name = rel_parts[0]
                if root_name in included_top_level_folders:
                    return not included_top_level_folders[root_name]
                if not is_dir:
                    survey_task_filters = normalized_exclude_tasks.get("survey", set())
                    if survey_task_filters:
                        task_match = re.search(
                            r"^task-([A-Za-z0-9]+)_survey\\.json$", root_name
                        )
                        if task_match and task_match.group(1) in survey_task_filters:
                            return True
                return False

            if not rel_parts[0].startswith("sub-"):
                return False

            part_index = 1
            if (
                part_index < len(rel_parts)
                and rel_parts[part_index].startswith("ses-")
            ):
                session_label = rel_parts[part_index]
                if session_label in normalized_exclude_sessions:
                    return True
                part_index += 1

            if part_index >= len(rel_parts):
                return False

            modality = rel_parts[part_index]
            if modality in normalized_exclude_modalities:
                return True

            if is_dir:
                return False

            filename = rel_parts[-1]
            excluded_acq_labels = normalized_exclude_acq.get(modality, set())
            if excluded_acq_labels:
                if modality in MRI_SUFFIX_LABEL_MODALITIES:
                    if _matches_excluded_acq_label(filename, excluded_acq_labels):
                        return True
                elif _matches_excluded_acq_label(filename, excluded_acq_labels):
                    return True

            excluded_task_labels = normalized_exclude_tasks.get(modality, set())
            if excluded_task_labels:
                task_label = _extract_export_task_label(filename, modality)
                if task_label and task_label in excluded_task_labels:
                    return True

            return False

        def _ignore(_current_dir: str, names: List[str]) -> List[str]:
            current_dir = Path(_current_dir)
            filtered_names: List[str] = []
            non_system_names = set(filter_system_files(names))
            for name in names:
                if name not in non_system_names:
                    filtered_names.append(name)
                    continue

                if name in ignored_names:
                    filtered_names.append(name)
                    continue

                candidate = current_dir / name
                try:
                    rel_parts = candidate.relative_to(copy_source_path).parts
                except ValueError:
                    continue

                if candidate.is_symlink() and not candidate.exists():
                    missing_source_paths.append(str(candidate))
                    filtered_names.append(name)
                    continue

                if _should_exclude_export_entry(rel_parts, is_dir=candidate.is_dir()):
                    filtered_names.append(name)

            return filtered_names

        def _copy_with_missing_tolerance(src: str, dst: str) -> str:
            try:
                return shutil.copy2(src, dst)
            except FileNotFoundError:
                missing_source_paths.append(src)
                return dst
            except OSError as exc:
                if exc.errno == 2:
                    missing_source_paths.append(src)
                    return dst
                raise

        def _count_visible_scoped_subject_files(root_path: Path) -> int:
            visible_file_count = 0
            for current_dir_raw, dir_names, file_names in os.walk(root_path):
                current_dir = Path(current_dir_raw)
                try:
                    rel_root_parts = current_dir.relative_to(root_path).parts
                except Exception:
                    continue

                non_system_dirs = set(filter_system_files(dir_names))
                kept_dirs: List[str] = []
                for dir_name in list(dir_names):
                    if dir_name not in non_system_dirs:
                        continue
                    if dir_name in ignored_names:
                        continue

                    rel_parts = rel_root_parts + (dir_name,)
                    if _should_exclude_export_entry(rel_parts, is_dir=True):
                        continue
                    kept_dirs.append(dir_name)
                dir_names[:] = kept_dirs

                non_system_files = set(filter_system_files(file_names))
                for file_name in file_names:
                    if file_name not in non_system_files:
                        continue
                    if file_name in ignored_names:
                        continue

                    rel_parts = rel_root_parts + (file_name,)
                    if not rel_parts or not rel_parts[0].startswith("sub-"):
                        continue
                    if _should_exclude_export_entry(rel_parts, is_dir=False):
                        continue

                    candidate = current_dir / file_name
                    if candidate.exists() and candidate.is_file():
                        visible_file_count += 1

            return visible_file_count

        try:
            self._emit_backend_progress(
                f'Starting filesystem copy for plain folder export "{export_path.name}".',
                command=f'cp -a "{copy_source_path}" "{export_path}"',
            )
            shutil.copytree(
                copy_source_path,
                export_path,
                copy_function=_copy_with_missing_tolerance,
                ignore=_ignore,
                symlinks=False,
                ignore_dangling_symlinks=False,
            )
        except Exception as exc:
            result["error"] = f"Could not export project folder: {exc}"
            return result
        finally:
            if not _cleanup_workspace(materialization_workspace):
                workspace_cleanup_error = (
                    "Temporary export workspace could not be deleted after export: "
                    f"{materialization_workspace}"
                )

        if materialized_export and copy_source_path != project_path:
            exported_visible_subject_files = _count_visible_scoped_subject_files(
                export_path
            )
            source_visible_subject_files = _count_visible_scoped_subject_files(
                project_path
            )

            if (
                exported_visible_subject_files == 0
                and source_visible_subject_files > 0
            ):
                materialization_warnings.append(
                    "Materialized temporary clone export contained no scoped subject files; "
                    "retrying scoped copy directly from source project files."
                )

                try:
                    shutil.rmtree(export_path, ignore_errors=True)
                except Exception:
                    pass

                missing_source_paths = []
                copy_source_path = project_path
                try:
                    self._emit_backend_progress(
                        (
                            "Retrying filesystem copy from source project because "
                            "temporary clone did not expose scoped subject files."
                        ),
                        command=f'cp -a "{copy_source_path}" "{export_path}"',
                    )
                    shutil.copytree(
                        copy_source_path,
                        export_path,
                        copy_function=_copy_with_missing_tolerance,
                        ignore=_ignore,
                        symlinks=False,
                        ignore_dangling_symlinks=False,
                    )
                except Exception as exc:
                    result["error"] = f"Could not export project folder: {exc}"
                    return result

        scrubbed_sidecars = 0
        scrubbed_fields = 0
        scrub_errors: List[str] = []
        if scrub_mri_json:
            try:
                from src.mri_json_scrubber import (
                    detect_modality_from_path,
                    scan_mri_jsons,
                    scrub_sensitive_json_fields,
                )

                for sidecar_path in scan_mri_jsons(export_path):
                    try:
                        with open(sidecar_path, "r", encoding="utf-8") as sidecar_file:
                            payload = json.load(sidecar_file)
                        if not isinstance(payload, dict):
                            continue

                        modality = detect_modality_from_path(sidecar_path)
                        scrubbed_payload, removed_fields = scrub_sensitive_json_fields(
                            payload,
                            modality=modality,
                            selected_groups=scrub_mri_json_groups,
                        )
                        if not removed_fields:
                            continue

                        with open(sidecar_path, "w", encoding="utf-8") as sidecar_file:
                            json.dump(
                                scrubbed_payload,
                                sidecar_file,
                                indent=2,
                                ensure_ascii=False,
                            )
                        scrubbed_sidecars += 1
                        scrubbed_fields += len(removed_fields)
                    except Exception as exc:
                        try:
                            rel_sidecar = sidecar_path.relative_to(export_path).as_posix()
                        except Exception:
                            rel_sidecar = str(sidecar_path)
                        scrub_errors.append(f"{rel_sidecar}: {exc}")
            except Exception as exc:
                scrub_errors.append(f"MRI scrub initialization failed: {exc}")

            if scrubbed_sidecars or scrub_errors:
                self._emit_backend_progress(
                    (
                        "Applied MRI JSON scrub to plain folder export "
                        f"({scrubbed_sidecars} file(s), {scrubbed_fields} field(s) removed)."
                    ),
                    command=(
                        f'python prism.py projects export-folder --project "{project_path}" '
                        f'--output "{export_path}" --scrub-mri-json'
                    ),
                )
            if scrub_errors:
                materialization_warnings.append(
                    "MRI JSON scrub skipped some files: " + "; ".join(scrub_errors[:5])
                )

        if materialized_export and missing_source_paths:
            # A temporary clone can miss locally present annex payloads; recover from source project.
            unresolved_source_paths: List[str] = []
            recovered_missing_files = 0
            for source_path in sorted(set(missing_source_paths)):
                source_candidate = Path(str(source_path))
                try:
                    rel_path = source_candidate.relative_to(copy_source_path)
                except Exception:
                    unresolved_source_paths.append(str(source_candidate))
                    continue

                original_candidate = project_path / rel_path
                if not original_candidate.exists() or original_candidate.is_dir():
                    unresolved_source_paths.append(str(source_candidate))
                    continue

                destination_candidate = export_path / rel_path
                try:
                    destination_candidate.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(str(original_candidate), str(destination_candidate))
                    recovered_missing_files += 1
                except FileNotFoundError:
                    unresolved_source_paths.append(str(source_candidate))
                except OSError as exc:
                    if exc.errno == 2:
                        unresolved_source_paths.append(str(source_candidate))
                    else:
                        raise

            if recovered_missing_files:
                materialization_warnings.append(
                    f"Recovered {recovered_missing_files} file(s) from the source project "
                    "after temporary clone materialization left them unavailable."
                )
            missing_source_paths = unresolved_source_paths

        bidsignore_rules_added: List[str] = []
        try:
            from src.bids_integration import check_and_update_bidsignore

            bidsignore_rules_added = check_and_update_bidsignore(
                str(export_path),
                PRISM_MODALITIES,
            )
        except Exception as exc:
            materialization_warnings.append(
                f"Could not update .bidsignore in exported folder: {exc}"
            )

        if workspace_cleanup_error:
            result["error"] = workspace_cleanup_error
            return result

        result["success"] = True
        result["output_path"] = str(export_path)
        if scrub_mri_json:
            result["scrubbed_mri_json_files"] = scrubbed_sidecars
            result["scrubbed_mri_json_fields"] = scrubbed_fields
        result["excluded_repository_metadata"] = sorted(ignored_names)
        result["message"] = f"Project folder export created at {export_path} without Git/DataLad metadata."
        if bidsignore_rules_added:
            result["bidsignore_rules_added"] = sorted(bidsignore_rules_added)
        if materialized_export:
            result["materialized_export"] = True
        if materialization_warnings:
            result["materialization_warnings"] = materialization_warnings[:10]
        if missing_source_paths:
            relative_missing_paths: List[str] = []
            for source_path in sorted(set(missing_source_paths)):
                source_candidate = Path(str(source_path))
                try:
                    relative_missing_paths.append(
                        source_candidate.relative_to(copy_source_path).as_posix()
                    )
                except Exception:
                    relative_missing_paths.append(str(source_path))

            unique_missing_paths = sorted(set(relative_missing_paths))
            result["partial_export"] = True
            result["missing_files_count"] = len(unique_missing_paths)
            result["missing_files_preview"] = unique_missing_paths[:20]
            result["missing_files_preview_root"] = str(project_path)
            if status.get("enabled"):
                warning = (
                    f"Skipped {len(unique_missing_paths)} file(s) that are not available locally. "
                    "This project is tracked by DataLad/git-annex; run 'datalad get -r .' "
                    "in the project folder, then export again to include all annexed content."
                )
            else:
                warning = (
                    f"Skipped {len(unique_missing_paths)} file(s) that were not found during export. "
                    "Re-run export after restoring missing files if you need a complete copy."
                )
            result["warning"] = warning
            result["message"] = f"{result['message']} {warning}"
        self._emit_backend_progress(
            f'Finished plain folder export for "{project_path.name}".',
            command=f'open "{export_path}"',
        )
        return result

    def preview_plain_folder_export_availability(
        self,
        path: Union[str, Path],
        *,
        include_derivatives: bool = True,
        include_sourcedata: bool = False,
        include_code: bool = True,
        include_analysis: bool = True,
        exclude_subjects: Optional[set[str]] = None,
        exclude_sessions: Optional[set[str]] = None,
        exclude_modalities: Optional[set[str]] = None,
        exclude_acq: Optional[Dict[str, set[str]]] = None,
        exclude_tasks: Optional[Dict[str, set[str]]] = None,
    ) -> Dict[str, Any]:
        """Report missing local files for the current plain folder export scope."""
        project_path = Path(path)
        status = self.get_datalad_status(project_path)
        result: Dict[str, Any] = {
            "success": False,
            "path": str(project_path),
            "datalad": dict(status),
            "is_datalad_dataset": bool(status.get("enabled")),
        }

        if not project_path.exists() or not project_path.is_dir():
            result["error"] = f"Path does not exist or is not a directory: {project_path}"
            return result

        ignored_names = {
            ".git",
            ".datalad",
            ".gitattributes",
            ".gitignore",
            ".gitmodules",
            "CHANGES",
        }

        included_top_level_folders = {
            "derivatives": include_derivatives,
            "sourcedata": include_sourcedata,
            "code": include_code,
            "analysis": include_analysis,
        }

        normalized_exclude_subjects = {
            str(label).strip()
            for label in (exclude_subjects or set())
            if str(label).strip()
        }

        normalized_exclude_sessions = {
            str(label).strip()
            for label in (exclude_sessions or set())
            if str(label).strip()
        }
        normalized_exclude_modalities = {
            str(label).strip()
            for label in (exclude_modalities or set())
            if str(label).strip()
        }
        normalized_exclude_acq = {
            str(modality).strip(): {
                str(label).strip() for label in labels if str(label).strip()
            }
            for modality, labels in (exclude_acq or {}).items()
            if str(modality).strip() and labels
        }
        normalized_exclude_tasks = {
            str(modality).strip(): {
                str(label).strip() for label in labels if str(label).strip()
            }
            for modality, labels in (exclude_tasks or {}).items()
            if str(modality).strip() and labels
        }

        def _should_exclude_export_entry(rel_parts: tuple[str, ...], *, is_dir: bool) -> bool:
            if not rel_parts:
                return False

            if rel_parts[0].startswith("sub-") and rel_parts[0] in normalized_exclude_subjects:
                return True

            if len(rel_parts) == 1:
                root_name = rel_parts[0]
                if root_name in included_top_level_folders:
                    return not included_top_level_folders[root_name]
                if not is_dir:
                    survey_task_filters = normalized_exclude_tasks.get("survey", set())
                    if survey_task_filters:
                        task_match = re.search(
                            r"^task-([A-Za-z0-9]+)_survey\\.json$", root_name
                        )
                        if task_match and task_match.group(1) in survey_task_filters:
                            return True
                return False

            if not rel_parts[0].startswith("sub-"):
                return False

            part_index = 1
            if (
                part_index < len(rel_parts)
                and rel_parts[part_index].startswith("ses-")
            ):
                session_label = rel_parts[part_index]
                if session_label in normalized_exclude_sessions:
                    return True
                part_index += 1

            if part_index >= len(rel_parts):
                return False

            modality = rel_parts[part_index]
            if modality in normalized_exclude_modalities:
                return True

            if is_dir:
                return False

            filename = rel_parts[-1]
            excluded_acq_labels = normalized_exclude_acq.get(modality, set())
            if excluded_acq_labels:
                if modality in MRI_SUFFIX_LABEL_MODALITIES:
                    if _matches_excluded_acq_label(filename, excluded_acq_labels):
                        return True
                elif _matches_excluded_acq_label(filename, excluded_acq_labels):
                    return True

            excluded_task_labels = normalized_exclude_tasks.get(modality, set())
            if excluded_task_labels:
                task_label = _extract_export_task_label(filename, modality)
                if task_label and task_label in excluded_task_labels:
                    return True

            return False

        missing_paths: List[str] = []

        for root, dir_names, file_names in os.walk(project_path):
            current_dir = Path(root)
            rel_root_parts = current_dir.relative_to(project_path).parts

            non_system_dirs = set(filter_system_files(dir_names))
            kept_dirs: List[str] = []
            for dir_name in list(dir_names):
                if dir_name not in non_system_dirs:
                    continue
                if dir_name in ignored_names:
                    continue

                rel_parts = rel_root_parts + (dir_name,)
                candidate = current_dir / dir_name

                if _should_exclude_export_entry(rel_parts, is_dir=True):
                    continue

                if candidate.is_symlink() and not candidate.exists():
                    missing_paths.append(Path(*rel_parts).as_posix())
                    continue

                kept_dirs.append(dir_name)

            dir_names[:] = kept_dirs

            non_system_files = set(filter_system_files(file_names))
            for file_name in file_names:
                if file_name not in non_system_files:
                    continue
                if file_name in ignored_names:
                    continue

                rel_parts = rel_root_parts + (file_name,)
                if _should_exclude_export_entry(rel_parts, is_dir=False):
                    continue

                candidate = current_dir / file_name
                if candidate.is_symlink() and not candidate.exists():
                    missing_paths.append(Path(*rel_parts).as_posix())

        unique_missing_paths = sorted(set(missing_paths))
        missing_count = len(unique_missing_paths)

        result["success"] = True
        result["missing_files_count"] = missing_count
        result["missing_files_preview"] = unique_missing_paths[:20]
        result["missing_files_preview_root"] = str(project_path)
        result["complete"] = missing_count == 0

        if status.get("enabled"):
            hint_command = f'datalad -C "{project_path}" get -r .'
            result["hint_command"] = hint_command
            if missing_count:
                result["message"] = (
                    f"Detected {missing_count} file(s) that are not available locally for the current export scope."
                )
            else:
                result["message"] = (
                    "All selected files appear available locally for folder export."
                )
        elif missing_count:
            result["message"] = (
                f"Detected {missing_count} missing file target(s) in the current export scope."
            )
        else:
            result["message"] = (
                "Project is not tracked by DataLad and no missing local file targets were detected."
            )

        return result

    def autosave_datalad_snapshot(
        self,
        path: Union[str, Path],
        *,
        reason: str,
    ) -> Dict[str, Any]:
        """Best-effort DataLad autosave used when PRISM changes project context."""
        project_path = Path(path)
        normalized_reason = str(reason or "").strip() or "session_closed"
        status = self.get_datalad_status(project_path)
        result: Dict[str, Any] = {
            "success": False,
            "attempted": False,
            "skipped": False,
            "reason": normalized_reason,
            "path": str(project_path),
            "datalad": dict(status),
        }

        if not project_path.exists() or not project_path.is_dir():
            result["skipped"] = True
            result["message"] = f"Path does not exist or is not a directory: {project_path}"
            return result

        if not status.get("enabled"):
            result["success"] = True
            result["skipped"] = True
            result["message"] = status.get("message") or "Current project is not a DataLad dataset."
            return result

        if not status.get("available"):
            result["message"] = status.get("message") or "DataLad is not available in this environment."
            return result

        save_result = self._run_datalad_save(
            project_path,
            message=self._build_auto_datalad_save_message(normalized_reason),
            datalad_executable=status.get("executable"),
        )
        refreshed_status = self.get_datalad_status(project_path)
        save_result.update(refreshed_status)
        result["attempted"] = True
        result["datalad"] = save_result

        if save_result.get("saved") or save_result.get("no_changes"):
            result["success"] = True
            result["message"] = save_result.get("message") or "DataLad auto-save completed."
            return result

        result["error"] = save_result.get("message") or "DataLad auto-save failed."
        result["message"] = result["error"]
        return result

    def enable_datalad_for_project(
        self,
        path: Union[str, Path],
        *,
        message: str = "Enable DataLad for PRISM project",
    ) -> Dict[str, Any]:
        """Initialize DataLad for an existing project and save an initial snapshot."""
        project_path = Path(path)
        result: Dict[str, Any] = {
            "success": False,
            "path": str(project_path),
        }

        if not project_path.exists() or not project_path.is_dir():
            result["error"] = f"Path does not exist or is not a directory: {project_path}"
            result["datalad"] = self.get_datalad_status(project_path)
            return result

        status = self.get_datalad_status(project_path)
        if status.get("enabled"):
            datalad_executable = status.get("executable") or shutil.which("datalad")
            if datalad_executable:
                datalad_result: Dict[str, Any] = {
                    "requested": True,
                    "available": True,
                    "initialized": True,
                    "saved": False,
                    "executable": str(datalad_executable),
                }
                gitattributes_policy_updated = (
                    self._ensure_datalad_editable_metadata_policy(
                        project_path,
                        {"initialized": True},
                    )
                )
                if gitattributes_policy_updated:
                    datalad_result["gitattributes_policy_updated"] = True
                datalad_result.update(
                    self._create_nested_subdatasets(
                        project_path,
                        str(datalad_executable),
                        max_to_create=1,
                    )
                )

                created_subdatasets = datalad_result.get(
                    "subdatasets_created",
                    [],
                )
                failed_subdatasets = datalad_result.get(
                    "subdataset_failures",
                    [],
                )
                remaining_subdatasets = int(
                    datalad_result.get("subdatasets_remaining_count", 0)
                )
                if created_subdatasets:
                    save_result = self._run_datalad_save(
                        project_path,
                        message=message,
                        datalad_executable=str(datalad_executable),
                    )
                    datalad_result.update(save_result)
                    if save_result.get("saved"):
                        if remaining_subdatasets > 0:
                            datalad_result["message"] = (
                                f'Current project is already tracked by DataLad. Added '
                                f'{len(created_subdatasets)} nested subdataset(s) and saved '
                                f'with message "{message}". {remaining_subdatasets} '
                                f'nested subdataset(s) remain; run repair again to continue.'
                            )
                        else:
                            datalad_result["message"] = (
                                f'Current project is already tracked by DataLad. Added '
                                f'{len(created_subdatasets)} nested subdataset(s) '
                                f'and saved with message "{message}".'
                            )
                    elif save_result.get("no_changes"):
                        if remaining_subdatasets > 0:
                            datalad_result["message"] = (
                                f"Current project is already tracked by DataLad. Added "
                                f"{len(created_subdatasets)} nested subdataset(s). "
                                f"{remaining_subdatasets} nested subdataset(s) remain; run "
                                f"repair again to continue."
                            )
                        else:
                            datalad_result["message"] = (
                                f"Current project is already tracked by DataLad. Added "
                                f"{len(created_subdatasets)} nested subdataset(s)."
                            )
                    else:
                        datalad_result["message"] = (
                            save_result.get("message")
                            or "DataLad save failed while registering nested subdatasets."
                        )
                elif failed_subdatasets:
                    datalad_result["message"] = (
                        "DataLad repair could not register the next missing nested "
                        f"dataset: {failed_subdatasets[0]}"
                    )
                else:
                    datalad_result.update(status)
                    if gitattributes_policy_updated:
                        datalad_result["message"] = (
                            "Current project is already tracked by DataLad. "
                            "Updated DataLad text-file tracking defaults in .gitattributes."
                        )
                    else:
                        datalad_result["message"] = "Current project is already tracked by DataLad."

                message_text = datalad_result.get("message")
                progress_total = int(datalad_result.get("subdatasets_total_count", 0) or 0)
                progress_registered = int(
                    datalad_result.get("subdatasets_registered_count", 0) or 0
                )
                progress_remaining = int(
                    datalad_result.get("subdatasets_remaining_count", 0) or 0
                )
                progress_next_missing = str(
                    datalad_result.get("next_missing_subdataset") or ""
                ).strip()
                refreshed_status = self.get_datalad_status(project_path)
                datalad_result.update(refreshed_status)
                if progress_total and int(datalad_result.get("subdatasets_total_count", 0) or 0) < progress_total:
                    datalad_result["subdatasets_total_count"] = progress_total
                if progress_registered and int(datalad_result.get("subdatasets_registered_count", 0) or 0) < progress_registered:
                    datalad_result["subdatasets_registered_count"] = progress_registered
                if progress_remaining < int(datalad_result.get("subdatasets_remaining_count", 0) or 0):
                    datalad_result["subdatasets_remaining_count"] = progress_remaining
                if progress_total:
                    registered_count = int(
                        datalad_result.get("subdatasets_registered_count", 0) or 0
                    )
                    total_count = int(
                        datalad_result.get("subdatasets_total_count", 0) or 0
                    )
                    datalad_result["subdatasets_progress_percent"] = (
                        100 if total_count == 0 else int((registered_count * 100) / total_count)
                    )
                if progress_next_missing and not str(datalad_result.get("next_missing_subdataset") or "").strip():
                    datalad_result["next_missing_subdataset"] = progress_next_missing
                if message_text:
                    datalad_result["message"] = message_text
                result["success"] = True
                result["message"] = datalad_result.get("message") or "Current project is already tracked by DataLad."
                result["datalad"] = datalad_result
                return result

            result["success"] = True
            result["message"] = "Current project is already tracked by DataLad."
            result["datalad"] = status
            return result

        datalad_result = self._create_datalad_dataset(project_path, enabled=True)
        refreshed_status = self.get_datalad_status(project_path)

        if not datalad_result.get("initialized"):
            datalad_result.update(refreshed_status)
            result["error"] = datalad_result.get("message") or "Could not enable DataLad for this project."
            result["datalad"] = datalad_result
            return result

        gitattributes_policy_updated = self._ensure_datalad_editable_metadata_policy(
            project_path,
            datalad_result,
        )
        if gitattributes_policy_updated:
            datalad_result["gitattributes_policy_updated"] = True

        datalad_result = self._save_datalad_changes(
            project_path,
            datalad_result,
            message=message,
        )
        refreshed_status = self.get_datalad_status(project_path)
        if not refreshed_status.get("enabled") and datalad_result.get("initialized"):
            refreshed_status["enabled"] = True
            refreshed_status["available"] = bool(datalad_result.get("available"))
            refreshed_status["can_save"] = bool(
                datalad_result.get("saved")
                or datalad_result.get("no_changes")
                or datalad_result.get("available")
            )
            refreshed_status["message"] = (
                datalad_result.get("message")
                or "DataLad enabled for the current project."
            )
        datalad_result.update(refreshed_status)
        result["datalad"] = datalad_result
        result["success"] = bool(
            refreshed_status.get("enabled") or datalad_result.get("initialized")
        )

        if result["success"]:
            result["message"] = datalad_result.get("message") or "DataLad enabled for the current project."
            return result

        result["error"] = datalad_result.get("message") or "Could not enable DataLad for this project."
        return result

    def _create_datalad_dataset(
        self,
        project_path: Path,
        enabled: Union[bool, str, None] = True,
    ) -> Dict[str, Any]:
        """Initialise a DataLad dataset when requested and available."""
        requested = self._normalize_feature_toggle(enabled, default=True)
        result: Dict[str, Any] = {
            "requested": requested,
            "available": False,
            "initialized": False,
            "saved": False,
            "message": "",
        }

        existing_datalad_root = (project_path / ".datalad").exists()
        datalad_executable = shutil.which("datalad")
        git_annex_executable = shutil.which("git-annex")

        if existing_datalad_root:
            result["available"] = bool(datalad_executable)
            result["annex_available"] = bool(git_annex_executable)
            result["initialized"] = True
            result["message"] = "Current project is already tracked by DataLad."
            if datalad_executable:
                result["executable"] = datalad_executable
            if git_annex_executable:
                result["annex_executable"] = git_annex_executable
            return result

        if not requested:
            result["message"] = "DataLad initialization skipped by user choice."
            return result

        result["available"] = bool(datalad_executable)
        if not datalad_executable:
            result["message"] = (
                "DataLad is not installed in this environment. PRISM continued without "
                f"DataLad integration. {DATALAD_INSTALL_HINT}. Learn more: {DATALAD_DOCS_URL}"
            )
            return result

        result["annex_available"] = bool(git_annex_executable)
        if not git_annex_executable:
            result["message"] = (
                "git-annex is not installed in this environment. PRISM continued "
                f"without DataLad integration. {DATALAD_INSTALL_HINT}. Learn more: {DATALAD_DOCS_URL}"
            )
            return result

        result["executable"] = datalad_executable
        result["annex_executable"] = git_annex_executable

        try:
            process = subprocess.run(
                [datalad_executable, "create", "--force"],
                cwd=str(project_path),
                capture_output=True,
                text=True,
                check=False,
            )
        except Exception as exc:
            result["message"] = (
                f"DataLad initialization failed ({type(exc).__name__}: {exc}). "
                "PRISM continued without DataLad integration."
            )
            return result

        if process.returncode != 0:
            detail = (process.stderr or process.stdout or "Unknown DataLad error").strip()
            result["message"] = (
                f"DataLad initialization failed: {detail}. "
                "PRISM continued without DataLad integration."
            )
            return result

        nested_result = self._create_nested_subdatasets(
            project_path,
            datalad_executable,
        )
        result.update(nested_result)
        result["initialized"] = True
        result["message"] = "DataLad dataset initialized."
        return result

    def _create_nested_subdatasets(
        self,
        project_path: Path,
        datalad_executable: str,
        *,
        max_to_create: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Create nested DataLad subdatasets under an existing project dataset."""
        created_paths: List[str] = []
        existing_paths: List[str] = []
        failed_paths: List[str] = []
        skipped_paths: List[str] = []

        if not datalad_executable:
            return {
                "subdatasets_created": created_paths,
                "subdatasets_existing": existing_paths,
                "subdataset_failures": failed_paths,
                "subdatasets_skipped": skipped_paths,
                "subdatasets_total_count": 0,
                "subdatasets_registered_count": 0,
                "subdatasets_remaining_count": 0,
                "subject_datasets_created": created_paths,
                "subject_datasets_existing": existing_paths,
                "subject_dataset_failures": failed_paths,
            }

        nested_dataset_paths = self._iter_nested_dataset_paths(project_path)
        registered_paths = self._get_registered_nested_dataset_paths(
            project_path,
            datalad_executable=datalad_executable,
        )
        missing_dataset_paths = [
            dataset_path
            for dataset_path in nested_dataset_paths
            if not self._is_registered_nested_dataset(
                project_path,
                dataset_path,
                registered_paths=registered_paths,
            )
        ]
        remaining_budget = max_to_create if max_to_create is not None else None

        for dataset_path in nested_dataset_paths:
            relative_dataset_path = dataset_path.relative_to(project_path)
            relative_dataset_text = relative_dataset_path.as_posix()

            if self._is_registered_nested_dataset(
                project_path,
                dataset_path,
                registered_paths=registered_paths,
            ):
                existing_paths.append(relative_dataset_text)
                continue

            if self._is_datalad_dataset(dataset_path):
                failed_paths.append(
                    f"{relative_dataset_text} ({self._build_nested_step_failure('verify nested dataset registration', 'local DataLad metadata exists but the parent dataset does not list this path as a registered subdataset')})"
                )
                continue

            if remaining_budget is not None and remaining_budget <= 0:
                skipped_paths.append(relative_dataset_text)
                continue

            if self._parent_tracks_nested_dataset_path(
                project_path,
                dataset_path,
            ) or self._parent_has_staged_nested_dataset_deletions(
                project_path,
                dataset_path,
            ):
                migration_result = self._migrate_parent_tracked_directory_to_subdataset(
                    project_path,
                    dataset_path,
                    datalad_executable,
                )
                if migration_result.get("success"):
                    registered_paths.add(relative_dataset_text)
                    created_paths.append(relative_dataset_text)
                    if remaining_budget is not None:
                        remaining_budget -= 1
                    continue

                failed_paths.append(
                    f"{relative_dataset_text} ({migration_result.get('message') or 'Could not migrate tracked parent content.'})"
                )
                continue

            create_result = self._create_registered_nested_dataset(
                project_path,
                dataset_path,
                datalad_executable,
            )
            if not create_result.get("success"):
                failed_paths.append(
                    f"{relative_dataset_text} ({create_result.get('message') or 'Could not create nested DataLad dataset.'})"
                )
                continue

            registered_paths = self._get_registered_nested_dataset_paths(
                project_path,
                datalad_executable=datalad_executable,
            )

            created_paths.append(relative_dataset_text)
            if remaining_budget is not None:
                remaining_budget -= 1

        return {
            "subdatasets_created": created_paths,
            "subdatasets_existing": existing_paths,
            "subdataset_failures": failed_paths,
            "subdatasets_skipped": skipped_paths,
            "subdatasets_total_count": len(nested_dataset_paths),
            "subdatasets_registered_count": len(existing_paths) + len(created_paths),
            "subdatasets_missing_before": [
                dataset_path.relative_to(project_path).as_posix()
                for dataset_path in missing_dataset_paths
            ],
            "subdatasets_remaining_count": len(missing_dataset_paths) - len(created_paths),
            "subject_datasets_created": created_paths,
            "subject_datasets_existing": existing_paths,
            "subject_dataset_failures": failed_paths,
        }

    def _parent_tracks_nested_dataset_path(
        self,
        project_path: Path,
        dataset_path: Path,
    ) -> bool:
        """Return True when the parent dataset already tracks content below a nested path."""
        relative_dataset_text = dataset_path.relative_to(project_path).as_posix()
        try:
            process = subprocess.run(
                ["git", "ls-files", "-z", "--", relative_dataset_text],
                cwd=str(project_path),
                capture_output=True,
                text=False,
                check=False,
            )
        except Exception:
            return False

        return process.returncode == 0 and bool(process.stdout)

    def _parent_has_staged_nested_dataset_deletions(
        self,
        project_path: Path,
        dataset_path: Path,
    ) -> bool:
        """Return True when a nested path is already staged for deletion from the parent dataset."""
        relative_dataset_text = dataset_path.relative_to(project_path).as_posix()
        try:
            process = subprocess.run(
                ["git", "diff", "--cached", "--name-only", "--", relative_dataset_text],
                cwd=str(project_path),
                capture_output=True,
                text=True,
                check=False,
            )
        except Exception:
            return False

        return process.returncode == 0 and bool(str(process.stdout or "").strip())

    def _emit_backend_progress(
        self,
        message: str,
        *,
        command: str = "",
    ) -> None:
        """Emit an immediate terminal progress line for long DataLad repair steps."""
        try:
            from flask import current_app, has_app_context

            if not has_app_context():
                return

            from src.web.backend_monitoring import emit_backend_action

            payload = str(message or "").strip()
            command_text = str(command or "").strip()
            if not payload:
                return
            if command_text:
                payload = f"{payload}\ncmd={command_text}"
            emit_backend_action(
                payload,
                app_root=str(Path(current_app.root_path)),
                prefix="PROJECT",
                force_emit=True,
            )
        except Exception:
            pass

    def _format_repair_timeout_message(self, step_label: str) -> str:
        return (
            f"{step_label} timed out after {DATALAD_REPAIR_STEP_TIMEOUT_SECONDS} seconds. "
            "Large tracked directories can take a while; please review the backend terminal output and retry."
        )

    def _build_nested_step_failure(self, step_label: str, detail: str = "") -> str:
        """Return a step-scoped nested dataset failure message."""
        normalized_step = str(step_label or "nested DataLad step").strip()
        normalized_detail = self._summarize_datalad_error(detail) if detail else ""
        if normalized_detail:
            return f"{normalized_step} failed: {normalized_detail}"
        return f"{normalized_step} failed"

    def _get_registered_nested_dataset_paths(
        self,
        project_path: Path,
        *,
        datalad_executable: Optional[str] = None,
    ) -> set[str]:
        """Return nested paths registered in the parent dataset."""
        registered_paths: set[str] = set()

        gitmodules_path = project_path / ".gitmodules"
        if gitmodules_path.is_file():
            try:
                for line in gitmodules_path.read_text(encoding="utf-8").splitlines():
                    match = re.match(r"^\s*path\s*=\s*(.+?)\s*$", line)
                    if not match:
                        continue
                    candidate_path = match.group(1).strip()
                    if candidate_path:
                        registered_paths.add(candidate_path)
            except OSError:
                pass

        resolved_executable = datalad_executable or shutil.which("datalad")
        if not resolved_executable:
            return registered_paths

        try:
            process = subprocess.run(
                [str(resolved_executable), "subdatasets"],
                cwd=str(project_path),
                capture_output=True,
                text=True,
                check=False,
                timeout=REGISTERED_SUBDATASET_QUERY_TIMEOUT_SECONDS,
            )
        except Exception:
            return registered_paths

        if process.returncode != 0:
            return registered_paths

        for line in str(process.stdout or "").splitlines():
            match = re.search(r"\):\s+(.*?)\s+\((?:dataset|gitmodule)\)\s*$", line.strip())
            if not match:
                continue
            candidate_path = match.group(1).strip()
            if candidate_path:
                registered_paths.add(candidate_path)

        return registered_paths

    def _is_registered_nested_dataset(
        self,
        project_path: Path,
        dataset_path: Path,
        *,
        registered_paths: Optional[set[str]] = None,
        datalad_executable: Optional[str] = None,
    ) -> bool:
        """Return True only when the parent dataset registers this nested dataset."""
        relative_dataset_text = dataset_path.relative_to(project_path).as_posix()
        resolved_registered_paths = (
            registered_paths
            if registered_paths is not None
            else self._get_registered_nested_dataset_paths(
                project_path,
                datalad_executable=datalad_executable,
            )
        )
        return relative_dataset_text in resolved_registered_paths

    def _migrate_parent_tracked_directory_to_subdataset(
        self,
        project_path: Path,
        dataset_path: Path,
        datalad_executable: str,
    ) -> Dict[str, Any]:
        """Convert a parent-tracked directory into a nested DataLad subdataset."""
        relative_dataset_text = dataset_path.relative_to(project_path).as_posix()
        stage_parent_message = (
            "PRISM: Converting data into nested PRISM-structure "
            f'(prepare parent untracking "{relative_dataset_text}")'
        )
        parent_tracks_dataset_path = self._parent_tracks_nested_dataset_path(
            project_path,
            dataset_path,
        )
        staged_parent_deletions = self._parent_has_staged_nested_dataset_deletions(
            project_path,
            dataset_path,
        )

        if parent_tracks_dataset_path:
            remove_command = ["git", "rm", "--cached", "-r", "--", relative_dataset_text]
            self._emit_backend_progress(
                f'Preparing nested DataLad dataset for "{relative_dataset_text}" by untracking parent-owned content.',
                command=" ".join(remove_command),
            )
            try:
                remove_process = subprocess.run(
                    remove_command,
                    cwd=str(project_path),
                    capture_output=True,
                    text=True,
                    check=False,
                    timeout=DATALAD_REPAIR_STEP_TIMEOUT_SECONDS,
                )
            except subprocess.TimeoutExpired:
                return {
                    "success": False,
                    "message": self._format_repair_timeout_message(
                        f'Untracking parent content under "{relative_dataset_text}"'
                    ),
                }
            if remove_process.returncode != 0:
                detail = (
                    remove_process.stderr
                    or remove_process.stdout
                    or "Could not untrack parent content."
                ).strip()
                return {
                    "success": False,
                    "message": self._build_nested_step_failure(
                        "untrack parent content",
                        detail,
                    ),
                }
        elif staged_parent_deletions:
            return self._migrate_staged_parent_deletions_to_subdataset(
                project_path,
                dataset_path,
                datalad_executable,
                stage_parent_message=stage_parent_message,
            )
        else:
            return {
                "success": False,
                "message": self._build_nested_step_failure(
                    "verify parent tracking state",
                    "parent dataset no longer tracks this path and no staged parent deletions were found",
                ),
            }

        self._emit_backend_progress(
            f'Checkpointing parent dataset before creating nested dataset "{relative_dataset_text}".',
            command=(
                f'{datalad_executable} save --updated -m '
                f'"{stage_parent_message}"'
            ),
        )
        prep_save_result = self._run_datalad_save(
            project_path,
            message=stage_parent_message,
            datalad_executable=datalad_executable,
            updated_only=True,
        )
        if not (prep_save_result.get("saved") or prep_save_result.get("no_changes")):
            detail = prep_save_result.get("message") or "Could not save parent dataset state."
            return {
                "success": False,
                "message": self._build_nested_step_failure(
                    "save parent staging state",
                    detail,
                ),
            }

        parent_still_tracks = self._parent_tracks_nested_dataset_path(
            project_path,
            dataset_path,
        )
        parent_has_staged_deletions = self._parent_has_staged_nested_dataset_deletions(
            project_path,
            dataset_path,
        )
        if parent_still_tracks:
            return {
                "success": False,
                "message": self._build_nested_step_failure(
                    "verify parent untracking",
                    (
                        "parent dataset still tracks content under "
                        f'"{relative_dataset_text}" after updated-only staging save'
                    ),
                ),
            }
        if parent_has_staged_deletions:
            return self._migrate_staged_parent_deletions_to_subdataset(
                project_path,
                dataset_path,
                datalad_executable,
                stage_parent_message=stage_parent_message,
            )

        create_result = self._create_registered_nested_dataset(
            project_path,
            dataset_path,
            datalad_executable,
        )
        if create_result.get("success"):
            return {
                "success": True,
                "message": "Migrated tracked parent content into a nested DataLad dataset.",
            }
        return create_result

    def _migrate_staged_parent_deletions_to_subdataset(
        self,
        project_path: Path,
        dataset_path: Path,
        datalad_executable: str,
        *,
        stage_parent_message: str,
    ) -> Dict[str, Any]:
        """Finalize a nested dataset migration when parent deletions are already staged."""
        relative_dataset_text = dataset_path.relative_to(project_path).as_posix()
        self._emit_backend_progress(
            f'Continuing nested DataLad migration for "{relative_dataset_text}" from staged parent deletions.',
            command=f'git diff --cached --name-only -- {relative_dataset_text}',
        )

        staged_dataset_path: Optional[Path] = None
        if dataset_path.exists() and dataset_path.is_dir():
            try:
                has_existing_content = any(dataset_path.iterdir())
            except Exception as exc:
                return {
                    "success": False,
                    "message": self._build_nested_step_failure(
                        "inspect existing directory content",
                        f"{type(exc).__name__}: {exc}",
                    ),
                }
            if has_existing_content:
                staged_dataset_path = self._build_nested_dataset_staging_path(
                    project_path,
                    dataset_path,
                )
                self._emit_backend_progress(
                    f'Parking existing content before committing parent deletions for "{relative_dataset_text}".',
                    command=f'mv "{dataset_path}" "{staged_dataset_path}"',
                )
                try:
                    dataset_path.rename(staged_dataset_path)
                except Exception as exc:
                    return {
                        "success": False,
                        "message": self._build_nested_step_failure(
                            "stage existing directory content",
                            f"{type(exc).__name__}: {exc}",
                        ),
                    }

        self._emit_backend_progress(
            f'Checkpointing staged parent deletions before creating nested dataset "{relative_dataset_text}".',
            command=(
                f'git commit -m "{stage_parent_message}" -- '
                f'{relative_dataset_text}'
            ),
        )
        prep_save_result = self._run_git_commit_for_path(
            project_path,
            relative_dataset_text=relative_dataset_text,
            message=stage_parent_message,
        )
        if not (prep_save_result.get("saved") or prep_save_result.get("no_changes")):
            restore_detail = self._restore_staged_nested_dataset_content(
                dataset_path,
                staged_dataset_path,
            )
            detail = prep_save_result.get("message") or "Could not commit parent dataset state."
            if restore_detail:
                detail = f"{detail} {restore_detail}".strip()
            return {
                "success": False,
                "message": self._build_nested_step_failure(
                    "save parent staging state",
                    detail,
                ),
            }

        if self._parent_tracks_nested_dataset_path(
            project_path,
            dataset_path,
        ) or self._parent_has_staged_nested_dataset_deletions(
            project_path,
            dataset_path,
        ):
            restore_detail = self._restore_staged_nested_dataset_content(
                dataset_path,
                staged_dataset_path,
            )
            detail = (
                "parent dataset still tracks or has staged deletions under "
                f'"{relative_dataset_text}" after path-scoped parent commit'
            )
            if restore_detail:
                detail = f"{detail} {restore_detail}".strip()
            return {
                "success": False,
                "message": self._build_nested_step_failure(
                    "verify parent untracking",
                    detail,
                ),
            }

        create_result = self._create_registered_nested_dataset(
            project_path,
            dataset_path,
            datalad_executable,
            staged_dataset_path=staged_dataset_path,
        )
        if create_result.get("success"):
            return {
                "success": True,
                "message": "Migrated tracked parent content into a nested DataLad dataset.",
            }
        return create_result

    def _create_registered_nested_dataset(
        self,
        project_path: Path,
        dataset_path: Path,
        datalad_executable: str,
        *,
        staged_dataset_path: Optional[Path] = None,
    ) -> Dict[str, Any]:
        """Create a registered nested DataLad dataset, staging existing content aside if needed."""
        relative_dataset_text = dataset_path.relative_to(project_path).as_posix()

        if staged_dataset_path is None and dataset_path.exists() and dataset_path.is_dir():
            try:
                has_existing_content = any(dataset_path.iterdir())
            except Exception as exc:
                return {
                    "success": False,
                    "message": self._build_nested_step_failure(
                        "inspect existing directory content",
                        f"{type(exc).__name__}: {exc}",
                    ),
                }
            if has_existing_content:
                staged_dataset_path = self._build_nested_dataset_staging_path(
                    project_path,
                    dataset_path,
                )
                self._emit_backend_progress(
                    f'Parking existing content before creating nested dataset "{relative_dataset_text}".',
                    command=(
                        f'mv "{dataset_path}" "{staged_dataset_path}"'
                    ),
                )
                try:
                    dataset_path.rename(staged_dataset_path)
                except Exception as exc:
                    return {
                        "success": False,
                        "message": self._build_nested_step_failure(
                            "stage existing directory content",
                            f"{type(exc).__name__}: {exc}",
                        ),
                    }

        create_command = [
            datalad_executable,
            "create",
            "-d",
            ".",
            "--force",
            relative_dataset_text,
        ]
        self._emit_backend_progress(
            f'Creating nested DataLad dataset "{relative_dataset_text}".',
            command=" ".join(create_command),
        )
        try:
            create_process = subprocess.run(
                create_command,
                cwd=str(project_path),
                capture_output=True,
                text=True,
                check=False,
                timeout=DATALAD_REPAIR_STEP_TIMEOUT_SECONDS,
            )
        except subprocess.TimeoutExpired:
            return {
                "success": False,
                "message": self._format_repair_timeout_message(
                    f'Creating nested DataLad dataset "{relative_dataset_text}"'
                ),
            }
        if create_process.returncode != 0:
            detail = (
                create_process.stderr
                or create_process.stdout
                or "Unknown DataLad error"
            ).strip()
            rollback_detail = self._restore_staged_nested_dataset_content(
                dataset_path,
                staged_dataset_path,
                remove_created_dataset=True,
            )
            if rollback_detail:
                detail = f"{detail} {rollback_detail}".strip()
            return {
                "success": False,
                "message": self._build_nested_step_failure(
                    "create nested dataset",
                    detail,
                ),
            }

        if staged_dataset_path is not None:
            self._emit_backend_progress(
                f'Restoring content into nested DataLad dataset "{relative_dataset_text}".',
                command=(
                    f'mv "{staged_dataset_path}"/* "{dataset_path}"/'
                ),
            )
            restore_detail = self._restore_staged_nested_dataset_content(
                dataset_path,
                staged_dataset_path,
            )
            if restore_detail:
                return {
                    "success": False,
                    "message": self._build_nested_step_failure(
                        "restore nested dataset content",
                        restore_detail,
                    ),
                }

        self._emit_backend_progress(
            f'Saving nested DataLad dataset "{dataset_path.name}".',
            command=(
                f'{datalad_executable} -C {dataset_path} save -m '
                f'"PRISM: Nested structure conversion '
                f'(initialize \"{dataset_path.name}\")"'
            ),
        )
        nested_save_result = self._run_datalad_save(
            dataset_path,
            message=(
                "PRISM: Nested structure conversion "
                f'(initialize "{dataset_path.name}")'
            ),
            datalad_executable=datalad_executable,
        )
        if not (nested_save_result.get("saved") or nested_save_result.get("no_changes")):
            detail = nested_save_result.get("message") or "Could not save nested dataset."
            return {
                "success": False,
                "message": self._build_nested_step_failure(
                    "save nested dataset",
                    detail,
                ),
            }

        if not self._is_registered_nested_dataset(
            project_path,
            dataset_path,
            datalad_executable=datalad_executable,
        ):
            return {
                "success": False,
                "message": self._build_nested_step_failure(
                    "verify nested dataset registration",
                    "parent dataset still does not list this path as a registered subdataset after create/save",
                ),
            }

        return {
            "success": True,
            "message": "Created nested DataLad dataset.",
        }

    def _build_nested_dataset_staging_path(
        self,
        project_path: Path,
        dataset_path: Path,
    ) -> Path:
        """Return a unique hidden staging path for temporary nested dataset moves."""
        relative_dataset_text = dataset_path.relative_to(project_path).as_posix()
        safe_label = relative_dataset_text.replace("/", "__")
        staged_dataset_path = project_path / f".prism-datalad-stage-{safe_label}"
        suffix = 1
        while staged_dataset_path.exists():
            staged_dataset_path = project_path / f".prism-datalad-stage-{safe_label}-{suffix}"
            suffix += 1
        return staged_dataset_path

    def _restore_staged_nested_dataset_content(
        self,
        dataset_path: Path,
        staged_dataset_path: Optional[Path],
        *,
        remove_created_dataset: bool = False,
    ) -> str:
        """Restore staged directory content into the nested dataset path."""
        if staged_dataset_path is None or not staged_dataset_path.exists():
            return ""

        try:
            if remove_created_dataset and dataset_path.exists():
                if dataset_path.is_dir() and not any(dataset_path.iterdir()):
                    dataset_path.rmdir()
                else:
                    return (
                        f'could not restore staged content because "{dataset_path}" '
                        "already contains unexpected files"
                    )

            if not dataset_path.exists():
                staged_dataset_path.rename(dataset_path)
                return ""

            if not dataset_path.is_dir():
                return f'could not restore staged content because "{dataset_path}" is not a directory'

            for child in list(staged_dataset_path.iterdir()):
                child.rename(dataset_path / child.name)
            staged_dataset_path.rmdir()
            return ""
        except Exception as exc:
            return f"{type(exc).__name__}: {exc}"

    def _summarize_datalad_error(self, detail: str) -> str:
        """Reduce verbose DataLad stderr/stdout into a concise UI-safe summary."""
        normalized_detail = str(detail or "Unknown DataLad error.").strip()
        if not normalized_detail:
            return "Unknown DataLad error."

        lowered_detail = normalized_detail.lower()
        if "collision with content in parent dataset" in lowered_detail:
            return "parent dataset still tracks content under this directory"
        if "nothing to save" in lowered_detail:
            return "no changes were pending"

        first_line = normalized_detail.splitlines()[0].strip()
        if len(first_line) > 220:
            return first_line[:217].rstrip() + "..."
        return first_line

    def _is_openneuro_remote_dataset(self, project_path: Path) -> bool:
        """Return True when a project's origin remote matches OpenNeuro patterns."""
        try:
            process = subprocess.run(
                ["git", "config", "--get", "remote.origin.url"],
                cwd=str(project_path),
                capture_output=True,
                text=True,
                check=False,
            )
        except Exception:
            return False

        if process.returncode != 0:
            return False

        remote_url = str(process.stdout or "").strip()
        if not remote_url:
            return False

        remote_info = self._classify_remote_dataset_url(remote_url)
        return str(remote_info.get("kind") or "").lower() == "openneuro"

    def _summarize_nested_subdatasets(self, project_path: Path) -> Dict[str, Any]:
        """Return nested DataLad registration progress for a project."""
        registered_paths = self._get_registered_nested_dataset_paths(project_path)
        if self._is_openneuro_remote_dataset(project_path):
            # OpenNeuro/DataLad datasets can legitimately use a topology where only
            # a subset of subject directories are nested datasets.
            nested_dataset_paths = [
                project_path / rel_path
                for rel_path in sorted(registered_paths)
                if rel_path
            ]
            topology_mode = "openneuro-registered"
        else:
            nested_dataset_paths = self._iter_nested_dataset_paths(project_path)
            topology_mode = "local-expected"
        existing_paths: List[str] = []
        missing_paths: List[str] = []

        for dataset_path in nested_dataset_paths:
            relative_path = dataset_path.relative_to(project_path).as_posix()
            if relative_path in registered_paths:
                existing_paths.append(relative_path)
            else:
                missing_paths.append(relative_path)

        total_count = len(nested_dataset_paths)
        registered_count = len(existing_paths)
        remaining_count = len(missing_paths)
        progress_percent = 100 if total_count == 0 else int((registered_count * 100) / total_count)

        return {
            "subdatasets_total_count": total_count,
            "subdatasets_registered_count": registered_count,
            "subdatasets_remaining_count": remaining_count,
            "subdatasets_progress_percent": progress_percent,
            "next_missing_subdataset": missing_paths[0] if missing_paths else "",
            "subdatasets_topology_mode": topology_mode,
        }

    def _iter_nested_dataset_paths(self, project_path: Path) -> List[Path]:
        """Return immediate project directories that should become DataLad subdatasets."""
        nested_paths: List[Path] = []
        seen_paths = set()

        derivatives_path = project_path / "derivatives"
        if derivatives_path.is_dir():
            nested_paths.append(derivatives_path)
            seen_paths.add(str(derivatives_path.resolve()))

        candidate_roots = [project_path]

        rawdata_path = project_path / "rawdata"
        if rawdata_path.is_dir():
            candidate_roots.append(rawdata_path)

        for candidate_root in candidate_roots:
            if not candidate_root.is_dir():
                continue

            for child_path in sorted(candidate_root.iterdir()):
                if not child_path.is_dir() or not child_path.name.startswith("sub-"):
                    continue

                resolved_path = str(child_path.resolve())
                if resolved_path in seen_paths:
                    continue

                seen_paths.add(resolved_path)
                nested_paths.append(child_path)

        return nested_paths

    def _is_datalad_dataset(self, path: Path) -> bool:
        """Return True when a path already has Git/DataLad dataset metadata."""
        return (path / ".datalad").exists() or (path / ".git").exists()

    def _save_datalad_changes(
        self,
        project_path: Path,
        datalad_result: Dict[str, Any],
        *,
        message: str,
    ) -> Dict[str, Any]:
        """Persist project changes into DataLad with a stable message when possible."""
        result = dict(datalad_result)
        result["save_message"] = message

        if not result.get("initialized"):
            return result

        save_result = self._run_datalad_save(
            project_path,
            message=message,
            datalad_executable=result.get("executable"),
        )
        result.update(save_result)

        if save_result.get("saved"):
            result["message"] = f'DataLad dataset initialized and saved with message "{message}".'
            return result

        if save_result.get("no_changes"):
            result["message"] = "DataLad dataset initialized. No additional DataLad save was needed."
            return result

        if not save_result.get("available"):
            result["message"] = (
                "DataLad was initialized, but the executable is no longer available "
                "to save changes."
            )
            return result

        detail = save_result.get("message") or "Unknown DataLad error."
        result["message"] = f"DataLad dataset initialized, but saving project changes failed: {detail}"
        return result

    def _run_datalad_save(
        self,
        project_path: Path,
        *,
        message: str,
        datalad_executable: Optional[str] = None,
        updated_only: bool = False,
        recursive: bool = False,
    ) -> Dict[str, Any]:
        """Run a DataLad save command and normalize the result payload."""
        normalized_message = str(message or "").strip() or "Save PRISM project changes"
        result: Dict[str, Any] = {
            "available": False,
            "saved": False,
            "no_changes": False,
            "save_message": normalized_message,
            "updated_only": bool(updated_only),
            "recursive": bool(recursive),
            "message": "",
        }

        resolved_executable = datalad_executable or shutil.which("datalad")
        if not resolved_executable:
            result["message"] = "DataLad executable is not available."
            return result

        result["available"] = True
        result["executable"] = str(resolved_executable)
        save_command = [str(resolved_executable), "save"]
        if recursive:
            save_command.append("-r")
        if updated_only:
            save_command.append("--updated")
        save_command.extend(["-m", normalized_message])

        try:
            process = subprocess.run(
                save_command,
                cwd=str(project_path),
                capture_output=True,
                text=True,
                check=False,
                timeout=DATALAD_REPAIR_STEP_TIMEOUT_SECONDS,
            )
        except subprocess.TimeoutExpired:
            result["message"] = self._format_repair_timeout_message(
                f'DataLad save for "{project_path.name}"'
            )
            return result
        except Exception as exc:
            result["message"] = f"DataLad save failed ({type(exc).__name__}: {exc})."
            return result

        if process.returncode == 0:
            result["saved"] = True
            if recursive:
                result["message"] = (
                    f'DataLad recursively saved project and nested dataset changes '
                    f'with message "{normalized_message}".'
                )
            else:
                result["message"] = f'DataLad saved changes with message "{normalized_message}".'
            return result

        detail = (process.stderr or process.stdout or "").strip()
        if "nothing to save" in detail.lower():
            result["no_changes"] = True
            if recursive:
                result["message"] = (
                    "No DataLad changes were pending in the project or nested datasets."
                )
            else:
                result["message"] = "No DataLad changes were pending."
            return result

        result["message"] = f"DataLad save failed: {detail or 'Unknown DataLad error.'}"
        return result

    def _run_git_commit_for_path(
        self,
        project_path: Path,
        *,
        relative_dataset_text: str,
        message: str,
    ) -> Dict[str, Any]:
        """Commit staged parent changes for one nested path after working-tree content is parked aside."""
        normalized_message = str(message or "").strip() or "Checkpoint parent dataset changes"
        result: Dict[str, Any] = {
            "available": True,
            "saved": False,
            "no_changes": False,
            "save_message": normalized_message,
            "message": "",
        }

        commit_command = [
            "git",
            "commit",
            "-m",
            normalized_message,
            "--",
            relative_dataset_text,
        ]

        try:
            process = subprocess.run(
                commit_command,
                cwd=str(project_path),
                capture_output=True,
                text=True,
                check=False,
                timeout=DATALAD_REPAIR_STEP_TIMEOUT_SECONDS,
            )
        except subprocess.TimeoutExpired:
            result["message"] = self._format_repair_timeout_message(
                f'Git commit for "{relative_dataset_text}"'
            )
            return result
        except Exception as exc:
            result["message"] = f"Git commit failed ({type(exc).__name__}: {exc})."
            return result

        if process.returncode == 0:
            result["saved"] = True
            result["message"] = f'Git committed staged parent changes for "{relative_dataset_text}".'
            return result

        detail = (process.stderr or process.stdout or "").strip()
        lowered_detail = detail.lower()
        if "nothing to commit" in lowered_detail or "no changes added to commit" in lowered_detail:
            result["no_changes"] = True
            result["message"] = "No staged parent changes were pending."
            return result

        result["message"] = f"Git commit failed: {detail or 'Unknown Git error.'}"
        return result

    def _iter_datalad_dataset_roots(self, project_path: Path) -> List[Path]:
        """Return likely dataset roots without full recursive filesystem scans.

        Fast-path order:
        1) project root
        2) paths declared in `.gitmodules`
        3) top-level child dirs that contain `.datalad`

        Avoid using `rglob('.datalad')` here because project load status calls this
        frequently and full recursive scans can time out on large remote/external
        datasets.
        """
        dataset_roots: set[Path] = {project_path}

        gitmodules_path = project_path / ".gitmodules"
        if gitmodules_path.is_file():
            try:
                for line in gitmodules_path.read_text(encoding="utf-8").splitlines():
                    match = re.match(r"^\s*path\s*=\s*(.+?)\s*$", line)
                    if not match:
                        continue
                    rel_path = match.group(1).strip()
                    if not rel_path:
                        continue
                    candidate = project_path / rel_path
                    if candidate.is_dir():
                        dataset_roots.add(candidate)
            except OSError:
                pass

        try:
            for child in project_path.iterdir():
                if child.is_dir() and (child / ".datalad").is_dir():
                    dataset_roots.add(child)
        except OSError:
            pass

        return sorted(dataset_roots)

    def _summarize_datalad_text_policy(self, project_path: Path) -> Dict[str, Any]:
        """Report whether text-file Git tracking policy is present in dataset roots."""
        dataset_roots = self._iter_datalad_dataset_roots(project_path)
        missing_roots: List[str] = []

        for dataset_root in dataset_roots:
            gitattributes_path = dataset_root / ".gitattributes"
            has_rule = False
            if gitattributes_path.is_file():
                try:
                    content = CrossPlatformFile.read_text(str(gitattributes_path))
                    existing_lines = {
                        line.strip()
                        for line in content.splitlines()
                        if line.strip()
                    }
                    has_rule = all(
                        policy_line in existing_lines
                        for policy_line in DATALAD_TEXT_POLICY_REQUIRED_LINES
                    )
                except Exception:
                    has_rule = False

            if not has_rule:
                if dataset_root == project_path:
                    missing_roots.append(".")
                else:
                    try:
                        missing_roots.append(dataset_root.relative_to(project_path).as_posix())
                    except ValueError:
                        missing_roots.append(str(dataset_root))

        missing_count = len(missing_roots)
        return {
            "text_policy_complete": missing_count == 0,
            "text_policy_dataset_count": len(dataset_roots),
            "text_policy_missing_count": missing_count,
            "text_policy_missing_examples": missing_roots[:10],
        }

    def _ensure_datalad_editable_metadata_policy(
        self,
        project_path: Path,
        datalad_result: Dict[str, Any],
    ) -> bool:
        """Keep core project metadata and common text files in Git."""
        if not datalad_result.get("initialized"):
            return False

        updated = False
        for dataset_root in self._iter_datalad_dataset_roots(project_path):
            gitattributes_path = dataset_root / ".gitattributes"
            existing_content = ""
            existing_lines = set()
            if gitattributes_path.exists():
                try:
                    existing_content = CrossPlatformFile.read_text(str(gitattributes_path))
                except Exception:
                    existing_content = ""
                existing_lines = {
                    line.strip()
                    for line in existing_content.splitlines()
                    if line.strip()
                }

            missing_lines = [
                line
                for line in DATALAD_TEXT_POLICY_REQUIRED_LINES
                if line not in existing_lines
            ]
            if not missing_lines:
                continue

            if existing_content.strip():
                new_content = (
                    existing_content.rstrip() + "\n" + "\n".join(missing_lines) + "\n"
                )
            else:
                new_content = (
                    "# Keep PRISM metadata and common text files editable when DataLad is enabled.\n"
                    + "\n".join(missing_lines)
                    + "\n"
                )

            CrossPlatformFile.write_text(str(gitattributes_path), new_content)
            updated = True

        return updated

    def _normalize_datalad_text_patterns(self, patterns: List[str]) -> List[str]:
        """Normalize comma/newline separated pattern lists while preserving order."""
        if not isinstance(patterns, list):
            return []

        normalized_patterns: List[str] = []
        seen_patterns: set[str] = set()

        for value in patterns:
            for raw_part in re.split(r"[,\n]+", str(value or "")):
                pattern = raw_part.strip()
                if not pattern or pattern in seen_patterns:
                    continue
                seen_patterns.add(pattern)
                normalized_patterns.append(pattern)

        return normalized_patterns

    def _build_auto_datalad_save_message(self, reason: str) -> str:
        """Return a stable commit message for lifecycle-triggered DataLad saves."""
        normalized_reason = str(reason or "").strip().lower()
        if normalized_reason.startswith("project_switch"):
            return "PRISM auto-save before project switch"
        if normalized_reason == "project_cleared":
            return "PRISM auto-save before clearing current project"
        if normalized_reason == "prism_closed":
            return "PRISM auto-save on PRISM close"
        return "PRISM auto-save"

    def _create_bidsignore(self, modalities: List[str]) -> str:
        """Create .bidsignore content."""
        content = "# .bidsignore - PRISM and YODA files excluded from BIDS validation\n"
        content += (
            "# This ensures compatibility with standard BIDS tools (fMRIPrep, etc.)\n\n"
        )

        # Ignore project-level metadata
        content += "project.json\n"
        content += ".prismrc.json\n\n"

        # Ignore YODA folders (they are outside rawdata/ but just in case)
        content += "sourcedata/\n"
        content += "derivatives/\n"
        content += "analysis/\n"
        content += "paper/\n"
        content += "code/\n\n"

        # Ignore legacy/non-BIDS project folders if present
        content += "recipes/\n"
        content += "recipe/\n"
        content += "library/\n"
        content += "code/recipes/\n"
        content += "code/library/\n\n"

        for mod in modalities:
            if mod in PRISM_MODALITIES and mod not in BIDS_PASSTHROUGH_MODALITIES:
                content += f"{mod}/\n"

        return content

    def _create_prismrc(self) -> Dict[str, Any]:
        """Create .prismrc.json content."""
        return {
            "schemaVersion": "stable",
            "strictMode": False,
            "runBids": False,
            "ignorePaths": [
                "library/**",
                "recipe/**",
                "sourcedata/**",
                "derivatives/**",
                "analysis/**",
                "paper/**",
                "code/**",
            ],
        }

    def _create_readme(self, name: str, sessions: int, modalities: List[str]) -> str:
        """Create README.md content with YODA instructions."""
        today = date.today().isoformat()

        content = f"""# {name}

PRISM/BIDS-compatible dataset (YODA layout) created on {today}.

## Structure

This project follows the YODA principles for data management, keeping raw data, code, and papers together.

### Project Layout

```
project/
├── rawdata/                # PRISM/BIDS compatible dataset (Validated)
│   ├── dataset_description.json
│   ├── participants.tsv
│   └── sub-<label>/
│
├── sourcedata/             # Raw source files (LimeSurvey exports, etc.)
│
├── derivatives/            # Processed/derived outputs (scored surveys)
│   └── qc/                 # Quality control reports
│
├── analysis/               # Analysis scripts and results
│
├── paper/                  # Manuscripts and figures
│
├── stimuli/                # Stimulus files (images, audio, etc.)
│
├── library/                # JSON templates for conversion (Survey/Biometrics)
│
├── recipe/                 # Transformation recipes
│
├── code/                   # Project-specific scripts and tools
│
├── project.json            # Study-level metadata (funding, ethics, links)
├── CITATION.cff            # Dataset citation metadata (authors, DOI, license)
├── .prismrc.json           # PRISM validation settings
└── README.md               # This file
```

## Getting Started

1. **Populate rawdata**: Use the PRISM Converter to move data from `sourcedata/` to `rawdata/`.
2. **Use the Library**: Store your `.json` templates in `library/survey/` or `library/biometrics/`.
3. **Define Recipes**: Use `recipe/` to store scoring logic and data transformations.
4. **Validate**: Point the PRISM Validator to the `rawdata/` folder to check compliance.

## Resources

- PRISM Documentation: https://prism-studio.readthedocs.io/
- BIDS Specification: https://bids-specification.readthedocs.io/
- YODA Principles: https://handbook.datalad.org/en/latest/basics/101-127-yoda.html
"""
        return content

    def _create_yoda_folders(self, project_path: Path) -> List[str]:
        """Create standard YODA folder structure."""
        created = []

        # List of folders to create in the project root
        folders = ["sourcedata", "derivatives", "analysis", "paper", "code"]
        for folder in folders:
            path = project_path / folder
            path.mkdir(exist_ok=True)
            created.append(f"{folder}/")

            # Add README to each
            readme_path = path / "README"
            content = ""
            if folder == "sourcedata":
                content = "Place original/raw data files here before converting to BIDS/PRISM format.\n"
            elif folder == "derivatives":
                content = "Processed and derived data outputs (e.g. scored surveys) go here.\n"
            elif folder == "analysis":
                content = "Code and results for statistical analysis.\n"
            elif folder == "paper":
                content = "Manuscripts, figures, and publication-related files.\n"
            elif folder == "code":
                content = """Project-specific scripts, templates, and recipes (YODA-compliant).

Subfolders:
  • library/{modality}/  - Custom templates (survey/biometrics JSON definitions)
  • recipes/{modality}/  - Custom scoring recipes (transformation logic)
  • scripts/             - Analysis and processing scripts
"""

            CrossPlatformFile.write_text(str(readme_path), content)
            created.append(f"{folder}/README")

            if folder == "derivatives":
                qc_path = path / "qc"
                qc_path.mkdir(exist_ok=True)
                created.append("derivatives/qc/")
                qc_readme_path = qc_path / "README"
                qc_content = (
                    "Quality control reports, validator outputs, and data snapshots.\n"
                )
                CrossPlatformFile.write_text(str(qc_readme_path), qc_content)
                created.append("derivatives/qc/README")

        # stimuli/ - optional, for stimulus files
        stimuli_path = project_path / "stimuli"
        stimuli_path.mkdir(exist_ok=True)
        created.append("stimuli/")

        return created

    def _create_library_structure(
        self, project_path: Path, modalities: List[str]
    ) -> List[str]:
        """Create library & recipe folder structure under code/ (YODA-compliant)."""
        created = []

        # Everything goes under code/ to follow YODA principles
        code_root = project_path / "code"
        code_root.mkdir(parents=True, exist_ok=True)

        # 1. Library Root (JSON templates)
        library_root = code_root / "library"
        library_root.mkdir(parents=True, exist_ok=True)
        created.append("code/library/")

        # 2. Recipe Root (Transformation logic)
        recipe_root = code_root / "recipes"
        recipe_root.mkdir(parents=True, exist_ok=True)
        created.append("code/recipes/")

        # Create modality subfolders for both library and recipe
        core_mods = ["survey", "biometrics"]
        for mod in core_mods:
            # Library folders
            lib_mod_path = library_root / mod
            lib_mod_path.mkdir(exist_ok=True)
            created.append(f"code/library/{mod}/")

            if mod == "survey":
                example_survey = self._create_example_survey_template()
                lib_example_path = lib_mod_path / "survey-example.json"
                CrossPlatformFile.write_text(
                    str(lib_example_path),
                    json.dumps(example_survey, indent=2, ensure_ascii=False),
                )
                created.append(f"code/library/{mod}/survey-example.json")
            elif mod == "biometrics":
                example_bio = self._create_example_biometrics_template()
                lib_example_path = lib_mod_path / "biometrics-example.json"
                CrossPlatformFile.write_text(
                    str(lib_example_path),
                    json.dumps(example_bio, indent=2, ensure_ascii=False),
                )
                created.append(f"code/library/{mod}/biometrics-example.json")

            # Recipe folders
            rec_mod_path = recipe_root / mod
            rec_mod_path.mkdir(exist_ok=True)
            created.append(f"code/recipes/{mod}/")

        return created

    def _create_project_metadata(
        self, name: str, config: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Create project-level metadata template."""
        project_icon = normalize_project_icon(config.get("icon")) or choose_random_project_icon()
        return {
            "name": name,
            "icon": project_icon,
            "paths": {"sourcedata": "sourcedata"},
            "app": {"schema": "1", "last_opened": date.today().isoformat()},
            "governance": {
                "funding": config.get("funding", []),
                "ethics_approvals": config.get("ethics_approvals", []),
                "contacts": [],
                "preregistration": "",
                "data_access": "",
                "notes": "",
            },
            "Basics": config.get("Basics", {}),
            "Overview": config.get("Overview", {}),
            "StudyDesign": config.get("StudyDesign", {}),
            "Recruitment": config.get("Recruitment", {}),
            "Eligibility": config.get("Eligibility", {}),
            "DataCollection": config.get("DataCollection", {}),
            "Procedure": config.get("Procedure", {}),
            "MissingData": config.get("MissingData", {}),
            "References": config.get("References", ""),
            "Conditions": config.get("Conditions", {}),
            "TaskDefinitions": {},
        }

    def _create_contributors_template(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """Create contributors template with CRediT roles."""
        authors = config.get("authors", []) or []
        contributors: List[Any] = []
        for author in authors:
            display_name = self._author_display_name(author)
            if not display_name:
                continue

            orcid_value = ""
            email_value = ""
            if isinstance(author, dict):
                orcid_value = str(author.get("orcid") or "").strip()
                email_value = str(author.get("email") or "").strip()

            contributors.append(
                {
                    "name": display_name,
                    "roles": ["Conceptualization"],
                    "orcid": orcid_value,
                    "email": email_value,
                }
            )
        if not contributors:
            contributors.append({"name": "", "roles": [], "orcid": "", "email": ""})
        return {
            "contributors": contributors,
            "roles_reference": "https://credit.niso.org/",
        }

    @staticmethod
    def _yaml_quote(value: str) -> str:
        return json.dumps(value or "", ensure_ascii=False)

    @staticmethod
    def _split_author_name(author: str) -> tuple[str, str]:
        text = str(author or "").strip()
        if not text:
            return "", ""

        # Support "Family, Given" inputs produced by dataset_description Authors.
        if "," in text:
            family, given = text.split(",", 1)
            family = family.strip()
            given = given.strip()
            if family and given:
                return given, family
            if family:
                return "", family
            if given:
                return "", given

        parts = text.split()
        if not parts:
            return "", ""
        if len(parts) == 1:
            return "", parts[0]
        return " ".join(parts[:-1]), parts[-1]

    @staticmethod
    def _author_display_name(author: Any) -> str:
        """Normalize author entry to a display string."""
        if isinstance(author, dict):
            given = str(author.get("given-names") or author.get("given") or "").strip()
            family = str(
                author.get("family-names") or author.get("family") or ""
            ).strip()
            if given and family:
                return f"{given} {family}"
            if family:
                return family
            if given:
                return given
            return str(author.get("name") or "").strip()
        return str(author or "").strip()

    @staticmethod
    def _normalize_doi(doi_value: Any) -> str:
        """Normalize DOI input and return empty string when invalid."""
        doi = str(doi_value or "").strip()
        if not doi:
            return ""
        doi = re.sub(r"^https?://doi\.org/", "", doi, flags=re.IGNORECASE)
        doi = re.sub(r"^doi:\\s*", "", doi, flags=re.IGNORECASE)

        if re.match(r"^10\.\d{4,9}/.+$", doi, flags=re.IGNORECASE):
            return doi
        return ""

    @staticmethod
    def _normalize_list(value: Any) -> List[Any]:
        if value is None:
            return []
        if isinstance(value, list):
            return value
        if isinstance(value, str):
            parts = [item.strip() for item in value.split(",")]
            return [item for item in parts if item]
        return [value]

    @staticmethod
    def _normalize_keywords(value: Any) -> List[str]:
        """Normalize keywords, splitting comma/semicolon-delimited strings."""
        raw_values = ProjectManager._normalize_list(value)
        normalized: List[str] = []
        seen = set()
        for raw in raw_values:
            text = str(raw or "").strip()
            if not text:
                continue
            parts = [item.strip() for item in re.split(r"[;,]", text) if item.strip()]
            if not parts:
                parts = [text]
            for part in parts:
                key = part.lower()
                if key in seen:
                    continue
                seen.add(key)
                normalized.append(part)
        return normalized

    @staticmethod
    def _is_url(value: Any) -> bool:
        text = str(value or "").strip()
        if not text:
            return False
        try:
            parsed = urlparse(text)
        except Exception:
            return False
        return parsed.scheme in {"http", "https"} and bool(parsed.netloc)

    @staticmethod
    def _normalize_license_value(raw_license: Any) -> str:
        license_text = str(raw_license or "").strip()
        if not license_text:
            return ""

        normalized = re.sub(r"\s+", " ", license_text).strip()
        upper = normalized.upper()
        mapping = {
            "CC0": "CC0-1.0",
            "CC0 1.0": "CC0-1.0",
            "CC0-1.0": "CC0-1.0",
            "CC BY 4.0": "CC-BY-4.0",
            "CC-BY 4.0": "CC-BY-4.0",
            "CC-BY-4.0": "CC-BY-4.0",
            "CC BY-SA 4.0": "CC-BY-SA-4.0",
            "CC-BY-SA 4.0": "CC-BY-SA-4.0",
            "CC-BY-SA-4.0": "CC-BY-SA-4.0",
            "CC BY-NC 4.0": "CC-BY-NC-4.0",
            "CC-BY-NC 4.0": "CC-BY-NC-4.0",
            "CC-BY-NC-4.0": "CC-BY-NC-4.0",
            "CC BY-NC-SA 4.0": "CC-BY-NC-SA-4.0",
            "CC-BY-NC-SA 4.0": "CC-BY-NC-SA-4.0",
            "CC-BY-NC-SA-4.0": "CC-BY-NC-SA-4.0",
            "ODBL 1.0": "ODbL-1.0",
            "ODBL-1.0": "ODbL-1.0",
            "PDDL 1.0": "PDDL-1.0",
            "PDDL-1.0": "PDDL-1.0",
        }
        if upper in mapping:
            return mapping[upper]

        if upper == "OTHER":
            return ""

        if re.match(r"^[A-Za-z0-9][A-Za-z0-9+\.-]*$", normalized):
            return normalized
        return ""

    @staticmethod
    def _normalize_reference_text(raw_value: Any) -> str:
        """Normalize free-text reference values and drop placeholder artifacts."""
        text = str(raw_value or "").strip()
        if not text:
            return ""

        text = re.sub(r"\s+", " ", text).strip()
        lowered = text.lower()

        if lowered in {"[object object]", "object object", "none", "null", "undefined"}:
            return ""
        if lowered.startswith("[object "):
            return ""

        # Guard against serialized object/list blobs being treated as references.
        if text.startswith("{") or text.startswith("["):
            try:
                decoded = json.loads(text)
                if isinstance(decoded, (dict, list)):
                    return ""
            except Exception:
                pass

        return text

    @staticmethod
    def _normalize_mapping_keys(value: Any) -> Dict[str, Any]:
        if not isinstance(value, dict):
            return {}

        normalized: Dict[str, Any] = {}
        for key, item in value.items():
            normalized_key = str(key or "").strip().lower()
            if normalized_key and normalized_key not in normalized:
                normalized[normalized_key] = item
        return normalized

    @staticmethod
    def _normalize_reference_scalar_value(raw_value: Any) -> str:
        if raw_value is None:
            return ""
        if isinstance(raw_value, (int, float)):
            return str(raw_value).strip()
        return ProjectManager._normalize_reference_text(raw_value)

    def _build_fallback_reference_authors(
        self, fallback_authors: Optional[List[Any]] = None
    ) -> List[Dict[str, Any]]:
        fallback_author_objects = []
        for author in fallback_authors or []:
            display = self._author_display_name(author)
            if display:
                fallback_author_objects.append({"name": display})
        if not fallback_author_objects:
            fallback_author_objects = [{"name": "Unknown"}]
        return fallback_author_objects

    def _normalize_cff_party(self, raw_value: Any) -> Optional[Dict[str, Any]]:
        if isinstance(raw_value, dict):
            normalized_value = self._normalize_mapping_keys(raw_value)
            given = self._normalize_reference_scalar_value(
                normalized_value.get("given-names")
                or normalized_value.get("given")
                or normalized_value.get("first_name")
                or normalized_value.get("firstname")
                or normalized_value.get("first")
            )
            family = self._normalize_reference_scalar_value(
                normalized_value.get("family-names")
                or normalized_value.get("family")
                or normalized_value.get("last_name")
                or normalized_value.get("lastname")
                or normalized_value.get("last")
                or normalized_value.get("surname")
            )
            name = self._normalize_reference_scalar_value(
                normalized_value.get("name")
                or normalized_value.get("full_name")
                or normalized_value.get("fullname")
                or normalized_value.get("contact")
                or normalized_value.get("organization")
            )

            if not family and name:
                parsed_given, parsed_family = self._split_author_name(name)
                if parsed_family:
                    family = parsed_family
                if parsed_given and not given:
                    given = parsed_given

            entry: Dict[str, Any] = {}
            if family:
                if given:
                    entry["given-names"] = given
                entry["family-names"] = family
            elif name:
                entry["name"] = name
            elif given:
                entry["name"] = given
            else:
                return None

            optional_aliases = {
                "email": ("email",),
                "affiliation": ("affiliation",),
                "orcid": ("orcid",),
                "website": ("website", "url"),
            }
            for field_name, aliases in optional_aliases.items():
                value = ""
                for alias in aliases:
                    candidate = self._normalize_reference_scalar_value(
                        normalized_value.get(alias)
                    )
                    if candidate:
                        value = candidate
                        break
                if not value:
                    continue
                if field_name == "website" and not self._is_url(value):
                    continue
                entry[field_name] = value
            return entry

        text = self._normalize_reference_text(raw_value)
        if not text:
            return None

        given, family = self._split_author_name(text)
        if family:
            entry = {"family-names": family}
            if given:
                entry["given-names"] = given
            return entry
        return {"name": text}

    def _normalize_cff_party_list(self, raw_value: Any) -> List[Dict[str, Any]]:
        if isinstance(raw_value, list):
            raw_values = raw_value
        elif raw_value in (None, "", {}, []):
            raw_values = []
        else:
            raw_values = [raw_value]

        normalized: List[Dict[str, Any]] = []
        seen = set()
        for item in raw_values:
            party = self._normalize_cff_party(item)
            if not party:
                continue
            key = self._author_identity_key(party)
            if key in seen:
                continue
            seen.add(key)
            normalized.append(party)
        return normalized

    def _normalize_identifier_entries(self, raw_value: Any) -> List[Dict[str, str]]:
        if isinstance(raw_value, list):
            raw_values = raw_value
        elif raw_value in (None, "", {}, []):
            raw_values = []
        else:
            raw_values = [raw_value]

        normalized: List[Dict[str, str]] = []
        seen = set()
        for item in raw_values:
            identifier_type = ""
            identifier_value = item
            description = ""

            if isinstance(item, dict):
                normalized_item = self._normalize_mapping_keys(item)
                identifier_type = self._normalize_reference_scalar_value(
                    normalized_item.get("type")
                ).lower()
                identifier_value = (
                    normalized_item.get("value")
                    or normalized_item.get("id")
                    or normalized_item.get("doi")
                    or normalized_item.get("url")
                )
                description = self._normalize_reference_scalar_value(
                    normalized_item.get("description")
                )

            value_text = self._normalize_reference_scalar_value(identifier_value)
            if not value_text:
                continue

            doi_value = self._normalize_doi(value_text)
            if doi_value:
                entry = {"type": "doi", "value": doi_value}
            elif self._is_url(value_text):
                entry = {"type": "url", "value": value_text}
            else:
                normalized_type = identifier_type or "other"
                if normalized_type not in {"doi", "url", "swh", "other"}:
                    normalized_type = "other"
                if normalized_type == "doi":
                    doi_value = self._normalize_doi(value_text)
                    if not doi_value:
                        continue
                    value_text = doi_value
                elif normalized_type == "url" and not self._is_url(value_text):
                    continue
                entry = {"type": normalized_type, "value": value_text}

            if description:
                entry["description"] = description

            key = (
                entry["type"],
                str(entry["value"] or "").strip().lower().rstrip("/"),
            )
            if key in seen:
                continue
            seen.add(key)
            normalized.append(entry)

        return normalized

    @staticmethod
    def _reference_identity_key(reference: Any) -> tuple[str, str]:
        if not isinstance(reference, dict):
            return ("", "")

        doi_value = str(reference.get("doi") or "").strip().lower()
        if doi_value:
            return ("doi", doi_value)

        url_value = str(reference.get("url") or "").strip().lower().rstrip("/")
        if url_value:
            return ("url", url_value)

        title_value = str(reference.get("title") or "").strip().lower()
        if title_value:
            return ("title", title_value)

        return ("", "")

    def _build_preferred_citation(
        self,
        raw_value: Any,
        references: List[Dict[str, Any]],
        how_to_acknowledge: Any,
        fallback_authors: Optional[List[Any]] = None,
    ) -> Optional[Dict[str, Any]]:
        fallback_author_objects = self._build_fallback_reference_authors(
            fallback_authors
        )

        if raw_value not in (None, "", {}, []):
            explicit_candidates = self._normalize_reference_entries(
                [raw_value], fallback_authors=fallback_authors
            )
            if explicit_candidates:
                return explicit_candidates[0]

        acknowledgement_text = str(how_to_acknowledge or "").strip()
        acknowledgement_doi = self._normalize_doi(acknowledgement_text)
        acknowledgement_url = (
            acknowledgement_text if self._is_url(acknowledgement_text) else ""
        )
        if not acknowledgement_doi and not acknowledgement_url:
            return None

        for reference in references:
            reference_doi = self._normalize_doi(reference.get("doi"))
            reference_url = str(reference.get("url") or "").strip()
            if acknowledgement_doi and reference_doi == acknowledgement_doi:
                return dict(reference)
            if (
                acknowledgement_url
                and reference_url
                and reference_url.rstrip("/") == acknowledgement_url.rstrip("/")
            ):
                return dict(reference)

        preferred_citation: Dict[str, Any] = {
            "type": "generic",
            "title": "Preferred citation",
            "authors": fallback_author_objects,
        }
        if acknowledgement_doi:
            preferred_citation["doi"] = acknowledgement_doi
        if acknowledgement_url:
            preferred_citation["url"] = acknowledgement_url
        return preferred_citation

    @staticmethod
    def _is_code_repository_url(value: Any) -> bool:
        text = str(value or "").strip().lower()
        if not text:
            return False
        try:
            host = urlparse(text).netloc.lower()
        except Exception:
            return False
        return any(token in host for token in ("github.com", "gitlab", "bitbucket"))

    @staticmethod
    def _is_archive_repository_url(value: Any) -> bool:
        text = str(value or "").strip().lower()
        if not text:
            return False
        try:
            host = urlparse(text).netloc.lower()
        except Exception:
            return False
        return any(
            token in host
            for token in (
                "osf.io",
                "zenodo.org",
                "figshare.com",
                "dataverse",
                "dryad",
            )
        )

    def _normalize_reference_entries(
        self, references: Any, fallback_authors: Optional[List[Any]] = None
    ) -> List[Dict[str, Any]]:
        normalized: List[Dict[str, Any]] = []
        fallback_author_objects = self._build_fallback_reference_authors(
            fallback_authors
        )

        text_field_aliases = (
            ("abstract", ("abstract",)),
            ("collection-title", ("collection-title", "collection_title")),
            ("collection-type", ("collection-type", "collection_type")),
            ("data-type", ("data-type", "data_type")),
            ("date-accessed", ("date-accessed", "date_accessed")),
            ("date-downloaded", ("date-downloaded", "date_downloaded")),
            ("date-published", ("date-published", "date_published")),
            ("date-released", ("date-released", "date_released")),
            ("edition", ("edition",)),
            ("issue", ("issue",)),
            ("issue-date", ("issue-date", "issue_date")),
            ("issue-title", ("issue-title", "issue_title")),
            ("journal", ("journal",)),
            ("month", ("month",)),
            ("notes", ("notes",)),
            ("pages", ("pages",)),
            ("repository", ("repository",)),
            ("repository-artifact", ("repository-artifact", "repository_artifact")),
            ("repository-code", ("repository-code", "repository_code")),
            ("scope", ("scope",)),
            ("section", ("section",)),
            ("start", ("start",)),
            ("end", ("end",)),
            ("status", ("status",)),
            ("version", ("version",)),
            ("volume", ("volume",)),
            ("volume-title", ("volume-title", "volume_title")),
            ("year", ("year",)),
            ("year-original", ("year-original", "year_original")),
        )

        for ref in self._normalize_list(references):
            entry: Dict[str, Any] = {}
            if isinstance(ref, dict):
                normalized_ref = self._normalize_mapping_keys(ref)
                ref_type = self._normalize_reference_scalar_value(
                    normalized_ref.get("type")
                )
                ref_title = self._normalize_reference_scalar_value(
                    normalized_ref.get("title")
                )
                ref_url = self._normalize_reference_scalar_value(
                    normalized_ref.get("url")
                )
                ref_doi = self._normalize_doi(normalized_ref.get("doi"))
                ref_authors_raw = normalized_ref.get("authors")

                if ref_url and self._is_url(ref_url):
                    entry["url"] = ref_url
                if ref_doi:
                    entry["doi"] = ref_doi

                if ref_title:
                    entry["title"] = ref_title
                elif ref_url:
                    entry["title"] = f"Referenced resource: {ref_url}"
                elif ref_doi:
                    entry["title"] = f"Referenced work: {ref_doi}"
                else:
                    continue

                if ref_type:
                    entry["type"] = ref_type
                else:
                    entry["type"] = "generic"

                author_objects = self._normalize_cff_party_list(ref_authors_raw)
                entry["authors"] = author_objects or fallback_author_objects

                collection_doi = self._normalize_doi(
                    normalized_ref.get("collection-doi")
                    or normalized_ref.get("collection_doi")
                )
                if collection_doi:
                    entry["collection-doi"] = collection_doi

                for field_name, aliases in text_field_aliases:
                    value = ""
                    for alias in aliases:
                        candidate = self._normalize_reference_scalar_value(
                            normalized_ref.get(alias)
                        )
                        if candidate:
                            value = candidate
                            break
                    if not value:
                        continue
                    if field_name in {
                        "repository",
                        "repository-artifact",
                        "repository-code",
                    } and not self._is_url(value):
                        continue
                    entry[field_name] = value

                keywords = self._normalize_keywords(normalized_ref.get("keywords"))
                if keywords:
                    entry["keywords"] = keywords

                languages: List[str] = []
                seen_languages = set()
                for raw_language in self._normalize_list(normalized_ref.get("languages")):
                    language = self._normalize_reference_scalar_value(raw_language)
                    language_key = language.lower()
                    if not language or language_key in seen_languages:
                        continue
                    seen_languages.add(language_key)
                    languages.append(language)
                if languages:
                    entry["languages"] = languages

                identifiers = self._normalize_identifier_entries(
                    normalized_ref.get("identifiers")
                )
                if identifiers:
                    entry["identifiers"] = identifiers

                normalized.append(entry)
                continue

            text = self._normalize_reference_text(ref)
            if not text:
                continue

            if self._is_url(text):
                entry["url"] = text
                entry["title"] = f"Referenced resource: {text}"
                entry["type"] = "generic"
                entry["authors"] = fallback_author_objects
                normalized.append(entry)
                continue

            doi = self._normalize_doi(text)
            if doi:
                entry["doi"] = doi
                entry["title"] = f"Referenced work: {doi}"
                entry["type"] = "generic"
                entry["authors"] = fallback_author_objects
                normalized.append(entry)
                continue

            entry["title"] = text
            entry["type"] = "generic"
            entry["authors"] = fallback_author_objects
            normalized.append(entry)

        deduped: List[Dict[str, Any]] = []
        seen = set()
        for item in normalized:
            item_doi = str(item.get("doi") or "").strip().lower()
            item_url = str(item.get("url") or "").strip().lower().rstrip("/")
            item_title = str(item.get("title") or "").strip().lower()
            if item_doi:
                key = ("doi", item_doi)
            elif item_url:
                key = ("url", item_url)
            else:
                key = ("title", item_title)
            if key in seen:
                continue
            seen.add(key)
            deduped.append(item)
        return deduped

    def _flatten_reference_candidates(self, value: Any) -> List[Any]:
        """Flatten nested reference-like structures to list entries."""
        flattened: List[Any] = []

        if value is None:
            return flattened
        if isinstance(value, list):
            for item in value:
                flattened.extend(self._flatten_reference_candidates(item))
            return flattened
        if isinstance(value, dict):
            if any(key in value for key in ("title", "url", "doi", "type", "authors")):
                flattened.append(value)
                return flattened
            for nested in value.values():
                flattened.extend(self._flatten_reference_candidates(nested))
            return flattened

        text = str(value or "").strip()
        if text:
            parts = [part.strip() for part in re.split(r"[\r\n]+", text) if part.strip()]
            if len(parts) > 1:
                flattened.extend(parts)
            else:
                flattened.append(text)
        return flattened

    def _normalize_contact_author(self, contact: Any) -> Optional[Dict[str, str] | str]:
        """Convert governance contact entries into CFF-compatible author records."""
        if isinstance(contact, dict):
            given = str(
                contact.get("given-names")
                or contact.get("given")
                or contact.get("first_name")
                or contact.get("firstName")
                or ""
            ).strip()
            family = str(
                contact.get("family-names")
                or contact.get("family")
                or contact.get("last_name")
                or contact.get("lastName")
                or contact.get("surname")
                or ""
            ).strip()
            name = str(
                contact.get("name")
                or contact.get("full_name")
                or contact.get("contact")
                or ""
            ).strip()

            if not family and name:
                parsed_given, parsed_family = self._split_author_name(name)
                if parsed_family:
                    family = parsed_family
                if parsed_given:
                    given = parsed_given

            author_entry: Dict[str, Any] = {}
            if family:
                author_entry["family-names"] = family
                if given:
                    author_entry["given-names"] = given
            elif name:
                author_entry["name"] = name
            elif given:
                author_entry["name"] = given
            else:
                return None

            email_value = str(contact.get("email") or "").strip()
            if email_value:
                author_entry["email"] = email_value

            orcid_value = str(
                contact.get("orcid") or contact.get("ORCID") or ""
            ).strip()
            if orcid_value:
                author_entry["orcid"] = orcid_value

            affiliation_value = str(contact.get("affiliation") or "").strip()
            if affiliation_value:
                author_entry["affiliation"] = affiliation_value

            website_value = str(contact.get("website") or "").strip()
            if website_value:
                author_entry["website"] = website_value

            roles_value = contact.get("roles")
            normalized_roles: List[str] = []
            if isinstance(roles_value, list):
                normalized_roles = [
                    str(role).strip() for role in roles_value if str(role).strip()
                ]
            elif isinstance(roles_value, str):
                normalized_roles = [
                    role.strip() for role in roles_value.split(",") if role.strip()
                ]
            if normalized_roles:
                author_entry["roles"] = normalized_roles

            if contact.get("corresponding"):
                author_entry["corresponding"] = True

            return author_entry

        display = str(contact or "").strip()
        if display:
            return display
        return None

    def _extract_project_authors(
        self, project_meta: Dict[str, Any], project_path: Optional[Path] = None
    ) -> List[Any]:
        """Extract author information from project governance metadata."""
        governance = project_meta.get("governance") or {}
        contacts = self._normalize_list(governance.get("contacts"))
        authors: List[Any] = []

        for contact in contacts:
            normalized = self._normalize_contact_author(contact)
            if normalized:
                authors.append(normalized)

        return authors

    @classmethod
    def _canonical_author_identity_text(cls, author: Any) -> str:
        """Normalize author text so strings and structured names de-duplicate reliably."""
        if isinstance(author, dict):
            given = str(author.get("given-names") or author.get("given") or "").strip()
            family = str(author.get("family-names") or author.get("family") or "").strip()
            if given or family:
                return " ".join(
                    part.lower() for part in (given, family) if part
                ).strip()
            text = str(author.get("name") or "").strip()
        else:
            text = str(author or "").strip()

        if not text:
            return ""

        given, family = cls._split_author_name(text)
        if given or family:
            return " ".join(
                part.lower() for part in (given, family) if part
            ).strip()
        return text.lower()

    @staticmethod
    def _author_identity_key(author: Any) -> tuple[str, ...]:
        """Build a stable identity key for author de-duplication."""
        if isinstance(author, dict):
            canonical_name = ProjectManager._canonical_author_identity_text(author)
            if canonical_name:
                return ("person", canonical_name)

            orcid = str(author.get("orcid") or author.get("ORCID") or "").strip().lower()
            if orcid:
                return ("orcid", orcid)

            email = str(author.get("email") or "").strip().lower()
            if email:
                return ("email", email)
            return ("raw", json.dumps(author, sort_keys=True, ensure_ascii=False))

        canonical_name = ProjectManager._canonical_author_identity_text(author)
        if canonical_name:
            return ("person", canonical_name)
        return ("raw", str(author or "").strip().lower())

    def resolve_project_authors(
        self,
        authors: Any,
        project_meta: Optional[Dict[str, Any]] = None,
        project_path: Optional[Path] = None,
    ) -> List[Any]:
        """Resolve canonical project authors with governance contacts as the source of truth."""
        if isinstance(project_meta, dict):
            resolved_project_meta = project_meta
        elif project_path:
            resolved_project_meta = self._load_json_dict(Path(project_path) / "project.json")
        else:
            resolved_project_meta = {}

        provided_authors = self._normalize_list(authors)
        project_authors = self._extract_project_authors(
            resolved_project_meta, project_path
        )

        basics = resolved_project_meta.get("Basics")
        if not isinstance(basics, dict):
            basics = {}
        governance = resolved_project_meta.get("governance")
        has_governance_contacts = isinstance(governance, dict) and "contacts" in governance
        has_basic_authors = "Authors" in basics
        basic_authors = self._clean_citation_source_list(basics.get("Authors"))

        if project_authors:
            merged_authors = list(project_authors)
            index_by_key = {
                self._author_identity_key(author): index
                for index, author in enumerate(merged_authors)
            }

            for author in provided_authors:
                key = self._author_identity_key(author)
                existing_index = index_by_key.get(key)
                if existing_index is None:
                    continue
                merged_authors[existing_index] = self._merge_author_entries(
                    merged_authors[existing_index], author
                )

            if basic_authors:
                merged_authors.extend(basic_authors)
            return self._dedupe_authors(merged_authors)

        if has_governance_contacts or has_basic_authors:
            return self._dedupe_authors(basic_authors)

        combined_authors: List[Any] = []
        combined_authors.extend(provided_authors)
        combined_authors.extend(basic_authors)
        return self._dedupe_authors(combined_authors)

    def apply_project_metadata_precedence(
        self,
        description: Optional[Dict[str, Any]],
        project_path: Optional[Path] = None,
        project_meta: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Overlay canonical project.json metadata onto a dataset description payload."""
        merged = dict(description) if isinstance(description, dict) else {}

        if isinstance(project_meta, dict):
            resolved_project_meta = project_meta
        elif project_path:
            resolved_project_meta = self._load_json_dict(Path(project_path) / "project.json")
        else:
            resolved_project_meta = {}

        basics = resolved_project_meta.get("Basics")
        if not isinstance(basics, dict):
            basics = {}

        name = (
            self._clean_citation_source_text(basics.get("DatasetName"))
            or self._clean_citation_source_text(basics.get("Name"))
            or self._clean_citation_source_text(resolved_project_meta.get("name"))
        )
        if name:
            merged["Name"] = name

        scalar_fields = {
            "BIDSVersion": ("BIDSVersion",),
            "DatasetType": ("DatasetType",),
            "DatasetDOI": ("DatasetDOI", "DOI", "doi"),
            "License": ("License", "license"),
            "HowToAcknowledge": ("HowToAcknowledge", "how_to_acknowledge"),
            "Description": ("Description",),
            "HEDVersion": ("HEDVersion",),
            "Acknowledgements": ("Acknowledgements",),
            "DatasetVersion": ("DatasetVersion", "Version", "version"),
        }
        for target_key, source_keys in scalar_fields.items():
            project_owns_value = any(source_key in basics for source_key in source_keys)
            if not project_owns_value:
                continue

            value = ""
            for source_key in source_keys:
                value = self._clean_citation_source_text(basics.get(source_key))
                if value:
                    break

            if value:
                merged[target_key] = value
            else:
                merged.pop(target_key, None)

        if "Keywords" in basics:
            keywords = self._normalize_keywords(basics.get("Keywords"))
            if keywords:
                merged["Keywords"] = keywords
            else:
                merged.pop("Keywords", None)

        if "ReferencesAndLinks" in basics:
            references = self._clean_citation_source_list(
                basics.get("ReferencesAndLinks")
            )
            if references:
                merged["ReferencesAndLinks"] = references
            else:
                merged.pop("ReferencesAndLinks", None)

        if "DatasetLinks" in basics:
            dataset_links = self._clean_citation_source_mapping(
                basics.get("DatasetLinks")
            )
            if dataset_links:
                merged["DatasetLinks"] = dataset_links
            else:
                merged.pop("DatasetLinks", None)

        for list_key in ("Funding", "EthicsApprovals"):
            if list_key not in basics:
                continue
            values = self._clean_citation_source_list(basics.get(list_key))
            if values:
                merged[list_key] = values
            else:
                merged.pop(list_key, None)

        resolved_authors = self.resolve_project_authors(
            merged.get("Authors"),
            project_meta=resolved_project_meta,
            project_path=project_path,
        )
        governance = resolved_project_meta.get("governance")
        project_owns_authors = (
            isinstance(governance, dict) and "contacts" in governance
        ) or ("Authors" in basics)
        if resolved_authors:
            merged["Authors"] = resolved_authors
        elif project_owns_authors:
            merged.pop("Authors", None)

        return merged

    @staticmethod
    def _author_richness(author: Any) -> int:
        """Rank author entries so richer dict objects win over plain strings."""
        if not isinstance(author, dict):
            return 0
        score = 1
        for key in (
            "given-names",
            "given",
            "family-names",
            "family",
            "name",
            "email",
            "affiliation",
            "orcid",
            "ORCID",
            "website",
            "roles",
            "corresponding",
        ):
            value = author.get(key)
            if value not in (None, "", [], {}):
                score += 1
        return score

    def _merge_author_entries(self, current: Any, incoming: Any) -> Any:
        """Merge duplicate authors while preserving the richer metadata entry."""
        if not isinstance(current, dict):
            return incoming if isinstance(incoming, dict) else current
        if not isinstance(incoming, dict):
            return current

        merged = dict(current)
        for key, value in incoming.items():
            if key == "corresponding":
                if value:
                    merged[key] = True
                continue
            if key == "roles":
                role_values: List[str] = []
                for source in (current.get("roles"), value):
                    if isinstance(source, list):
                        role_values.extend(
                            str(item).strip() for item in source if str(item).strip()
                        )
                    elif isinstance(source, str):
                        role_values.extend(
                            item.strip() for item in source.split(",") if item.strip()
                        )

                deduped_roles: List[str] = []
                seen_roles = set()
                for role in role_values:
                    role_key = role.lower()
                    if role_key in seen_roles:
                        continue
                    seen_roles.add(role_key)
                    deduped_roles.append(role)
                if deduped_roles:
                    merged[key] = deduped_roles
                continue

            if merged.get(key) in (None, "", [], {}) and value not in (None, "", [], {}):
                merged[key] = value

        if self._author_richness(incoming) > self._author_richness(current):
            for key in ("given-names", "given", "family-names", "family", "name"):
                if incoming.get(key) not in (None, "", [], {}):
                    merged[key] = incoming.get(key)
        return merged

    def _dedupe_authors(self, authors: Any) -> List[Any]:
        """De-duplicate authors while preserving order and richest metadata."""
        if isinstance(authors, (str, dict)):
            author_list = [authors]
        elif isinstance(authors, list):
            author_list = authors
        else:
            return []

        deduped: List[Any] = []
        index_by_key: Dict[tuple[str, ...], int] = {}
        for author in author_list:
            key = self._author_identity_key(author)
            existing_index = index_by_key.get(key)
            if existing_index is None:
                index_by_key[key] = len(deduped)
                deduped.append(author)
                continue
            deduped[existing_index] = self._merge_author_entries(
                deduped[existing_index], author
            )
        return deduped

    def _build_project_abstract(
        self, description: Dict[str, Any], project_meta: Dict[str, Any]
    ) -> str:
        """Build abstract text from dataset_description first, project metadata second."""
        explicit_description = str(description.get("Description") or "").strip()
        if explicit_description:
            return explicit_description

        overview = project_meta.get("Overview") or {}
        study_design = project_meta.get("StudyDesign") or {}
        data_collection = project_meta.get("DataCollection") or {}
        procedure = project_meta.get("Procedure") or {}

        parts = [
            str(overview.get("Main") or "").strip(),
            str(study_design.get("TypeDescription") or "").strip(),
            str(data_collection.get("Description") or "").strip(),
            str(procedure.get("Overview") or "").strip(),
        ]

        merged: List[str] = []
        seen = set()
        for part in parts:
            if not part or part in seen:
                continue
            seen.add(part)
            merged.append(part)
        return " ".join(merged).strip()

    def _build_project_keywords(
        self, description: Dict[str, Any], project_meta: Dict[str, Any]
    ) -> List[str]:
        """Build keywords from dataset_description and structured project metadata."""
        basics = project_meta.get("Basics") or {}
        study_design = project_meta.get("StudyDesign") or {}
        task_definitions = project_meta.get("TaskDefinitions") or {}

        keywords = self._normalize_keywords(description.get("Keywords"))
        keywords.extend(self._normalize_keywords(basics.get("Keywords")))

        study_type = str(study_design.get("Type") or "").strip()
        if study_type:
            keywords.append(study_type)

        if isinstance(task_definitions, dict):
            for task_name, task_config in task_definitions.items():
                task_label = str(task_name or "").strip()
                if task_label:
                    keywords.append(task_label)
                if isinstance(task_config, dict):
                    modality = str(task_config.get("modality") or "").strip()
                    if modality:
                        keywords.append(modality)

        deduped: List[str] = []
        seen = set()
        for item in keywords:
            for text in self._normalize_keywords(item):
                key = text.lower()
                if key in seen:
                    continue
                seen.add(key)
                deduped.append(text)
        return deduped

    @staticmethod
    def _default_citation_message(has_preferred_citation: bool = False) -> str:
        if has_preferred_citation:
            return (
                "If you use this dataset, please cite both the "
                "preferred-citation and the dataset itself."
            )
        return "If you use this dataset, please cite it using the metadata from this file."

    def _build_citation_message(self, config: Dict[str, Any]) -> str:
        value = str(config.get("how_to_acknowledge") or "").strip()
        if value and not self._is_url(value) and not self._normalize_doi(value):
            return value
        return self._default_citation_message(
            has_preferred_citation=bool(config.get("preferred_citation"))
        )

    @staticmethod
    def _yaml_folded_block(field_name: str, value: str) -> List[str]:
        lines = [f"{field_name}: >-"]
        for part in str(value or "").splitlines() or [str(value or "")]:
            text = part.strip()
            if text:
                lines.append(f"  {text}")
        return lines

    def _build_citation_config(
        self,
        name: str,
        description: Dict[str, Any],
        project_path: Optional[Path] = None,
    ) -> Dict[str, Any]:
        project_meta: Dict[str, Any] = {}
        if project_path:
            project_json = Path(project_path) / "project.json"
            if project_json.exists():
                try:
                    with open(project_json, "r", encoding="utf-8") as handle:
                        loaded = json.load(handle)
                        if isinstance(loaded, dict):
                            project_meta = loaded
                except Exception:
                    project_meta = {}

        description = self.apply_project_metadata_precedence(
            description,
            project_path=project_path,
            project_meta=project_meta,
        )
        overview = project_meta.get("Overview") or {}
        basics = project_meta.get("Basics") or {}

        def _first_project_value(*aliases: str) -> Any:
            for source in (description, basics, project_meta):
                normalized_source = self._normalize_mapping_keys(source)
                if not normalized_source:
                    continue
                for alias in aliases:
                    if alias in normalized_source:
                        value = normalized_source.get(alias)
                        if value not in (None, "", {}, []):
                            return value
            return None

        description_text = self._build_project_abstract(description, project_meta)
        keywords = self._build_project_keywords(description, project_meta)

        references: List[Any] = []
        references.extend(
            self._flatten_reference_candidates(description.get("ReferencesAndLinks"))
        )
        references.extend(
            self._flatten_reference_candidates(project_meta.get("References"))
        )
        references.extend(
            self._flatten_reference_candidates(project_meta.get("ReferencesAndLinks"))
        )

        all_authors = self.resolve_project_authors(
            description.get("Authors", []),
            project_meta=project_meta,
            project_path=project_path,
        )
        normalized_references = self._normalize_reference_entries(
            references, fallback_authors=all_authors
        )

        preferred_citation = self._build_preferred_citation(
            _first_project_value(
                "preferredcitation",
                "preferred-citation",
                "preferred_citation",
            ),
            normalized_references,
            description.get("HowToAcknowledge", ""),
            fallback_authors=all_authors,
        )
        preferred_citation_key = self._reference_identity_key(preferred_citation)
        if preferred_citation_key != ("", ""):
            filtered_references: List[Dict[str, Any]] = []
            removed_preferred_reference = False
            for reference in normalized_references:
                if (
                    not removed_preferred_reference
                    and self._reference_identity_key(reference)
                    == preferred_citation_key
                ):
                    removed_preferred_reference = True
                    continue
                filtered_references.append(reference)
            normalized_references = filtered_references

        url_candidates: List[str] = []

        def _append_candidate_url(value: Any) -> None:
            text = self._normalize_reference_text(value)
            if text and self._is_url(text):
                url_candidates.append(text)

        dataset_links = description.get("DatasetLinks")
        if isinstance(dataset_links, dict):
            for value in dataset_links.values():
                _append_candidate_url(value)
        else:
            for value in self._flatten_reference_candidates(dataset_links):
                _append_candidate_url(value)

        for ref in normalized_references:
            _append_candidate_url(ref.get("url"))

        deduped_urls: List[str] = []
        seen_urls = set()
        for candidate in url_candidates:
            key = candidate.lower().rstrip("/")
            if key in seen_urls:
                continue
            seen_urls.add(key)
            deduped_urls.append(candidate)

        repository_code = ""
        repository = ""
        canonical_url = ""

        for candidate in deduped_urls:
            if not repository_code and self._is_code_repository_url(candidate):
                repository_code = candidate
            if not repository and self._is_archive_repository_url(candidate):
                repository = candidate
            if (
                not canonical_url
                and not self._is_code_repository_url(candidate)
                and not self._is_archive_repository_url(candidate)
            ):
                canonical_url = candidate

        if not canonical_url and repository:
            canonical_url = repository
        if (
            repository_code
            and canonical_url
            and repository_code.rstrip("/") == canonical_url.rstrip("/")
        ):
            canonical_url = ""

        identifiers = self._normalize_identifier_entries(
            _first_project_value("identifiers")
        )
        if isinstance(dataset_links, dict):
            for link_key, link_value in dataset_links.items():
                link_url = self._normalize_reference_scalar_value(link_value)
                if not link_url or not self._is_url(link_url):
                    continue
                if link_url in {canonical_url, repository_code, repository}:
                    continue
                identifier_entry = {
                    "type": "url",
                    "value": link_url,
                }
                label = self._normalize_reference_scalar_value(link_key)
                if label:
                    identifier_entry["description"] = f"Dataset link: {label}"
                identifiers.extend(
                    self._normalize_identifier_entries([identifier_entry])
                )

        license_value = self._normalize_license_value(description.get("License"))
        license_url = ""
        if self._is_url(description.get("License")):
            license_url = str(description.get("License") or "").strip()
            license_value = ""
        elif self._is_url(license_value):
            license_url = license_value
            license_value = ""

        # Build contact list from corresponding authors
        contact_authors: List[Any] = []
        for author in all_authors:
            if isinstance(author, dict) and author.get("corresponding"):
                contact_authors.append(author)
        contact_authors = self._dedupe_authors(contact_authors)

        return {
            "name": description.get("Name")
            or basics.get("DatasetName")
            or project_meta.get("name")
            or name,
            "authors": all_authors,
            "contact": contact_authors,
            "doi": description.get("DatasetDOI", ""),
            "license": license_value,
            "license_url": license_url,
            "how_to_acknowledge": description.get("HowToAcknowledge", ""),
            "identifiers": identifiers,
            "preferred_citation": preferred_citation,
            "references": normalized_references,
            "keywords": keywords,
            "abstract": description_text,
            "url": canonical_url,
            "repository_code": repository_code,
            "repository": repository,
            "repository_artifact": self._normalize_reference_scalar_value(
                _first_project_value(
                    "repositoryartifact",
                    "repository-artifact",
                    "repository_artifact",
                )
            ),
            "commit": self._normalize_reference_scalar_value(
                _first_project_value("commit")
            ),
            "version": str(description.get("DatasetVersion") or "").strip(),
        }

    def _build_author_lines(self, authors: List[Any]) -> List[str]:
        """Build YAML author lines for a list of author entries (dict or string)."""
        lines: List[str] = []
        for author in authors:
            if isinstance(author, dict):
                given = str(author.get("given-names") or author.get("given") or "").strip()
                family = str(author.get("family-names") or author.get("family") or "").strip()
                aname = str(author.get("name") or "").strip()
                if family:
                    if given:
                        lines.append(f"  - given-names: {self._yaml_quote(given)}")
                        lines.append(f"    family-names: {self._yaml_quote(family)}")
                    else:
                        lines.append(f"  - family-names: {self._yaml_quote(family)}")
                elif aname:
                    lines.append(f"  - name: {self._yaml_quote(aname)}")
                else:
                    continue
                for field, key in [("email", "email"), ("affiliation", "affiliation"), ("orcid", "orcid"), ("website", "website")]:
                    val = str(author.get(key) or "").strip()
                    if val:
                        lines.append(f"    {field}: {self._yaml_quote(val)}")
            else:
                given, family = self._split_author_name(str(author))
                if not given and not family:
                    continue
                if given:
                    lines.append(f"  - given-names: {self._yaml_quote(given)}")
                    lines.append(f"    family-names: {self._yaml_quote(family)}")
                else:
                    lines.append(f"  - family-names: {self._yaml_quote(family)}")
        return lines

    def _append_yaml_field(
        self, lines: List[str], field_name: str, value: Any, indent: int = 0
    ) -> None:
        prefix = " " * indent
        if isinstance(value, dict):
            if not value:
                return
            lines.append(f"{prefix}{field_name}:")
            self._append_yaml_mapping(lines, value, indent + 2)
            return
        if isinstance(value, list):
            if not value:
                return
            lines.append(f"{prefix}{field_name}:")
            self._append_yaml_sequence(lines, value, indent + 2)
            return

        text = str(value or "").strip()
        if not text:
            return
        lines.append(f"{prefix}{field_name}: {self._yaml_quote(text)}")

    def _append_yaml_mapping(
        self, lines: List[str], mapping: Dict[str, Any], indent: int = 0
    ) -> None:
        for key, value in mapping.items():
            self._append_yaml_field(lines, key, value, indent)

    def _append_yaml_sequence(
        self, lines: List[str], values: List[Any], indent: int = 0
    ) -> None:
        prefix = " " * indent
        for item in values:
            if isinstance(item, dict):
                if not item:
                    continue
                lines.append(f"{prefix}-")
                self._append_yaml_mapping(lines, item, indent + 2)
                continue

            text = str(item or "").strip()
            if text:
                lines.append(f"{prefix}- {self._yaml_quote(text)}")

    def _create_citation_cff(self, name: str, config: Dict[str, Any]) -> str:
        """Create a CITATION.cff file with dataset-focused metadata."""
        authors = self._dedupe_authors(config.get("authors", []) or [])

        author_lines = []
        for author in authors:
            if isinstance(author, dict):
                given = str(
                    author.get("given-names") or author.get("given") or ""
                ).strip()
                family = str(
                    author.get("family-names") or author.get("family") or ""
                ).strip()
                author_name = str(author.get("name") or "").strip()

                if family:
                    author_lines.append(
                        f"  - given-names: {self._yaml_quote(given)}"
                        if given
                        else f"  - family-names: {self._yaml_quote(family)}"
                    )
                    if given:
                        author_lines.append(
                            f"    family-names: {self._yaml_quote(family)}"
                        )
                elif author_name:
                    author_lines.append(f"  - name: {self._yaml_quote(author_name)}")
                else:
                    continue

                optional_fields = [
                    ("email", author.get("email")),
                    ("affiliation", author.get("affiliation")),
                    ("orcid", author.get("orcid")),
                    ("website", author.get("website")),
                ]
                for field_name, field_value in optional_fields:
                    value = str(field_value or "").strip()
                    if value:
                        author_lines.append(
                            f"    {field_name}: {self._yaml_quote(value)}"
                        )
                continue

            given, family = self._split_author_name(str(author))
            if not given and not family:
                continue
            if given:
                author_lines.append(f"  - given-names: {self._yaml_quote(given)}")
                author_lines.append(f"    family-names: {self._yaml_quote(family)}")
            else:
                author_lines.append(f"  - family-names: {self._yaml_quote(family)}")

        if not author_lines:
            author_lines = [
                '  - family-names: "prism-studio"',
                '    given-names: "dataset"',
            ]

        title = config.get("name", name)
        doi = self._normalize_doi(config.get("doi", ""))
        license_value = self._normalize_license_value(config.get("license", ""))
        license_url = str(config.get("license_url", "") or "").strip()
        references = self._normalize_reference_entries(
            config.get("references", []), fallback_authors=authors
        )
        preferred_citation = self._build_preferred_citation(
            config.get("preferred_citation"),
            references,
            config.get("how_to_acknowledge"),
            fallback_authors=authors,
        )
        preferred_citation_key = self._reference_identity_key(preferred_citation)
        if preferred_citation_key != ("", ""):
            filtered_references: List[Dict[str, Any]] = []
            removed_preferred_reference = False
            for reference in references:
                if (
                    not removed_preferred_reference
                    and self._reference_identity_key(reference)
                    == preferred_citation_key
                ):
                    removed_preferred_reference = True
                    continue
                filtered_references.append(reference)
            references = filtered_references
        message = self._build_citation_message(
            {**config, "preferred_citation": preferred_citation}
        )
        identifiers = self._normalize_identifier_entries(config.get("identifiers", []))
        keywords = self._normalize_keywords(config.get("keywords", []))
        abstract = str(config.get("abstract", "") or "").strip()
        canonical_url = str(config.get("url", "") or "").strip()
        repository_code = str(config.get("repository_code", "") or "").strip()
        repository = str(config.get("repository", "") or "").strip()
        repository_artifact = str(
            config.get("repository_artifact", "") or ""
        ).strip()
        commit = str(config.get("commit", "") or "").strip()
        version = str(config.get("version", "") or "").strip()

        contact_authors = config.get("contact") or []
        if isinstance(contact_authors, (str, dict)):
            contact_authors = [contact_authors]
        contact_lines = self._build_author_lines(contact_authors)

        lines = [
            "cff-version: 1.2.0",
            f"title: {self._yaml_quote(title)}",
            "type: dataset",
            f"date-released: {self._yaml_quote(date.today().isoformat())}",
        ]
        lines.extend(self._yaml_folded_block("message", message))
        if doi:
            lines.append(f"doi: {self._yaml_quote(doi)}")
        if identifiers:
            lines.append("identifiers:")
            self._append_yaml_sequence(lines, identifiers, 2)

        lines.append("authors:")
        lines.extend(author_lines)

        if contact_lines:
            lines.append("contact:")
            lines.extend(contact_lines)

        if preferred_citation:
            lines.append("preferred-citation:")
            self._append_yaml_mapping(lines, preferred_citation, 2)

        if repository_code and self._is_url(repository_code):
            lines.append(f"repository-code: {self._yaml_quote(repository_code)}")
        if canonical_url and self._is_url(canonical_url):
            lines.append(f"url: {self._yaml_quote(canonical_url)}")
        if repository and self._is_url(repository):
            lines.append(f"repository: {self._yaml_quote(repository)}")
        if repository_artifact and self._is_url(repository_artifact):
            lines.append(
                f"repository-artifact: {self._yaml_quote(repository_artifact)}"
            )
        if commit:
            lines.append(f"commit: {self._yaml_quote(commit)}")
        if abstract:
            lines.append(f"abstract: {self._yaml_quote(abstract)}")
        if keywords:
            lines.append("keywords:")
            for keyword in keywords:
                lines.append(f"  - {self._yaml_quote(keyword)}")
        if license_value:
            lines.append(f"license: {self._yaml_quote(license_value)}")
        if license_url and self._is_url(license_url):
            lines.append(f"license-url: {self._yaml_quote(license_url)}")
        if version:
            lines.append(f"version: {self._yaml_quote(version)}")

        if references:
            lines.append("references:")
            self._append_yaml_sequence(lines, references, 2)

        return "\n".join(lines) + "\n"

    def update_citation_cff(
        self, project_path: Path, description: Dict[str, Any]
    ) -> None:
        """Update CITATION.cff based on dataset_description.json metadata."""
        name = description.get("Name", "Untitled Dataset")
        config = self._build_citation_config(name, description, Path(project_path))
        content = self._create_citation_cff(name, config)
        citation_path = Path(project_path) / "CITATION.cff"
        CrossPlatformFile.write_text(str(citation_path), content)

    @staticmethod
    def _clean_citation_source_text(value: Any) -> str:
        text = str(value or "").strip()
        if not text:
            return ""

        lowered = text.lower()
        if lowered == "[object object]":
            return ""
        if (
            lowered.startswith("required.")
            or lowered.startswith("recommended.")
            or lowered.startswith("optional.")
        ):
            return ""
        return text

    def _clean_citation_source_list(self, value: Any) -> List[str]:
        if isinstance(value, list):
            values = value
        elif value in (None, "", {}, []):
            values = []
        else:
            values = [value]

        cleaned: List[str] = []
        for item in values:
            text = self._clean_citation_source_text(item)
            if text:
                cleaned.append(text)
        return cleaned

    def _clean_citation_source_mapping(self, value: Any) -> Dict[str, str]:
        if not isinstance(value, dict):
            return {}

        cleaned: Dict[str, str] = {}
        for key, raw_item in value.items():
            normalized_key = str(key or "").strip()
            normalized_value = self._clean_citation_source_text(raw_item)
            if normalized_key and normalized_value:
                cleaned[normalized_key] = normalized_value
        return cleaned

    @staticmethod
    def _load_json_dict(path: Path) -> Dict[str, Any]:
        if not path.exists():
            return {}

        try:
            loaded = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return {}

        return loaded if isinstance(loaded, dict) else {}

    def _build_citation_status_description(self, project_path: Path) -> Dict[str, Any]:
        dataset_desc = self._load_json_dict(Path(project_path) / "dataset_description.json")
        project_data = self._load_json_dict(Path(project_path) / "project.json")
        payload = self.apply_project_metadata_precedence(
            dataset_desc,
            project_path=project_path,
            project_meta=project_data,
        )

        if not self._clean_citation_source_text(payload.get("Name")):
            payload["Name"] = Path(project_path).name

        return payload

    def _build_expected_citation_cff_content(self, project_path: Path) -> str:
        description = self._build_citation_status_description(project_path)
        name = description.get("Name") or Path(project_path).name
        config = self._build_citation_config(name, description, Path(project_path))
        return self._create_citation_cff(name, config)

    def regenerate_citation_cff(self, project_path: Path) -> None:
        """Regenerate CITATION.cff from canonical project metadata."""
        normalized_project_path = Path(project_path)
        content = self._build_expected_citation_cff_content(normalized_project_path)
        citation_path = normalized_project_path / "CITATION.cff"
        CrossPlatformFile.write_text(str(citation_path), content)

    @staticmethod
    def _normalize_citation_content_for_comparison(content: str) -> str:
        normalized_lines: List[str] = []
        for raw_line in str(content or "").splitlines():
            stripped = raw_line.strip()
            if not stripped:
                continue
            if stripped.startswith("date-released:"):
                continue
            normalized_lines.append(raw_line.rstrip())
        return "\n".join(normalized_lines).strip()

    def sync_dataset_metadata_to_project_json(
        self, project_path: Path, description: Dict[str, Any]
    ) -> None:
        """Mirror dataset-level metadata into project.json for app-side consistency."""
        project_json = Path(project_path) / "project.json"
        payload = self._load_json_dict(project_json)

        basics = payload.get("Basics")
        if not isinstance(basics, dict):
            basics = {}

        dataset_name = self._clean_citation_source_text(description.get("Name"))
        if dataset_name:
            payload["name"] = dataset_name
            basics["Name"] = dataset_name
            basics["DatasetName"] = dataset_name

        scalar_fields = {
            "BIDSVersion": self._clean_citation_source_text(
                description.get("BIDSVersion")
            ),
            "DatasetType": self._clean_citation_source_text(
                description.get("DatasetType")
            ),
            "DatasetDOI": self._clean_citation_source_text(
                description.get("DatasetDOI")
            ),
            "License": self._clean_citation_source_text(description.get("License")),
            "HowToAcknowledge": self._clean_citation_source_text(
                description.get("HowToAcknowledge")
            ),
            "Description": self._clean_citation_source_text(
                description.get("Description")
            ),
            "HEDVersion": self._clean_citation_source_text(
                description.get("HEDVersion")
            ),
            "Acknowledgements": self._clean_citation_source_text(
                description.get("Acknowledgements")
            ),
        }
        for key, value in scalar_fields.items():
            basics[key] = value

        basics["Keywords"] = self._normalize_keywords(description.get("Keywords"))
        basics["ReferencesAndLinks"] = self._clean_citation_source_list(
            description.get("ReferencesAndLinks")
        )
        basics["DatasetLinks"] = self._clean_citation_source_mapping(
            description.get("DatasetLinks")
        )
        basics["Funding"] = self._clean_citation_source_list(
            description.get("Funding")
        )
        basics["EthicsApprovals"] = self._clean_citation_source_list(
            description.get("EthicsApprovals")
        )
        basics["Authors"] = [
            author_name
            for author_name in (
                self._author_display_name(author)
                for author in self._normalize_list(description.get("Authors"))
            )
            if author_name
        ]

        payload["Basics"] = basics
        CrossPlatformFile.write_text(
            str(project_json), json.dumps(payload, indent=2, ensure_ascii=False)
        )

    def get_metadata_sync_status(self, project_path: Path) -> Dict[str, Any]:
        """Return consistency status for project.json and generated metadata files."""
        project_json_path = Path(project_path) / "project.json"
        dataset_desc_path = Path(project_path) / "dataset_description.json"

        project_exists = project_json_path.exists()
        dataset_exists = dataset_desc_path.exists()
        citation_status = self.get_citation_cff_status(Path(project_path))

        issues: List[str] = []

        if not project_exists:
            issues.append("project.json is missing at the dataset root.")
        if not dataset_exists:
            issues.append("dataset_description.json is missing at the dataset root.")

        project_data = self._load_json_dict(project_json_path)
        dataset_desc = self._load_json_dict(dataset_desc_path)

        if project_data and dataset_desc:
            basics = project_data.get("Basics")
            if not isinstance(basics, dict):
                basics = {}

            project_name = (
                self._clean_citation_source_text(project_data.get("name"))
                or self._clean_citation_source_text(basics.get("DatasetName"))
                or self._clean_citation_source_text(basics.get("Name"))
            )
            dataset_name = self._clean_citation_source_text(dataset_desc.get("Name"))
            if project_name and dataset_name and project_name != dataset_name:
                issues.append(
                    "project.json name does not match dataset_description.json Name."
                )

            comparisons = [
                (
                    "BIDS version",
                    self._clean_citation_source_text(basics.get("BIDSVersion")),
                    self._clean_citation_source_text(dataset_desc.get("BIDSVersion")),
                ),
                (
                    "Dataset type",
                    self._clean_citation_source_text(basics.get("DatasetType")),
                    self._clean_citation_source_text(dataset_desc.get("DatasetType")),
                ),
                (
                    "Dataset DOI",
                    self._clean_citation_source_text(basics.get("DatasetDOI")),
                    self._clean_citation_source_text(dataset_desc.get("DatasetDOI")),
                ),
                (
                    "Description",
                    self._clean_citation_source_text(basics.get("Description")),
                    self._clean_citation_source_text(dataset_desc.get("Description")),
                ),
                (
                    "HED version",
                    self._clean_citation_source_text(basics.get("HEDVersion")),
                    self._clean_citation_source_text(dataset_desc.get("HEDVersion")),
                ),
            ]
            for label, project_value, dataset_value in comparisons:
                if project_value and dataset_value and project_value != dataset_value:
                    issues.append(
                        f"project.json {label.lower()} does not match dataset_description.json."
                    )

            project_keywords = self._normalize_keywords(basics.get("Keywords"))
            dataset_keywords = self._normalize_keywords(dataset_desc.get("Keywords"))
            if project_keywords and dataset_keywords and project_keywords != dataset_keywords:
                issues.append(
                    "project.json keywords do not match dataset_description.json."
                )

        deduped_issues: List[str] = []
        seen = set()
        for issue in issues:
            key = issue.lower()
            if key in seen:
                continue
            seen.add(key)
            deduped_issues.append(issue)

        return {
            "project_json_exists": project_exists,
            "dataset_description_exists": dataset_exists,
            "citation_exists": bool(citation_status.get("exists")),
            "consistent": len(deduped_issues) == 0,
            "issues": deduped_issues,
        }

    def get_citation_cff_status(self, project_path: Path) -> Dict[str, Any]:
        """Return lightweight CITATION.cff health information for UI warnings."""
        citation_path = Path(project_path) / "CITATION.cff"
        if not citation_path.exists():
            return {
                "exists": False,
                "valid": False,
                "issues": ["CITATION.cff is missing at the dataset root."],
                "consistent": False,
                "consistency_issues": [],
            }

        try:
            content = citation_path.read_text(encoding="utf-8")
        except Exception as exc:
            return {
                "exists": True,
                "valid": False,
                "issues": [f"CITATION.cff could not be read: {exc}"],
                "consistent": False,
                "consistency_issues": [],
            }

        issues: List[str] = []

        required_root_keys = ("cff-version", "title", "message", "authors")
        for key in required_root_keys:
            if not re.search(rf"(?m)^{re.escape(key)}:\s*", content):
                issues.append(f"Missing required key: {key}.")

        version_match = re.search(r"(?m)^cff-version:\s*['\"]?([^'\"\n]+)", content)
        if version_match and version_match.group(1).strip() != "1.2.0":
            issues.append("cff-version must be 1.2.0.")

        author_entry_present = re.search(
            r"(?ms)^authors:\s*\n(?:\s{2,}[^\n]*\n)*\s{2,}-\s+(?:given-names:|family-names:|name:)",
            content,
        )
        if not author_entry_present:
            issues.append("Authors section must include at least one author entry.")

        references_match = re.search(
            r"(?ms)^references:\s*\n((?:\s{2,}[^\n]*\n?)*)", content
        )
        if references_match:
            ref_block = references_match.group(1)
            entries = list(
                re.finditer(r"(?ms)^\s{2}-\s*\n((?:\s{4,}[^\n]*\n?)*)", ref_block)
            )
            if not entries:
                issues.append(
                    "References section is present but contains no valid reference entries."
                )
            for index, match in enumerate(entries, start=1):
                entry_text = match.group(1)
                has_type = re.search(r"(?m)^\s{4}type:\s*", entry_text) is not None
                has_title = re.search(r"(?m)^\s{4}title:\s*", entry_text) is not None
                has_authors = (
                    re.search(
                        r"(?ms)^\s{4}authors:\s*\n(?:\s{6,}[^\n]*\n)*\s{6}-\s+",
                        entry_text,
                    )
                    is not None
                )

                if not has_type:
                    issues.append(f"Reference #{index} is missing required key: type.")
                if not has_title:
                    issues.append(f"Reference #{index} is missing required key: title.")
                if not has_authors:
                    issues.append(
                        f"Reference #{index} is missing required key: authors."
                    )

        consistency_issues: List[str] = []
        has_canonical_metadata = any(
            (Path(project_path) / filename).exists()
            for filename in ("dataset_description.json", "project.json")
        )
        if len(issues) == 0 and has_canonical_metadata:
            try:
                expected_content = self._build_expected_citation_cff_content(
                    Path(project_path)
                )
                if self._normalize_citation_content_for_comparison(content) != (
                    self._normalize_citation_content_for_comparison(expected_content)
                ):
                    consistency_issues.append(
                        "CITATION.cff differs from the metadata managed in PRISM Studio. Regenerate CITATION.cff or review the manual edits."
                    )
            except Exception as exc:
                consistency_issues.append(
                    f"CITATION.cff consistency check could not be completed: {exc}"
                )

        return {
            "exists": True,
            "valid": len(issues) == 0,
            "issues": issues,
            "consistent": len(consistency_issues) == 0,
            "consistency_issues": consistency_issues,
        }

    def _create_data_dictionary(self) -> str:
        """Create a minimal data dictionary template for sourcedata."""
        return "file\tcolumn\tname\tunit\tlevels\tdescription\n\t\t\t\t\t\n"

    def _create_example_survey_template(self) -> dict:
        """Create an example survey JSON template."""
        return {
            "Technical": {
                "StimulusType": "Questionnaire",
                "FileFormat": "tsv",
                "SoftwarePlatform": "Other",
                "Language": "en",
                "Respondent": "self",
            },
            "Study": {
                "TaskName": "example",
                "OriginalName": "Example Survey",
                "Version": "1.0",
                "Description": "Example survey template - replace with your questionnaire",
            },
            "Metadata": {
                "SchemaVersion": "1.1.1",
                "CreationDate": date.today().isoformat(),
                "Creator": "PRISM Project Manager",
            },
            "Q01": {
                "Description": "Example question 1 - replace with your items",
                "Levels": {
                    "1": "Strongly disagree",
                    "2": "Disagree",
                    "3": "Neutral",
                    "4": "Agree",
                    "5": "Strongly agree",
                },
            },
            "Q02": {
                "Description": "Example question 2 - replace with your items",
                "Levels": {
                    "1": "Never",
                    "2": "Rarely",
                    "3": "Sometimes",
                    "4": "Often",
                    "5": "Always",
                },
            },
        }

    def _create_example_biometrics_template(self) -> dict:
        """Create an example biometrics JSON template."""
        return {
            "Technical": {
                "StimulusType": "Measurement",
                "FileFormat": "tsv",
                "SoftwarePlatform": "Other",
            },
            "Study": {
                "TaskName": "example",
                "OriginalName": "Example Biometrics",
                "Version": "1.0",
                "Description": "Example biometrics template - replace with your measures",
            },
            "Metadata": {
                "SchemaVersion": "1.1.1",
                "CreationDate": date.today().isoformat(),
                "Creator": "PRISM Project Manager",
            },
            "height": {"Description": "Height measurement", "Unit": "cm"},
            "weight": {"Description": "Weight measurement", "Unit": "kg"},
            "heart_rate": {"Description": "Resting heart rate", "Unit": "bpm"},
        }


def get_available_modalities() -> List[str]:
    """Return list of available PRISM modalities."""
    return PRISM_MODALITIES.copy()
