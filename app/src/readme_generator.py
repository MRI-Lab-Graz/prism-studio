"""
README Generator for PRISM Projects.

Generates structured README.md files from project.json study metadata
following the ANC (Austrian NeuroCloud) dataset documentation standard.
"""

import json
from pathlib import Path
from typing import Dict, Any, Optional


class ReadmeGenerator:
    """Generate README.md from project.json study metadata."""

    def __init__(self, project_path: Path):
        """Initialize generator with project path.
        
        Args:
            project_path: Path to project root containing project.json
        """
        self.project_path = Path(project_path)
        self.template_path = (
            Path(__file__).parent.parent.parent / "official" / "anc_templates" / 
            "dataset_README_template.md"
        )

    def generate(self, custom_metadata: Optional[Dict[str, Any]] = None) -> str:
        """Generate README content from project metadata.
        
        Args:
            custom_metadata: Optional dict to override extracted metadata
            
        Returns:
            Generated README content as string
        """
        # Extract metadata from project files
        metadata = self._extract_metadata()
        
        # Override with custom metadata if provided
        if custom_metadata:
            metadata.update(custom_metadata)
        
        # Load template
        if not self.template_path.exists():
            return self._create_basic_readme(metadata)
        
        with open(self.template_path, "r", encoding="utf-8") as f:
            template = f.read()
        
        # Replace all placeholders
        readme_content = template
        for key, value in metadata.items():
            placeholder = f"{{{key}}}"
            readme_content = readme_content.replace(placeholder, str(value))
        
        return readme_content

    def _extract_metadata(self) -> Dict[str, Any]:
        """Extract metadata from project.json, dataset_description.json, and other files."""
        metadata = {}
        
        # --- Load project.json ---
        project_json_path = self.project_path / "project.json"
        project_data = {}
        if project_json_path.exists():
            with open(project_json_path, "r", encoding="utf-8") as f:
                project_data = json.load(f)
        
        # --- Load dataset_description.json (check both root and rawdata/) ---
        dataset_desc = {}
        for desc_path in [
            self.project_path / "dataset_description.json",
            self.project_path / "rawdata" / "dataset_description.json"
        ]:
            if desc_path.exists():
                with open(desc_path, "r", encoding="utf-8") as f:
                    dataset_desc = json.load(f)
                break
        
        # --- Basic dataset info ---
        metadata["DATASET_NAME"] = dataset_desc.get("Name", project_data.get("name", "Untitled Dataset"))
        metadata["DATASET_DESCRIPTION"] = dataset_desc.get("Description", "A PRISM/BIDS-compatible dataset.")
        metadata["BIDS_VERSION"] = dataset_desc.get("BIDSVersion", "1.9.0")
        metadata["LICENSE"] = dataset_desc.get("License", "CC-BY-4.0")
        
        # --- Overview section from project.json ---
        overview = project_data.get("Overview", {})
        overview_main = overview.get("Main", "")
        if overview_main:
            metadata["DATASET_DESCRIPTION"] = overview_main  # Override with detailed overview
        
        # --- Dataset contents ---
        participant_count = self._count_participants()
        modalities = self._detect_modalities()
        modality_str = ", ".join(modalities) if modalities else "behavioral data"
        metadata["DATASET_CONTENTS"] = f"{participant_count} participants; {modality_str}"
        
        # --- Independent/Dependent/Control Variables ---
        metadata["INDEPENDENT_VARIABLES"] = overview.get("IndependentVariables", "Not specified")
        metadata["DEPENDENT_VARIABLES"] = overview.get("DependentVariables", "Not specified")
        metadata["CONTROL_VARIABLES"] = overview.get("ControlVariables", "Not specified")
        metadata["QUALITY_ASSESSMENT"] = overview.get("QualityAssessment", "Dataset validated with PRISM Studio")
        
        # --- Participants / Recruitment ---
        recruitment = project_data.get("Recruitment", {})
        eligibility = project_data.get("Eligibility", {})
        
        # Subject description
        subject_parts = [f"Total participants: {participant_count}"]
        
        target_n = eligibility.get("TargetSampleSize")
        if target_n:
            subject_parts.append(f"Target sample size: {target_n}")
        
        power = eligibility.get("PowerAnalysis", "")
        if power:
            subject_parts.append(f"\n\n**Power Analysis**: {power}")
        
        metadata["SUBJECT_DESCRIPTION"] = "\n\n".join(subject_parts)
        
        # Recruitment info
        rec_parts = []
        method = recruitment.get("Method", "")
        if method:
            rec_parts.append(f"**Method**: {method}")
        
        location = recruitment.get("Location", "")
        if location:
            rec_parts.append(f"**Location**: {location}")
        
        period = recruitment.get("Period", {})
        period_start = period.get("Start", "")
        period_end = period.get("End", "")
        if period_start:
            period_str = f"{period_start}"
            if period_end:
                period_str += f" to {period_end}"
            rec_parts.append(f"**Period**: {period_str}")
        
        compensation = recruitment.get("Compensation", "")
        if compensation:
            rec_parts.append(f"**Compensation**: {compensation}")
        
        platform = recruitment.get("Platform", "")
        if platform:
            rec_parts.append(f"**Platform**: {platform}")
        
        metadata["RECRUITMENT_INFO"] = "\n\n".join(rec_parts) if rec_parts else "Not specified"
        
        # Eligibility criteria
        inclusion = eligibility.get("InclusionCriteria", [])
        if inclusion:
            metadata["INCLUSION_CRITERIA"] = "\n".join(f"- {c}" for c in inclusion)
        else:
            metadata["INCLUSION_CRITERIA"] = "Not specified"
        
        exclusion = eligibility.get("ExclusionCriteria", [])
        if exclusion:
            metadata["EXCLUSION_CRITERIA"] = "\n".join(f"- {c}" for c in exclusion)
        else:
            metadata["EXCLUSION_CRITERIA"] = "Not specified"
        
        # --- Data Collection ---
        data_collection = project_data.get("DataCollection", {})
        apparatus_parts = []
        
        platform_sw = data_collection.get("Platform", "")
        platform_ver = data_collection.get("PlatformVersion", "")
        if platform_sw:
            app_str = f"**Software**: {platform_sw}"
            if platform_ver:
                app_str += f" (version {platform_ver})"
            apparatus_parts.append(app_str)
        
        equipment = data_collection.get("Equipment", "")
        if equipment:
            apparatus_parts.append(f"**Equipment**: {equipment}")
        
        method_dc = data_collection.get("Method", "")
        if method_dc:
            apparatus_parts.append(f"**Method**: {method_dc}")
        
        supervision = data_collection.get("SupervisionLevel", "")
        if supervision:
            apparatus_parts.append(f"**Supervision**: {supervision}")
        
        metadata["APPARATUS_DESCRIPTION"] = "\n\n".join(apparatus_parts) if apparatus_parts else "Not specified"
        
        dc_location = data_collection.get("Location", "")
        metadata["LOCATION_INFO"] = dc_location if dc_location else location if location else "Not specified"
        
        # --- Procedure ---
        procedure = project_data.get("Procedure", {})
        setup = procedure.get("InitialSetup", "")
        metadata["INITIAL_SETUP"] = setup if setup else "Not specified"
        
        # --- Procedure ---
        procedure = project_data.get("Procedure", {})
        setup = procedure.get("InitialSetup", "")
        metadata["INITIAL_SETUP"] = setup if setup else "Not specified"
        
        additional_data = procedure.get("AdditionalData", "")
        metadata["ADDITIONAL_DATA"] = additional_data if additional_data else "Not specified"
        
        # Task organization from Sessions
        sessions = project_data.get("Sessions", [])
        if sessions:
            task_org_parts = [f"**Sessions**: {len(sessions)}"]
            for i, sess in enumerate(sessions, 1):
                sess_name = sess.get("name", f"Session {i}")
                tasks = sess.get("tasks", [])
                if tasks:
                    task_names = [t.get("name", "unnamed") for t in tasks]
                    task_org_parts.append(f"- {sess_name}: {', '.join(task_names)}")
            metadata["TASK_ORGANIZATION"] = "\n".join(task_org_parts)
        else:
            metadata["TASK_ORGANIZATION"] = "Not specified"
        
        # Task details from TaskDefinitions
        task_defs = project_data.get("TaskDefinitions", {})
        if task_defs:
            task_detail_parts = []
            for task_id, task_info in task_defs.items():
                name = task_info.get("name", task_id)
                desc = task_info.get("description", "")
                task_detail_parts.append(f"**{name}**: {desc if desc else 'No description'}")
            metadata["TASK_DETAILS"] = "\n\n".join(task_detail_parts)
        # --- Missing data / Known issues from project.json ---
        missing_data = project_data.get("MissingData", {})
        miss_desc = missing_data.get("Description", "")
        metadata["MISSING_DATA_DESCRIPTION"] = miss_desc if miss_desc else "No known missing data"
        
        # Format missing files table
        miss_files = missing_data.get("MissingFiles", "")
        if miss_files:
            table_rows = []
            for line in miss_files.strip().split('\n'):
                if '|' in line:
                    parts = line.split('|', 1)
                    table_rows.append(f"{parts[0].strip()} | {parts[1].strip()}")
            metadata["MISSING_FILES_TABLE"] = '\n'.join(table_rows) if table_rows else "| | |"
        else:
            metadata["MISSING_FILES_TABLE"] = "| | |"
        
        # Format known issues table
        known_issues = missing_data.get("KnownIssues", "")
        if known_issues:
            table_rows = []
            for line in known_issues.strip().split('\n'):
                if '|' in line:
                    parts = line.split('|', 1)
                    table_rows.append(f"{parts[0].strip()} | {parts[1].strip()}")
            metadata["KNOWN_ISSUES_TABLE"] = '\n'.join(table_rows) if table_rows else "| | |"
        else:
            metadata["KNOWN_ISSUES_TABLE"] = "| | |"
        
        notes = procedure.get("Notes", "")
        metadata["ADDITIONAL_NOTES"] = notes if notes else "This dataset was created using PRISM Studio."
        
        # --- Data access ---
        governance = project_data.get("governance", {})
        data_access = governance.get("data_access", "")
        metadata["DATA_AGREEMENT"] = data_access if data_access else "Contact dataset authors for data use agreement"
        
        # --- Contact info ---
        contacts = governance.get("contacts", [])
        if contacts and len(contacts) > 0:
            contact = contacts[0]
            metadata["CONTACT_NAME"] = contact.get("name", "Dataset Contact")
            metadata["CONTACT_EMAIL"] = contact.get("email", "contact@example.com")
            metadata["CONTACT_ORCID"] = contact.get("orcid", "")
        else:
            # Fallback to Authors from dataset_description
            authors = dataset_desc.get("Authors", [])
            if authors:
                if isinstance(authors[0], dict):
                    metadata["CONTACT_NAME"] = authors[0].get("name", "Dataset Contact")
                    metadata["CONTACT_EMAIL"] = authors[0].get("email", "")
                    metadata["CONTACT_ORCID"] = authors[0].get("orcid", "")
                else:
                    metadata["CONTACT_NAME"] = str(authors[0])
                    metadata["CONTACT_EMAIL"] = ""
                    metadata["CONTACT_ORCID"] = ""
            else:
                metadata["CONTACT_NAME"] = "Dataset Contact"
                metadata["CONTACT_EMAIL"] = "contact@example.com"
                metadata["CONTACT_ORCID"] = ""
        
        # --- Funding & Ethics ---
        funding = dataset_desc.get("Funding", [])
        if funding:
            if isinstance(funding[0], dict):
                funding_strs = []
                for f in funding:
                    agency = f.get("agency", "")
                    grant = f.get("grant_number", "")
                    if agency:
                        funding_strs.append(f"{agency} ({grant})" if grant else agency)
                metadata["FUNDING"] = "; ".join(funding_strs)
            else:
                metadata["FUNDING"] = "; ".join(str(f) for f in funding)
        else:
            gov_funding = governance.get("funding", [])
            metadata["FUNDING"] = "; ".join(str(f) for f in gov_funding) if gov_funding else "Not specified"
        
        ethics = dataset_desc.get("EthicsApprovals", [])
        if ethics:
            if isinstance(ethics[0], dict):
                ethics_strs = []
                for e in ethics:
                    committee = e.get("committee", "")
                    approval = e.get("approval_number", "")
                    ethics_strs.append(f"{committee} (approval: {approval})" if approval else committee)
                metadata["ETHICS_APPROVALS"] = "; ".join(ethics_strs)
            else:
                metadata["ETHICS_APPROVALS"] = "; ".join(str(e) for e in ethics)
        else:
            gov_ethics = governance.get("ethics_approvals", [])
            metadata["ETHICS_APPROVALS"] = "; ".join(str(e) for e in gov_ethics) if gov_ethics else "Not specified"
        
        # --- References from project.json ---
        refs_str = project_data.get("References", "")
        if refs_str:
            # Convert to list format if it's a multi-line string
            ref_lines = [line.strip() for line in refs_str.strip().split('\n') if line.strip()]
            if ref_lines:
                metadata["REFERENCES"] = "\n".join(f"- {r}" if not r.startswith('-') else r for r in ref_lines)
            else:
                metadata["REFERENCES"] = "Not specified"
        else:
            # Fallback to dataset_description
            refs = dataset_desc.get("ReferencesAndLinks", [])
            if refs:
                metadata["REFERENCES"] = "\n".join(f"- {r}" for r in refs)
            else:
                metadata["REFERENCES"] = "Not specified"
        
        # --- Version info ---
        metadata["PRISM_VERSION"] = "1.9.1"
        
        return metadata

    def _count_participants(self) -> int:
        """Count participants from participants.tsv or sub-* folders."""
        # Try participants.tsv first
        for tsv_path in [
            self.project_path / "participants.tsv",
            self.project_path / "rawdata" / "participants.tsv"
        ]:
            if tsv_path.exists():
                try:
                    with open(tsv_path, "r", encoding="utf-8") as f:
                        lines = [line for line in f if line.strip() and not line.startswith("participant_id")]
                        return len(lines)
                except Exception:
                    pass
        
        # Fallback: count sub-* directories
        for data_dir in [self.project_path, self.project_path / "rawdata"]:
            if data_dir.is_dir():
                sub_dirs = [d for d in data_dir.iterdir() if d.is_dir() and d.name.startswith("sub-")]
                if sub_dirs:
                    return len(sub_dirs)
        
        return 0

    def _detect_modalities(self) -> list:
        """Detect which modalities are present in the dataset."""
        modalities = set()
        
        # Check for modality folders
        for data_dir in [self.project_path, self.project_path / "rawdata"]:
            if not data_dir.is_dir():
                continue
            
            # Look in subject folders
            for sub_dir in data_dir.iterdir():
                if not sub_dir.is_dir() or not sub_dir.name.startswith("sub-"):
                    continue
                
                # Check session folders and root
                check_dirs = [sub_dir]
                check_dirs.extend([d for d in sub_dir.iterdir() if d.is_dir() and d.name.startswith("ses-")])
                
                for check_dir in check_dirs:
                    for item in check_dir.iterdir():
                        if item.is_dir():
                            mod_name = item.name
                            if mod_name in ["survey", "biometrics", "physio", "eyetracking", "eeg", 
                                          "func", "anat", "dwi", "meg", "beh"]:
                                modalities.add(mod_name)
        
        return sorted(list(modalities))

    def _create_basic_readme(self, metadata: Dict[str, Any]) -> str:
        """Create basic README if template not found."""
        name = metadata.get("DATASET_NAME", "Dataset")
        desc = metadata.get("DATASET_DESCRIPTION", "A PRISM/BIDS-compatible dataset.")
        contents = metadata.get("DATASET_CONTENTS", "")
        
        return f"""# {name}

> This dataset follows the BIDS and PRISM standards.

{desc}

## Dataset Contents

{contents}

## Participants

{metadata.get("SUBJECT_DESCRIPTION", "Not specified")}

### Recruitment

{metadata.get("RECRUITMENT_INFO", "Not specified")}

### Inclusion Criteria

{metadata.get("INCLUSION_CRITERIA", "Not specified")}

### Exclusion Criteria

{metadata.get("EXCLUSION_CRITERIA", "Not specified")}

## Data Collection

{metadata.get("APPARATUS_DESCRIPTION", "Not specified")}

**Location**: {metadata.get("LOCATION_INFO", "Not specified")}

## Contact

**Name**: {metadata.get("CONTACT_NAME", "Dataset Contact")}  
**Email**: {metadata.get("CONTACT_EMAIL", "")}  
**ORCID**: {metadata.get("CONTACT_ORCID", "")}

## Metadata

- **BIDS Version**: {metadata.get("BIDS_VERSION", "1.9.0")}
- **License**: {metadata.get("LICENSE", "CC-BY-4.0")}
- **Funding**: {metadata.get("FUNDING", "Not specified")}
- **Ethics Approvals**: {metadata.get("ETHICS_APPROVALS", "Not specified")}

---

*Generated with PRISM Studio*
"""

    def save(self, output_path: Optional[Path] = None) -> Path:
        """Generate and save README.md to file.
        
        Args:
            output_path: Optional custom output path. Defaults to project_path/README.md
            
        Returns:
            Path where README was saved
        """
        if output_path is None:
            output_path = self.project_path / "README.md"
        
        content = self.generate()
        
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(content)
        
        return output_path
