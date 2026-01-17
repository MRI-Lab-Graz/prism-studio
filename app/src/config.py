"""
Configuration file support for prism.

Supports per-project configuration via:
- .prismrc.json (hidden file)
- prism.config.json (visible file)

Configuration Options:
    schemaVersion: Schema version to use (e.g., "stable", "v0.1")
    ignorePaths: Glob patterns for paths to ignore during validation
    strictMode: Enable strict validation (treat warnings as errors)
    runBids: Automatically run BIDS validator
    customModalities: Additional modality patterns to recognize
    templateLibraryPath: Path to external template library (overrides global default)

Example .prismrc.json:
{
    "schemaVersion": "stable",
    "ignorePaths": ["recipes/**", "derivatives/**", "sourcedata/**"],
    "strictMode": false,
    "runBids": false,
    "customModalities": {},
    "templateLibraryPath": "/shared/templates"
}
"""

import os
import json
import fnmatch
from dataclasses import dataclass, field, asdict
from typing import Dict, List, Optional, Any


CONFIG_FILENAMES = [".prismrc.json", "prism.config.json"]

DEFAULT_IGNORE_PATTERNS = [
    "library/**",
    "recipe/**",
    "derivatives/**",
    "sourcedata/**",
    "analysis/**",
    "paper/**",
    "code/**",
    ".git/**",
    ".datalad/**",
    "__pycache__/**",
    "*.pyc",
]


@dataclass
class PrismConfig:
    """Configuration for prism"""

    # Schema settings
    schema_version: str = "stable"

    # Paths to ignore (glob patterns)
    ignore_paths: List[str] = field(
        default_factory=lambda: DEFAULT_IGNORE_PATTERNS.copy()
    )

    # Validation behavior
    strict_mode: bool = False  # Treat warnings as errors
    run_bids: bool = False  # Run BIDS validator by default
    show_bids_warnings: bool = False  # Show BIDS validator warnings

    # Custom modality patterns (modality_name -> regex pattern)
    custom_modalities: Dict[str, str] = field(default_factory=dict)

    # Output settings
    default_output_format: str = "text"  # "text" or "json"

    # Advanced settings
    max_file_size_mb: int = 100  # Skip files larger than this for content validation
    parallel_validation: bool = False  # Enable parallel file validation

    # Template library path (overrides global default)
    # Points to external shared template library (Nextcloud, GitLab, etc.)
    template_library_path: Optional[str] = None

    # Config file location (set after loading)
    _config_path: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary (excludes internal fields)"""
        d = asdict(self)
        d.pop("_config_path", None)
        return d

    def should_ignore(self, path: str) -> bool:
        """Check if a path should be ignored based on ignore patterns"""
        # Normalize path separators
        path = path.replace("\\", "/")

        for pattern in self.ignore_paths:
            if fnmatch.fnmatch(path, pattern):
                return True
            # Also check without leading ./
            if path.startswith("./"):
                if fnmatch.fnmatch(path[2:], pattern):
                    return True
        return False


def find_config_file(dataset_path: str) -> Optional[str]:
    """
    Find configuration file in dataset directory.

    Args:
        dataset_path: Path to dataset root

    Returns:
        Path to config file if found, None otherwise
    """
    for filename in CONFIG_FILENAMES:
        config_path = os.path.join(dataset_path, filename)
        if os.path.exists(config_path):
            return config_path
    return None


def load_config(dataset_path: str) -> PrismConfig:
    """
    Load configuration from dataset directory.

    Args:
        dataset_path: Path to dataset root

    Returns:
        PrismConfig instance (defaults if no config file found)
    """
    config_path = find_config_file(dataset_path)

    if config_path is None:
        return PrismConfig()

    try:
        with open(config_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        config = PrismConfig(
            schema_version=data.get("schemaVersion", "stable"),
            ignore_paths=data.get("ignorePaths", DEFAULT_IGNORE_PATTERNS.copy()),
            strict_mode=data.get("strictMode", False),
            run_bids=data.get("runBids", False),
            show_bids_warnings=data.get("showBidsWarnings", False),
            custom_modalities=data.get("customModalities", {}),
            default_output_format=data.get("defaultOutputFormat", "text"),
            max_file_size_mb=data.get("maxFileSizeMb", 100),
            parallel_validation=data.get("parallelValidation", False),
            template_library_path=data.get("templateLibraryPath"),
        )
        config._config_path = config_path
        return config

    except json.JSONDecodeError as e:
        print(f"⚠️  Error parsing config file {config_path}: {e}")
        return PrismConfig()
    except Exception as e:
        print(f"⚠️  Error loading config file {config_path}: {e}")
        return PrismConfig()


def save_config(
    config: PrismConfig, dataset_path: str, filename: str = ".prismrc.json"
) -> str:
    """
    Save configuration to dataset directory.

    Args:
        config: PrismConfig instance to save
        dataset_path: Path to dataset root
        filename: Config filename (default: .prismrc.json)

    Returns:
        Path to saved config file
    """
    config_path = os.path.join(dataset_path, filename)

    # Convert to JSON-friendly format
    data = {
        "schemaVersion": config.schema_version,
        "ignorePaths": config.ignore_paths,
        "strictMode": config.strict_mode,
        "runBids": config.run_bids,
        "showBidsWarnings": config.show_bids_warnings,
        "customModalities": config.custom_modalities,
        "defaultOutputFormat": config.default_output_format,
        "maxFileSizeMb": config.max_file_size_mb,
        "parallelValidation": config.parallel_validation,
    }

    # Only include template library path if set
    if config.template_library_path:
        data["templateLibraryPath"] = config.template_library_path

    with open(config_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)

    return config_path


def create_default_config(dataset_path: str, filename: str = ".prismrc.json") -> str:
    """
    Create a default configuration file in the dataset.

    Args:
        dataset_path: Path to dataset root
        filename: Config filename (default: .prismrc.json)

    Returns:
        Path to created config file
    """
    config = PrismConfig()
    return save_config(config, dataset_path, filename)


def merge_cli_args(config: PrismConfig, args: Any) -> PrismConfig:
    """
    Merge CLI arguments with config file settings.
    CLI arguments take precedence over config file.

    Args:
        config: PrismConfig loaded from file
        args: argparse namespace with CLI arguments

    Returns:
        Updated PrismConfig
    """
    # CLI arguments override config file
    if hasattr(args, "schema_version") and args.schema_version:
        config.schema_version = args.schema_version

    if hasattr(args, "bids") and args.bids:
        config.run_bids = True

    if hasattr(args, "bids_warnings") and args.bids_warnings:
        config.show_bids_warnings = True

    if hasattr(args, "json") and args.json:
        config.default_output_format = "json"

    if hasattr(args, "json_pretty") and args.json_pretty:
        config.default_output_format = "json-pretty"

    return config


# =============================================================================
# App-level Settings (Global defaults for PRISM Studio)
# =============================================================================

APP_SETTINGS_FILENAME = "prism_studio_settings.json"


@dataclass
class AppSettings:
    """App-level settings for PRISM Studio (global defaults)"""

    # Global template library path (shared, read-only templates from Nextcloud/GitLab)
    global_template_library_path: Optional[str] = None

    # Default modalities for new projects
    default_modalities: List[str] = field(
        default_factory=lambda: ["survey", "biometrics"]
    )

    # Settings file location (set after loading)
    _settings_path: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary (excludes internal fields)"""
        d = asdict(self)
        d.pop("_settings_path", None)
        return d


def get_app_settings_path(app_root: str = None) -> str:
    """
    Get the path to the app settings file.

    Args:
        app_root: Application root directory (defaults to current working directory)

    Returns:
        Path to settings file
    """
    if app_root is None:
        # Try to find settings in current directory or user home
        locations = [
            os.getcwd(),
            os.path.expanduser("~/.prism-studio"),
            os.path.expanduser("~"),
        ]
        for loc in locations:
            path = os.path.join(loc, APP_SETTINGS_FILENAME)
            if os.path.exists(path):
                return path
        # Default to current directory if not found
        return os.path.join(os.getcwd(), APP_SETTINGS_FILENAME)

    return os.path.join(app_root, APP_SETTINGS_FILENAME)


def load_app_settings(app_root: str = None) -> AppSettings:
    """
    Load app-level settings.

    Args:
        app_root: Application root directory

    Returns:
        AppSettings instance (defaults if no settings file found)
    """
    settings_path = get_app_settings_path(app_root)

    if not os.path.exists(settings_path):
        return AppSettings()

    try:
        with open(settings_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        settings = AppSettings(
            global_template_library_path=data.get("globalTemplateLibraryPath"),
            default_modalities=data.get("defaultModalities", ["survey", "biometrics"]),
        )
        settings._settings_path = settings_path
        return settings

    except (json.JSONDecodeError, Exception) as e:
        print(f"Warning: Error loading app settings from {settings_path}: {e}")
        return AppSettings()


def save_app_settings(settings: AppSettings, app_root: str = None) -> str:
    """
    Save app-level settings.

    Args:
        settings: AppSettings instance to save
        app_root: Application root directory

    Returns:
        Path to saved settings file
    """
    if app_root is None:
        app_root = os.getcwd()

    settings_path = os.path.join(app_root, APP_SETTINGS_FILENAME)

    data = {
        "globalTemplateLibraryPath": settings.global_template_library_path,
        "defaultModalities": settings.default_modalities,
    }

    # Remove None values
    data = {k: v for k, v in data.items() if v is not None}

    with open(settings_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)

    return settings_path


def get_effective_template_library_path(
    project_path: str = None,
    app_settings: AppSettings = None,
    app_root: str = None
) -> Dict[str, Any]:
    """
    Get the effective template library paths considering both global and project settings.

    Resolution order:
    1. Project .prismrc.json templateLibraryPath (if set)
    2. App-level globalTemplateLibraryPath (if configured)
    3. Default: app's survey_library folder

    Args:
        project_path: Path to current project (optional)
        app_settings: Pre-loaded app settings (optional, will load if not provided)
        app_root: Application root directory for default path (optional)

    Returns:
        Dictionary with:
        - global_library_path: Global shared template library (read-only)
        - project_library_path: Project's own library folder (user templates, usually code/library or legacy library/)
        - effective_external_path: The resolved external library path
        - source: 'project', 'global', or 'default' indicating where external path came from
    """
    if app_settings is None:
        app_settings = load_app_settings()

    # Determine effective global path (configured or default)
    global_path = app_settings.global_template_library_path
    source = "global" if global_path else None

    # If no configured global, use default survey_library from app root
    if not global_path and app_root:
        default_path = os.path.join(app_root, "survey_library")
        if os.path.exists(default_path):
            global_path = default_path
            source = "default"

    result = {
        "global_library_path": global_path,
        "project_library_path": None,
        "effective_external_path": None,
        "source": None,
    }

    # If we have a project, check its settings and library folder
    if project_path and os.path.exists(project_path):
        project_path = os.path.abspath(project_path)

        # Project's own library folders (legacy and new code/library layout)
        project_library_candidates = [
            os.path.join(project_path, "code", "library"),
            os.path.join(project_path, "library"),
        ]
        for candidate in project_library_candidates:
            if os.path.exists(candidate):
                result["project_library_path"] = candidate
                break

        # Check project config for external library override
        project_config = load_config(project_path)
        if project_config.template_library_path:
            result["effective_external_path"] = project_config.template_library_path
            result["source"] = "project"

    # If no project override, use global setting (or default)
    if not result["effective_external_path"] and global_path:
        result["effective_external_path"] = global_path
        result["source"] = source

    return result
