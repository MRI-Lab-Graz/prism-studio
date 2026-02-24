"""
Auto-fix functionality for prism.

Provides automatic repair of common issues:
- Missing .bidsignore entries for PRISM modalities
- Missing dataset_description.json (creates template)
- Missing sidecar JSON files (creates stubs)
- Fixing common filename issues

Usage:
    from fixer import DatasetFixer
    fixer = DatasetFixer(dataset_path)
    fixes = fixer.analyze()  # Get list of fixable issues
    fixer.apply_fixes()      # Apply all fixes
"""

import os
import json
from datetime import date
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field


@dataclass
class FixAction:
    """Represents a fixable issue and its repair action"""

    issue_code: str
    description: str
    file_path: str
    action_type: str  # "create", "modify", "rename", "delete"
    details: Dict[str, Any] = field(default_factory=dict)
    applied: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "issue_code": self.issue_code,
            "description": self.description,
            "file_path": self.file_path,
            "action_type": self.action_type,
            "details": self.details,
            "applied": self.applied,
        }


class DatasetFixer:
    """
    Analyze and fix common dataset issues.

    Usage:
        fixer = DatasetFixer("/path/to/dataset")
        fixes = fixer.analyze()

        # Review fixes
        for fix in fixes:
            print(f"{fix.action_type}: {fix.description}")

        # Apply all fixes
        results = fixer.apply_fixes()

        # Or apply specific fixes
        fixer.apply_fix(fixes[0])
    """

    def __init__(self, dataset_path: str, dry_run: bool = False):
        """
        Initialize the fixer.

        Args:
            dataset_path: Path to dataset root
            dry_run: If True, analyze but don't actually apply fixes
        """
        self.dataset_path = os.path.abspath(dataset_path)
        self.dry_run = dry_run

        # Canonical PRISM location: project folder is the BIDS root.
        self.bids_path = self.dataset_path

        self.fixes: List[FixAction] = []
        self._analyzed = False

    def analyze(self) -> List[FixAction]:
        """
        Analyze dataset for fixable issues.

        Returns:
            List of FixAction objects describing available fixes
        """
        self.fixes = []

        # Check for missing dataset_description.json
        self._check_dataset_description()

        # Check for missing/incomplete .bidsignore
        self._check_bidsignore()

        # Check for missing sidecars
        self._check_missing_sidecars()

        # Check for .prismrc.json (offer to create if missing)
        self._check_config_file()

        self._analyzed = True
        return self.fixes

    def apply_fixes(self, fix_codes: Optional[List[str]] = None) -> List[FixAction]:
        """
        Apply fixes to the dataset.

        Args:
            fix_codes: Optional list of issue codes to fix. If None, applies all.

        Returns:
            List of applied fixes
        """
        if not self._analyzed:
            self.analyze()

        applied = []
        for fix in self.fixes:
            if fix_codes is None or fix.issue_code in fix_codes:
                if self._apply_fix(fix):
                    fix.applied = True
                    applied.append(fix)

        return applied

    def _apply_fix(self, fix: FixAction) -> bool:
        """Apply a single fix action"""
        if self.dry_run:
            return True

        try:
            if fix.action_type == "create":
                return self._create_file(fix)
            elif fix.action_type == "modify":
                return self._modify_file(fix)
            elif fix.action_type == "rename":
                return self._rename_file(fix)
            else:
                return False
        except Exception as e:
            print(f"⚠️  Error applying fix: {e}")
            return False

    def _create_file(self, fix: FixAction) -> bool:
        """Create a new file"""
        content = fix.details.get("content", "")

        # Ensure directory exists
        dir_path = os.path.dirname(fix.file_path)
        if dir_path and not os.path.exists(dir_path):
            os.makedirs(dir_path)

        with open(fix.file_path, "w", encoding="utf-8") as f:
            f.write(content)

        return True

    def _modify_file(self, fix: FixAction) -> bool:
        """Modify an existing file"""
        append_content = fix.details.get("append", "")

        if append_content:
            with open(fix.file_path, "a", encoding="utf-8") as f:
                f.write(append_content)

        return True

    def _rename_file(self, fix: FixAction) -> bool:
        """Rename a file"""
        new_path = fix.details.get("new_path")
        if new_path and os.path.exists(fix.file_path):
            os.rename(fix.file_path, new_path)
            return True
        return False

    # =========================================================================
    # Issue Detection and Fix Generation
    # =========================================================================

    def _check_dataset_description(self):
        """Check for missing dataset_description.json"""
        desc_path = os.path.join(self.bids_path, "dataset_description.json")

        if not os.path.exists(desc_path):
            # Create a template
            template = {
                "Name": os.path.basename(self.dataset_path),
                "BIDSVersion": "1.10.1",
                "DatasetType": "raw",
                "License": "CC0",
                "Authors": ["TODO: Add author names"],
                "Acknowledgements": "",
                "HowToAcknowledge": "",
                "Funding": [],
                "ReferencesAndLinks": [],
                "DatasetDOI": "",
            }

            self.fixes.append(
                FixAction(
                    issue_code="PRISM001",
                    description="Create dataset_description.json with template",
                    file_path=desc_path,
                    action_type="create",
                    details={"content": json.dumps(template, indent=2)},
                )
            )

    def _check_bidsignore(self):
        """Check for missing .bidsignore entries"""
        bidsignore_path = os.path.join(self.bids_path, ".bidsignore")

        # PRISM-specific folders that should be in .bidsignore
        prism_folders = ["survey/", "biometrics/", "physio/", "eyetracking/", "events/"]

        existing_rules = set()
        if os.path.exists(bidsignore_path):
            with open(bidsignore_path, "r") as f:
                existing_rules = {
                    line.strip()
                    for line in f
                    if line.strip() and not line.startswith("#")
                }

        missing_rules = [r for r in prism_folders if r not in existing_rules]

        # Check if any PRISM folders actually exist in the BIDS root
        folders_present = []
        for folder in missing_rules:
            folder_name = folder.rstrip("/")
            # Check if folder exists at any level within BIDS root
            for root, dirs, files in os.walk(self.bids_path):
                if folder_name in dirs:
                    folders_present.append(folder)
                    break

        if folders_present:
            content = "\n# PRISM modalities (added by prism --fix)\n"
            content += "\n".join(folders_present) + "\n"

            if os.path.exists(bidsignore_path):
                self.fixes.append(
                    FixAction(
                        issue_code="PRISM501",
                        description=f"Add PRISM folders to .bidsignore: {', '.join(folders_present)}",
                        file_path=bidsignore_path,
                        action_type="modify",
                        details={"append": content},
                    )
                )
            else:
                header = "# .bidsignore created by prism\n"
                header += (
                    "# Ignores PRISM-specific folders for BIDS-App compatibility\n\n"
                )
                self.fixes.append(
                    FixAction(
                        issue_code="PRISM501",
                        description="Create .bidsignore with PRISM folders",
                        file_path=bidsignore_path,
                        action_type="create",
                        details={"content": header + content},
                    )
                )

    def _check_missing_sidecars(self):
        """Check for data files missing sidecar JSON files

        Respects BIDS inheritance: if a file can find a sidecar via inheritance
        (e.g., root-level task-{name}_survey.json), it is NOT flagged as missing.
        """
        # Extensions that need sidecars
        data_extensions = {".tsv", ".edf", ".nii", ".nii.gz"}

        for root, dirs, files in os.walk(self.bids_path):
            # Skip hidden directories and common non-data directories
            dirs[:] = [
                d
                for d in dirs
                if not d.startswith(".")
                and d
                not in [
                    "code",
                    "library",
                    "recipe",
                    "recipes",
                    "derivatives",
                    "sourcedata",
                    "analysis",
                    "paper",
                ]
            ]

            for filename in files:
                # Skip JSON files and hidden files
                if filename.endswith(".json") or filename.startswith("."):
                    continue

                # Check if this file needs a sidecar
                file_path = os.path.join(root, filename)
                needs_sidecar = False

                for ext in data_extensions:
                    if filename.endswith(ext):
                        needs_sidecar = True
                        break

                if not needs_sidecar:
                    continue

                # Determine sidecar path (for subject-level sidecar)
                if filename.endswith(".nii.gz"):
                    stem = filename[:-7]
                elif filename.endswith(".tsv.gz"):
                    stem = filename[:-7]
                else:
                    stem = os.path.splitext(filename)[0]

                subject_level_sidecar = os.path.join(root, f"{stem}.json")

                # Check if a sidecar exists at subject level
                if os.path.exists(subject_level_sidecar):
                    continue

                # Check if a sidecar can be found via BIDS inheritance (root-level)
                # This looks for inherited sidecars like task-{name}_survey.json at the dataset root
                if self._has_inherited_sidecar(file_path, filename):
                    continue

                # Only flag as missing if no sidecar found at any level
                # Determine modality from path/filename
                modality = self._infer_modality(file_path, filename)

                # Create stub sidecar
                stub = self._create_sidecar_stub(modality, filename)

                self.fixes.append(
                    FixAction(
                        issue_code="PRISM201",
                        description=f"Create sidecar stub for {filename}",
                        file_path=subject_level_sidecar,
                        action_type="create",
                        details={
                            "content": json.dumps(stub, indent=2),
                            "modality": modality,
                        },
                    )
                )

    def _check_config_file(self):
        """Check for missing .prismrc.json config file"""
        config_path = os.path.join(self.dataset_path, ".prismrc.json")
        alt_config_path = os.path.join(self.dataset_path, "prism.config.json")

        if not os.path.exists(config_path) and not os.path.exists(alt_config_path):
            config = {
                "schemaVersion": "stable",
                "ignorePaths": [
                    "derivatives/**",
                    "sourcedata/**",
                    "analysis/**",
                    "paper/**",
                    "code/**",
                ],
                "strictMode": False,
                "runBids": False,
            }

            # This is a low-priority fix, so we add it but mark it optional
            self.fixes.append(
                FixAction(
                    issue_code="PRISM000",  # Info-level
                    description="Create .prismrc.json configuration file",
                    file_path=config_path,
                    action_type="create",
                    details={
                        "content": json.dumps(config, indent=2),
                        "optional": True,
                    },
                )
            )

    def _has_inherited_sidecar(self, file_path: str, filename: str) -> bool:
        """Check if a file has an inherited sidecar via BIDS inheritance rules.

        BIDS inheritance allows root-level sidecars to apply to all matching files.
        For example: task-panas_survey.json in the root applies to all
        sub-*/ses-*/survey/sub-*_ses-*_task-panas_survey.tsv files.

        Args:
            file_path: Full path to the data file
            filename: Just the filename (basename)

        Returns:
            True if an inherited sidecar exists
        """
        stem = filename
        if filename.endswith(".nii.gz"):
            stem = filename[:-7]
        elif filename.endswith(".tsv.gz"):
            stem = filename[:-7]
        else:
            stem = os.path.splitext(filename)[0]

        # Extract common BIDS entities from the filename
        # Look for patterns like task-<name>, survey-<name>, biometrics-<name>
        entities = ["task", "survey", "biometrics"]

        for entity in entities:
            # Try to extract entity value: task-panas -> panas
            entity_pattern = f"{entity}-"
            if entity_pattern in stem:
                # Extract the value after the entity prefix
                parts = stem.split(entity_pattern)
                if len(parts) > 1:
                    value = parts[1].split("_")[0]  # Get value before next underscore

                    # Check for inherited sidecar at root level
                    # e.g., task-panas_survey.json
                    suffix = stem.split("_")[
                        -1
                    ]  # Get the last part (survey, biometrics, etc.)
                    inherited_name = f"{entity}-{value}_{suffix}.json"
                    inherited_path = os.path.join(self.bids_path, inherited_name)

                    if os.path.exists(inherited_path):
                        return True

                    # Also check in subdirectories like surveys/ or biometrics/
                    search_dirs = [
                        os.path.join(self.bids_path, "surveys"),
                        os.path.join(self.bids_path, "biometrics"),
                    ]
                    for search_dir in search_dirs:
                        inherited_path = os.path.join(search_dir, inherited_name)
                        if os.path.exists(inherited_path):
                            return True

        return False

    def _infer_modality(self, file_path: str, filename: str) -> str:
        """Infer modality from file path and name"""
        path_lower = file_path.lower()
        name_lower = filename.lower()

        if "/survey/" in path_lower or "_survey-" in name_lower:
            return "survey"
        elif "/biometrics/" in path_lower or "_biometrics-" in name_lower:
            return "biometrics"
        elif "/physio/" in path_lower or "_physio" in name_lower:
            return "physio"
        elif (
            "/eyetrack" in path_lower
            or "_eyetrack" in name_lower
            or "_eye" in name_lower
        ):
            return "eyetracking"
        elif "/anat/" in path_lower:
            return "anat"
        elif "/func/" in path_lower:
            return "func"
        elif "_events.tsv" in name_lower:
            return "events"
        else:
            return "unknown"

    def _create_sidecar_stub(self, modality: str, filename: str) -> Dict[str, Any]:
        """Create a stub sidecar JSON for a given modality"""
        today = date.today().isoformat()

        if modality == "survey":
            return {
                "Technical": {
                    "StimulusType": "Questionnaire",
                    "FileFormat": "tsv",
                    "Language": "en",
                    "Respondent": "self",
                },
                "Study": {
                    "TaskName": "TODO",
                    "OriginalName": "TODO: Full instrument name",
                },
                "Metadata": {"SchemaVersion": "1.1.1", "CreationDate": today},
            }
        elif modality == "biometrics":
            return {
                "Technical": {"StimulusType": "Assessment", "FileFormat": "tsv"},
                "Study": {"TaskName": "TODO", "OriginalName": "TODO: Assessment name"},
                "Metadata": {"SchemaVersion": "1.1.1", "CreationDate": today},
            }
        elif modality == "physio":
            return {
                "Technical": {
                    "SamplingFrequency": 1000,
                    "Columns": ["TODO: column names"],
                },
                "Study": {"TaskName": "TODO"},
                "Metadata": {"SchemaVersion": "1.1.1", "CreationDate": today},
            }
        elif modality == "eyetracking":
            return {
                "Technical": {
                    "SamplingFrequency": 1000,
                    "Manufacturer": "TODO",
                    "RecordedEye": "both",
                },
                "Screen": {"ScreenResolution": [1920, 1080], "ScreenDistance": 60},
                "Study": {"TaskName": "TODO"},
                "Metadata": {"SchemaVersion": "1.1.1", "CreationDate": today},
            }
        else:
            # Generic stub
            return {
                "Description": f"TODO: Add description for {filename}",
                "Metadata": {"SchemaVersion": "1.1.1", "CreationDate": today},
            }


def get_fixable_issues() -> Dict[str, str]:
    """
    Return a dictionary of issue codes that can be auto-fixed.

    Returns:
        Dict mapping issue code to fix description
    """
    return {
        "PRISM001": "Create dataset_description.json template",
        "PRISM201": "Create sidecar JSON stub files",
        "PRISM501": "Update .bidsignore for PRISM compatibility",
        "PRISM000": "Create .prismrc.json configuration (optional)",
    }
