"""
AND (Austrian NeuroCloud) Export Converter

Converts PRISM datasets to ANC-compatible format for submission.

Features:
- Generates ANC-required files (README, CITATION.cff, .bids-validator-config.json)
- Optionally converts DataLad to Git LFS for AND compatibility
- Validates dataset against AND requirements
- Creates export package ready for AND submission

Usage:
    python -m src.converters.anc_export /path/to/dataset --output /path/to/anc_export
"""

from pathlib import Path
import json
import shutil
import logging
from typing import Dict, Optional, Any
from datetime import datetime
import sys

# Add parent directory to path for imports
if __name__ == "__main__":
    sys.path.insert(0, str(Path(__file__).parent.parent.parent))

try:
    from app.src.readme_generator import ReadmeGenerator

    HAS_README_GENERATOR = True
except ImportError:
    HAS_README_GENERATOR = False

logger = logging.getLogger(__name__)


class ANCExporter:
    """
    Export PRISM datasets to ANC-compatible format.
    """

    def __init__(self, dataset_path: Path, output_path: Optional[Path] = None):
        """
        Initialize AND exporter.

        Args:
            dataset_path: Path to PRISM dataset
            output_path: Output path for AND export (default: dataset_path_anc)
        """
        self.dataset_path = Path(dataset_path)
        self.output_path = (
            Path(output_path) if output_path else Path(f"{dataset_path}_anc_export")
        )

        if not self.dataset_path.exists():
            raise ValueError(f"Dataset not found: {dataset_path}")

    def export(
        self,
        metadata: Optional[Dict[str, Any]] = None,
        convert_to_git_lfs: bool = False,
        copy_data: bool = True,
        include_ci_examples: bool = False,
    ) -> Path:
        """
        Export dataset to ANC-compatible format.

        Args:
            metadata: Dataset metadata for README/CITATION generation
            convert_to_git_lfs: Convert from DataLad to Git LFS
            copy_data: Copy dataset files (vs creating symlinks)
            include_ci_examples: Include CI/CD example files

        Returns:
            Path to exported dataset
        """
        logger.info(f"Exporting PRISM dataset to AND format: {self.output_path}")

        # Create output directory
        self.output_path.mkdir(parents=True, exist_ok=True)

        # Step 1: Copy/link dataset structure
        if copy_data:
            self._copy_dataset_structure()
        else:
            logger.info("Skipping data copy (metadata only)")

        # Step 2: Generate README from project.json (if available)
        if HAS_README_GENERATOR:
            self._generate_readme_from_project()
        else:
            # Fallback to legacy method
            existing_metadata = self._extract_metadata()
            if metadata:
                existing_metadata.update(metadata)
            self._generate_readme(existing_metadata)

        # Step 3: Generate other ANC-required files
        existing_metadata = self._extract_metadata()
        if metadata:
            existing_metadata.update(metadata)
        self._generate_bids_validator_config()
        self._generate_citation(existing_metadata)

        # Step 4: Handle Git LFS conversion if requested
        if convert_to_git_lfs:
            self._convert_to_git_lfs()
        else:
            self._add_datalad_note()

        # Step 5: Include CI/CD examples if requested
        if include_ci_examples:
            self._add_ci_examples()

        # Step 6: Validate export
        validation_report = self._validate_anc_requirements()

        logger.info(f"✓ AND export completed: {self.output_path}")
        return self.output_path

    def _copy_dataset_structure(self):
        """Copy dataset structure to export directory."""
        logger.info("Copying dataset structure...")

        # Files to copy
        copy_patterns = [
            "dataset_description.json",
            "participants.tsv",
            "participants.json",
            "README.md",
            "CHANGES",
            "LICENSE",
            "sub-*",
            "ses-*",
            "code/",
            "derivatives/",
            "stimuli/",
        ]

        # Files to skip (DataLad-specific)
        skip_patterns = [
            ".datalad/",
            ".git/",
            ".gitannex/",
        ]

        for item in self.dataset_path.iterdir():
            if item.name.startswith(".") and item.name not in [
                ".bidsignore",
                ".gitignore",
            ]:
                continue

            dest = self.output_path / item.name

            if item.is_dir():
                if not dest.exists():
                    shutil.copytree(item, dest, symlinks=False)
            else:
                if not dest.exists():
                    shutil.copy2(item, dest)

    def _extract_metadata(self) -> Dict[str, Any]:
        """Extract metadata from existing PRISM dataset."""
        metadata = {}

        # Extract from dataset_description.json
        desc_file = self.dataset_path / "dataset_description.json"
        if desc_file.exists():
            with open(desc_file) as f:
                desc = json.load(f)
                metadata["DATASET_NAME"] = desc.get("Name", "Untitled Dataset")
                metadata["BIDS_VERSION"] = desc.get("BIDSVersion", "1.10.0")
                metadata["LICENSE"] = desc.get("License", "Unknown")
                metadata["FUNDING"] = ", ".join(desc.get("Funding", []))
                metadata["ETHICS_APPROVALS"] = ", ".join(
                    desc.get("EthicsApprovals", [])
                )

                # Extract authors if present
                if "Authors" in desc and desc["Authors"]:
                    first_author = desc["Authors"][0]
                    if isinstance(first_author, str):
                        parts = first_author.split()
                        metadata["AUTHOR_GIVEN_NAME"] = parts[0] if parts else "Unknown"
                        metadata["AUTHOR_FAMILY_NAME"] = (
                            parts[-1] if len(parts) > 1 else "Author"
                        )

        # Extract from README if exists
        readme_file = self.dataset_path / "README.md"
        if readme_file.exists():
            readme_text = readme_file.read_text()
            # Extract first paragraph as abstract
            lines = [
                l.strip()
                for l in readme_text.split("\n")
                if l.strip() and not l.startswith("#")
            ]
            if lines:
                metadata["DATASET_ABSTRACT"] = lines[0][:500]  # First 500 chars

        # Count participants
        participants_file = self.dataset_path / "participants.tsv"
        if participants_file.exists():
            import pandas as pd

            df = pd.read_csv(participants_file, sep="\t")
            metadata["PARTICIPANT_COUNT"] = len(df)
            metadata["DATASET_CONTENTS"] = f"{len(df)} participants"

        return metadata

    def _generate_readme_from_project(self):
        """Generate README using the new project.json-based generator."""
        try:
            # Check if project.json exists in source dataset
            project_json = self.dataset_path / "project.json"
            if not project_json.exists():
                logger.warning("No project.json found, falling back to basic README")
                return

            # Use ReadmeGenerator for source dataset
            generator = ReadmeGenerator(self.dataset_path)
            readme_content = generator.generate()

            # Write to output path
            output_readme = self.output_path / "README.md"
            with open(output_readme, "w", encoding="utf-8") as f:
                f.write(readme_content)

            logger.info("✓ Generated README.md from project metadata")
        except Exception as e:
            logger.warning(f"Failed to generate README from project.json: {e}")
            logger.info("Falling back to legacy README generation")

    def _generate_bids_validator_config(self):
        """Generate ANC-compatible .bids-validator-config.json."""
        config = {
            "ignore": [
                {"code": "SIDECAR_KEY_RECOMMENDED"},
                {"code": "JSON_KEY_RECOMMENDED"},
                {"code": "TOO_FEW_AUTHORS"},
            ],
            "warning": [
                {"code": "SUBJECT_FOLDERS"},
                {"code": "PARTICIPANT_ID_MISMATCH"},
                {"code": "STIMULUS_FILE_MISSING"},
                {"code": "PHENOTYPE_SUBJECTS_MISSING"},
            ],
            "error": [
                {"code": "EVENTS_TSV_MISSING"},
                {"code": "TSV_ADDITIONAL_COLUMNS_UNDEFINED"},
            ],
            "ignoredFiles": [
                "/code/",
                "/scripts/",
                "**/survey/",
                "**/image/",
                "**/movie/",
                "**/audio/",
                "**/biometrics/",
            ],
        }

        output_file = self.output_path / ".bids-validator-config.json"
        with open(output_file, "w") as f:
            json.dump(config, f, indent=2)

        logger.info(f"✓ Generated {output_file.name}")

    def _generate_readme(self, metadata: Dict[str, Any]):
        """Generate ANC-compatible README.md."""
        # Load template
        template_path = (
            Path(__file__).parent.parent.parent
            / "official"
            / "anc_templates"
            / "dataset_README_template.md"
        )

        if not template_path.exists():
            logger.warning("README template not found, creating basic README")
            self._create_basic_readme(metadata)
            return

        with open(template_path) as f:
            template = f.read()

        # Set defaults for missing fields
        defaults = {
            "DATASET_NAME": "Untitled Dataset",
            "DATASET_DESCRIPTION": "A PRISM/BIDS dataset exported for AND.",
            "DATASET_CONTENTS": metadata.get("DATASET_CONTENTS", "Not specified"),
            "INDEPENDENT_VARIABLES": "Not specified",
            "DEPENDENT_VARIABLES": "Not specified",
            "CONTROL_VARIABLES": "Not specified",
            "QUALITY_ASSESSMENT": "See PRISM validation report",
            "SUBJECT_DESCRIPTION": f"Total participants: {metadata.get('PARTICIPANT_COUNT', 'N/A')}",
            "RECRUITMENT_INFO": "Not specified",
            "INCLUSION_CRITERIA": "Not specified",
            "EXCLUSION_CRITERIA": "Not specified",
            "APPARATUS_DESCRIPTION": "Not specified",
            "INITIAL_SETUP": "Not specified",
            "TASK_ORGANIZATION": "Not specified",
            "TASK_DETAILS": "Not specified",
            "ADDITIONAL_DATA": "Not specified",
            "LOCATION_INFO": "Not specified",
            "MISSING_DATA_DESCRIPTION": "No known missing data",
            "MISSING_FILES_TABLE": "| | |",
            "KNOWN_ISSUES_TABLE": "| | |",
            "ADDITIONAL_NOTES": "This dataset was created using PRISM Studio and exported for AND submission.",
            "DATA_AGREEMENT": "Contact dataset authors for data use agreement",
            "CONTACT_NAME": "Dataset Contact",
            "CONTACT_EMAIL": "contact@example.com",
            "CONTACT_ORCID": "",
            "BIDS_VERSION": metadata.get("BIDS_VERSION", "1.10.0"),
            "PRISM_VERSION": "1.9.1",
            "LICENSE": metadata.get("LICENSE", "Not specified"),
            "FUNDING": metadata.get("FUNDING", "Not specified"),
            "ETHICS_APPROVALS": metadata.get("ETHICS_APPROVALS", "Not specified"),
            "REFERENCES": "Not specified",
        }

        # Merge with user metadata
        fields = {**defaults, **metadata}

        # Replace placeholders
        readme_content = template
        for key, value in fields.items():
            readme_content = readme_content.replace(f"{{{key}}}", str(value))

        # Write README
        output_file = self.output_path / "README.md"
        with open(output_file, "w") as f:
            f.write(readme_content)

        logger.info(f"✓ Generated {output_file.name}")

    def _create_basic_readme(self, metadata: Dict[str, Any]):
        """Create basic README if template not found."""
        readme = f"""# {metadata.get("DATASET_NAME", "Dataset")}

This dataset was generated with PRISM Studio and exported for AND (Austrian NeuroCloud) submission.

## Dataset Information

- **Participants**: {metadata.get("PARTICIPANT_COUNT", "N/A")}
- **License**: {metadata.get("LICENSE", "Not specified")}
- **BIDS Version**: {metadata.get("BIDS_VERSION", "1.10.0")}

## Contact

For more information about this dataset, please contact the dataset authors.

---

*Exported with PRISM Studio*
"""

        output_file = self.output_path / "README.md"
        output_file.write_text(readme)
        logger.info(f"✓ Generated basic {output_file.name}")

    def _generate_citation(self, metadata: Dict[str, Any]):
        """Generate ANC-compatible CITATION.cff."""
        citation = f"""# This CITATION.cff file was generated with PRISM Studio
# For AND (Austrian NeuroCloud) submission

cff-version: 1.2.0
title: {metadata.get("DATASET_NAME", "Untitled Dataset")}
message: >-
  If you use this dataset, please cite it using the metadata from this file.
type: dataset
authors:
  - given-names: {metadata.get("AUTHOR_GIVEN_NAME", "Unknown")}
    family-names: {metadata.get("AUTHOR_FAMILY_NAME", "Author")}
    email: {metadata.get("CONTACT_EMAIL", "contact@example.com")}
    orcid: '{metadata.get("CONTACT_ORCID", "https://orcid.org/0000-0000-0000-0000")}'
keywords: 
  - cognitive science
  - BIDS
  - PRISM
abstract: >-
  {metadata.get("DATASET_ABSTRACT", "A PRISM/BIDS dataset.")}
license: {metadata.get("LICENSE", "Unknown")}
version: 1.0.0
date-released: {datetime.now().strftime("%Y-%m-%d")}
"""

        output_file = self.output_path / "CITATION.cff"
        output_file.write_text(citation)
        logger.info(f"✓ Generated {output_file.name}")

    def _convert_to_git_lfs(self):
        """Convert from DataLad to Git LFS."""
        logger.info("Converting to Git LFS...")

        # Create .gitattributes for Git LFS
        gitattributes = """# Git LFS configuration for AND
*.nii filter=lfs diff=lfs merge=lfs -text
*.gz filter=lfs diff=lfs merge=lfs -text
*.svg filter=lfs diff=lfs merge=lfs -text
*.h5 filter=lfs diff=lfs merge=lfs -text
*.png filter=lfs diff=lfs merge=lfs -text
*.fif filter=lfs diff=lfs merge=lfs -text
*.mp4 filter=lfs diff=lfs merge=lfs -text
*.wav filter=lfs diff=lfs merge=lfs -text
*.edf filter=lfs diff=lfs merge=lfs -text
*.eeg filter=lfs diff=lfs merge=lfs -text
*.vhdr filter=lfs diff=lfs merge=lfs -text
*.vmrk filter=lfs diff=lfs merge=lfs -text
*.set filter=lfs diff=lfs merge=lfs -text
*.fdt filter=lfs diff=lfs merge=lfs -text
*.bdf filter=lfs diff=lfs merge=lfs -text
derivatives/mriqc/*.html filter=lfs diff=lfs merge=lfs -text
"""

        gitattributes_file = self.output_path / ".gitattributes"
        gitattributes_file.write_text(gitattributes)
        logger.info("✓ Created .gitattributes for Git LFS")

        # Add instructions
        instructions_file = self.output_path / "GIT_LFS_SETUP.md"
        instructions_file.write_text("""# Git LFS Setup Instructions

This dataset has been prepared for Git LFS. To push to AND:

1. Initialize Git repository:
   ```bash
   cd {dataset_path}
   git init
   ```

2. Install and initialize Git LFS:
   ```bash
   git lfs install
   git lfs track "*.nii" "*.gz" "*.mp4" "*.edf"  # etc.
   ```

3. Add files and commit:
   ```bash
   git add .
   git commit -m "Initial commit for AND submission"
   ```

4. Add AND remote and push:
   ```bash
   git remote add origin <ANC_REPO_URL>
   git push -u origin main
   ```

For more information, see: https://git-lfs.github.com/
""")
        logger.info("✓ Created Git LFS setup instructions")

    def _add_datalad_note(self):
        """Add note about DataLad usage."""
        note_file = self.output_path / "DATALAD_NOTE.md"
        note_file.write_text("""# DataLad Dataset Note

This dataset was exported from a PRISM/DataLad dataset.

**For AND submission**: If AND requires Git LFS instead of DataLad, run the export again with:
```bash
python -m src.converters.anc_export /path/to/dataset --convert-to-git-lfs
```

**For DataLad users**: This dataset can be used with DataLad directly.
""")
        logger.info("✓ Added DataLad note")

    def _add_ci_examples(self):
        """Add CI/CD example files to export."""
        logger.info("Adding CI/CD example files...")

        templates_dir = (
            Path(__file__).parent.parent.parent / "official" / "anc_templates"
        )

        # Copy GitLab CI example
        gitlab_ci_src = templates_dir / "example-gitlab-ci.yml"
        if gitlab_ci_src.exists():
            gitlab_ci_dest = self.output_path / ".gitlab-ci.yml.example"
            shutil.copy2(gitlab_ci_src, gitlab_ci_dest)
            logger.info(f"✓ Added {gitlab_ci_dest.name}")

        # Copy GitHub Actions example
        github_actions_src = templates_dir / "example-github-actions.yml"
        if github_actions_src.exists():
            github_workflows_dir = self.output_path / ".github" / "workflows"
            github_workflows_dir.mkdir(parents=True, exist_ok=True)
            github_actions_dest = github_workflows_dir / "validate.yml.example"
            shutil.copy2(github_actions_src, github_actions_dest)
            logger.info(f"✓ Added {github_actions_dest.name}")

        # Add instructions
        ci_info_file = self.output_path / "CI_SETUP.md"
        ci_info_file.write_text("""# CI/CD Setup Instructions

Example CI/CD configuration files have been included:

## For GitLab

1. Rename the example file:
   ```bash
   mv .gitlab-ci.yml.example .gitlab-ci.yml
   ```

2. Customize as needed and commit:
   ```bash
   git add .gitlab-ci.yml
   git commit -m "Add GitLab CI pipeline"
   ```

## For GitHub Actions

1. Rename the example file:
   ```bash
   mv .github/workflows/validate.yml.example .github/workflows/validate.yml
   ```

2. Customize as needed and commit:
   ```bash
   git add .github/workflows/validate.yml
   git commit -m "Add GitHub Actions workflow"
   ```

## What These Do

- Validate your dataset with BIDS validator
- Run PRISM validation checks
- Check for required files
- Generate validation reports

See the example files for customization options.
""")
        logger.info("✓ Added CI setup instructions")

    def _validate_anc_requirements(self) -> Dict[str, Any]:
        """Validate export against AND requirements."""
        logger.info("Validating AND requirements...")

        required_files = [
            "dataset_description.json",
            "participants.tsv",
            "README.md",
            "CITATION.cff",
            ".bids-validator-config.json",
        ]

        missing = []
        found = []

        for filename in required_files:
            file_path = self.output_path / filename
            if file_path.exists():
                found.append(filename)
            else:
                missing.append(filename)

        report = {
            "valid": len(missing) == 0,
            "found": found,
            "missing": missing,
        }

        if report["valid"]:
            logger.info("✓ All AND requirements met")
        else:
            logger.warning(f"⚠ Missing required files: {missing}")

        # Save report
        report_file = self.output_path / "ANC_EXPORT_REPORT.json"
        with open(report_file, "w") as f:
            json.dump(report, f, indent=2)

        return report


def main():
    """CLI entry point."""
    import argparse

    parser = argparse.ArgumentParser(
        description="Export PRISM dataset to ANC-compatible format"
    )
    parser.add_argument("dataset", type=Path, help="Path to PRISM dataset")
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        help="Output path for AND export (default: <dataset>_anc_export)",
    )
    parser.add_argument(
        "--git-lfs",
        action="store_true",
        help="Convert to Git LFS format (from DataLad)",
    )
    parser.add_argument(
        "--metadata", type=Path, help="JSON file with additional metadata"
    )
    parser.add_argument(
        "--include-ci-examples",
        action="store_true",
        help="Include CI/CD example files (.gitlab-ci.yml, GitHub Actions)",
    )

    args = parser.parse_args()

    # Load metadata if provided
    metadata = {}
    if args.metadata and args.metadata.exists():
        with open(args.metadata) as f:
            metadata = json.load(f)

    # Create exporter and run
    exporter = ANCExporter(args.dataset, args.output)
    output_path = exporter.export(
        metadata=metadata,
        convert_to_git_lfs=args.git_lfs,
        include_ci_examples=args.include_ci_examples,
    )

    print(f"\n✓ AND export completed: {output_path}")
    print("\nNext steps:")
    print("1. Review the generated README.md and CITATION.cff")
    print("2. Update metadata as needed")
    print("3. Run BIDS validator to confirm compliance")
    if args.git_lfs:
        print("4. Follow instructions in GIT_LFS_SETUP.md")
    print("5. Submit to AND")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    main()
