# Psycho-Validator v1.0.0 - First Major Release 🎉

We're excited to announce the first major release of **Psycho-Validator**, a comprehensive BIDS-inspired validation tool for psychological and psychophysical research datasets!

## 🌟 Highlights

### Schema Versioning System
The biggest new feature is our **Docker-like schema versioning** system:

```bash
# List available schema versions
python psycho-validator.py --list-versions

# Validate with a specific version
python psycho-validator.py /path/to/dataset --schema-version v0.1
```

- ✅ Multiple schema versions (`stable`, `v0.1`, etc.)
- ✅ Web interface dropdown selector
- ✅ Version tracking in validation results
- ✅ Easy to add new versions as schemas evolve

### Web Interface
Enhanced user experience with:
- 📋 Schema version selection dropdown
- 🎨 Improved logo display
- 🔍 Clear version information in results
- 🚀 Fast local folder validation

### Complete Feature Set
- ✅ **Multi-modal support**: Images, movies, audio, EEG, eye-tracking, behavior, physiological data
- ✅ **BIDS-inspired validation**: Strict filename and structure checking
- ✅ **Metadata validation**: JSON schema validation for all modalities
- ✅ **Consistency checking**: Cross-subject validation
- ✅ **Flexible deployment**: CLI, web interface, or Python API
- ✅ **Privacy-focused**: All processing happens locally

## 📦 Installation

### Quick Start
```bash
git clone https://github.com/MRI-Lab-Graz/psycho-validator.git
cd psycho-validator
./setup.sh  # macOS/Linux
# or
setup.bat   # Windows
```

### Requirements
- Python 3.10 or higher
- Flask (for web interface)
- jsonschema

## 🚀 Quick Start

### Web Interface (Recommended)
```bash
python launch_web.py
```
Then open your browser to http://127.0.0.1:5000

### Command Line
```bash
# Validate a dataset
python psycho-validator.py /path/to/dataset

# With specific schema version
python psycho-validator.py /path/to/dataset --schema-version v0.1

# Verbose output
python psycho-validator.py /path/to/dataset -v
```

### Python API
```python
from runner import validate_dataset

issues, stats = validate_dataset('/path/to/dataset', 
                                schema_version='stable')
```

## 📚 Documentation

Complete documentation suite:
- **[Quick Start Guide](docs/QUICK_START.md)** - Get started in 5 minutes
- **[Schema Versioning Guide](docs/SCHEMA_VERSIONING_GUIDE.md)** - Learn about versions
- **[Web Interface Guide](docs/WEB_INTERFACE.md)** - Web UI documentation
- **[Project Structure](docs/PROJECT_STRUCTURE.md)** - Understand the codebase

## 🎯 What's New in v1.0.0

### Features
- 🆕 Schema versioning system (Docker-like)
- 🆕 Version selection in web interface
- 🆕 `--schema-version` and `--list-versions` CLI flags
- 🆕 Version tracking in validation results
- 🆕 Comprehensive schema versioning documentation
- ✨ Improved web interface UI
- ✨ Better logo display
- ✨ Enhanced error messages

### Technical
- 📦 Organized schemas into version directories
- 🔧 Version-aware schema loading
- 🔧 Automatic version normalization
- 🔧 Backward-compatible changes
- 📝 Complete test coverage

## 🔄 Migration from Beta

If you were using an earlier version:
- ✅ **No breaking changes** - Everything continues to work
- ✅ Default behavior uses `stable` schema version
- ✅ Your existing validation scripts work as-is
- 📖 New schema version features are optional

## 💡 Usage Examples

### List Available Schema Versions
```bash
$ python psycho-validator.py --list-versions
Available schema versions:
  • stable (default)
  • v0.1
```

### Validate with Specific Version
```bash
$ python psycho-validator.py my-dataset --schema-version v0.1
🔍 Validating dataset: my-dataset
📋 Using schema version: v0.1
📋 Loaded 7 schemas (version: v0.1)
...
```

### Web Interface with Version Selection
1. Start: `python launch_web.py`
2. Select schema version from dropdown
3. Upload or enter local folder path
4. View results with version information

## 🛠️ Supported Modalities

| Modality | Extensions | Validation |
|----------|-----------|------------|
| Images | `.png`, `.jpg`, `.jpeg`, `.tiff` | ✅ Full |
| Movies | `.mp4`, `.avi`, `.mov` | ✅ Full |
| Audio | `.wav`, `.mp3`, `.flac` | ✅ Full |
| EEG | `.edf`, `.bdf`, `.eeg` | ✅ Full |
| Eye-tracking | `.tsv`, `.edf` | ✅ Full |
| Behavior | `.tsv`, `.csv` | ✅ Full |
| Physiological | `.tsv`, `.edf` | ✅ Full |

## 🤝 Contributing

We welcome contributions! See our [Contributing Guide](CONTRIBUTING.md) for details.

## 📄 License

This project is open source. See [LICENSE](LICENSE) for details.

## 👥 Team

**MRI-Lab Graz** - University of Graz  
**Maintainer**: Karl Koschutnig (karl.koschutnig@uni-graz.at)

Built with ❤️ for the research community

## 🔗 Links

- **GitHub**: https://github.com/MRI-Lab-Graz/psycho-validator
- **Documentation**: [docs/](docs/)
- **Issues**: https://github.com/MRI-Lab-Graz/psycho-validator/issues

## 🎉 Thank You!

Thank you for using Psycho-Validator! We hope it makes your dataset validation easier and more reliable.

If you find this tool useful, please:
- ⭐ Star the repository
- 📢 Share with colleagues
- 🐛 Report issues
- 💡 Suggest improvements

---

**Version**: 1.0.0  
**Release Date**: October 9, 2025  
**Status**: Production Ready ✅
