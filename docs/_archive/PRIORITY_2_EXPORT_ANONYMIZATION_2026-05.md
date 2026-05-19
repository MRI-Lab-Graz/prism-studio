# Priority 2 - Export Anonymization Plan (2026-05)

Status: COMPLETED

Goal:
- fully anonymize participant identities in exported datasets while keeping source datasets untouched.

Scope:

| Step | What | Files affected |
|---|---|---|
| 1 | Rename `sub-XXX` -> `sub-RNDXXX` in folder/file names | `sub-*` directories and files |
| 2 | Replace participant IDs in TSV columns (`participant_id`, `subject_id`) | `participants.tsv` and sidecar TSV files |
| 3 | Replace participant IDs in JSON string values (`IntendedFor`, path references) | JSON sidecars across dataset |
| 4 | Save reversible mapping file outside shared export zip | `code/anonymization_map.json` |

Implementation targets:
- [src/anonymizer.py](src/anonymizer.py)
  - `update_intendedfor_paths(json_data: dict, participant_mapping: dict) -> dict`
- [app/src/web/export_project.py](app/src/web/export_project.py)
  - apply JSON path replacement when `anonymize=true`
- Keep existing UI and blueprint request flags unchanged (existing anonymize checkbox is sufficient).

Execution order:
1. Build/verify deterministic participant mapping generation.
2. Apply path+filename rewrite across copied export tree.
3. Apply TSV column value rewrites (`participant_id`, `subject_id`).
4. Apply JSON string rewrites (including `IntendedFor`, legacy and `bids::` URI styles).
5. Write reversible mapping to `code/anonymization_map.json` outside shared zip.
6. Run focused export tests and full RTK gate.

Checkpoint (2026-05-12):
- Step 1 wiring completed in export adapters: project export sync and async routes now pass deterministic mapping to backend export.
- Covered by blueprint route tests and focused export anonymization tests.
- Step 2/3 integration checks completed: export tests now assert subject_id TSV value rewrites and recursive JSON string-path rewrites (including legacy and bids:: URI path styles).
- Step 2/3 UI/API smoke checks completed: async export UI wiring now explicitly validated for status-path rendering, anonymized filename generation, and non-leakage of mapping metadata in status responses.
- Validation gates: focused export suites pass and full RTK coverage gate passes (85.70%, 2051 passed, 3 skipped).

Definition of done:
- Name/path/TSV/JSON replacements are all consistent in exported copy.
- `IntendedFor` supports both legacy and `bids::` URI styles.
- Mapping file is generated and not shipped in public zip.
- Existing BIDS app compatibility remains intact.
