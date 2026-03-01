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
from src.cross_platform import CrossPlatformFile
from src.issues import get_fix_hint
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

            contributors_path = project_path / "contributors.json"
            contributors = self._create_contributors_template(config)
            CrossPlatformFile.write_text(
                str(contributors_path),
                json.dumps(contributors, indent=2, ensure_ascii=False),
            )
            created_files.append("contributors.json")

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

    def validate_structure(self, path: str) -> Dict[str, Any]:
        """
        Validate an existing project's folder structure.

        Args:
            path: Path to the project

        Returns:
            Dict with validation results:
                - valid: Whether structure is valid
                - issues: List of issues found
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
        fixable_issues: List[str] = []
        subject_count = 0
        sessions: set[str] = set()
        modalities: set[str] = set()
        has_dataset_description = False
        has_participants_tsv = False
        has_participants_json = False
        has_bidsignore = False

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

        if (bids_root / "participants.tsv").exists():
            has_participants_tsv = True
        else:
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
                                if (
                                    mod_item.is_dir()
                                    and mod_item.name in PRISM_MODALITIES
                                ):
                                    modalities.add(mod_item.name)
                        elif sub_item.name in PRISM_MODALITIES:
                            # Direct modality folder (no session)
                            modalities.add(sub_item.name)

        stats = {
            "subjects": subject_count,
            "sessions": sorted(sessions),
            "modalities": sorted(modalities),
            "has_dataset_description": has_dataset_description,
            "has_participants_tsv": has_participants_tsv,
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

        raw_authors = config.get("authors") or []
        if isinstance(raw_authors, (str, dict)):
            raw_authors = [raw_authors]

        normalized_authors = [
            self._author_display_name(author)
            for author in raw_authors
            if self._author_display_name(author)
        ]
        normalized_doi = self._normalize_doi(config.get("doi", ""))

        return {
            "Name": name,
            "BIDSVersion": "1.10.1",
            "DatasetType": self._normalize_dataset_type(config.get("dataset_type")),
            "Description": config.get("description")
            or "A PRISM-compatible dataset for psychological research.",
            "License": config.get("license", "CC0"),
            "Authors": normalized_authors or ["prism-studio"],
            "Acknowledgements": config.get("acknowledgements", ""),
            "HowToAcknowledge": config.get(
                "how_to_acknowledge",
                "Please cite the original paper or the dataset DOI below.",
            ),
            "Funding": config.get("funding", []),
            "ReferencesAndLinks": config.get("references_and_links", []),
            "DatasetDOI": normalized_doi,
            "EthicsApprovals": config.get("ethics_approvals", []),
            "Keywords": config.get("keywords", ["psychology", "experiment", "PRISM"]),
            "HEDVersion": config.get("hed_version", "8.2.0"),
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
        content += "contributors.json\n"
        content += "CITATION.cff\n"
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
            if mod in PRISM_MODALITIES:
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
├── contributors.json       # CRediT roles and contributor list
├── CITATION.cff            # Dataset citation metadata
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
        contributors = []
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
        parts = author.strip().split()
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
            family = str(author.get("family-names") or author.get("family") or "").strip()
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

    def _normalize_reference_entries(
        self, references: Any, fallback_authors: Optional[List[Any]] = None
    ) -> List[Dict[str, Any]]:
        normalized: List[Dict[str, Any]] = []
        fallback_author_objects = []
        for author in (fallback_authors or []):
            display = self._author_display_name(author)
            if display:
                fallback_author_objects.append({"name": display})
        if not fallback_author_objects:
            fallback_author_objects = [{"name": "Unknown"}]

        for ref in self._normalize_list(references):
            entry: Dict[str, Any] = {}
            if isinstance(ref, dict):
                ref_type = str(ref.get("type") or "").strip()
                ref_title = str(ref.get("title") or "").strip()
                ref_url = str(ref.get("url") or "").strip()
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

                if entry.get("title"):
                    normalized.append(entry)
                continue

            text = str(ref or "").strip()
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
            key = (
                item.get("type", ""),
                item.get("title", ""),
                item.get("doi", ""),
                item.get("url", ""),
            )
            if key in seen:
                continue
            seen.add(key)
            deduped.append(item)
        return deduped

    def _build_citation_config(
        self, name: str, description: Dict[str, Any], project_path: Optional[Path] = None
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
        governance = project_meta.get("governance") or {}

        description_text = (
            str(description.get("Description") or "").strip()
            or str(overview.get("Main") or "").strip()
        )
        keywords = self._normalize_list(
            description.get("Keywords") or basics.get("Keywords")
        )

        references = []
        references.extend(self._normalize_list(description.get("ReferencesAndLinks")))
        references.extend(self._normalize_list(project_meta.get("References")))
        references.extend(self._normalize_list(governance.get("preregistration")))
        references.extend(self._normalize_list(governance.get("data_access")))
        normalized_references = self._normalize_reference_entries(
            references, fallback_authors=description.get("Authors", [])
        )

        dataset_links = description.get("DatasetLinks")
        canonical_url = ""
        if isinstance(dataset_links, dict):
            for value in dataset_links.values():
                text = str(value or "").strip()
                if self._is_url(text):
                    canonical_url = text
                    break

        if not canonical_url:
            for ref in normalized_references:
                ref_url = str(ref.get("url") or "").strip()
                if ref_url and self._is_url(ref_url):
                    canonical_url = ref_url
                    break

        repository_code = ""
        for ref in normalized_references:
            ref_url = str(ref.get("url") or "").strip()
            if not ref_url:
                continue
            if any(host in ref_url.lower() for host in ("github.com", "gitlab", "bitbucket")):
                repository_code = ref_url
                break

        license_value = self._normalize_license_value(description.get("License"))
        license_url = ""
        if self._is_url(description.get("License")):
            license_url = str(description.get("License") or "").strip()
            license_value = ""
        elif self._is_url(license_value):
            license_url = license_value
            license_value = ""

        return {
            "name": description.get("Name", name),
            "authors": description.get("Authors", []) or [],
            "doi": description.get("DatasetDOI", ""),
            "license": license_value,
            "license_url": license_url,
            "how_to_acknowledge": description.get("HowToAcknowledge", ""),
            "references": normalized_references,
            "keywords": [str(item).strip() for item in keywords if str(item).strip()],
            "abstract": description_text,
            "url": canonical_url,
            "repository_code": repository_code,
            "version": str(description.get("DatasetVersion") or "").strip(),
        }

    def _create_citation_cff(self, name: str, config: Dict[str, Any]) -> str:
        """Create a CITATION.cff file with dataset-focused metadata."""
        authors = config.get("authors", []) or []
        if isinstance(authors, str):
            authors = [authors]

        author_lines = []
        for author in authors:
            if isinstance(author, dict):
                given = str(author.get("given-names") or author.get("given") or "").strip()
                family = str(author.get("family-names") or author.get("family") or "").strip()
                name = str(author.get("name") or "").strip()

                if family:
                    author_lines.append(f"  - family-names: {self._yaml_quote(family)}")
                    if given:
                        author_lines.append(f"    given-names: {self._yaml_quote(given)}")
                elif name:
                    author_lines.append(f"  - name: {self._yaml_quote(name)}")
                else:
                    continue

                optional_fields = [
                    ("website", author.get("website")),
                    ("orcid", author.get("orcid")),
                    ("affiliation", author.get("affiliation")),
                    ("email", author.get("email")),
                ]
                for field_name, field_value in optional_fields:
                    value = str(field_value or "").strip()
                    if value:
                        author_lines.append(f"    {field_name}: {self._yaml_quote(value)}")
                continue

            given, family = self._split_author_name(str(author))
            if not given and not family:
                continue
            author_lines.append(f"  - family-names: {self._yaml_quote(family)}")
            if given:
                author_lines.append(f"    given-names: {self._yaml_quote(given)}")
        if not author_lines:
            author_lines = [
                '  - family-names: "prism-studio"',
                '    given-names: "dataset"',
            ]

        title = config.get("name", name)
        doi = self._normalize_doi(config.get("doi", ""))
        license_value = self._normalize_license_value(config.get("license", ""))
        license_url = str(config.get("license_url", "") or "").strip()
        message = (
            config.get("how_to_acknowledge")
            or "If you use this dataset, please cite it."
        )
        references = self._normalize_reference_entries(
            config.get("references", []), fallback_authors=authors
        )
        keywords = [
            str(item).strip()
            for item in self._normalize_list(config.get("keywords", []))
            if str(item).strip()
        ]
        abstract = str(config.get("abstract", "") or "").strip()
        canonical_url = str(config.get("url", "") or "").strip()
        repository_code = str(config.get("repository_code", "") or "").strip()
        version = str(config.get("version", "") or "").strip()

        lines = [
            "cff-version: 1.2.0",
            f"title: {self._yaml_quote(title)}",
            f"message: {self._yaml_quote(message)}",
            "type: dataset",
            f"date-released: {self._yaml_quote(date.today().isoformat())}",
        ]
        if doi:
            lines.append(f"doi: {self._yaml_quote(doi)}")
        if license_value:
            lines.append(f"license: {self._yaml_quote(license_value)}")
        if license_url and self._is_url(license_url):
            lines.append(f"license-url: {self._yaml_quote(license_url)}")
        if canonical_url and self._is_url(canonical_url):
            lines.append(f"url: {self._yaml_quote(canonical_url)}")
        if repository_code and self._is_url(repository_code):
            lines.append(f"repository-code: {self._yaml_quote(repository_code)}")
        if version:
            lines.append(f"version: {self._yaml_quote(version)}")
        if abstract:
            lines.append(f"abstract: {self._yaml_quote(abstract)}")
        if keywords:
            lines.append("keywords:")
            for keyword in keywords:
                lines.append(f"  - {self._yaml_quote(keyword)}")

        lines.append("authors:")
        lines.extend(author_lines)

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
                            lines.append(f"      - name: {self._yaml_quote(author_name)}")

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
            r"(?ms)^authors:\s*\n(?:\s{2,}[^\n]*\n)*\s{2,}-\s+(?:family-names:|name:)",
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
                re.finditer(
                    r"(?ms)^\s{2}-\s*\n((?:\s{4,}[^\n]*\n?)*)", ref_block
                )
            )
            if not entries:
                issues.append(
                    "References section is present but contains no valid reference entries."
                )
            for index, match in enumerate(entries, start=1):
                entry_text = match.group(1)
                has_type = re.search(r"(?m)^\s{4}type:\s*", entry_text) is not None
                has_title = re.search(r"(?m)^\s{4}title:\s*", entry_text) is not None
                has_authors = re.search(
                    r"(?ms)^\s{4}authors:\s*\n(?:\s{6,}[^\n]*\n)*\s{6}-\s+",
                    entry_text,
                ) is not None

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
