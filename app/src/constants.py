"""
Central constants for the PRISM backend.
Single source of truth for values that must remain consistent across modules.
"""

# Default BIDS specification version used when creating or fixing dataset_description.json.
# Update here only — all modules should import from this module.
DEFAULT_BIDS_VERSION = "1.10.1"

# Modalities the Template Editor / Recipe Builder features support. This is
# a feature-scope concept, not filename grammar (see src/entity_rules.py for
# that) - it happens to share values with some entity_rules modalities today
# but is a separate axis (e.g. adding a new BIDS suffix to entities.schema.json
# should not automatically expand recipe/template support to it).
SUPPORTED_MODALITIES: tuple[str, ...] = ("survey", "biometrics")
