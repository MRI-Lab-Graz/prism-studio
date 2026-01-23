# Web Interface Anonymization

The PRISM web interface now includes built-in anonymization features for data sharing and double-blind studies.

## Features

### Anonymization Options

When processing recipes through the web interface, you can enable the following anonymization options:

1. **Anonymize Participant IDs** (✓ enabled by default)
   - Randomizes all participant IDs in the exported data
   - Generates mapping file for re-identification
   - Options:
     - **Deterministic**: Same input always generates same random IDs (reproducible)
     - **Random**: Truly random IDs for each run

2. **Mask Question Text**
   - Replaces copyrighted question text with `[MASKED]`
   - Useful for sharing data from commercial surveys
   - Preserves responses while hiding proprietary content

3. **ID Length**
   - Configure the length of anonymized IDs (default: 8 characters)
   - Longer IDs reduce collision probability
   - Format: `sub-XXXXXXXX`

## Usage

### Web Interface

1. Navigate to the **Recipes** tab
2. Select your dataset and recipe options
3. Check **Anonymization Options**:
   - ✓ **Anonymize participant IDs** (checked by default)
   - ☐ **Mask copyrighted question text**
   - **ID length**: 8 (adjustable)
   - ☐ **Use random IDs** (checked for non-deterministic)
4. Click **Run Processing**

### Output

Anonymized data is written to:
```
dataset/
  derivatives/
    prism-export-{modality}/
      participants_mapping.json  ← KEEP SECURE!
      sub-XXXXXXXX_task-name_survey.tsv
      ...
```

### Mapping File

The `participants_mapping.json` file contains:

```json
{
  "_description": "Participant ID anonymization mapping",
  "_warning": "KEEP THIS FILE SECURE! It allows re-identification.",
  "mapping": {
    "sub-001": "sub-FX6CFCNX",
    "sub-002": "sub-LNMOFWV4"
  },
  "reverse_mapping": {
    "sub-FX6CFCNX": "sub-001",
    "sub-LNMOFWV4": "sub-002"
  }
}
```

**⚠️ SECURITY WARNING**: This file allows re-identification. Store it securely and do NOT share it with your anonymized data.

## API Integration

The anonymization is integrated into the `/api/recipes-surveys` endpoint:

### Request Payload

```json
{
  "dataset_path": "/path/to/dataset",
  "modality": "survey",
  "format": "csv",
  "anonymize": true,
  "mask_questions": false,
  "id_length": 8,
  "random_ids": false
}
```

### Response

```json
{
  "ok": true,
  "message": "✅ Data processing complete: wrote 3 file(s)\n🔒 Anonymized with deterministic IDs (length: 8)\n⚠️ SECURITY: Keep mapping file secure: participants_mapping.json",
  "anonymized": true,
  "mapping_file": "participants_mapping.json",
  "written_files": 3
}
```

## CLI Alternative

You can also use the CLI for anonymization:

```bash
python prism_tools.py anonymize --dataset /path/to/dataset --output /path/to/output
```

Options:
- `--id-length 8`: Set ID length (default: 6)
- `--random`: Use random IDs instead of deterministic
- `--mask-questions`: Mask copyrighted question text
- `--force`: Overwrite existing mapping file

## Best Practices

1. **Double-Blind Studies**:
   - Use deterministic IDs for reproducibility
   - Store mapping file separately from data
   - Only share anonymized exports

2. **Data Sharing**:
   - Enable question masking for commercial surveys
   - Verify no identifiable information remains
   - Include data use agreement

3. **Security**:
   - Never commit mapping files to version control
   - Add `*_mapping.json` to `.gitignore`
   - Restrict mapping file access to authorized personnel

4. **Reproducibility**:
   - Use deterministic IDs for same results across runs
   - Document ID length and settings
   - Archive mapping file securely

## Technical Details

### Implementation

- **Frontend**: `app/templates/recipes.html` - UI controls
- **Backend**: `app/src/web/blueprints/tools.py` - API endpoint
- **Core Logic**: `src/anonymizer.py` - Anonymization functions

### ID Generation

- Deterministic: MD5 hash of `{participant_id}{seed}` → base36 encoding
- Random: Cryptographically secure random bytes → base36 encoding
- Collision detection with automatic retry

### Data Processing

1. Parse `participants.tsv` to extract participant IDs
2. Generate mapping (deterministic or random)
3. Save mapping to `participants_mapping.json`
4. Process all TSV files in output directory
5. Replace IDs using mapping
6. Optionally mask question columns
7. Write anonymized TSV files

## Troubleshooting

### "participants.tsv not found"
- Ensure your dataset has a valid `participants.tsv` file
- Check the file is in the root of your dataset

### "participants.tsv must have a 'participant_id' column"
- Verify column name is exactly `participant_id`
- Check for typos or extra spaces

### IDs not anonymized
- Verify the checkbox is enabled
- Check the terminal output for error messages
- Ensure TSV files have a `participant_id` column

### Mapping file missing
- Check `derivatives/prism-export-{modality}/` directory
- Verify write permissions on output directory
- Look for error messages in browser console

## Related Documentation

- [Anonymization Guide](ANONYMIZATION.md) - Full CLI documentation
- [Web Interface Guide](WEB_INTERFACE.md) - General web interface usage
- [Recipes Documentation](RECIPES.md) - Recipe processing details
- [PRISM Specifications](SPECIFICATIONS.md) - Dataset structure

## Example Workflow

### Research Data Sharing

1. **Collect Data**: Run your study with identifiable IDs (sub-001, sub-002, etc.)

2. **Process & Anonymize**:
   - Open dataset in PRISM web interface
   - Navigate to Recipes tab
   - Select modality (e.g., `survey`)
   - ✓ Check "Anonymize participant IDs"
   - ✓ Check "Mask copyrighted question text"
   - Set ID length to 8
   - Click "Run Processing"

3. **Review Output**:
   ```
   derivatives/prism-export-survey/
     participants_mapping.json  ← Store securely
     sub-K7X2M9FN_task-ads_survey.tsv  ← Share this
     sub-L4P8Q3WV_task-ads_survey.tsv
   ```

4. **Share Data**:
   - Upload TSV files to repository
   - Do NOT upload `participants_mapping.json`
   - Include data use agreement

5. **Archive Mapping**:
   - Store `participants_mapping.json` in secure location
   - Document storage location in lab records
   - Restrict access to PI and authorized personnel

### Publication Workflow

When preparing data for publication:

1. Anonymize using **deterministic IDs** for reproducibility
2. Share anonymized TSV files in supplementary materials
3. Archive mapping file with institutional data repository
4. Include anonymization details in methods section:

> "Participant identifiers were anonymized using PRISM's deterministic ID 
> generation (8-character alphanumeric codes). The mapping file is archived 
> with [Institution Name] and available upon reasonable request for 
> verification purposes."

## Future Enhancements

Planned features for future releases:

- [ ] Partial anonymization (keep some columns identifiable)
- [ ] Custom anonymization rules per column
- [ ] Batch anonymization of multiple datasets
- [ ] Integration with institutional data repositories
- [ ] Automated compliance checking (GDPR, HIPAA)
- [ ] Reversible anonymization with access controls
