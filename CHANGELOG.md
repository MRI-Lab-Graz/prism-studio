# Changelog

All notable changes to the PRISM project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.5.0] - 2025-12-20

### Added

#### Survey Data Processing (PRISM Studio)
- **Survey import wizard** with TSV/CSV/Excel support
- **Library-based conversion** using template JSON schemas
- **Automatic participant detection** from data columns
- **Value validation** against library definitions (min/max/levels)
- **Missing value handling** with configurable strategies
- **Detailed import logs** with row-by-row feedback

#### Derivatives System
- **Survey scoring recipes** in JSON format (`derivatives/surveys/*.json`)
- **Reverse coding** support for inverted items
- **Subscale computation** (sum, mean methods)
- **Multi-format export**: CSV, Excel (with Codebook sheet), SPSS (.save), R/Feather
- **Rich metadata in exports**: Variable labels, value labels, score details
- **Codebook generation**: JSON and TSV codebooks with full documentation
- **Participant variables merge**: Age, sex, education included in derivatives

#### PRISM Naming Conventions
- **Strict suffix validation** for survey (`_survey`) and biometrics (`_biometrics`)
- **Physio and eyetrack suffixes** added to BIDS regex
- **Task-based sidecar naming** (`task-<name>_survey.json`)

#### Structured Issue System
- **PRISM error codes** (PRISM001-PRISM9xx) with severity levels and categories
- Error categories: dataset structure, file naming, sidecar/metadata, schema validation, content validation, BIDS compatibility, plugin errors
- Comprehensive `src/issues.py` module for consistent error reporting
- Updated `docs/ERROR_CODES.md` with complete error code reference

#### Output Formats
- **JSON output** (`--json`, `--json-pretty`) for CI/CD integration
- **SARIF format** (`--format sarif`) for GitHub Code Scanning
- **JUnit XML** (`--format junit`) for test runners
- **Markdown** (`--format markdown`) for documentation
- **CSV export** (`--format csv`) for spreadsheet analysis
- Output file redirection (`-o`, `--output`)

#### Auto-Fix System
- **Automatic fixing** of common issues (`--fix`)
- **Dry-run mode** (`--dry-run`) to preview fixes
- **Fixable issues**: missing dataset_description.json, missing sidecars, .bidsignore updates
- List all fixable issues (`--list-fixes`)

#### Plugin System
- **Custom validators** via Python plugins in `<dataset>/validators/`
- **Plugin template generator** (`--init-plugin <name>`)
- **Plugin discovery** and loading (`--list-plugins`)
- **Plugin disable flag** (`--no-plugins`)
- Context-aware API with access to files, subjects, modalities

#### REST API
- **Blueprint-based API** at `/api/v1/`
- Endpoints: `/health`, `/schemas`, `/schemas/<version>`, `/validate`
- JSON request/response format
- Async validation with progress tracking

#### New Schemas
- **Physiological (physio)** schema: ECG, EDA, respiration, PPG, EMG support
- **Eyetracking** schema: gaze tracking, fixations, saccades

#### Survey Library
- **Bilingual survey templates** (German + English in single JSON)
- **i18n system** for compile-time language selection
- Surveys: PHQ-9, GAD-7, PSS-10, WHO-5, Rosenberg, MAIA, PSQI, BDI, DANCEQ, HFerst, GoldDSI
- Migration tools: `prism_tools.py survey i18n-migrate` and `i18n-build`

#### Project Configuration
- **`.prismrc.json`** project config file support
- Settings: default schema version, output format, strict mode, ignored patterns
- Per-dataset configuration

#### Testing
- **pytest unit tests** covering core functionality
- Test coverage for issues, validators, config, formatters
- Demo folder used for integration testing

#### Web Interface Enhancements
- **Derivatives page** with terminal output log
- **Progress tracking** with percentage and current file
- **Navbar links** to Derivatives and ReadTheDocs
- Server-Sent Events for real-time updates
- API blueprint integration

### Changed
- Renamed entry script to `prism-studio.py`
- CLI now uses structured error codes instead of free-form messages
- Validation results include severity levels (error, warning, info)
- Improved error messages with fix hints

### Fixed
- Fixed `.gitignore` to properly track test files
- Fixed modality patterns to include JSON sidecars for physio/eyetrack
- Fixed BIDS regex to accept physio, eyetrack, events suffixes

---

## [1.0.0] - 2025-10-09

### Added - Major Release 🎉

This is the first major release of PRISM with comprehensive features for validating psychological research datasets.

#### Schema Versioning System
- **Docker-like schema versioning** (`stable`, `v0.1`, etc.)
- `--schema-version` CLI flag to specify validation schema version
- `--list-versions` command to display available schema versions
- Schema version selector in web interface (dropdown menu)
- Version information included in all validation results
- Automatic version normalization (supports both `0.1` and `v0.1` formats)
- Default to `stable` version when not specified
- Comprehensive documentation for schema versioning

#### Web Interface Improvements
- Schema version dropdown in upload form
- Schema version selector for local folder validation
- Updated results page to display schema version used
- Improved logo display with correct aspect ratio
- Enhanced user experience with clear version selection

#### Core Features
- Multi-modal validation support (image, movie, audio, EEG, eye-tracking, behavior, physiological)
- BIDS-inspired filename validation
- JSON schema validation for metadata files
- Cross-subject consistency checking
- Comprehensive validation reports
- Support for session-based and direct subject organization
- Local folder validation (no upload required)
- DataLad-style upload (metadata only, placeholders for large files)

#### Documentation
- Added `SCHEMA_VERSIONING_GUIDE.md` - Complete user guide
- Added `SCHEMA_VERSIONING_IMPLEMENTATION.md` - Technical details
- Added `SCHEMA_VERSIONING_QUICKREF.md` - Quick reference
- Added `SCHEMA_VERSIONING_COMPLETE.md` - Implementation summary
- Added `SCHEMA_VERSIONING_CHECKLIST.md` - Development checklist
- Added `SCHEMA_VERSIONING_VISUAL.md` - Visual documentation
- Updated README.md with versioning information

#### Infrastructure
- Created `schemas/stable/` directory for stable schema version
- Created `schemas/v0.1/` directory for version 0.1
- Enhanced `schema_manager.py` with version-aware loading
- Updated `runner.py` to support schema version parameter
- Improved web interface validation workflow

### Changed
- Updated main validator to accept `schema_version` parameter
- Modified web interface to pass schema version through validation pipeline
- Enhanced templates with schema version UI elements
- Updated README with new features and examples

### Technical Details
- Python 3.10+ compatible
- Flask-based web interface
- JSON Schema validation
- Cross-platform support (Windows, macOS, Linux)
- Zero-dependency validation core

### Migration Guide
For existing users:
- No breaking changes - all existing code continues to work
- Default behavior uses `stable` schema version
- Explicitly specify version only if needed for specific use cases
- See `docs/SCHEMA_VERSIONING_GUIDE.md` for detailed migration instructions

---

## Release Notes

### v1.0.0 Highlights

🎉 **First Major Release** - PRISM is now production-ready!

**Key Features:**
- ✅ Schema versioning system (Docker-like)
- ✅ Web interface with schema selection
- ✅ Command-line tools with version support
- ✅ Comprehensive validation for psychological datasets
- ✅ Complete documentation suite

**What's Next:**
- Schema diff utilities
- Auto-migration tools
- Enhanced modality support
- CI/CD integration examples

### Acknowledgments
- Developed at **MRI-Lab Graz**, University of Graz
- Maintained by **Karl Koschutnig**
- Built for the research community ❤️

### Links
- [GitHub Repository](https://github.com/MRI-Lab-Graz/prism)
- [Documentation](https://github.com/MRI-Lab-Graz/prism/tree/main/docs)
- [Schema Versioning Guide](https://github.com/MRI-Lab-Graz/prism/blob/main/docs/SCHEMA_VERSIONING_GUIDE.md)

---

[1.0.0]: https://github.com/MRI-Lab-Graz/prism/releases/tag/v1.0.0

## [1.3.0] - 2025-11-28

### Changed
- **Project Rename**: Renamed project from `psycho-validator` to `prism`.
- **Repository Restructuring**: Moved helper scripts to `helpers/` directory.
- **Documentation**: Updated all documentation to reflect the new name.
