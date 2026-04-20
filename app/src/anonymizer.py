"""
Proxy module for anonymizer - delegates to canonical repo root src/anonymizer.py.
Uses _compat.load_canonical_module so this works in both dev and PyInstaller bundles
(where the real src/ is bundled under backend_bundle/src/).
"""

from __future__ import annotations

from src._compat import load_canonical_module

_real_anonymizer = load_canonical_module(
    current_file=__file__,
    canonical_rel_path="anonymizer.py",
    alias="prism_backend_src.anonymizer",
)

# Re-export all public functions
generate_random_id = _real_anonymizer.generate_random_id
create_participant_mapping = _real_anonymizer.create_participant_mapping
create_question_mask_mapping = _real_anonymizer.create_question_mask_mapping
anonymize_tsv_file = _real_anonymizer.anonymize_tsv_file
anonymize_dataset = _real_anonymizer.anonymize_dataset
check_survey_copyright = _real_anonymizer.check_survey_copyright
replace_participant_ids_in_text = _real_anonymizer.replace_participant_ids_in_text
update_intendedfor_paths = _real_anonymizer.update_intendedfor_paths

__all__ = [
    "generate_random_id",
    "create_participant_mapping",
    "create_question_mask_mapping",
    "anonymize_tsv_file",
    "anonymize_dataset",
    "check_survey_copyright",
    "replace_participant_ids_in_text",
    "update_intendedfor_paths",
]
