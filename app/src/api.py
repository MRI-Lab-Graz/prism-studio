"""
Proxy module for api - delegates to canonical repo root src/api.py.
Uses _compat.load_canonical_module so this works in both dev and PyInstaller bundles
(where the real src/ is bundled under backend_bundle/src/).
"""

from __future__ import annotations

from src._compat import load_canonical_module

_real = load_canonical_module(
    current_file=__file__,
    canonical_rel_path="api.py",
    alias="prism_backend_src.api",
)

# Re-export public API
create_api_blueprint = _real.create_api_blueprint
_utc_isoformat_z = _real._utc_isoformat_z
validate_dataset = getattr(_real, "validate_dataset", None)
get_available_schema_versions = getattr(_real, "get_available_schema_versions", None)
load_all_schemas = getattr(_real, "load_all_schemas", None)

__all__ = [
    "create_api_blueprint",
]
