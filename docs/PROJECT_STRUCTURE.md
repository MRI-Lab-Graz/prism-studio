# Psycho-Validator: Clean Project Structure

## Root Directory (Essential Files Only)
```
psycho-validator/
├── README.md                     # Main project documentation
├── requirements.txt              # Python dependencies  
├── setup.py                      # Package installation
├── psycho-validator.py           # Main entry point (streamlined)
├── .gitignore                    # Git ignore rules
└── .bidsignore                   # BIDS validator ignore rules
```

## Organized Subdirectories

### Core Source Code
```
src/
├── __init__.py                   # Package init
├── validator.py                  # Core validation logic
├── schema_manager.py             # Schema loading & versioning
├── stats.py                      # Dataset statistics
├── reporting.py                  # Output formatting
├── fair_checker.py               # FAIR compliance checking
└── fair_export.py                # FAIR metadata export
```

### JSON Schemas
```
schemas/
├── behavior.schema.json          # Behavioral data schema
├── dataset_description.schema.json # Dataset metadata schema
├── eeg.schema.json                # EEG data schema
├── eyetracking.schema.json        # Eye-tracking schema
├── image.schema.json              # Image stimuli schema
├── movie.schema.json              # Video stimuli schema
└── physiological.schema.json     # Physiological data schema
```

### Utility Scripts
```
scripts/
├── setup-simple.sh               # Simple setup (pip/venv)
├── setup.sh                      # Advanced setup (uv)
├── setup.bat                     # Windows setup
├── create_dummy_files.py         # Generate test datasets
├── create_multimodal_demo.py     # Multimodal demo
├── demo_validator.py             # Validator demonstration
├── demo_schema_versioning.py     # Schema versioning demo
└── psycho-validator-legacy.py    # Full-featured legacy version
```

### Tests & Test Data
```
tests/
├── test_validator.py             # Main validation tests
├── test_reorganization.py        # Structure verification
├── consistent_test_dataset/      # Clean test dataset
├── test_dataset/                 # Dataset with issues
└── dataset_description.json      # Sample dataset metadata
```

### Documentation
```
docs/
├── README.md                     # Documentation overview
├── ASSESSMENT_SUMMARY.md         # Project assessment results
├── REORGANIZATION.md             # Reorganization details
├── FAIR_IMPLEMENTATION.md        # FAIR principles implementation
├── FAIR_POLICY.md                # FAIR compliance policy
├── PROPOSED_MODALITIES.md        # Future modality proposals
├── SCHEMA_VERSIONING.md          # Schema versioning guidelines
└── examples/                     # Usage examples
```

## Key Improvements

### ✅ Clean Root Directory
- Only 6 essential files in root
- No scattered utility scripts
- Clear entry point (`psycho-validator.py`)

### ✅ Logical Organization
- Source code in `src/`
- Utilities in `scripts/`
- Tests and test data in `tests/`
- Documentation in `docs/`

### ✅ Professional Structure
- Follows Python packaging standards
- Easy to navigate and understand
- Clear separation of concerns
- Ready for PyPI distribution

## Usage

### Quick Start
```bash
# Setup (one time)
bash scripts/setup-simple.sh
source .venv/bin/activate

# Validate a dataset
python psycho-validator.py /path/to/dataset

# View help
python psycho-validator.py --help
```

### Development
```bash
# Run tests
python tests/test_reorganization.py

# Create test data
python scripts/create_dummy_files.py

# Use legacy full-featured version
python scripts/psycho-validator-legacy.py /path/to/dataset --fair-check
```

This structure makes the project much more maintainable and professional while keeping all functionality accessible.