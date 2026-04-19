# PRISM Studio — Roadmap

## Priority 1.5 — Safe participants merge ✅ DONE

Allow users to merge a new sociodemographic source table into an existing
`participants.tsv` without silently overwriting conflicting participant values.

**What was done:**
- Added canonical backend merge services in `src/participants_backend.py`.
- Added CLI preview/apply flow: `prism_tools.py participants merge`.
- Added full conflict export: `prism_tools.py participants merge --conflicts-csv` and matching Studio download action.
- Merge now matches on canonical `participant_id` values only.
- Merge fills missing existing values, appends new participants, and adds new columns.
- Conflicting non-empty values now block apply and are reported in preview output.
- Applying a merge creates backups of existing `participants.tsv` and `participants.json`.
- Added focused CLI tests and verified the broader participants test set.

**Lessons learned:**
- Merging participant data is a separate workflow from creating a fresh `participants.tsv`.
- `participants.json` enrichment must stay separate from rewriting `participants.tsv` values.
- Preview-first conflict reporting is required for participant-safe merges.
- Conflict previews need a non-truncated export path; the on-screen list is only a summary, not a resolution workflow.

## Priority 1 — Init PRISM on BIDS-valid data ✅ DONE

Allow users to adopt an existing BIDS-valid dataset into PRISM without touching any
existing files.

**What was done:**
- `ProjectManager.init_on_existing_bids()` — validates `dataset_description.json`
  exists, then creates only the missing PRISM artefacts (`.prismrc.json`, `project.json`,
  `contributors.json`, `CITATION.cff`, `.bidsignore`, `CHANGES`, `sourcedata/`,
  `derivatives/`, `code/`). Fully **idempotent** — running it twice creates no files
  the second time.
- Route `POST /api/projects/init-on-bids`
- Third card "Init PRISM on BIDS Dataset" on the Projects page (amber icon)
- All 11 tests pass; smoke-tested idempotency and rejection of non-BIDS folders.

**Lessons learned:**
- Check for `dataset_description.json` (not an empty directory) as the BIDS gate.
- Never overwrite existing files; only create what is missing.

---

## Priority 2 — Export anonymization: participant ID renaming 🚧 TODO

Fully anonymize participant identities when exporting a PRISM/BIDS dataset for sharing.

### Scope

| Step | What | Files affected |
|------|------|----------------|
| 1 | Rename `sub-XXX` → `sub-RNDXXX` in folder/file **names** | all `sub-*/` directories and their files |
| 2 | Replace participant IDs in **TSV columns** (`participant_id`, `subject_id`) | `participants.tsv`, any sidecar `.tsv` |
| 3 | Replace participant IDs inside **JSON values** (`IntendedFor`, fMRI event links, etc.) | fieldmap sidecars (`fmap/`), any BIDS JSON that embeds subject paths |
| 4 | Save a reversible mapping file (`code/anonymization_map.json`) | protected, not included in the shareable export ZIP |

### What "IntendedFor" means and why it matters

BIDS fieldmap JSON sidecars contain a field like:
```json
"IntendedFor": "ses-1/func/sub-001_task-rest_bold.nii.gz"
```
or, in newer BIDS (v1.6+), URI style:
```json
"IntendedFor": "bids::sub-001/ses-1/func/sub-001_task-rest_bold.nii.gz"
```
When `sub-001` is remapped to `sub-R7X2K9`, all these path strings must also be rewritten
or the fieldmap becomes dangling (BIDS-invalid).

### What needs to be built

**`src/anonymizer.py`** — add:
- `update_intendedfor_paths(json_data: dict, participant_mapping: dict) -> dict`
  Scans the `IntendedFor` value (string or list of strings) and replaces any
  occurrence of each original participant ID with its remapped equivalent.
  Handles both legacy path style and `bids::` URI style.

**`app/src/web/export_project.py`** — extend `export_project()`:
- When copying a `.json` file and `anonymize=True`, load the JSON, call
  `update_intendedfor_paths(data, participant_mapping)`, then write.
  (Current code copies JSON without any participant-ID substitution.)

**`app/src/web/blueprints/projects_export_blueprint.py`** — no parameter changes
needed; `anonymize` flag already exists.

**UI** — no changes needed for this step; existing "Randomize Participant IDs"
checkbox already gates the feature.

### Open questions / risks
- `IntendedFor` can appear in _any_ JSON sidecar, not just fieldmaps — scan all JSONs.
- BIDS v1.6+ `"IntendedFor": "bids::sub-001/..."` — regex must match both formats.
- Verify that folder renaming (`sub-001/` → `sub-R7X2K9/`) already works end-to-end
  in `export_project.py` (check `anonymize_filename()` covers directory entries).

---

## Priority 3 — JSON tag stripping and NIfTI GZIP header cleaning ⏳ DEFERRED

Lower priority — useful for hardened clinical sharing but not needed for typical
research data exchange.

### JSON tag stripping
Remove known identifying fields from NIfTI sidecar `.json` files:
`AcquisitionTime`, `PatientName`, `PatientBirthDate`, `InstitutionName`,
`DeviceSerialNumber`, `StationName`, and similar.

Add `DEFAULT_IDENTIFYING_BIDS_TAGS` + `strip_bids_json_tags()` to `src/anonymizer.py`.  
Add "Remove Identifying BIDS Tags" accordion to export UI.

### NIfTI GZIP header cleaning
`.nii.gz` files can embed an **original filename** (`FNAME`) and a **compression
timestamp** (`MTIME`) in the GZIP header itself — invisible to the researcher but
readable with any hex editor or GZIP tool.

Port `gz_header_cleaner.py` logic (see `MRI-Lab-Graz/datalad` repo, same author,
MIT) into `src/anonymizer.py` as `clean_nifti_gz_headers(dataset_path)`.  
Invoke during export when the "Deface / Clean NIfTI headers" option is enabled.

### Defacing (structural MRI)
Integrate an optional external defacing step (`pydeface`, `mri_deface`, or
`deepdefacer`) for `*_T1w.nii.gz`, `*_T2w.nii.gz`, `*_FLAIR.nii.gz` files.  
Check tool availability via `shutil.which()` before showing the option in the UI.

---

## Lessons Learned

- `app/src/` is a thin adapter — all new anonymization logic goes into `src/`.
- Never modify source files during export — always write to a temp directory first,
  then ZIP.
- The `create_participant_mapping()` function in `src/anonymizer.py` already handles
  deterministic seeding; reuse it rather than adding a new ID generator.
- `export_project.py` walks `sub-*/` dirs but currently only renames filenames,
  not folder-embedded IDs inside JSON values — that is the core gap for Priority 2.
