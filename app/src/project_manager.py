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
import re
from pathlib import Path
from datetime import date
from typing import Dict, List, Any, Optional
from urllib.parse import urlparse

from src.fixer import DatasetFixer
from src.constants import DEFAULT_BIDS_VERSION
from src.cross_platform import CrossPlatformFile
from src.issues import get_fix_hint, infer_code_from_message
from src.schema_manager import load_schema
from src.readme_generator import ReadmeGenerator
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
            if any(project_path.iterdir()):
                return {
                    "success": False,
                    "error": f"Directory '{path}' already exists and is not empty",
                }

        # In the new YODA layout, sessions and modalities are not pre-selected.
        # We always create a standard structure that is populated later.
        sessions = 0  # Default to 0, since it's for later import
        modalities = ["survey", "biometrics"]  # Default core modalities for folders

        created_files = []

        try:
            # Create project root
            project_path.mkdir(parents=True, exist_ok=True)

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

            return {
                "success": True,
                "path": str(project_path),
                "created_files": created_files,
                "message": f"Project '{name}' created successfully with {len(created_files)} files",
            }

        except Exception as e:
            return {"success": False, "error": str(e), "created_files": created_files}

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

        try:
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

            skipped = (
                "  (existing files were not modified)" if not created_files else ""
            )
            msg = (
                f"PRISM initialised on '{name}': "
                f"{len(created_files)} file(s) added.{skipped}"
            )
            return {
                "success": True,
                "path": str(project_path),
                "created_files": created_files,
                "message": msg,
            }

        except Exception as exc:
            return {"success": False, "error": str(exc), "created_files": created_files}

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
        return {
            "name": name,
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
            "Sessions": [],
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
        return json.dumps(value or "")

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
        fallback_author_objects = []
        for author in fallback_authors or []:
            display = self._author_display_name(author)
            if display:
                fallback_author_objects.append({"name": display})
        if not fallback_author_objects:
            fallback_author_objects = [{"name": "Unknown"}]

        for ref in self._normalize_list(references):
            entry: Dict[str, Any] = {}
            if isinstance(ref, dict):
                ref_type = self._normalize_reference_text(ref.get("type"))
                ref_title = self._normalize_reference_text(ref.get("title"))
                ref_url = self._normalize_reference_text(ref.get("url"))
                ref_doi = self._normalize_doi(ref.get("doi"))
                ref_authors_raw = ref.get("authors")

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

                author_objects = []
                if isinstance(ref_authors_raw, list):
                    for raw_author in ref_authors_raw:
                        display = self._author_display_name(raw_author)
                        if display:
                            author_objects.append({"name": display})
                elif ref_authors_raw:
                    display = self._author_display_name(ref_authors_raw)
                    if display:
                        author_objects.append({"name": display})

                entry["authors"] = author_objects or fallback_author_objects
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

            author_entry: Dict[str, str] = {}
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

    @staticmethod
    def _author_identity_key(author: Any) -> tuple[str, ...]:
        """Build a stable identity key for author de-duplication."""
        if isinstance(author, dict):
            given = str(author.get("given-names") or author.get("given") or "").strip().lower()
            family = str(author.get("family-names") or author.get("family") or "").strip().lower()
            name = str(author.get("name") or "").strip().lower()

            if given or family:
                display = " ".join(part for part in (given, family) if part).strip()
                return ("person", display)
            if name:
                return ("name", name)

            orcid = str(author.get("orcid") or author.get("ORCID") or "").strip().lower()
            if orcid:
                return ("orcid", orcid)

            email = str(author.get("email") or "").strip().lower()
            if email:
                return ("email", email)
            return ("raw", json.dumps(author, sort_keys=True, ensure_ascii=False))

        display = ProjectManager._author_display_name(author).strip().lower()
        if display:
            return ("person", display)
        return ("raw", str(author or "").strip().lower())

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
    def _default_citation_message() -> str:
        return (
            "If you use this dataset, please cite both the article from "
            "preferred-citation and the dataset itself."
        )

    def _build_citation_message(self, config: Dict[str, Any]) -> str:
        value = str(config.get("how_to_acknowledge") or "").strip()
        if value and not self._is_url(value) and not self._normalize_doi(value):
            return value
        return self._default_citation_message()

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

        overview = project_meta.get("Overview") or {}
        basics = project_meta.get("Basics") or {}

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

        description_authors = description.get("Authors", []) or []
        project_authors = self._extract_project_authors(project_meta, project_path)
        all_authors = self._dedupe_authors(
            description_authors if description_authors else project_authors
        )
        normalized_references = self._normalize_reference_entries(
            references, fallback_authors=all_authors
        )

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
        if repository_code and canonical_url and repository_code.rstrip("/") == canonical_url.rstrip("/"):
            canonical_url = ""

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
            "references": normalized_references,
            "keywords": keywords,
            "abstract": description_text,
            "url": canonical_url,
            "repository_code": repository_code,
            "repository": repository,
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
                name = str(author.get("name") or "").strip()

                if family:
                    author_lines.append(f"  - given-names: {self._yaml_quote(given)}" if given else f"  - family-names: {self._yaml_quote(family)}")
                    if given:
                        author_lines.append(
                            f"    family-names: {self._yaml_quote(family)}"
                        )
                elif name:
                    author_lines.append(f"  - name: {self._yaml_quote(name)}")
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
        message = self._build_citation_message(config)
        references = self._normalize_reference_entries(
            config.get("references", []), fallback_authors=authors
        )
        keywords = self._normalize_keywords(config.get("keywords", []))
        abstract = str(config.get("abstract", "") or "").strip()
        canonical_url = str(config.get("url", "") or "").strip()
        repository_code = str(config.get("repository_code", "") or "").strip()
        repository = str(config.get("repository", "") or "").strip()
        version = str(config.get("version", "") or "").strip()

        # Build contact lines from corresponding authors
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

        lines.append("authors:")
        lines.extend(author_lines)

        if contact_lines:
            lines.append("contact:")
            lines.extend(contact_lines)

        if repository_code and self._is_url(repository_code):
            lines.append(f"repository-code: {self._yaml_quote(repository_code)}")
        if canonical_url and self._is_url(canonical_url):
            lines.append(f"url: {self._yaml_quote(canonical_url)}")
        if repository and self._is_url(repository):
            lines.append(f"repository: {self._yaml_quote(repository)}")
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
            for ref in references:
                lines.append("  -")
                for key in ("type", "title", "doi", "url"):
                    value = str(ref.get(key) or "").strip()
                    if not value:
                        continue
                    lines.append(f"    {key}: {self._yaml_quote(value)}")
                ref_authors = ref.get("authors") or []
                if isinstance(ref_authors, list) and ref_authors:
                    lines.append("    authors:")
                    for ref_author in ref_authors:
                        if not isinstance(ref_author, dict):
                            continue
                        author_name = str(ref_author.get("name") or "").strip()
                        if author_name:
                            lines.append(
                                f"      - name: {self._yaml_quote(author_name)}"
                            )

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

    def get_citation_cff_status(self, project_path: Path) -> Dict[str, Any]:
        """Return lightweight CITATION.cff health information for UI warnings."""
        citation_path = Path(project_path) / "CITATION.cff"
        if not citation_path.exists():
            return {
                "exists": False,
                "valid": False,
                "issues": ["CITATION.cff is missing at the dataset root."],
            }

        try:
            content = citation_path.read_text(encoding="utf-8")
        except Exception as exc:
            return {
                "exists": True,
                "valid": False,
                "issues": [f"CITATION.cff could not be read: {exc}"],
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

        return {
            "exists": True,
            "valid": len(issues) == 0,
            "issues": issues,
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
                "SoftwarePlatform": "Generic",
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
                "SoftwarePlatform": "Generic",
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
