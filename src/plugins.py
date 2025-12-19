"""
Plugin system for prism.

Allows users to add custom validators via:
1. .prismrc.json: plugins array with paths to plugin modules
2. <dataset>/validators/: Directory containing custom validator scripts

Example .prismrc.json:
{
    "plugins": [
        "./validators/custom_checks.py",
        "./validators/naming_conventions.py"
    ]
}

Plugin modules should define:
- validate(dataset_path: str, context: dict) -> List[Issue]
"""

import os
import sys
import importlib.util
from pathlib import Path
from typing import List, Dict, Any, Optional, Callable
from dataclasses import dataclass, field

from issues import Issue, error, warning, info


# =============================================================================
# PLUGIN DEFINITIONS
# =============================================================================

@dataclass
class Plugin:
    """Represents a loaded plugin."""
    name: str
    path: str
    module: Any
    description: str = ""
    version: str = "1.0.0"
    enabled: bool = True
    
    @property
    def validate_func(self) -> Optional[Callable]:
        """Get the validate function from the plugin."""
        return getattr(self.module, 'validate', None)
    
    @property
    def has_validate(self) -> bool:
        """Check if plugin has a validate function."""
        return self.validate_func is not None


@dataclass
class PluginContext:
    """Context passed to plugin validators."""
    dataset_path: str
    schema_version: str
    subjects: List[str]
    sessions: List[str]
    tasks: List[str]
    modalities: Dict[str, int]
    config: Dict[str, Any] = field(default_factory=dict)
    verbose: bool = False


# =============================================================================
# PLUGIN MANAGER
# =============================================================================

class PluginManager:
    """
    Manages loading and execution of validator plugins.
    
    Usage:
        manager = PluginManager(dataset_path)
        manager.load_from_config(config)
        manager.discover_local_plugins()
        
        for plugin in manager.plugins:
            issues = manager.run_plugin(plugin, context)
    """
    
    def __init__(self, dataset_path: str):
        self.dataset_path = os.path.abspath(dataset_path)
        self.plugins: List[Plugin] = []
        self._loaded_paths: set = set()
    
    def load_from_config(self, config: Dict[str, Any]) -> None:
        """
        Load plugins specified in config.
        
        Args:
            config: Config dict with optional 'plugins' key
        """
        plugin_paths = config.get('plugins', [])
        
        for path in plugin_paths:
            # Resolve relative paths from dataset root
            if not os.path.isabs(path):
                path = os.path.join(self.dataset_path, path)
            
            plugin = self._load_plugin(path)
            if plugin:
                self.plugins.append(plugin)
    
    def discover_local_plugins(self) -> None:
        """
        Discover plugins in <dataset>/validators/ directory.
        """
        validators_dir = os.path.join(self.dataset_path, 'validators')
        
        if not os.path.isdir(validators_dir):
            return
        
        for filename in sorted(os.listdir(validators_dir)):
            if filename.endswith('.py') and not filename.startswith('_'):
                path = os.path.join(validators_dir, filename)
                plugin = self._load_plugin(path)
                if plugin:
                    self.plugins.append(plugin)
    
    def _load_plugin(self, path: str) -> Optional[Plugin]:
        """
        Load a single plugin from path.
        
        Args:
            path: Path to Python plugin file
            
        Returns:
            Plugin object or None if loading failed
        """
        path = os.path.abspath(path)
        
        # Avoid loading same plugin twice
        if path in self._loaded_paths:
            return None
        
        if not os.path.isfile(path):
            return None
        
        try:
            # Load module dynamically
            module_name = f"prism_plugin_{Path(path).stem}"
            spec = importlib.util.spec_from_file_location(module_name, path)
            
            if spec is None or spec.loader is None:
                return None
            
            module = importlib.util.module_from_spec(spec)
            sys.modules[module_name] = module
            spec.loader.exec_module(module)
            
            # Extract metadata
            name = getattr(module, 'PLUGIN_NAME', Path(path).stem)
            description = getattr(module, 'PLUGIN_DESCRIPTION', '')
            version = getattr(module, 'PLUGIN_VERSION', '1.0.0')
            
            self._loaded_paths.add(path)
            
            return Plugin(
                name=name,
                path=path,
                module=module,
                description=description,
                version=version,
            )
            
        except Exception as e:
            # Silently fail for individual plugins
            return None
    
    def run_plugin(
        self,
        plugin: Plugin,
        context: PluginContext,
    ) -> List[Issue]:
        """
        Run a single plugin's validate function.
        
        Args:
            plugin: Plugin to run
            context: Validation context
            
        Returns:
            List of issues from plugin
        """
        if not plugin.enabled or not plugin.has_validate:
            return []
        
        try:
            result = plugin.validate_func(context.dataset_path, context.__dict__)
            
            # Ensure result is a list
            if result is None:
                return []
            
            # Convert tuples to Issues if needed
            issues = []
            for item in result:
                if isinstance(item, Issue):
                    # Tag with plugin source
                    if item.details is None:
                        item.details = {}
                    item.details['plugin'] = plugin.name
                    issues.append(item)
                elif isinstance(item, tuple) and len(item) >= 2:
                    # Legacy format: (severity, message, [file_path])
                    severity_str, message = item[0], item[1]
                    file_path = item[2] if len(item) > 2 else None
                    
                    if severity_str.upper() == 'ERROR':
                        issue = error('PRISM900',
                                     file_path=file_path,
                                     message=f"[{plugin.name}] {message}")
                    elif severity_str.upper() == 'WARNING':
                        issue = warning('PRISM900',
                                       file_path=file_path,
                                       message=f"[{plugin.name}] {message}")
                    else:
                        issue = info('PRISM900',
                                    file_path=file_path,
                                    message=f"[{plugin.name}] {message}")
                    
                    if issue.details is None:
                        issue.details = {}
                    issue.details['plugin'] = plugin.name
                    issues.append(issue)
            
            return issues
            
        except Exception as e:
            # Return error about plugin failure
            return [error('PRISM901',
                         message=f"Plugin '{plugin.name}' failed: {str(e)}",
                         details={'plugin': plugin.name, 'exception': str(e)})]
    
    def run_all(self, context: PluginContext) -> List[Issue]:
        """
        Run all loaded plugins.
        
        Args:
            context: Validation context
            
        Returns:
            Combined list of issues from all plugins
        """
        all_issues = []
        
        for plugin in self.plugins:
            issues = self.run_plugin(plugin, context)
            all_issues.extend(issues)
        
        return all_issues


# =============================================================================
# BUILT-IN PLUGINS (Examples)
# =============================================================================

def create_context(
    dataset_path: str,
    stats: Any,
    schema_version: str = "stable",
    config: Dict[str, Any] = None,
    verbose: bool = False,
) -> PluginContext:
    """
    Create a PluginContext from validation stats.
    
    Args:
        dataset_path: Path to dataset
        stats: DatasetStats object from validation
        schema_version: Schema version used
        config: Config dict
        verbose: Verbose mode
        
    Returns:
        PluginContext for plugins
    """
    return PluginContext(
        dataset_path=os.path.abspath(dataset_path),
        schema_version=schema_version,
        subjects=list(stats.subjects) if hasattr(stats, 'subjects') else [],
        sessions=list(stats.sessions) if hasattr(stats, 'sessions') else [],
        tasks=list(stats.tasks) if hasattr(stats, 'tasks') else [],
        modalities=dict(stats.modalities) if hasattr(stats, 'modalities') else {},
        config=config or {},
        verbose=verbose,
    )


# =============================================================================
# PLUGIN TEMPLATE GENERATOR
# =============================================================================

PLUGIN_TEMPLATE = '''"""
Custom validator plugin for prism.

This plugin is automatically loaded from the validators/ directory.
"""

# Plugin metadata
PLUGIN_NAME = "{name}"
PLUGIN_DESCRIPTION = "{description}"
PLUGIN_VERSION = "1.0.0"

# Import helpers for creating issues
import os
from pathlib import Path


def validate(dataset_path: str, context: dict) -> list:
    """
    Validate the dataset and return a list of issues.
    
    Args:
        dataset_path: Absolute path to dataset root
        context: Dict containing:
            - schema_version: str
            - subjects: List[str]
            - sessions: List[str]
            - tasks: List[str]
            - modalities: Dict[str, int]
            - config: Dict[str, Any]
            - verbose: bool
    
    Returns:
        List of issues. Each issue can be:
        - tuple: (severity, message) or (severity, message, file_path)
          where severity is "ERROR", "WARNING", or "INFO"
        - Issue object (if imported from prism_validator)
    
    Example:
        return [
            ("WARNING", "Subject folder name should be lowercase", "sub-001/"),
            ("ERROR", "Missing required file", "sub-001/anat/sub-001_T1w.nii.gz"),
        ]
    """
    issues = []
    
    # Example: Check for README file
    readme_path = os.path.join(dataset_path, "README")
    readme_md_path = os.path.join(dataset_path, "README.md")
    
    if not os.path.exists(readme_path) and not os.path.exists(readme_md_path):
        issues.append(("WARNING", "Dataset should include a README file"))
    
    # Example: Check for LICENSE file
    license_path = os.path.join(dataset_path, "LICENSE")
    if not os.path.exists(license_path):
        issues.append(("INFO", "Consider adding a LICENSE file"))
    
    # Add your custom validation logic here
    # ...
    
    return issues
'''


def generate_plugin_template(
    output_path: str,
    name: str = "custom_validator",
    description: str = "Custom validation checks",
) -> str:
    """
    Generate a plugin template file.
    
    Args:
        output_path: Path to write template
        name: Plugin name
        description: Plugin description
        
    Returns:
        Path to generated file
    """
    content = PLUGIN_TEMPLATE.format(name=name, description=description)
    
    # Ensure directory exists
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    
    with open(output_path, 'w') as f:
        f.write(content)
    
    return output_path


# =============================================================================
# CLI HELPER
# =============================================================================

def list_plugins(manager: PluginManager) -> None:
    """Print loaded plugins to console."""
    if not manager.plugins:
        print("No plugins loaded.")
        return
    
    print(f"Loaded {len(manager.plugins)} plugin(s):")
    for plugin in manager.plugins:
        status = "✓" if plugin.enabled else "✗"
        has_validate = "✓" if plugin.has_validate else "✗"
        print(f"  {status} {plugin.name} v{plugin.version}")
        if plugin.description:
            print(f"      {plugin.description}")
        print(f"      validate(): {has_validate}  Path: {plugin.path}")
