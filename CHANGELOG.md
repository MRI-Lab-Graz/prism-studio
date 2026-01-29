# Changelog

All notable changes to the PRISM project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- **Template Editor — Language Overview Bar**: Shows detected languages, primary language badge, and warning indicator when `Technical.Language` mismatches content. "Add Language" and "Remove Language" buttons batch-update all question Descriptions and Levels consistently.
- **Template Editor — Preview Tab**: New "Preview" tab renders questions as a mock survey form with language switcher. Missing translations highlighted with warning styling. Shows Reversed/Required badges and response options (radio buttons or text input).
- **Language Consistency Validation**: Backend `_validate_language_consistency()` detects fake translations (identical content across languages), inconsistent language keys across items, `Technical.Language` vs content key mismatches, and complementary/disjoint language sets. All warnings shown during template validation without blocking saves.

### Fixed
- **Template Editor — Global Template Access**: Fixed `initializeLibraryPath()` incorrectly setting the library path to project directory, which caused `refreshTemplateList()` to use the non-merged API and hide global templates. Now uses merged API when a project is active, showing both `[Global]` and `[Project]` templates.

## [1.9.1] - 2026-01-21

### Fixed
- **Windows Stability**: Additional Windows-specific stability improvements and bug fixes.

## [1.9.0] - 2026-01-21

### Added
- **Cross-Platform**: Native folder picker for Windows and Linux using tkinter with graceful fallbacks.
- **Windows Support**: Platform-specific browser launching with Windows fallback (cmd /c start).
- **Logging**: Comprehensive logging system for compiled Windows builds (prism_studio.log in user home directory).
- **Windows UI**: Startup notification dialog showing application URL when browser doesn't auto-launch.
- **Code Signing**: Integrated free SignPath.io code signing for Windows executables in GitHub Actions.
- **Path Handling**: Added Windows-specific temp path recognition in error messages.
- **Error Feedback**: Enhanced error alerts for failed folder picker operations in all templates.
- **Documentation**: Added comprehensive cross-platform development guides (CROSS_PLATFORM.md, DEVELOPING_FOR_WINDOWS_ON_MACOS.md, CODE_SIGNING_SETUP.md).
- **Setup Scripts**: Added tkinter availability checks with installation instructions in setup.ps1 and setup.sh.

### Changed
- **Folder Picker**: Improved platform detection and error handling in /api/browse-folder endpoint.
- **Windows Compatibility**: All templates (projects.html, recipes.html, survey_generator.html, converter.html) now show error messages when folder picker fails.
- **Build Workflow**: GitHub Actions now automatically signs Windows executables when SignPath credentials are configured.

### Fixed
- **Windows Paths**: Removed all hardcoded Unix paths (/Users/karl/work/) from codebase.
- **Temp Paths**: Fixed Windows temp directory patterns in path_utils.py (\Temp\, \AppData\, C:\Users).
- **Browser Launch**: Fixed browser not opening on Windows compiled version.
- **Silent Errors**: Fixed folder picker failing silently without user feedback.
- **Console Output**: Fixed missing console output in Windows compiled builds using log redirection.

### Security
- **Code Signing**: Windows executables are now digitally signed by trusted CA (SignPath) for IT department compliance.

## [1.8.1] - 2026-01-15

### Fixed
- **Build**: Fixed PyInstaller `--add-data` syntax error on Unix-based systems.
- **Build**: Corrected `--target-architecture` flag for macOS Silicon builds.
- **Build**: Fixed missing icon source path in build script.

## [1.8.0] - 2026-01-15

### Added
- **Project Tab**: Enhanced participants.json management with required field highlighting and star indicators.
- **NeuroBagel Widget**: Improved error handling instructions when the widget cannot be loaded.
- **CI/CD**: Added multi-platform build support for macOS (Intel/Silicon), Linux, and Windows in GitHub Actions.
- **Conversion**: Added file head preview in terminal and logs for TSV/CSV debugging to help diagnose delimiter issues.

### Changed
- **UI**: Removed confusing red error styling for mandatory fields in Project Tab.
- **Workflow**: Updated build pipeline to generate specific artifacts for different architectures.

## [1.7.1] - 2026-01-12

### Added
- **Custom Recipes**: Added support for custom recipe folders in survey and biometrics commands.
- **Project UI**: Added dataset description API endpoints and metadata management.
- **Converter UI**: Option to save conversion outputs directly to the project.
- **Logging**: New logging helper for file previews and streamlined log processing in the converter UI.

### Changed
- **BIDS Compatibility**: Enhanced `.bidsignore` rules and integrated automatic updates during survey conversion.
- **Refactoring**: Updated imports in the web module for improved organization.

### Removed
- **Examples**: Removed outdated example files.

## [1.7.0] - 2026-01-12

### Added
- **Workshop Materials**: New PRISM workshop exercises and materials for data conversion, metadata creation, and SPSS export.
- **Alias Support**: Implemented `AliasOf` and `Aliases` resolution in sidecar data and schemas for better handling of redundant definitions.
- **UI Enchancements**: Added server shutdown functionality and quit button in the Web UI.
- **Project Management**: Enhanced project selection enforcement and project management workflows.

### Changed
- **Validation**: Enhanced validation logic and reporting for `eyetracking`, `physiological`, `func`, and `eeg` modalities.
- **Reporting**: Improved dataset statistics and task reporting in summaries.
- **Architecture**: Refactored survey recipes and core code structure for improved maintainability and readability.
- **Logic**: Updated `participants.json` resolution logic to be more robust across modules.

## [1.6.6] - 2026-01-02

### Changed
- **Documentation**: Updated ReadTheDocs specifications with new schema keys and features.
- **Consistency**: Synchronized version numbers across all project files (`codemeta.json`, `CITATION.cff`, etc.).

## [1.6.5] - 2025-12-25

### Added
- **Template Editor (Web UI)**: Create and edit Survey/Biometrics JSON templates with schema-derived field help.
- **Value-only editing**: Keys are fixed; users edit values via form controls (no raw JSON/brackets for typical fields).
- **Item workflows**: Add/select items (questions/metrics), edit per-item fields, validate, and download templates.

## [1.6.2] - 2025-12-24

### Added
- **Biometrics Support**: Enhanced biometrics conversion and validation UI.
- **Methods Boilerplate**: Added API endpoint and UI for generating methods boilerplate text.
- **Internationalization**: Enhanced metadata structure for internationalization support.
- **Build Tools**: Added macOS build script and enhanced Windows build version metadata.
- **Schemas**: Added new PRISM schemas and example templates for survey and biometrics.

### Changed
- **Refactoring**: Improved output directory handling and validation for survey and biometrics imports.
- **Demo Data**: Restructured demo dataset paths and related scripts.

## [1.6.1] - 2025-12-22

### Added
- **Survey Generator UI**: Added display of response scales (levels), units, and value ranges for items in the Survey Export tool.
- **Metadata Extraction**: Enhanced template info extraction to include item-level metadata (Scale, Units, Min/Max values).
- **Rebranding**: Renamed repository to `prism-studio` and updated all internal/external references.

### Fixed
- **Version Consistency**: Synchronized version numbers across `setup.py`, `src/__init__.py`, `prism.py`, and API endpoints.
- **Documentation**: Updated all documentation links and script names to reflect the new `prism-studio` branding.

## [1.6.0] - 2025-12-20

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
- **Project Rename**: Renamed project from `prism-studio` to `prism`.
- **Repository Restructuring**: Moved helper scripts to `helpers/` directory.
- **Documentation**: Updated all documentation to reflect the new name.
