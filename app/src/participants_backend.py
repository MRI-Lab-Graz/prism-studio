"""Proxy module for participants backend helpers.

Delegates to canonical repo root src/participants_backend.py and works in both
dev and PyInstaller bundles via src._compat.load_canonical_module.
"""

from __future__ import annotations

from src._compat import load_canonical_module

_real = load_canonical_module(
    current_file=__file__,
    canonical_rel_path="participants_backend.py",
    alias="prism_backend_src.participants_backend",
)

ParticipantLogCallback = _real.ParticipantLogCallback
apply_participants_merge = _real.apply_participants_merge
collect_dataset_participants = _real.collect_dataset_participants
convert_dataset_participants = _real.convert_dataset_participants
describe_participants_workflow = _real.describe_participants_workflow
export_participants_merge_conflicts_csv = _real.export_participants_merge_conflicts_csv
merge_neurobagel_schema_for_columns = _real.merge_neurobagel_schema_for_columns
normalize_participant_mapping = _real.normalize_participant_mapping
preview_dataset_participants = _real.preview_dataset_participants
preview_participants_merge = _real.preview_participants_merge
resolve_participant_mapping_target = _real.resolve_participant_mapping_target
save_participant_mapping = _real.save_participant_mapping

__all__ = [
    "ParticipantLogCallback",
    "apply_participants_merge",
    "collect_dataset_participants",
    "convert_dataset_participants",
    "describe_participants_workflow",
    "export_participants_merge_conflicts_csv",
    "merge_neurobagel_schema_for_columns",
    "normalize_participant_mapping",
    "preview_dataset_participants",
    "preview_participants_merge",
    "resolve_participant_mapping_target",
    "save_participant_mapping",
]
