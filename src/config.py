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

Example .prismrc.json:
{
    "schemaVersion": "stable",
    "ignorePaths": ["derivatives/**", "sourcedata/**"],
    "strictMode": false,
    "runBids": false,
    "customModalities": {}
}
"""

import os
import json
import fnmatch
from dataclasses import dataclass, field, asdict
from typing import Dict, List, Optional, Any


CONFIG_FILENAMES = [".prismrc.json", "prism.config.json"]

DEFAULT_IGNORE_PATTERNS = [
    "derivatives/**",
    "sourcedata/**",
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
    ignore_paths: List[str] = field(default_factory=lambda: DEFAULT_IGNORE_PATTERNS.copy())
    
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
        )
        config._config_path = config_path
        return config
        
    except json.JSONDecodeError as e:
        print(f"⚠️  Error parsing config file {config_path}: {e}")
        return PrismConfig()
    except Exception as e:
        print(f"⚠️  Error loading config file {config_path}: {e}")
        return PrismConfig()


def save_config(config: PrismConfig, dataset_path: str, filename: str = ".prismrc.json") -> str:
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
    if hasattr(args, 'schema_version') and args.schema_version:
        config.schema_version = args.schema_version
    
    if hasattr(args, 'bids') and args.bids:
        config.run_bids = True
    
    if hasattr(args, 'bids_warnings') and args.bids_warnings:
        config.show_bids_warnings = True
    
    if hasattr(args, 'json') and args.json:
        config.default_output_format = "json"
    
    if hasattr(args, 'json_pretty') and args.json_pretty:
        config.default_output_format = "json-pretty"
    
    return config
