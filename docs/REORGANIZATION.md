# Psycho-Validator Project Structure

This document outlines the reorganized structure of the psycho-validator project.

## Directory Structure

```
psycho-validator/
├── README.md                     # Main project documentation
├── requirements.txt              # Python dependencies
├── setup.py                      # Package installation script
├── psycho-validator.py           # Full-featured main script (legacy)
├── psycho-validator-streamlined.py # Streamlined modular version
│
├── src/                          # Core source code modules
│   ├── __init__.py
│   ├── validator.py              # Core validation logic
│   ├── schema_manager.py         # Schema loading and versioning
│   ├── stats.py                  # Dataset statistics and consistency
│   ├── reporting.py              # Output formatting and reporting
│   ├── fair_checker.py           # FAIR compliance checking
│   └── fair_export.py            # FAIR metadata export
│
├── schemas/                      # JSON schemas for validation
│   ├── behavior.schema.json
│   ├── dataset_description.schema.json
│   ├── eeg.schema.json
│   ├── eyetracking.schema.json
│   ├── image.schema.json
│   ├── movie.schema.json
│   └── physiological.schema.json
│
├── scripts/                      # Utility and demo scripts
│   ├── create_dummy_files.py     # Generate test datasets
│   ├── create_multimodal_demo.py # Multimodal demonstrations
│   ├── demo_validator.py         # Validation demonstrations
│   └── demo_schema_versioning.py # Schema versioning demo
│
├── tests/                        # Test suites
│   └── test_validator.py         # Main test script
│
└── docs/                         # Project documentation
    ├── README.md                 # Documentation overview
    ├── FAIR_IMPLEMENTATION.md    # FAIR principles implementation
    ├── FAIR_POLICY.md            # FAIR compliance policy
    ├── PROPOSED_MODALITIES.md    # Future modality proposals
    ├── SCHEMA_VERSIONING.md      # Schema versioning guidelines
    └── examples/                 # Usage examples
```

## Key Improvements

### 1. **Modular Architecture**
- Separated core validation logic into focused modules
- Schema management isolated from validation logic
- FAIR compliance checking as separate module
- Clear separation of concerns

### 2. **Better Organization**
- `src/` contains core library code
- `scripts/` contains utilities and demonstrations
- `tests/` contains all test files
- `docs/` centralizes documentation

### 3. **Dual Entry Points**
- `psycho-validator.py` - Full-featured legacy script
- `psycho-validator-streamlined.py` - Clean, modular version

### 4. **Improved Maintainability**
- Smaller, focused files (~200-300 lines each)
- Clear module dependencies
- Easier to test individual components
- Easier to extend with new features

## Usage

### For Users
```bash
# Use the streamlined version for basic validation
python psycho-validator-streamlined.py /path/to/dataset

# Use the full version for advanced features
python psycho-validator.py /path/to/dataset --fair-check
```

### For Developers
```bash
# Install in development mode
pip install -e .

# Run tests
python -m pytest tests/

# Generate demo datasets
python scripts/create_dummy_files.py
```

## Migration Benefits

1. **Easier Testing**: Individual modules can be tested separately
2. **Better Documentation**: Each module has focused responsibility
3. **Simplified Debugging**: Smaller files easier to understand
4. **Enhanced Extensibility**: New modalities/features easier to add
5. **Professional Structure**: Follows Python packaging best practices

## Future Enhancements

With this structure, the following becomes easier:
- Adding new modality schemas
- Implementing web interface
- Creating GUI application
- Publishing to PyPI
- Setting up CI/CD pipelines
- Community contributions