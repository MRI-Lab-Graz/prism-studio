"""
Proxy module for anonymizer - imports from repo root src.
This allows both app/src and repo/src imports to work.
"""
from pathlib import Path
import importlib.util

# Load the real anonymizer module directly from repo root
repo_root = Path(__file__).resolve().parents[2]
real_anonymizer_path = repo_root / "src" / "anonymizer.py"

spec = importlib.util.spec_from_file_location("_real_anonymizer", real_anonymizer_path)
_real_anonymizer = importlib.util.module_from_spec(spec)
spec.loader.exec_module(_real_anonymizer)

# Re-export all public functions
generate_random_id = _real_anonymizer.generate_random_id
create_participant_mapping = _real_anonymizer.create_participant_mapping
create_question_mask_mapping = _real_anonymizer.create_question_mask_mapping
anonymize_tsv_file = _real_anonymizer.anonymize_tsv_file
anonymize_dataset = _real_anonymizer.anonymize_dataset
check_survey_copyright = _real_anonymizer.check_survey_copyright

__all__ = [
    "generate_random_id",
    "create_participant_mapping",
    "create_question_mask_mapping",
    "anonymize_tsv_file",
    "anonymize_dataset",
    "check_survey_copyright",
]
