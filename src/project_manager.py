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
        sessions = max(1, config.get("sessions", 1))  # Minimum 1 session
        modalities = config.get("modalities", PRISM_MODALITIES)  # All modalities by default

        # Validate modalities
        invalid_mods = [m for m in modalities if m not in PRISM_MODALITIES]
        if invalid_mods:
            return {
                "success": False,
                "error": f"Invalid modalities: {invalid_mods}. Valid: {PRISM_MODALITIES}"
            }

        created_files = []

        try:
            # Create project root
            project_path.mkdir(parents=True, exist_ok=True)

            # 1. Create dataset_description.json
            desc_path = project_path / "dataset_description.json"
            desc_content = self._create_dataset_description(name, config)
            CrossPlatformFile.write_text(str(desc_path), json.dumps(desc_content, indent=2))
            created_files.append("dataset_description.json")

            # 2. Create participants.tsv with example row
            tsv_path = project_path / "participants.tsv"
            tsv_content = self._create_participants_tsv()
            CrossPlatformFile.write_text(str(tsv_path), tsv_content)
            created_files.append("participants.tsv")

            # 3. Copy participants.json template
            json_path = project_path / "participants.json"
            template_json = self.template_dir / "participants.json"
            if template_json.exists():
                shutil.copy(str(template_json), str(json_path))
            else:
                # Create minimal template if demo file doesn't exist
                minimal = {
                    "participant_id": {"Description": "Unique participant identifier"},
                    "age": {"Description": "Age of participant", "Units": "years"},
                    "sex": {"Description": "Biological sex", "Levels": {"M": "Male", "F": "Female"}}
                }
                CrossPlatformFile.write_text(str(json_path), json.dumps(minimal, indent=2))
            created_files.append("participants.json")

            # 4. Create .bidsignore
            bidsignore_path = project_path / ".bidsignore"
            bidsignore_content = self._create_bidsignore(modalities)
            CrossPlatformFile.write_text(str(bidsignore_path), bidsignore_content)
            created_files.append(".bidsignore")

            # 5. Create .prismrc.json
            prismrc_path = project_path / ".prismrc.json"
            prismrc_content = self._create_prismrc()
            CrossPlatformFile.write_text(str(prismrc_path), json.dumps(prismrc_content, indent=2))
            created_files.append(".prismrc.json")

            # 6. Create README.md with instructions
            readme_path = project_path / "README.md"
            readme_content = self._create_readme(name, sessions, modalities)
            CrossPlatformFile.write_text(str(readme_path), readme_content)
            created_files.append("README.md")

            # 7. Create CHANGES file (Recommended by BIDS)
            changes_path = project_path / "CHANGES"
            changes_content = f"1.0.0 {date.today().isoformat()}\n  - Initial dataset structure created and validated via PRISM.\n"
            CrossPlatformFile.write_text(str(changes_path), changes_content)
            created_files.append("CHANGES")

            # 8. Create BIDS standard folders
            bids_folders = self._create_bids_folders(project_path)
            created_files.extend(bids_folders)

            # 9. Create library folder structure for templates
            library_files = self._create_library_structure(project_path, modalities)
            created_files.extend(library_files)

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
            "has_bidsignore": False
        }

        # Check root files
        if (project_path / "dataset_description.json").exists():
            stats["has_dataset_description"] = True
        else:
            issues.append({
                "code": "PRISM001",
                "message": "Missing dataset_description.json",
                "fixable": True
            })
            fixable_issues.append("PRISM001")

        if (project_path / "participants.tsv").exists():
            stats["has_participants_tsv"] = True
        else:
            issues.append({
                "code": "PRISM002",
                "message": "Missing participants.tsv",
                "fixable": False
            })

        if (project_path / "participants.json").exists():
            stats["has_participants_json"] = True

        if (project_path / ".bidsignore").exists():
            stats["has_bidsignore"] = True

        # Scan for subjects
        for item in project_path.iterdir():
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
            "DatasetType": "raw",
            "License": config.get("license", "CC0"),
            "Authors": config.get("authors", ["TODO: Add author names"]),
            "Acknowledgements": config.get("acknowledgements", ""),
            "HowToAcknowledge": config.get("how_to_acknowledge", "Please cite the original paper or the dataset DOI below."),
            "Funding": config.get("funding", []),
            "ReferencesAndLinks": config.get("references_and_links", []),
            "DatasetDOI": config.get("doi", ""),
            "EthicsApprovals": config.get("ethics_approvals", []),
            "Keywords": config.get("keywords", []),
            "HEDVersion": "8.2.0",
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
                "sourcedata/**",
                "derivatives/**",
                "code/**"
            ]
        }

    def _create_readme(
        self, name: str, sessions: int, modalities: List[str]
    ) -> str:
        """Create README.md content with instructions."""
        today = date.today().isoformat()

        content = f"""# {name}

PRISM/BIDS-compatible dataset created on {today}.

## Structure

This project uses the PRISM framework for psychological research data.

### Modalities included:
"""
        for mod in modalities:
            content += f"- `{mod}/`\n"

        if sessions > 0:
            content += f"\n### Sessions: {sessions}\n"
        else:
            content += "\n### Sessions: None (single timepoint)\n"

        content += """
## Getting Started

1. **Create subject folders**: Make `sub-<label>/` directories (add `ses-01/` … if your study uses sessions) and place modality TSV files beneath them.
2. **Add metadata sidecars**: Every modality TSV needs a matching `.json` sidecar describing the data.
3. **Populate participants.tsv**: Add each subject here and keep descriptions synchronized with `participants.json`.
4. **Store raw & derived data**: Use the `sourcedata/` and `derivatives/` folders for source exports and processed outputs.
5. **Validate**: Run PRISM validation to confirm structural and metadata compliance before sharing.

## Project Structure

```
project/
├── dataset_description.json   # Dataset metadata (update Authors!)
├── participants.tsv           # Participant demographics
├── participants.json          # Column descriptions for participants.tsv
├── .bidsignore                # Excludes PRISM folders from BIDS validation
├── .prismrc.json              # PRISM validation settings
├── README.md                  # This file
│
├── sub-<label>/               # Create your subject folders here
│   ├── ses-01/                # Session folder (if applicable)
│   │   ├── survey/
│   │   └── biometrics/
│   └── ses-02/                # Add more sessions (if used)
│       ├── survey/
│       └── biometrics/
│
├── sourcedata/                # Raw source files (before BIDS conversion)
│   └── README                 # Describe incoming formats (Excel, LimeSurvey, etc.)
│
├── derivatives/               # Processed/derived outputs
│   └── README                 # e.g., scoring, analysis, recipe exports
│
├── code/                      # Analysis scripts
│   └── README                 # R, Python, SPSS, etc.
│
├── stimuli/                   # Stimulus files (images, audio, etc.)
│
└── code/library/              # JSON templates for conversion
    ├── survey/                # Survey JSON templates (LimeSurvey imports)
    └── biometrics/            # Biometrics JSON templates
```

## BIDS Standard Folders

- `sourcedata/` - Place original/raw data files here before converting to BIDS format
- `derivatives/` - Processed outputs (Recipes & Scoring writes to `derivatives/recipes/`)
- `code/` - Analysis scripts (R, Python, SPSS syntax, etc.)
- `stimuli/` - Stimulus files used in the study (images, audio, etc.)

## Library Folder

The `code/library/` folder contains JSON templates for your questionnaires and biometrics.
Use these with the Converter tool to process raw data into PRISM format.

- `code/library/survey/` - Place survey JSON templates here (e.g., from LimeSurvey import)
- `code/library/biometrics/` - Place biometrics JSON templates here

Note: The root `participants.json` is used for both BIDS compliance and the library.
When using the Converter, point "Template Library Root" to the `code/library/` folder.

## Resources

- PRISM Documentation: https://prism-studio.readthedocs.io/
- BIDS Specification: https://bids-specification.readthedocs.io/
"""
        return content

    def _create_bids_folders(self, project_path: Path) -> List[str]:
        """Create standard BIDS folder structure."""
        created = []

        # sourcedata/ - for raw source files before BIDS conversion
        sourcedata_path = project_path / "sourcedata"
        sourcedata_path.mkdir(exist_ok=True)
        created.append("sourcedata/")

        # Add README to sourcedata
        sourcedata_readme = sourcedata_path / "README"
        CrossPlatformFile.write_text(
            str(sourcedata_readme),
            "Place original/raw data files here before converting to BIDS format.\n"
            "Examples: Excel exports, LimeSurvey archives (.lsa), raw physio recordings.\n"
        )
        created.append("sourcedata/README")

        # derivatives/ - for processed/derived data
        derivatives_path = project_path / "derivatives"
        derivatives_path.mkdir(exist_ok=True)
        created.append("derivatives/")

        # Add README to derivatives
        derivatives_readme = derivatives_path / "README"
        CrossPlatformFile.write_text(
            str(derivatives_readme),
            "Processed and derived data outputs go here.\n"
            "Examples: Scored survey data, computed metrics, analysis outputs.\n"
            "The 'Recipes & Scoring' feature writes outputs to derivatives/recipes/.\n"
        )
        created.append("derivatives/README")

        # code/ - for analysis scripts
        code_path = project_path / "code"
        code_path.mkdir(exist_ok=True)
        created.append("code/")

        # Add README to code
        code_readme = code_path / "README"
        CrossPlatformFile.write_text(
            str(code_readme),
            "Place your analysis scripts here.\n"
            "Examples: R scripts, Python notebooks, SPSS syntax files.\n"
        )
        created.append("code/README")

        # stimuli/ - optional, for stimulus files
        stimuli_path = project_path / "stimuli"
        stimuli_path.mkdir(exist_ok=True)
        created.append("stimuli/")

        return created

    def _create_library_structure(
        self, project_path: Path, modalities: List[str]
    ) -> List[str]:
        """Create library folder structure for templates."""
        created = []
        library_root = project_path / "code" / "library"

        # Create library root under the ignored code/ folder
        library_root.mkdir(parents=True, exist_ok=True)
        created.append("code/library/")

        # Create modality subfolders
        if "survey" in modalities:
            survey_path = library_root / "survey"
            survey_path.mkdir(exist_ok=True)
            created.append("code/library/survey/")

            # Create example survey template
            example_survey = self._create_example_survey_template()
            example_path = survey_path / "survey-example.json"
            CrossPlatformFile.write_text(
                str(example_path), json.dumps(example_survey, indent=2, ensure_ascii=False)
            )
            created.append("code/library/survey/survey-example.json")

        if "biometrics" in modalities:
            biometrics_path = library_root / "biometrics"
            biometrics_path.mkdir(exist_ok=True)
            created.append("code/library/biometrics/")

            # Create example biometrics template
            example_bio = self._create_example_biometrics_template()
            example_path = biometrics_path / "biometrics-example.json"
            CrossPlatformFile.write_text(
                str(example_path), json.dumps(example_bio, indent=2, ensure_ascii=False)
            )
            created.append("code/library/biometrics/biometrics-example.json")

        # Note: participants.json is NOT duplicated in code/library/
        # The root-level participants.json (BIDS standard) is the single source of truth.
        # The converter will look for it at the project root.

        return created

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
                "Units": "cm"
            },
            "weight": {
                "Description": "Weight measurement",
                "Units": "kg"
            },
            "heart_rate": {
                "Description": "Resting heart rate",
                "Units": "bpm"
            }
        }


def get_available_modalities() -> List[str]:
    """Return list of available PRISM modalities."""
    return PRISM_MODALITIES.copy()
