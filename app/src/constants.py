"""
Central constants for the PRISM backend.
Single source of truth for values that must remain consistent across modules.
"""

# Default BIDS specification version used when creating or fixing dataset_description.json.
# Update here only — all modules should import from this module.
DEFAULT_BIDS_VERSION = "1.10.1"
