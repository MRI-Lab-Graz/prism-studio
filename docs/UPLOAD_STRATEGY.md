# Upload Strategy: Metadata-Only Validation

## Overview

The Psycho-Validator web interface uses a **metadata-only upload strategy** to dramatically reduce upload size and validation time. This is based on the BIDS principle that data files come in pairs: one contains the actual data, the other (JSON sidecar) contains the metadata description.

**Key Insight:** We only need to validate the metadata descriptions, not the actual data files!

## What Gets Uploaded

### ✅ Uploaded Files (Metadata)
- **`.json`** - Sidecar metadata files (primary validation target)
- **`.tsv`** - Behavioral/events data, participant info
- **`.csv`** - Alternative tabular format
- **`.txt`** - Text data, logs, documentation
- **`.edf`** - EEG/eye-tracking (relatively small)
- **`.bdf`** - BioSemi EEG format

### ⏭️ Skipped Files (Large Data)
- **`.nii`, `.nii.gz`** - NIfTI neuroimaging data (can be GB per file)
- **`.mp4`, `.avi`, `.mov`** - Video stimuli
- **`.png`, `.jpg`, `.jpeg`, `.tiff`** - Large image stimuli
- **`.eeg`, `.dat`, `.fif`** - Large electrophysiology raw data
- **`.mat`** - MATLAB files (can be very large)

## How It Works

### BIDS File Pairing Example

```
sub-01/
  ses-01/
    func/
      sub-01_ses-01_task-nback_bold.nii.gz    ← SKIPPED (300 MB)
      sub-01_ses-01_task-nback_bold.json      ← UPLOADED (2 KB) ✓
      
    anat/
      sub-01_ses-01_T1w.nii.gz                ← SKIPPED (50 MB)
      sub-01_ses-01_T1w.json                  ← UPLOADED (1 KB) ✓
      
    eeg/
      sub-01_ses-01_task-rest_eeg.edf         ← UPLOADED (small)
      sub-01_ses-01_task-rest_eeg.json        ← UPLOADED (2 KB) ✓
```

### What Gets Validated

Even though large data files are skipped during upload:

1. **Filename validation** - The validator creates empty placeholder files, so it can still check if filenames follow BIDS conventions
2. **Sidecar validation** - JSON sidecars are fully validated against schemas
3. **Structure validation** - Directory structure and file pairing is checked
4. **Metadata completeness** - All required metadata fields are verified

### Upload Size Comparison

**Before (Upload Everything):**
```
Dataset: 10 subjects, 2 sessions, functional MRI + anatomical + EEG
- 40 .nii.gz files @ 200 MB each = 8 GB
- 40 .json files @ 2 KB each = 80 KB
- 10 .edf files @ 10 MB each = 100 MB
Total: ~8.1 GB upload
```

**After (Metadata Only):**
```
Dataset: Same 10 subjects, 2 sessions
- 40 .json files @ 2 KB each = 80 KB
- 10 .edf files @ 10 MB each = 100 MB
Total: ~100 MB upload (98.8% reduction!)
```

## Configuration

### Server Settings

In `web_interface.py`:

```python
# Max upload size (metadata only)
app.config['MAX_CONTENT_LENGTH'] = 100 * 1024 * 1024  # 100MB

# Extensions to upload
METADATA_EXTENSIONS = {
    '.json', '.tsv', '.csv', '.txt',
    '.edf', '.bdf'
}

# Extensions to skip
SKIP_EXTENSIONS = {
    '.nii', '.nii.gz',
    '.mp4', '.avi', '.mov',
    '.png', '.jpg', '.jpeg', '.tiff',
    '.eeg', '.dat', '.fif', '.mat'
}
```

### Adjusting Limits

If you have very large EEG/EDF files or want to include other formats:

1. **Add to METADATA_EXTENSIONS:**
   ```python
   METADATA_EXTENSIONS = {
       '.json', '.tsv', '.csv', '.txt',
       '.edf', '.bdf',
       '.yourformat'  # Add your extension
   }
   ```

2. **Increase upload limit if needed:**
   ```python
   app.config['MAX_CONTENT_LENGTH'] = 200 * 1024 * 1024  # 200MB
   ```

## Benefits

### 1. Faster Uploads ⚡
- 50-100x smaller upload size
- Seconds instead of minutes/hours
- Works on slower connections

### 2. Lower Server Costs 💰
- Less bandwidth usage
- Less storage needed
- Can use cheaper hosting

### 3. Better User Experience 😊
- Quick validation feedback
- No timeout errors
- Works with large datasets

### 4. Efficient Resource Usage 🌱
- Minimal disk I/O
- Lower memory footprint
- Can validate more datasets concurrently

## Edge Cases

### What if a data file has no sidecar?

The validator will detect the missing sidecar through:
1. Empty placeholder files created for skipped data files
2. Validation checks that look for matching `.json` files
3. Error reported: "Missing sidecar for sub-01_task-test_bold.nii.gz"

### What if metadata refers to data file properties?

Some metadata fields reference properties of the data file (e.g., dimensions, voxel sizes). These are **not validated** since we don't have the data file. The validator focuses on:
- ✅ Required metadata fields present
- ✅ Correct data types (string, number, array)
- ✅ Valid enumerated values
- ✅ Filename conventions
- ❌ Data file content/properties (not checked)

### Can I still upload everything?

Yes! For local folder validation:

```python
# In web_interface.py, remove the extension filtering:
def process_folder_upload(files, temp_dir):
    for file in files:
        # Save ALL files regardless of extension
        file.save(file_path)
```

Or use the **local folder path** option which doesn't upload anything - it validates the dataset directly from disk.

## Implementation Details

### Folder Upload (Browser)

```javascript
// Client-side filtering in templates/index.html
folderInput.addEventListener('change', function() {
    const metadataExtensions = ['.json', '.tsv', '.csv', '.txt'];
    const skipExtensions = ['.nii', '.gz', '.mp4', ...];
    
    // Count and report what will be uploaded
    for (let file of folderInput.files) {
        if (isMetadata) uploadCount++;
        if (isSkipped) skipCount++;
    }
    
    // Show user: "X metadata files, Y data files skipped"
});
```

### ZIP Upload

```python
def process_zip_upload(file, temp_dir, filename):
    with zipfile.ZipFile(file_path, 'r') as zip_ref:
        for zip_info in zip_ref.namelist():
            ext = get_extension(zip_info)
            
            if ext in METADATA_EXTENSIONS:
                # Extract metadata file
                zip_ref.extract(zip_info, temp_dir)
            elif ext in SKIP_EXTENSIONS:
                # Create empty placeholder
                create_placeholder(zip_info)
```

### Local Folder (No Upload)

```python
# No filtering needed - validates everything in place
@app.route('/validate_folder', methods=['POST'])
def validate_folder():
    folder_path = request.form.get('folder_path')
    # Validate directly from disk
    issues, stats = validate_dataset(folder_path)
```

## Troubleshooting

### "Request Entity Too Large" Error

**Cause:** Upload exceeds MAX_CONTENT_LENGTH
**Solution:** 
1. Check if large data files are being uploaded (they shouldn't be)
2. If you have many large EEG/EDF files, increase the limit
3. Use ZIP upload (more efficient) or local folder path

### Files Not Being Validated

**Cause:** File extension not in METADATA_EXTENSIONS
**Solution:**
1. Check file extensions in your dataset
2. Add missing extensions to METADATA_EXTENSIONS
3. Check server logs for "skipped X data files"

### Validation Says "Missing Files"

**Cause:** Data files were skipped but validator detected structure
**Solution:** This is expected! The validator correctly identifies that data files exist (through directory structure) but their sidecars are missing.

## Future Enhancements

1. **Progressive upload** - Upload metadata files first, then optionally upload data files if validation passes
2. **Smart detection** - Auto-detect if data files are needed based on validation errors
3. **Streaming validation** - Validate files as they're uploaded without storing everything
4. **Client-side pre-validation** - Check filename conventions before upload

## Summary

✅ **Metadata-only uploads = Fast, efficient validation**
✅ **98% reduction in upload size for typical datasets**
✅ **Same validation quality - we check what matters**
✅ **Better user experience and lower costs**

The strategy recognizes that BIDS validation is fundamentally about **metadata structure and completeness**, not data content. By focusing validation on metadata files, we achieve dramatic efficiency gains without sacrificing validation quality.
