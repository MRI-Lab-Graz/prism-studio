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

## Priority 1.6 — Overlap-safe export anonymization ✅ DONE

Harden anonymized export workflows so overlapping participant IDs do not corrupt
ZIP paths or embedded JSON references.

**What was done:**
- Added canonical backend replacement logic in `src/anonymizer.py` that treats
  participant IDs as bounded tokens instead of raw substrings.
- Updated Projects export filename/path anonymization to use the shared backend
  helper.
- Updated CLI anonymization path rewriting to use the same overlap-safe helper.
- Added a regression test covering `sub-01` and `sub-010` in the same export,
  including a BIDS URI `IntendedFor` reference.

**Lessons learned:**
- Raw substring replacement is unsafe for BIDS entity labels because common IDs
  can be prefixes of other valid IDs.
- Exported filenames, archive paths, and JSON references must share one
  replacement primitive or the anonymized dataset becomes internally
  inconsistent.

## Priority 1.7 — Async export cancellation and cleanup hardening ✅ DONE

Harden the Projects export workflow so GUI cancellation matches backend state and
export ZIP lifecycle does not leak or delete the wrong file.

**What was done:**
- Fixed the Projects page export flow so cancelling before the async start call
  returns still sends a deferred cancel request once the job ID becomes known.
- Added TTL pruning for completed/cancelled/errored export jobs so status-store
  entries do not accumulate forever.
- Fixed synchronous `/api/projects/export` to delete its temporary ZIP after the
  download response closes.
- Fixed async `/api/projects/export/<job_id>/download` to clean up only job
  metadata after download instead of deleting the user-saved export ZIP.
- Added focused backend tests plus frontend wiring coverage for the deferred
  cancel path.

**Lessons learned:**
- A cancel button is not a real cancellation path until it survives the gap
  between optimistic UI state and the backend returning a job identifier.
- Export jobs differ from converter temp artifacts because the async export ZIP
  is a user-requested output, not a disposable server-side intermediate.

## Priority 1.8 — Export preferences must stay bound to the active project ✅ DONE

Prevent export filter and output-folder preferences from leaking across project
switches, slow responses, or multi-tab session drift.

**What was done:**
- Added explicit `project_path` targeting to the project preferences GET/POST
  handlers so the export page can read and write preferences for the intended
  project instead of relying only on session state.
- Added a dedicated export-preferences load token in the Projects export module
  so late responses from an older project cannot repaint the current project's
  filters or output folder.
- Updated export preference saves to send the active project path explicitly.
- Added handler tests covering explicit-project preference reads/writes and
  frontend wiring coverage for stale-response guards.

**Lessons learned:**
- Session-backed `current_project_path` is not a sufficient source of truth for
  page-scoped preferences once multiple tabs or fast project switches are in
  play.
- Structure-loading race protection and preference-loading race protection must
  be separate; guarding one does not protect the other.

## Priority 1.9 — Metadata and methods actions must target the visible project ✅ DONE

Harden the remaining Projects page actions so metadata, citation, schema, README,
and methods generation follow the visible project instead of stale session state
or stale frontend responses.

**What was done:**
- Added a shared backend helper to resolve either an explicit `project_path` or
  the current session project, then wired schema-config, dataset-description,
  study-metadata, citation, methods generation, and README generation handlers
  through it.
- Updated the Projects metadata module to use desktop/file-mode API fallback for
  all project actions that were still using raw `fetch('/api/...')` calls.
- Updated metadata/methods frontend requests to send the active `project_path`
  explicitly for project-bound operations.
- Added stale-load guards for metadata/schema/description reloads so late
  responses from a previous project cannot repaint the current form.
- Reset methods preview state on project switch and guarded generated-methods
  responses so project A output cannot remain visible on project B.
- Added focused handler tests plus frontend wiring coverage for explicit project
  targeting and fallback usage.

**Lessons learned:**
- On the Projects page, session state is only a fallback; once the frontend
  already knows the active project, requests should carry that path explicitly.
- Export was not the only async stale-state surface; metadata reloads and cached
  methods previews can leak across project switches unless they are explicitly
  invalidated.

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
