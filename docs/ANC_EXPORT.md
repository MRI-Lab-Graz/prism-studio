# ANC Export Guide

Export PRISM datasets to ANC (Austrian NeuroCloud) compatible format.

## Quick Start

### Web Interface (Recommended)

1. Open PRISM Studio:
   ```bash
   ./prism-studio.py
   ```

2. Go to **Projects** page

3. Open your project

4. Scroll to **Data Export / Share** section

5. Enable **ANC Export** checkbox

6. (Optional) Configure options:
   - **Convert to Git LFS**: Only if ANC requires it
   - **Include CI/CD Examples**: Add validation workflows
   - **Edit Metadata**: Click to customize README/CITATION details

7. Click **Export for ANC** button

8. Find exported dataset in folder ending with `_anc_export`

### Command Line

```bash
# Basic export (keeps DataLad compatible)
python -m src.converters.anc_export /path/to/my_dataset

# Export with Git LFS conversion (for ANC submission)
python -m src.converters.anc_export /path/to/my_dataset --git-lfs

# Custom output location
python -m src.converters.anc_export /path/to/my_dataset -o /path/to/anc_ready_dataset

# With additional metadata
python -m src.converters.anc_export /path/to/my_dataset --metadata metadata.json

# Include CI/CD example files
python -m src.converters.anc_export /path/to/my_dataset --include-ci-examples
```

### Metadata JSON Example

Create a `metadata.json` file with dataset information:

```json
{
  "DATASET_NAME": "My Cognitive Study",
  "DATASET_DESCRIPTION": "fMRI study investigating working memory in healthy adults",
  "DATASET_CONTENTS": "30 participants, fMRI (T1w, BOLD), behavioral data",
  
  "INDEPENDENT_VARIABLES": "- Working memory load (low vs. high)\n- Task difficulty",
  "DEPENDENT_VARIABLES": "- Reaction time\n- BOLD signal\n- Accuracy",
  "CONTROL_VARIABLES": "- Age (20-35 years)\n- Education level\n- Handedness",
  
  "SUBJECT_DESCRIPTION": "30 healthy adults (15 female, 15 male) aged 20-35",
  "RECRUITMENT_INFO": "Recruited via university mailing lists",
  "INCLUSION_CRITERIA": "Right-handed, normal or corrected vision, no neurological conditions",
  "EXCLUSION_CRITERIA": "MRI contraindications, psychiatric disorders, left-handedness",
  
  "APPARATUS_DESCRIPTION": "3T Siemens Prisma scanner, 64-channel head coil",
  "TASK_ORGANIZATION": "Two runs per session, counterbalanced order",
  "TASK_DETAILS": "N-back task with 2-back and 3-back conditions",
  
  "CONTACT_NAME": "Dr. Jane Doe",
  "CONTACT_EMAIL": "jane.doe@university.edu",
  "CONTACT_ORCID": "https://orcid.org/0000-0001-2345-6789",
  
  "AUTHOR_GIVEN_NAME": "Jane",
  "AUTHOR_FAMILY_NAME": "Doe",
  "AUTHOR_AFFILIATION": "University of Example, Department of Psychology",
  
  "LICENSE": "CC-BY-4.0",
  "FUNDING": "Example Foundation Grant 12345",
  "ETHICS_APPROVALS": "University Ethics Committee Approval #2024-001"
}
```

## What Gets Generated

The ANC export creates:

### Required Files
- ✅ `README.md` - ANC-structured dataset documentation
- ✅ `CITATION.cff` - Citation metadata for the dataset
- ✅ `.bids-validator-config.json` - BIDS validator configuration
- ✅ `participants.tsv` - Participant demographics (copied from source)
- ✅ `dataset_description.json` - BIDS dataset description (copied from source)

### Optional Files
- 📄 `GIT_LFS_SETUP.md` - Instructions for Git LFS setup (if `--git-lfs` used)
- 📄 `DATALAD_NOTE.md` - DataLad usage notes (default)
- 📄 `ANC_EXPORT_REPORT.json` - Validation report
- 📄 `.gitlab-ci.yml.example` - CI/CD example for GitLab (if `--include-ci-examples`)
- 📄 `.github/workflows/validate.yml.example` - CI/CD example for GitHub (if `--include-ci-examples`)
- 📄 `CI_SETUP.md` - Instructions for CI/CD setup (if `--include-ci-examples`)

### Dataset Structure
```
my_dataset_anc_export/
├── README.md                          # ANC-formatted documentation
├── CITATION.cff                       # Citation metadata
├── .bids-validator-config.json        # Validator config
├── .gitattributes                     # Git LFS config (if --git-lfs)
├── dataset_description.json           # BIDS description
├── participants.tsv                   # Participant data
├── participants.json                  # Participant metadata
├── sub-01/                            # Subject folders
│   └── ses-01/
│       ├── anat/
│       ├── func/
│       └── ...
└── code/                              # Analysis code
```

## DataLad vs Git LFS

### Default Export (DataLad-friendly)
```bash
python -m src.converters.anc_export /path/to/my_dataset
```
- Keeps dataset DataLad compatible
- No `.gitattributes` for Git LFS
- Adds `DATALAD_NOTE.md` with instructions

### Git LFS Export (For ANC)
```bash
python -m src.converters.anc_export /path/to/my_dataset --git-lfs
```
- Creates `.gitattributes` for Git LFS
- Adds `GIT_LFS_SETUP.md` with instructions
- Required if ANC mandates Git LFS

**Ask ANC first!** They may accept DataLad datasets.

## Workflow

### 1. Prepare Your PRISM Dataset
Ensure your dataset is valid:
```bash
python prism.py /path/to/my_dataset
```

### 2. Create Metadata File
Create `metadata.json` with your dataset information (see example above).

### 3. Run Export
```bash
python -m src.converters.anc_export /path/to/my_dataset \
  --metadata metadata.json \
  --git-lfs  # Only if ANC requires Git LFS
```

### 4. Review Generated Files
Check the exported dataset:
```bash
cd my_dataset_anc_export
cat README.md           # Review documentation
cat CITATION.cff        # Review citation
cat ANC_EXPORT_REPORT.json  # Check validation
```

### 5. Edit as Needed
Manually edit any generated files to add missing information:
- `README.md` - Add detailed methods
- `CITATION.cff` - Update author affiliations
- `.bids-validator-config.json` - Adjust validation rules

### 6. Validate
Run BIDS validator:
```bash
bids-validator . --config .bids-validator-config.json
```

### 7. Submit to ANC
Follow ANC submission guidelines with your prepared dataset.

## Integration with PRISM Studio (Web UI)

The ANC export is integrated into the PRISM Studio web interface:

1. **Projects** → **Data Export / Share** section
2. Enable **ANC Export** checkbox to show options
3. Configure export settings:
   - Git LFS conversion (if required)
   - CI/CD example files
   - Dataset metadata (optional)
4. Click **Export for ANC** to create submission-ready dataset
5. Review generated files in `<project>_anc_export/` folder

### Features

- ✅ **Form-based metadata editing** - No JSON required
- ✅ **Visual progress tracking** - See export status
- ✅ **One-click export** - Complete ANC package in seconds
- ✅ **Integrated validation** - Checks requirements before export

See [Web Interface Documentation](WEB_INTERFACE.md) for more details.

## Programmatic Usage

```python
from src.converters.anc_export import ANCExporter

# Create exporter
exporter = ANCExporter(
    dataset_path="/path/to/my_dataset",
    output_path="/path/to/anc_export"
)

# Define metadata
metadata = {
    "DATASET_NAME": "My Study",
    "CONTACT_EMAIL": "me@university.edu",
    # ... more fields
}

# Export
output_path = exporter.export(
    metadata=metadata,
    convert_to_git_lfs=False,  # Keep DataLad compatible
    copy_data=True
)

print(f"Exported to: {output_path}")
```

## Troubleshooting

### Missing Required Files
If export reports missing files, check your source dataset:
- `dataset_description.json` → Required by BIDS
- `participants.tsv` → Required by BIDS

### README Placeholders Not Replaced
Create a complete metadata JSON file with all fields. See example above.

### Git LFS Conversion Issues
- Ensure source files are not symlinks (DataLad issue)
- Use `datalad get` to retrieve actual files first
- Then run export with `--git-lfs`

### Validation Failures
Check `ANC_EXPORT_REPORT.json` for details on missing files or validation issues.

## Related Documentation

- [PRISM Specifications](../docs/SPECIFICATIONS.md)
- [BIDS Standard](https://bids-specification.readthedocs.io/)
- [ANC Handbook](https://handbook.anc.plus.ac.at/)
- [DataLad Documentation](https://docs.datalad.org/)
- [Git LFS Documentation](https://git-lfs.github.com/)

## Support

For questions about ANC export:
- PRISM Issues: https://github.com/MRI-Lab-Graz/prism-studio/issues
- ANC Support: Contact ANC directly for submission requirements
