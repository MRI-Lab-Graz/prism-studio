# Psycho-Validator: BIDS-inspired Validation Tool

## Overview

This tool validates datasets containing psychological/psychophysical stimuli and experimental data following a BIDS-inspired structure. It's designed specifically for experiments involving multiple stimulus modalities like images, videos, audio, etc.

## Features

- **Multi-modal validation**: Supports images, movies, audio, EEG, eye-tracking, and behavioral data
- **BIDS-inspired naming**: Validates filenames follow the pattern `sub-<label>_[ses-<label>_]task-<label>_[run-<index>_]<suffix>`
- **JSON schema validation**: Validates sidecar metadata files against modality-specific schemas
- **Flexible structure**: Supports both session-based and direct subject organization
- **Cross-subject consistency checking**: Warns when subjects have inconsistent modalities or tasks (critical for scientific datasets)
- **Comprehensive reporting**: 
  - Dataset summary with subject/session counts
  - Modality breakdown with file counts
  - Task detection and listing
  - File statistics (data files vs sidecars)
  - Cross-subject consistency warnings
  - Clear error and warning categorization
  - Exit codes for automation

## Directory Structure

```
dataset/
├── dataset_description.json     # Required dataset metadata
├── participants.tsv            # Optional participant information
├── sub-<label>/               # Subject directories
│   ├── ses-<label>/          # Optional session directories
│   │   └── <modality>/       # Modality-specific folders
│   └── <modality>/           # Or direct modality folders
```

## Supported Modalities

| Modality | File Extensions | Required Fields |
|----------|----------------|-----------------|
| `image` | .png, .jpg, .jpeg, .tiff | StimulusType, FileFormat, Resolution, TaskName |
| `movie` | .mp4, .avi, .mov | StimulusType, FileFormat, Resolution, Duration, TaskName |
| `audio` | .wav, .mp3, .flac | StimulusType, FileFormat, SampleRate, Duration, TaskName |
| `eyetracking` | .tsv, .edf | (Schema not implemented yet) |
| `eeg` | .edf, .bdf, .eeg | (Schema not implemented yet) |
| `behavior` | .tsv | (Schema not implemented yet) |

## Schema Structure

Each stimulus file must have a corresponding `.json` sidecar file with the same basename. These JSON files contain metadata about the stimulus and are validated against JSON schemas in the `schemas/` directory.

### Example Image Metadata (`.json` sidecar):
```json
{
  "StimulusType": "Image",
  "FileFormat": "png",
  "Resolution": [800, 600],
  "ColorSpace": "RGB",
  "TaskName": "facerecognition",
  "StimulusID": "face_001",
  "PresentedWith": "PsychoPy 2023.1"
}
```

## Usage

### Basic validation:
```bash
python psycho-validator.py /path/to/dataset
```

### Verbose output (shows scanning details):
```bash
python psycho-validator.py /path/to/dataset -v
```

### Example Output:

For a valid dataset:
```
🔍 Validating dataset: valid_test_dataset/

============================================================
🗂️  DATASET SUMMARY
============================================================
📁 Dataset: valid_test_dataset
👥 Subjects: 2
📋 Sessions: No session structure detected

🎯 MODALITIES (2 found):
  ✅ audio: 2 files
  ✅ image: 2 files

📝 TASKS (2 found):
  • listening
  • recognition

📄 FILES:
  • Data files: 2
  • Sidecar files: 2
  • Total files: 4

============================================================
✅ VALIDATION RESULTS
============================================================
🎉 No issues found! Dataset is valid.
```

For a dataset with issues:
```
============================================================
🔍 VALIDATION RESULTS
============================================================

🔴 ERRORS (1):
   1. Missing sidecar for test_dataset/sub-003/image/invalid-file.jpg

� WARNINGS (3):
   1. Subject sub-003 session ses-001 missing audio data
   2. Subject sub-003 session ses-001 missing task soundrecognition
   3. Mixed session structure: 2 subjects have sessions, 1 don't

�📊 SUMMARY: 1 errors, 3 warnings
❌ Dataset validation failed due to errors.
```

## Consistency Checking

The validator performs cross-subject consistency checks to ensure scientific rigor:

- **Modality consistency**: All subjects should have the same modalities (e.g., if one subject has both image and audio data, all should)
- **Task consistency**: All subjects should perform the same tasks within each session
- **Session structure**: Warns if mixing subjects with and without session directories
- **Per-session consistency**: For multi-session studies, ensures each subject has consistent data across sessions

These checks generate **warnings** (not errors) since missing data might be due to technical issues, dropouts, or valid experimental design decisions.

### Exit codes:
- `0`: Dataset is valid
- `1`: Validation errors found

## Test Dataset

The included `test_dataset/` demonstrates:
- ✅ Valid files with proper naming and metadata
- ❌ Invalid naming conventions
- ❌ Missing sidecar files
- ✅ Mixed session/no-session structures

## Files in this Repository

- `psycho-validator.py` - Main validation script
- `schemas/` - JSON schemas for each modality
- `test_dataset/` - Example dataset for testing
- `test_validator.py` - Comprehensive test script
- `create_dummy_files.py` - Script to generate realistic test files
- `docs/` - Project documentation and examples

## Future Enhancements

1. **Additional modalities**: Add schemas for EEG, eye-tracking, and behavioral data
2. **Cross-file validation**: Validate stimulus-response timing relationships
3. **BIDS compatibility**: Ensure full compatibility with official BIDS standard
4. **Web interface**: Create a web-based validation tool
5. **Batch processing**: Support for validating multiple datasets

## Installation

### Quick Start

1. **Clone the repository**:
   ```bash
   git clone https://github.com/your-repo/psycho-validator.git
   cd psycho-validator
   ```

2. **Set up the environment**:
   
   **Linux/macOS**:
   ```bash
   bash scripts/setup.sh
   ```
   
   **Windows**:
   ```cmd
   scripts\setup-windows.bat
   ```

3. **Test the installation**:
   ```bash
   python psycho-validator.py --help
   ```

### Manual Installation

1. **Create virtual environment**:
   ```bash
   python -m venv .venv
   source .venv/bin/activate  # Linux/macOS
   # or
   .venv\Scripts\activate     # Windows
   ```

2. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

### Cross-Platform Support

The psycho-validator is designed to work on Windows, macOS, and Linux with automatic handling of:
- Path separators and file encodings
- Line ending differences (CRLF vs LF)
- Case-sensitive vs case-insensitive filesystems
- Platform-specific filename restrictions

For Windows-specific setup instructions, see [`docs/WINDOWS_SETUP.md`](docs/WINDOWS_SETUP.md).

## Usage

### Web Interface (Recommended for most users)

For an easy-to-use graphical interface:

**Windows:**
```cmd
launch_web.bat
```

**Linux/macOS:**
```bash
python launch_web.py
```

The web interface provides:
- 🎯 User-friendly drag & drop interface
- 📊 Visual validation results with charts
- 🔒 Local processing (no data uploaded)
- 📁 Support for ZIP uploads and local folders

See [`docs/WEB_INTERFACE.md`](docs/WEB_INTERFACE.md) for detailed usage instructions.

### Command Line Interface

For automation and advanced usage:

```bash
python psycho-validator.py /path/to/your/dataset
```

#### Command Line Options
```bash
python psycho-validator.py --help
```

## Dependencies

- Python 3.6+
- `jsonschema` - For JSON schema validation

Optional (for dummy file generation):

- `Pillow` - For creating test images
- `numpy` - For generating test data

## Documentation

See the `docs/` directory for FAIR policy/implementation, proposed modalities, schema versioning, and examples.
