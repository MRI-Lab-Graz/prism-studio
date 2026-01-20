# Global Library Configuration

PRISM now supports a global library and recipe repository that all projects can access by default. This eliminates the need to specify `--repo` for every command and provides a centralized, curated collection of validated surveys and recipes.

## Overview

The global library system uses the `official/` folder in the PRISM repository as the default source for:

- **Survey Templates** (`official/library/survey/`)
- **Biometric Templates** (`official/library/biometrics/`)
- **Survey Recipes** (`official/recipe/survey/`)
- **Biometric Recipes** (`official/recipe/biometrics/`)

## Configuration

### Initial Setup

Run the configuration script to set up global library paths:

```bash
python scripts/setup/configure_global_library.py
```

This creates `app/prism_studio_settings.json` with:

```json
{
  "globalLibraryRoot": "/path/to/prism-studio/official",
  "defaultModalities": ["survey", "biometrics"]
}
```

**Important**: After configuring, restart any running PRISM Studio instances to pick up the new settings.

### Verify Configuration

Check that paths are correctly configured:

```bash
python scripts/setup/verify_global_library.py
```

Or quickly view current settings:

```bash
python scripts/setup/show_global_config.py
```

## How It Works

### Path Resolution Priority

1. **Project Override**: If a project has `templateLibraryPath` in `.prismrc.json`, that takes precedence
2. **Global Configuration**: Uses `globalLibraryRoot` from `app/prism_studio_settings.json`
3. **Default Fallback**: Uses `official/` folder in the repository

### Recipe Commands

When using recipe commands, both the library and recipe paths are automatically configured:

```bash
# Uses global library and recipes automatically
prism_tools.py recipes surveys --prism /path/to/dataset

# Override with specific repository (advanced)
prism_tools.py recipes surveys --prism /path/to/dataset --repo /custom/repo

# Override just the recipe folder (advanced)
prism_tools.py recipes surveys --prism /path/to/dataset --recipes /custom/recipes
```

The web interface also uses these global paths by default. When you open the "Dataset Recipes & Scoring" tool, leaving the "Custom Recipe Folder" field empty will automatically use the global recipe library from `official/recipe/`.

### Library Structure

The official library follows this structure:

```
official/
├── library/
│   ├── survey/
│   │   ├── survey-ads.json
│   │   ├── survey-bdi2.json
│   │   └── ... (109 surveys)
│   └── biometrics/
│       └── (future biometric templates)
└── recipe/
    ├── survey/
    │   ├── ads.json
    │   ├── bdi2.json
    │   └── ... (109 recipes)
    └── biometrics/
        └── (future biometric recipes)
```

## Project-Level Configuration

Individual projects can still maintain their own libraries and override global settings:

### Option 1: Custom Library Path

In your project's `.prismrc.json`:

```json
{
  "templateLibraryPath": "/shared/nextcloud/prism-library"
}
```

### Option 2: Project-Specific Libraries

Maintain project-specific templates in:
- `code/library/` (recommended for new projects)
- `library/` (legacy projects)

These are used for custom/project-specific surveys not in the global library.

## Benefits

✅ **No more `--repo` flags**: Commands work out of the box
✅ **Centralized curation**: Single source of truth for validated surveys
✅ **Version control**: All surveys tracked in the official folder
✅ **Easy updates**: Pull new surveys from the repository
✅ **Project flexibility**: Projects can still override when needed

## Backwards Compatibility

The system maintains backwards compatibility:

- Existing projects with `.prismrc.json` continue to work unchanged
- Projects without configuration automatically use the global library
- The `--repo` flag still works for one-off overrides
- Legacy `library/` folders in projects are still respected

## Advanced Configuration

### Custom Global Location

For network shares or external repositories, edit `app/prism_studio_settings.json`:

```json
{
  "globalLibraryRoot": "/shared/network/prism-official",
  "defaultModalities": ["survey", "biometrics"]
}
```

### Multiple Locations (Future)

Future versions may support multiple library sources with fallback:

```json
{
  "librarySources": [
    "/local/prism-official",
    "/network/prism-shared",
    "https://gitlab.com/prism/library.git"
  ]
}
```

## Troubleshooting

### Check Current Configuration

```bash
python scripts/setup/verify_global_library.py
```

### Reset to Defaults

Delete `app/prism_studio_settings.json` and rerun:

```bash
rm app/prism_studio_settings.json
python scripts/setup/configure_global_library.py
```

### Test Recipe Command

```bash
# Create a test dataset
mkdir -p test_dataset
echo '{"Name":"Test","BIDSVersion":"1.8.0"}' > test_dataset/dataset_description.json

# Should use global library automatically
prism_tools.py recipes surveys --prism test_dataset --survey ads
```

## Related Documentation

- [Recipe System](../docs/RECIPES.md)
- [Configuration Files](../docs/CONFIG.md)
- [Library Management](../docs/SURVEY_LIBRARY.md)

## Developer Notes

The global configuration is implemented in:
- `app/src/config.py`: Configuration loading and resolution
- `app/prism_tools.py`: Integration with CLI commands
- `src/recipes_surveys.py`: Recipe loading logic

Key functions:
- `get_effective_library_paths()`: Resolves global library paths
- `load_app_settings()`: Loads app-level configuration
- `get_effective_template_library_path()`: Resolves project + global paths
