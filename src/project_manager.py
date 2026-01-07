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
        "create_example": True
    })

    # Validate existing project
    result = pm.validate_structure("/path/to/project")

    # Apply fixes
    result = pm.apply_fixes("/path/to/project")
"""

import os
import json
import re
import shutil
from pathlib import Path
from datetime import date
from typing import Dict, List, Any, Optional

from src.fixer import DatasetFixer, get_fixable_issues
from src.cross_platform import CrossPlatformFile, safe_path_join


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
                - create_example: Whether to create example subject folder

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
        create_example = config.get("create_example", True)

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
            desc_content = self._create_dataset_description(name)
            CrossPlatformFile.write_text(str(desc_path), json.dumps(desc_content, indent=2))
            created_files.append("dataset_description.json")

            # 2. Create participants.tsv with example row
            tsv_path = project_path / "participants.tsv"
            tsv_content = self._create_participants_tsv(create_example)
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

            # 6. Create example subject folder structure
            if create_example:
                example_files = self._create_example_subject(
                    project_path, sessions, modalities
                )
                created_files.extend(example_files)

            # 7. Create README.md with instructions
            readme_path = project_path / "README.md"
            readme_content = self._create_readme(name, sessions, modalities)
            CrossPlatformFile.write_text(str(readme_path), readme_content)
            created_files.append("README.md")

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

    def _create_dataset_description(self, name: str) -> Dict[str, Any]:
        """Create dataset_description.json content."""
        return {
            "Name": name,
            "BIDSVersion": "1.9.0",
            "DatasetType": "raw",
            "License": "CC0",
            "Authors": ["TODO: Add author names"],
            "Acknowledgements": "",
            "HowToAcknowledge": "",
            "Funding": [],
            "ReferencesAndLinks": [],
            "DatasetDOI": ""
        }

    def _create_participants_tsv(self, include_example: bool = True) -> str:
        """Create participants.tsv content."""
        header = "participant_id\tage\tsex"
        if include_example:
            return f"{header}\nsub-example\tn/a\tn/a\n"
        return f"{header}\n"

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

    def _create_example_subject(
        self, project_path: Path, sessions: int, modalities: List[str]
    ) -> List[str]:
        """Create example subject folder structure."""
        created = []
        subject_path = project_path / "sub-example"

        if sessions > 0:
            # Create session folders
            for i in range(1, sessions + 1):
                session_name = f"ses-{i:02d}"
                session_path = subject_path / session_name

                for mod in modalities:
                    mod_path = session_path / mod
                    mod_path.mkdir(parents=True, exist_ok=True)
                    created.append(f"sub-example/{session_name}/{mod}/")
        else:
            # No sessions - create modality folders directly
            for mod in modalities:
                mod_path = subject_path / mod
                mod_path.mkdir(parents=True, exist_ok=True)
                created.append(f"sub-example/{mod}/")

        return created

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

1. **Rename the example subject**: Copy/rename `sub-example/` to `sub-001/`, `sub-002/`, etc.

2. **Add your data**: Place TSV data files in the appropriate modality folders.

3. **Create sidecars**: Each `.tsv` file needs a corresponding `.json` sidecar with metadata.

4. **Update participants.tsv**: Add a row for each subject.

5. **Validate**: Run PRISM validation to check your dataset structure.

## Files

- `dataset_description.json` - Dataset metadata (update the Authors field!)
- `participants.tsv` - Participant demographics
- `participants.json` - Column descriptions for participants.tsv
- `.bidsignore` - Excludes PRISM folders from standard BIDS validation

## Resources

- PRISM Documentation: https://prism-studio.readthedocs.io/
- BIDS Specification: https://bids-specification.readthedocs.io/
"""
        return content


def get_available_modalities() -> List[str]:
    """Return list of available PRISM modalities."""
    return PRISM_MODALITIES.copy()
