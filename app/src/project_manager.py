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
import shutil
from pathlib import Path
from datetime import date
from typing import Dict, List, Any, Optional

from src.fixer import DatasetFixer
from src.cross_platform import CrossPlatformFile
from src.issues import get_fix_hint
from src.schema_manager import load_schema
from jsonschema import validate, ValidationError, Draft7Validator


# Available PRISM modalities
PRISM_MODALITIES = ["survey", "biometrics", "physio", "eyetracking", "events"]

# Valid project name pattern (no spaces, filesystem-safe)
PROJECT_NAME_PATTERN = re.compile(r'^[a-zA-Z0-9_-]+$')


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
                "error": f"Invalid project name '{name}'. Only letters, numbers, underscores and hyphens allowed."
            }

        # Validate path doesn't exist or is empty
        if project_path.exists():
            if any(project_path.iterdir()):
                return {
                    "success": False,
                    "error": f"Directory '{path}' already exists and is not empty"
                }
        
        # In the new YODA layout, sessions and modalities are not pre-selected.
        # We always create a standard structure that is populated later.
        sessions = 0  # Default to 0, since it's for later import
        modalities = ["survey", "biometrics"] # Default core modalities for folders

        created_files = []

        try:
            # Create project root
            project_path.mkdir(parents=True, exist_ok=True)
            
            # Create BIDS root (rawdata/)
            rawdata_path = project_path / "rawdata"
            rawdata_path.mkdir(exist_ok=True)
            created_files.append("rawdata/")

            # 1. Create dataset_description.json in rawdata/
            desc_path = rawdata_path / "dataset_description.json"
            desc_content = self._create_dataset_description(name, config)
            CrossPlatformFile.write_text(str(desc_path), json.dumps(desc_content, indent=2))
            created_files.append("rawdata/dataset_description.json")

            # 2. Create .bidsignore in rawdata/
            bidsignore_path = rawdata_path / ".bidsignore"
            bidsignore_content = self._create_bidsignore(modalities)
            CrossPlatformFile.write_text(str(bidsignore_path), bidsignore_content)
            created_files.append("rawdata/.bidsignore")

            # 3. Create .prismrc.json in root (controls project-wide validation)
            prismrc_path = project_path / ".prismrc.json"
            prismrc_content = self._create_prismrc()
            CrossPlatformFile.write_text(str(prismrc_path), json.dumps(prismrc_content, indent=2))
            created_files.append(".prismrc.json")

            # 4. Create README.md in root
            readme_path = project_path / "README.md"
            readme_content = self._create_readme(name, sessions, modalities)
            CrossPlatformFile.write_text(str(readme_path), readme_content)
            created_files.append("README.md")

            # 5. Create project governance files in root
            project_metadata_path = project_path / "project.json"
            project_metadata = self._create_project_metadata(name, config)
            CrossPlatformFile.write_text(
                str(project_metadata_path), json.dumps(project_metadata, indent=2, ensure_ascii=False)
            )
            created_files.append("project.json")

            contributors_path = project_path / "contributors.json"
            contributors = self._create_contributors_template(config)
            CrossPlatformFile.write_text(
                str(contributors_path), json.dumps(contributors, indent=2, ensure_ascii=False)
            )
            created_files.append("contributors.json")

            citation_path = project_path / "CITATION.cff"
            citation_content = self._create_citation_cff(name, config)
            CrossPlatformFile.write_text(str(citation_path), citation_content)
            created_files.append("CITATION.cff")

            # 6. Create CHANGES file in rawdata/
            changes_path = rawdata_path / "CHANGES"
            changes_content = f"1.0.0 {date.today().isoformat()}\n  - Initial dataset structure created and validated via PRISM.\n"
            CrossPlatformFile.write_text(str(changes_path), changes_content)
            created_files.append("rawdata/CHANGES")

            # 7. Create essential folders only (sourcedata, derivatives)
            # sourcedata/
            sourcedata_path = project_path / "sourcedata"
            sourcedata_path.mkdir(exist_ok=True)
            created_files.append("sourcedata/")

            # derivatives/
            derivatives_path = project_path / "derivatives"
            derivatives_path.mkdir(exist_ok=True)
            created_files.append("derivatives/")

            # code/ - minimal, for user scripts
            code_path = project_path / "code"
            code_path.mkdir(exist_ok=True)
            created_files.append("code/")

            return {
                "success": True,
                "path": str(project_path),
                "created_files": created_files,
                "message": f"Project '{name}' created successfully with {len(created_files)} files"
            }

        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "created_files": created_files
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
                - fixable_issues: List of auto-fixable issues
                - stats: Basic project statistics
        """
        project_path = Path(path)

        if not project_path.exists():
            return {
                "valid": False,
                "error": f"Path does not exist: {path}",
                "issues": [],
                "fixable_issues": []
            }

        if not project_path.is_dir():
            return {
                "valid": False,
                "error": f"Path is not a directory: {path}",
                "issues": [],
                "fixable_issues": []
            }

        issues = []
        fixable_issues = []
        stats = {
            "subjects": 0,
            "sessions": set(),
            "modalities": set(),
            "has_dataset_description": False,
            "has_participants_tsv": False,
            "has_participants_json": False,
            "has_bidsignore": False,
            "is_yoda": False
        }

        # Determine BIDS root: check for rawdata/ first (YODA layout)
        bids_root = project_path
        if (project_path / "rawdata").is_dir() and (project_path / "rawdata" / "dataset_description.json").exists():
            bids_root = project_path / "rawdata"
            stats["is_yoda"] = True

        # Check root files (in the identified BIDS root)
        if (bids_root / "dataset_description.json").exists():
            stats["has_dataset_description"] = True
        else:
            code = "PRISM001"
            msg = "Missing dataset_description.json"
            issues.append({
                "code": code,
                "message": msg,
                "fix_hint": get_fix_hint(code, msg),
                "fixable": True
            })
            fixable_issues.append(code)

        if (bids_root / "participants.tsv").exists():
            stats["has_participants_tsv"] = True
        else:
            code = "PRISM002"
            msg = "Missing participants.tsv"
            issues.append({
                "code": code,
                "message": msg,
                "fix_hint": get_fix_hint(code, msg),
                "fixable": False
            })

        if (bids_root / "participants.json").exists():
            stats["has_participants_json"] = True

        if (bids_root / ".bidsignore").exists():
            stats["has_bidsignore"] = True

        # Scan for subjects in BIDS root
        for item in bids_root.iterdir():
            if item.is_dir() and item.name.startswith("sub-"):
                stats["subjects"] += 1

                # Check for sessions
                for sub_item in item.iterdir():
                    if sub_item.is_dir():
                        if sub_item.name.startswith("ses-"):
                            stats["sessions"].add(sub_item.name)
                            # Check modalities in session
                            for mod_item in sub_item.iterdir():
                                if mod_item.is_dir() and mod_item.name in PRISM_MODALITIES:
                                    stats["modalities"].add(mod_item.name)
                        elif sub_item.name in PRISM_MODALITIES:
                            # Direct modality folder (no session)
                            stats["modalities"].add(sub_item.name)

        # Convert sets to lists for JSON serialization
        stats["sessions"] = sorted(list(stats["sessions"]))
        stats["modalities"] = sorted(list(stats["modalities"]))

        # Use DatasetFixer to find additional fixable issues
        try:
            fixer = DatasetFixer(path, dry_run=True)
            fixes = fixer.analyze()
            for fix in fixes:
                if fix.issue_code not in fixable_issues:
                    fixable_issues.append(fix.issue_code)
                    # Add to issues if not already present
                    if not any(i.get("code") == fix.issue_code for i in issues):
                        issues.append({
                            "code": fix.issue_code,
                            "message": fix.description,
                            "fix_hint": get_fix_hint(fix.issue_code, fix.description),
                            "fixable": True,
                            "file_path": fix.file_path
                        })
        except Exception:
            pass  # Fixer analysis failed, continue with basic checks

        return {
            "valid": len([i for i in issues if not i.get("fixable", False)]) == 0,
            "issues": issues,
            "fixable_issues": fixable_issues,
            "stats": stats
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
                "count": len(applied)
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "applied_fixes": []
            }

    def validate_dataset_description(self, description: Dict[str, Any]) -> List[Dict[str, Any]]:
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
            return [{"code": "SCHEMA_ERROR", "message": "Could not load dataset_description schema", "level": "ERROR"}]
            
        try:
            # Use Draft7Validator to get all errors
            validator = Draft7Validator(schema)
            errors = sorted(validator.iter_errors(description), key=lambda e: e.path)
            
            for error in errors:
                # Format the field path for better reporting
                field_path = " -> ".join([str(p) for p in error.path])
                msg = f"{field_path}: {error.message}" if field_path else error.message
                
                # Check for specific hints from issues.py
                code = "PRISM301" # General schema error
                if "too short" in error.message.lower() or "minlength" in error.message.lower() or "minitems" in error.message.lower():
                    code = "PRISM301"
                
                issues.append({
                    "code": code,
                    "message": msg,
                    "fix_hint": get_fix_hint(code, msg),
                    "level": "ERROR"
                })
        except Exception as e:
            issues.append({"code": "VALIDATION_ERROR", "message": str(e), "level": "ERROR"})
            
        return issues

    # =========================================================================
    # Private helper methods
    # =========================================================================

    def _create_dataset_description(self, name: str, config: Dict[str, Any] = None) -> Dict[str, Any]:
        """Create dataset_description.json content following BIDS v1.10.1."""
        if config is None:
            config = {}
            
        return {
            "Name": name,
            "BIDSVersion": "1.10.1",
            "DatasetType": config.get("dataset_type", "raw"),
            "Description": config.get("description", "A PRISM-compatible dataset for psychological research."),
            "License": config.get("license", "CC0"),
            "Authors": config.get("authors", ["TODO: Add author names"]),
            "Acknowledgements": config.get("acknowledgements", ""),
            "HowToAcknowledge": config.get("how_to_acknowledge", "Please cite the original paper or the dataset DOI below."),
            "Funding": config.get("funding", []),
            "ReferencesAndLinks": config.get("references_and_links", []),
            "DatasetDOI": config.get("doi", ""),
            "EthicsApprovals": config.get("ethics_approvals", []),
            "Keywords": config.get("keywords", ["psychology", "experiment", "PRISM"]),
            "HEDVersion": config.get("hed_version", "8.2.0"),
            "DatasetLinks": config.get("dataset_links", {}),
            "GeneratedBy": [
                {
                    "Name": "PRISM Validator",
                    "Version": "1.1.1",
                    "Description": "Dataset initialized and managed via PRISM Studio"
                }
            ],
            "SourceDatasets": config.get("source_datasets", [])
        }

    def _create_participants_tsv(self) -> str:
        """Create participants.tsv header (no sample rows)."""
        return "participant_id\tage\tsex\n"

    def _create_bidsignore(self, modalities: List[str]) -> str:
        """Create .bidsignore content."""
        content = "# .bidsignore - PRISM modalities excluded from BIDS validation\n"
        content += "# This ensures compatibility with standard BIDS tools (fMRIPrep, etc.)\n\n"

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
                "code/**"
            ]
        }

    def _create_readme(
        self, name: str, sessions: int, modalities: List[str]
    ) -> str:
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
                qc_content = "Quality control reports, validator outputs, and data snapshots.\n"
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
                    str(lib_example_path), json.dumps(example_survey, indent=2, ensure_ascii=False)
                )
                created.append(f"code/library/{mod}/survey-example.json")
            elif mod == "biometrics":
                example_bio = self._create_example_biometrics_template()
                lib_example_path = lib_mod_path / "biometrics-example.json"
                CrossPlatformFile.write_text(
                    str(lib_example_path), json.dumps(example_bio, indent=2, ensure_ascii=False)
                )
                created.append(f"code/library/{mod}/biometrics-example.json")

            # Recipe folders
            rec_mod_path = recipe_root / mod
            rec_mod_path.mkdir(exist_ok=True)
            created.append(f"code/recipes/{mod}/")

        return created

    def _create_project_metadata(self, name: str, config: Dict[str, Any]) -> Dict[str, Any]:
        """Create project-level metadata template."""
        return {
            "project_name": name,
            "created": date.today().isoformat(),
            "funding": config.get("funding", []),
            "ethics_approvals": config.get("ethics_approvals", []),
            "contacts": [],
            "preregistration": "",
            "data_access": "",
            "notes": ""
        }

    def _create_contributors_template(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """Create contributors template with CRediT roles."""
        authors = config.get("authors", []) or []
        contributors = []
        for author in authors:
            contributors.append({
                "name": author,
                "roles": ["Conceptualization"],
                "orcid": "",
                "email": ""
            })
        if not contributors:
            contributors.append({
                "name": "",
                "roles": [],
                "orcid": "",
                "email": ""
            })
        return {
            "contributors": contributors,
            "roles_reference": "https://credit.niso.org/"
        }

    def _create_citation_cff(self, name: str, config: Dict[str, Any]) -> str:
        """Create a minimal CITATION.cff file."""
        authors = config.get("authors", []) or []
        author_lines = "\n".join(
            [f"  - family-names: {author}\n    given-names: " for author in authors]
        )
        if not author_lines:
            author_lines = "  - family-names: \n    given-names: "
        title = config.get("name", name)
        doi = config.get("doi", "")
        return (
            "cff-version: 1.2.0\n"
            f"title: {title}\n"
            "message: If you use this dataset, please cite it.\n"
            f"date-released: {date.today().isoformat()}\n"
            f"doi: {doi}\n"
            "authors:\n"
            f"{author_lines}\n"
        )

    def _create_data_dictionary(self) -> str:
        """Create a minimal data dictionary template for sourcedata."""
        return (
            "file\tcolumn\tname\tunit\tlevels\tdescription\n"
            "\t\t\t\t\t\n"
        )

    def _create_example_survey_template(self) -> dict:
        """Create an example survey JSON template."""
        return {
            "Technical": {
                "StimulusType": "Questionnaire",
                "FileFormat": "tsv",
                "SoftwarePlatform": "Generic",
                "Language": "en",
                "Respondent": "self"
            },
            "Study": {
                "TaskName": "example",
                "OriginalName": "Example Survey",
                "Version": "1.0",
                "Description": "Example survey template - replace with your questionnaire"
            },
            "Metadata": {
                "SchemaVersion": "1.1.1",
                "CreationDate": date.today().isoformat(),
                "Creator": "PRISM Project Manager"
            },
            "Q01": {
                "Description": "Example question 1 - replace with your items",
                "Levels": {
                    "1": "Strongly disagree",
                    "2": "Disagree",
                    "3": "Neutral",
                    "4": "Agree",
                    "5": "Strongly agree"
                }
            },
            "Q02": {
                "Description": "Example question 2 - replace with your items",
                "Levels": {
                    "1": "Never",
                    "2": "Rarely",
                    "3": "Sometimes",
                    "4": "Often",
                    "5": "Always"
                }
            }
        }

    def _create_example_biometrics_template(self) -> dict:
        """Create an example biometrics JSON template."""
        return {
            "Technical": {
                "StimulusType": "Measurement",
                "FileFormat": "tsv",
                "SoftwarePlatform": "Generic"
            },
            "Study": {
                "TaskName": "example",
                "OriginalName": "Example Biometrics",
                "Version": "1.0",
                "Description": "Example biometrics template - replace with your measures"
            },
            "Metadata": {
                "SchemaVersion": "1.1.1",
                "CreationDate": date.today().isoformat(),
                "Creator": "PRISM Project Manager"
            },
            "height": {
                "Description": "Height measurement",
                "Unit": "cm"
            },
            "weight": {
                "Description": "Weight measurement",
                "Unit": "kg"
            },
            "heart_rate": {
                "Description": "Resting heart rate",
                "Unit": "bpm"
            }
        }


def get_available_modalities() -> List[str]:
    """Return list of available PRISM modalities."""
    return PRISM_MODALITIES.copy()
