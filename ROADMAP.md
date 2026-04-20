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

## Priority 1.10 — Template Editor import and delete must leave a coherent editor state ✅ DONE

Harden Template Editor state transitions so failed imports, invalid imported
templates, and project-template deletion do not strand the user in a stale or
misleading UI state.

**What was done:**
- Updated Template Editor validation so invalid templates keep JSON download
  enabled instead of trapping imported work behind a disabled export button.
- Added editor-state capture/restore around template import so transport or
  parsing failures restore the previous editor state instead of leaving the page
  half-disabled.
- Split post-import validation from the import transaction so a validation API
  failure no longer shows up as a false "import failed" error after the template
  was already loaded.
- Cleared and re-rendered editor state after deleting a project template so the
  item list, preview, and selected-item panel no longer show deleted content.
- Added workflow wiring coverage for import-state restoration and delete-state
  cleanup, then re-ran the existing Template Editor save-path/variant suite.

**Lessons learned:**
- Import, validate, and save are separate states in the Template Editor; treating
  validation as part of import produces misleading failures and stale controls.
- After destructive actions like delete, clearing internal state is not enough;
  the editor must re-render immediately or the UI continues to display content
  that no longer exists on disk.

## Priority 1.11 — Template Editor save/delete must follow the visible project ✅ DONE

Prevent the Template Editor from showing project A while save/delete/list actions
quietly operate on project B after a global project switch.

**What was done:**
- Added explicit `project_path` support to Template Editor project-bound backend
  routes for merged-list loading, save, and delete operations.
- Updated the Template Editor frontend to send the active project path explicitly
  for save/delete and project-library list refreshes.
- Added project-context invalidation in the frontend so stale list/load/validate
  responses from an older project context are ignored.
- Added `prism-project-changed` handling to refresh project-library state when the
  active project changes while the Template Editor stays open.
- Detached loaded project templates into drafts when the active project changes,
  preventing in-place overwrite/delete actions from silently retargeting a new
  project.
- Added focused backend tests for explicit project targeting and workflow wiring
  coverage for the project-switch invalidation path.

**Lessons learned:**
- In the Template Editor, project library state is page-scoped, not session-safe;
  once the visible project can change independently, backend writes must carry an
  explicit project path.
- Project switches are not just a list-refresh event: any currently loaded
  project template must either stay bound to its original project or be detached
  into a neutral draft state before the user can save again.

## Priority 1.12 — Template Editor schema switch must refresh validation badges ✅ DONE

Keep Template Editor file-status badges aligned with the currently selected
schema version.

**What was done:**
- Updated the schema-version change handler in the Template Editor to refresh the
  merged template list before loading the blank template for the new schema.
- Added workflow wiring coverage so future schema switches keep the
  schema-version-aware `[FILE OK]` and `[FILE !]` badges in sync with the active
  validator.

**Lessons learned:**
- In the Template Editor, schema version affects more than the blank template
  factory; it also drives the validation status shown in the project/global
  template dropdowns, so schema changes must refresh that list too.

## Priority 1.13 — Template Editor control state must revert on cancelled or failed source changes ✅ DONE

Keep the Template Editor controls aligned with the template that is actually
loaded when users cancel or hit backend failures during source changes.

**What was done:**
- Added tracked previous values for the modality and schema selectors so the
  first cancelled switch restores the visible control instead of leaving it on a
  value the editor never applied.
- Restored the active schema after failed modality/schema switches so the still-
  visible template is not validated or rendered against the wrong schema.
- Added rollback for failed project/global template loads so the previous
  selection, buttons, and editor state are restored if the new load fails.
- Added an unsaved-changes confirmation plus rollback protection for `Create
  Blank Template`, which previously discarded the current template without the
  same safeguards used by import and other switches.
- Extended workflow wiring coverage and re-ran the Template Editor regression
  slice after each state-path hardening pass.

**Lessons learned:**
- In the Template Editor, a changed `<select>` value is not proof that the
  editor state changed; cancelled or failed source switches must restore both
  control state and backing editor state together.
- Any action that replaces the current template, including "create blank", is a
  destructive source change and should follow the same unsaved-change and
  rollback rules as import or template switching.

## Priority 1.14 — File Management project copy must follow the visible project ✅ DONE

Keep File Management organizer and renamer copy-to-project actions bound to the
project the page is actually targeting, including during long multi-file copy
batches.

**What was done:**
- Added explicit `project_path` support in the File Management backend handlers
  for batch convert and physio rename so copy-to-project requests no longer rely
  on session state alone.
- Updated the File Management frontend to resolve the active project path,
  disable organizer/renamer copy buttons when no project is active, and send
  `project_path` with project-bound requests.
- Added a `prism-project-changed` listener so the copy controls immediately
  refresh when the active project changes while the page stays open.
- Locked renamer sequential copy batches to the project path that was active at
  batch start so one run cannot silently split files across two projects after a
  mid-run project switch.
- Added focused save-path and workflow-wiring regressions for explicit project
  targeting, no-project guards, and sequential-copy batch locking; the slice now
  passes green.

**Lessons learned:**
- On long-lived pages, disabling a project-bound action when no project is open
  is necessary but not sufficient; the request still needs to carry an explicit
  `project_path` so backend work cannot drift to whatever the session points to
  later.
- Multi-request operations like sequential renamer copy must lock the project
  target for the whole batch, otherwise a project switch mid-run can scatter one
  user action across multiple project roots.

## Priority 1.15 — File Management wide-to-long save must target the active project ✅ DONE

Keep the File Management wide-to-long save flow aligned with the visible
project instead of falling back to session drift or mismatched route behavior.

**What was done:**
- Updated the wide-to-long frontend to resolve the active project path, disable
  `Convert & Save to Project` when no project is active, and send `project_path`
  with the conversion request.
- Added a no-project frontend guard so a project switch away from the page no
  longer falls through to a backend download response that the UI cannot parse
  as JSON.
- Updated the wide-to-long backend route to accept explicit `project_path` and
  validate it with the same stale-project checks used by the other File
  Management save flows.
- Preserved backward-compatible download behavior for callers that do not target
  a project at all, while making stale project saves fail clearly instead of
  surfacing a generic file-write error.
- Added focused workflow-wiring and web-backend tests for explicit project
  targeting and stale-project rejection; the File Management plus wide-to-long
  slice now passes green.

**Lessons learned:**
- If a page-level action is labeled as saving to the current project, its
  frontend state and backend response contract must agree; leaving a download
  fallback active behind a JSON-only UI path creates a hidden failure mode after
  project changes.
- Route compatibility can be preserved without trusting session state: explicit
  `project_path` should be preferred for page-bound saves, while projectless
  callers can keep their legacy download behavior.

## Priority 1.16 — JSON Editor autoload must follow the real project root ✅ DONE

Keep the JSON Editor’s project-backed autoload and schema requests working when
the active project is tracked via `project.json` paths or the desktop app is
running in packaged file mode.

**What was done:**
- Updated the JSON Editor blueprint adapter to resolve the session project path
  to the real project root before handing it to the embedded file manager, so
  `current_project_path=/path/to/project.json` works the same as a directory
  path.
- Cleared the embedded file manager’s active dataset when the session project
  path becomes stale or disappears, preventing one request from reusing the
  previous project’s folder on the next request.
- Added a local `fetchWithApiFallback(...)` helper to the plain JSON Editor page
  and moved project file/schema loads onto it so packaged desktop/file-mode can
  still reach `/editor/api/...` routes.
- Added focused backend and wiring regressions for `project.json` session paths,
  stale-project clearing, and `/editor/api/...` fallback usage; the JSON Editor
  slice now passes green.

**Lessons learned:**
- Embedded helper apps with long-lived manager objects need the same project-root
  normalization as the main web blueprints; otherwise `project.json` session
  paths fail even though the rest of the UI treats them as valid project
  selections.
- A stale session project is not a harmless error for stateful adapters: if the
  adapter keeps its previous folder in memory, the next request can silently act
  on the wrong project.

## Priority 1.17 — Specifications quick links must react to project changes ✅ DONE

Keep the Specifications page’s project-bound derivative shortcuts aligned with
the active project while the page stays open.

**What was done:**
- Added stable DOM hooks and enabled-URL metadata for the Specifications page’s
  Survey Export and Recipes quick links.
- Added a small page script that tracks the initial project path from the
  rendered page state and listens for `prism-project-changed` events.
- Updated the derivative quick links in place when the active project changes so
  they no longer stay disabled after a project is opened or remain clickable
  after a project is cleared.
- Added workflow-wiring coverage for the page-level project-change listener and
  the derivative-link enable/disable logic; the slice passes green.

**Lessons learned:**
- Informational pages can still hold workflow bugs when they expose project-bound
  shortcuts; server-rendered disabled states are not enough once the global
  navbar can change the active project without forcing a reload.
- Small page scripts are often the least disruptive fix for static templates that
  need to follow global project state events.

## Priority 1.18 — Survey Export library state must follow the visible project ✅ DONE

Keep the Survey Export page’s merged library and export selections aligned with
the active project while the page stays open.

**What was done:**
- Updated the merged library handler to normalize `project.json` session paths,
  accept explicit `project_path`, and skip session fallback when the frontend
  explicitly requests a projectless library refresh.
- Updated the Survey Export frontend to resolve the active project path, reload
  the merged library on `prism-project-changed`, and ignore late library
  responses that belong to an older project state.
- Added a page-local `fetchWithApiFallback(...)` helper and moved the library,
  boilerplate, and quick-export requests onto it so the plain-script page also
  works in packaged/file-mode.
- Added focused handler and workflow-wiring regressions for explicit project
  targeting, `project.json` normalization, empty-project refreshes, stale-load
  guards, and API fallback usage; the Survey Export slice now passes green.

**Lessons learned:**
- On long-lived export pages, stale library data is more dangerous than a stale
  label: if selections are stored as absolute template paths, a project switch
  can silently keep exporting project A while the rest of the app shows project
  B.
- Library reload endpoints need the same explicit-project-path contract as other
  page-scoped actions, otherwise a cleared or changed project can fall back to
  whatever the server session last pointed at.

## Priority 1.19 — Survey Customizer save-to-project must stay tied to the loaded project ✅ DONE

Keep Survey Customizer’s save-to-project flow from copying templates into the
wrong project after project changes or stale session paths.

**What was done:**
- Updated Survey Export to store the active project path in the
  `surveyCustomizerData` session payload so Survey Customizer can tell which
  project the loaded template state came from.
- Updated Survey Customizer to resolve the current project path, react to
  `prism-project-changed`, disable and clear the save-to-project checkbox when
  the active project no longer matches the loaded customization state, and send
  explicit `project_path` with project-bound exports.
- Added page-local API fallback for Survey Customizer load/export requests so
  the plain-script page remains compatible with packaged/file-mode.
- Updated the Survey Customizer export route and backend handler to prefer an
  explicit `project_path`, normalize `project.json` paths to the real project
  root, and reject stale project paths instead of creating `code/library` under
  a missing or invalid location.
- Added focused save-path and workflow-wiring regressions for explicit project
  targeting, `project.json` normalization, stale-path rejection, and the
  source-project guard; the Survey Export plus Customizer slice now passes green.

**Lessons learned:**
- Wizard-style pages that load state from `sessionStorage` still need to carry
  the originating project context forward; otherwise a later project switch can
  make a valid save action target the wrong project even when the visible form
  still looks coherent.
- Project-bound copy flows should never create directories from unchecked raw
  session paths; they must resolve to an existing project root first or fail
  clearly.

## Priority 1.20 — Recipe Builder must reset on project changes and reject orphan saves ✅ DONE

Keep Recipe Builder from carrying a stale selected task across project switches
and saving recipes into a dataset that does not actually contain that survey
template.

**What was done:**
- Updated Recipe Builder to resolve the current project path explicitly, reset
  its loaded template/builder state on `prism-project-changed`, clear the stale
  selected task and metadata, and reload the survey template list for the new
  project instead of leaving the previous picker state in place.
- Added clearer survey-picker placeholders for loading and no-project states so
  a cleared or switched project does not leave an apparently valid template
  selection behind.
- Updated the Recipe Builder save handler to verify that `Survey.TaskName`
  exists in the target project or official library before writing
  `code/recipes/survey/recipe-*.json`, preventing orphan recipe saves after a
  cross-project switch.
- Added focused handler and workflow-wiring regressions for the project-change
  reset behavior and the missing-template save rejection; the Recipe Builder
  test slice now passes green.

**Lessons learned:**
- Hiding a stale builder panel is not enough when the selected entity is still
  stored in page state; project switches must clear the underlying selection so
  later save actions cannot reuse it silently.
- Recipe save endpoints need contextual validation against available templates,
  not just JSON schema validation, because a structurally valid recipe can still
  be semantically orphaned in the wrong dataset.

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
