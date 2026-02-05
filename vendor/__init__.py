"""
Vendored dependencies loader for PRISM.

This module checks for and loads vendored (bundled) versions of optional
dependencies that may require compilation on some systems.
"""
import sys
from pathlib import Path

# Add vendor directory to Python path if it exists
VENDOR_DIR = Path(__file__).parent
if VENDOR_DIR.exists():
    # Insert at position 1 (after current script directory)
    # This allows vendored packages to be found, but still allows
    # user-installed versions to take precedence
    vendor_str = str(VENDOR_DIR)
    if vendor_str not in sys.path:
        sys.path.insert(1, vendor_str)


def try_import_pyedflib():
    """
    Attempt to import pyedflib, trying vendored version if system version fails.
    
    Returns:
        module or None: The pyedflib module if available, None otherwise
    """
    try:
        import pyedflib
        return pyedflib
    except ImportError:
        # Try vendored version
        try:
            vendor_pyedflib = VENDOR_DIR / "pyedflib"
            if vendor_pyedflib.exists():
                sys.path.insert(0, str(VENDOR_DIR))
                import pyedflib
                return pyedflib
        except ImportError:
            pass
    return None


def check_optional_dependencies():
    """
    Check which optional dependencies are available.
    
    Returns:
        dict: Status of optional dependencies
    """
    status = {
        "pyedflib": False,
    }
    
    # Check pyedflib
    pyedflib_module = try_import_pyedflib()
    if pyedflib_module:
        status["pyedflib"] = True
        status["pyedflib_version"] = getattr(pyedflib_module, "__version__", "unknown")
    
    return status
