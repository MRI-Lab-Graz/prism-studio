# Data Anonymization for Sharing

PRISM includes powerful anonymization tools to prepare datasets for sharing while protecting participant privacy and respecting copyright restrictions on survey instruments.

## Overview

The anonymization feature provides two key capabilities:

1. **Participant ID Randomization**: Replace real participant IDs with random codes (e.g., `sub-001` → `sub-R7X2K9`)
2. **Question Text Masking**: Replace copyrighted survey questions with generic labels (e.g., "ADS Question 1")

This ensures true double-blind data sharing where neither participants nor specific copyrighted content can be identified.

## Quick Start

Anonymize a dataset with a single command:

```bash
python prism_tools.py anonymize \
  --dataset /path/to/original/dataset \
  --output /path/to/anonymized/dataset
```

This will:
- Create randomized participant IDs
- Copy and anonymize all data files
- Generate a secure mapping file for re-identification
- Preserve the dataset structure

## Features

### 1. Participant ID Randomization

Replace participant identifiers throughout the dataset:

```
Original Dataset:
├── sub-001/
│   └── ses-1/
│       └── survey/
│           └── sub-001_ses-1_task-ads_survey.tsv
├── sub-002/
└── participants.tsv

Anonymized Dataset:
├── sub-R7X2K9/
│   └── ses-1/
│       └── survey/
│           └── sub-R7X2K9_ses-1_task-ads_survey.tsv
├── sub-A4B8M3/
└── participants.tsv
```

**Features:**
- Randomized alphanumeric codes
- Deterministic by default (same input always produces same output)
- Truly random option available (`--random`)
- Configurable ID length (`--id-length`)
- Works with all PRISM entities (subjects, sessions)

### 2. Secure Mapping File

A secure JSON file maps original IDs to anonymized codes:

```json
{
  "_description": "Participant ID anonymization mapping",
  "_warning": "KEEP THIS FILE SECURE! It allows re-identification.",
  "mapping": {
    "sub-001": "sub-R7X2K9",
    "sub-002": "sub-A4B8M3",
    "sub-003": "sub-Q9N5P1"
  },
  "reverse_mapping": {
    "sub-R7X2K9": "sub-001",
    "sub-A4B8M3": "sub-002",
    "sub-Q9N5P1": "sub-003"
  }
}
```

**⚠️ IMPORTANT**: Keep this file secure and separate from the anonymized data!

### 3. Question Text Masking (Coming Soon)

For copyrighted surveys, replace full question text with generic labels:

**Before (copyrighted)**:
```json
{
  "ADS01": {
    "Description": "I feel confident about my ability to do things",
    "Levels": {"1": "Not at all", "4": "Very much"}
  }
}
```

**After (anonymized)**:
```json
{
  "ADS01": {
    "Description": "ADS Question 1",
    "Levels": {"1": "1", "4": "4"}
  }
}
```

This allows data sharing while respecting copyright restrictions.

## Command Reference

### Basic Usage

```bash
python prism_tools.py anonymize --dataset <input> [options]
```

### Options

| Option | Description | Default |
|--------|-------------|---------|
| `--dataset` | Path to original dataset (required) | - |
| `--output` | Path for anonymized output | `<dataset>_anonymized` |
| `--mapping` | Path to save/load mapping file | `<output>/code/anonymization_map.json` |
| `--id-length` | Length of random ID codes | `6` |
| `--random` | Use truly random IDs | Deterministic |
| `--force` | Force new mapping creation | Use existing |
| `--mask-questions` | Mask copyrighted question text | `false` |

### Examples

**Basic anonymization:**
```bash
python prism_tools.py anonymize \
  --dataset /data/my_study \
  --output /data/my_study_share
```

**Custom ID length:**
```bash
python prism_tools.py anonymize \
  --dataset /data/my_study \
  --id-length 8
```

**Truly random IDs:**
```bash
python prism_tools.py anonymize \
  --dataset /data/my_study \
  --random
```

**With question masking:**
```bash
python prism_tools.py anonymize \
  --dataset /data/my_study \
  --mask-questions
```

**Reuse existing mapping:**
```bash
# First time - creates mapping
python prism_tools.py anonymize --dataset /data/study1 --output /share/study1

# Additional datasets with same participants - reuse mapping
python prism_tools.py anonymize \
  --dataset /data/study2 \
  --output /share/study2 \
  --mapping /share/study1/code/anonymization_map.json
```

## Best Practices

### Before Sharing

1. **Review Output**: Always review the anonymized dataset before sharing
2. **Check Mappings**: Verify that IDs are properly randomized
3. **Test Loading**: Ensure the anonymized dataset loads correctly
4. **Remove Mapping**: Never include the mapping file with shared data

### Security Checklist

- [ ] Mapping file stored securely and separately
- [ ] No direct identifiers in text fields (names, dates of birth)
- [ ] Dates shifted/removed if needed
- [ ] Free-text responses reviewed for identifying information
- [ ] Copyrighted content masked appropriately
- [ ] Small cell sizes aggregated (n < 5)

### Mapping File Management

**DO:**
- Store in secure, encrypted location
- Back up with strict access controls
- Document who has access
- Use version control with restricted access

**DON'T:**
- Include in shared datasets
- Store in public repositories
- Email unencrypted
- Share without institutional approval

## Integration with Data Sharing

### OpenNeuro / DataLad

```bash
# Anonymize dataset
python prism_tools.py anonymize \
  --dataset /data/my_study \
  --output /data/my_study_openneuro

# Upload to OpenNeuro
datalad create -c text2git /data/my_study_openneuro
cd /data/my_study_openneuro
datalad save -m "Initial commit"
datalad siblings add --name openneuro --url https://openneuro.org/...
datalad push --to openneuro
```

### OSF / Zenodo

```bash
# Anonymize and package
python prism_tools.py anonymize \
  --dataset /data/my_study \
  --output /data/my_study_share

# Create archive
cd /data
tar -czf my_study_share.tar.gz my_study_share/

# Upload to OSF or Zenodo
```

## Technical Details

### Deterministic vs Random IDs

**Deterministic (default)**:
- Same input always produces same randomized ID
- Useful for consistent anonymization across multiple runs
- Uses hash of original ID as seed

**Random**:
- Each run produces different IDs
- Use when you need truly unpredictable codes
- Cannot reproduce the same anonymization

### ID Generation Algorithm

```python
# Deterministic
hash = MD5(original_id)
seed = int(hash, 16)
random.seed(seed)
chars = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789'
random_id = prefix + '-' + ''.join(random.choice(chars) for _ in range(length))
```

### File Processing

1. **participants.tsv**: IDs replaced in first column
2. **Data TSVs**: IDs replaced in `participant_id` column
3. **Filenames**: IDs replaced in paths (e.g., `sub-001` → `sub-R7X2K9`)
4. **JSON sidecars**: Copied unchanged (or masked if `--mask-questions`)

## Troubleshooting

**Problem**: "No participants found in dataset"
- Check that `participants.tsv` exists or there are `sub-*` folders

**Problem**: "Could not generate unique ID"
- Increase `--id-length` (default 6 may collide with many participants)

**Problem**: Mapping file already exists
- Use `--force` to create new mapping
- Or specify different `--mapping` path

## Privacy Regulations

This tool helps comply with:
- **GDPR**: Pseudonymization requirement (Article 32)
- **HIPAA**: De-identification standard (§164.514)
- **Ethics**: Double-blind study requirements

**Note**: Additional steps may be needed for full compliance (date shifting, location generalization, etc.)

## Related Documentation

- [Recipe System](RECIPES.md) - Score calculation on anonymized data
- [Data Sharing](../docs/FAIR_POLICY.md) - FAIR principles
- [Copyright](../docs/SPECIFICATIONS.md) - Survey licensing

## Future Enhancements

- [ ] Automatic date shifting
- [ ] Free-text scrubbing
- [ ] Integration with recipe exports
- [ ] Web interface for anonymization
- [ ] Batch processing multiple datasets
- [ ] Reversible anonymization with key management

## Support

For questions or issues:
- GitHub Issues: https://github.com/MRI-Lab-Graz/prism-studio/issues
- Documentation: https://prism-studio.readthedocs.io
