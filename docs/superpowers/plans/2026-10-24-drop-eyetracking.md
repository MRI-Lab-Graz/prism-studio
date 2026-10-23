# Drop PRISM's own eyetracking modality; eye tracking goes through BIDS (eye2bids) — Plan

> Written 2026-10-23 so the work can continue on another computer. Nothing of this plan is built yet.
> Follow the repo rules in `CLAUDE.md`: TDD, one implementation in the backend/CLI (the GUI only calls it),
> vendored specification files are edited in prism-specification only, ponytail audit before merging, no `git stash`,
> ask before pushing/tagging.

## Decision (user, 2026-10-23)

- **Drop the `eyetracking` modality completely.** There is no eye-tracking data in any PRISM project, so nothing needs
  a migration path and nobody is hurt. (If a project still has an `eyetracking/` folder, the validator says what to do;
  that is a message, not a compatibility layer.)
- **Use the `eye2bids` converter** (https://github.com/bids-standard/eye2bids, MIT) instead of writing our own.
  Vendor-specific files (EyeLink `.edf`) are converted to BIDS TSV, like DICOM to NIfTI. The raw files stay as
  untouched `sourcedata/`.
- **Update 2026-10-23: no converter for now.** The eye2bids spike (below) showed it is not on PyPI and needs EyeLink's
  proprietary Developers Kit (`edf2asc`) for `.edf`. So this work only drops the modality; B3 is deferred
  (see "Later: eyetracking converter"). The validator message points users to eye2bids and BIDS physio.
- Physio stays as decided in the physio branch: `physio/` = task-free PRISM recordings; task-bound recordings use BIDS.

## What BIDS says (Eye-Tracking-BIDS, BEP20, bioRxiv 10.64898/2026.02.03.703514; part of BIDS **1.11.0**)

- Gaze data: `sub-<l>[_ses-<l>]_task-<l>_recording-<label>_physio.tsv.gz` + `.json`; `recording-<label>` is required
  (`eye1`, `eye2` recommended); optional `..._recording-<label>_physioevents.tsv.gz` + `.json` (device messages,
  fixations, saccades, blinks; `OnsetSource` in the sidecar).
- Stored in the datatype folder of the main recording (`func/`, `eeg/`, ...); if eye tracking is the only modality:
  `beh/`. `func/` and `beh/` require `task-`, so BIDS has no folder for a task-free eye recording.
- Physio sidecar: `PhysioType: "eyetrack"`, `SamplingFrequency`, `StartTime`, `Columns`, `RecordedEye`
  (`left|right|cyclopean`), `SampleCoordinateSystem` (`gaze-on-screen|eye-in-head|gaze-in-world|custom`), `Units` for
  `x_coordinate`/`y_coordinate`. TSV columns: `timestamp`, `x_coordinate`, `y_coordinate` first, `pupil_size` optional.
- With `gaze-on-screen`, the task `_events.json` needs `StimulusPresentation.ScreenDistance/ScreenOrigin/ScreenResolution/ScreenSize`.
- Examples: bids-examples `eyetracking_fmri`, `eyetracking_binocular`.

## What exists today (checked 2026-10-23)

- Studio, `app/schemas/stable/entities.schema.json`: `eyetracking` is a `bidsPassthrough` modality (own folder
  `eyetracking/`, suffixes `eyetrack|eye|gaze`, entity `trackedEye`, extensions `tsv|tsv.gz|json|edf|asc`).
- Vendored from prism-specification (do not edit in Studio): `app/schemas/stable/eyetracking.schema.json` (1.1.0),
  `app/schemas/v0.2/eyetracking.schema.json`, `docs/specs/eyetracking.md`, the `eyetracking` entries in
  `entities.schema.json`, `docs/specs/entities.md`, `project.schema.json` (version-pin key).
- prism-specification: `schemas/stable/eyetracking.schema.json`, `schemas/v0.2/eyetracking.schema.json`,
  `specs/eyetracking.md`, `specs/entities.md`, `schemas/stable/entities.schema.json`, `scripts/generate_schema_reference.py`
  (mentions it), `README.md`.
- Studio code that mentions eyetracking (about 45 files; `grep -rli eyetrack` outside `docs/superpowers`): the converter
  page and script (`app/templates/converter_eyetracking.html`, `app/static/js/modules/converter/eyetracking.js`,
  `converter-bootstrap.js`, `converter.html`), `app/src/web/blueprints/conversion*.py`,
  `conversion_physio_handlers.py`, `projects*.py`, `upload.py`, `path_utils.py`, `spec_docs.py`, `runner.py`,
  `stats.py`, `reporting*.py`, `readme_generator.py`, `fixer.py`, `issues.py`, `bids_integration.py`,
  `project_manager.py`, the CLI (`app/src/cli/parser.py` `convert physio` choice `eyetracking`, `commands/file_management.py`,
  the physio batch rename), and tests (`tests/test_eyetracking_bids_passthrough.py`, `test_physio_renamer.py`,
  `test_batch_convert_*`, `test_project_manager*`, `test_entity_rules_write_path.py`, `test_bids_validator.py`,
  `test_modality_proposal_check.py`, `test_spec_docs.py`, `test_specification_boundaries.py`, ...).

## Open questions to settle first (spike, in a scratch folder, no repo change)

1. **eye2bids:** install it (`pip install eye2bids`, check the PyPI name and Python versions), run it on an example
   EyeLink `.edf`/`.asc` (get a sample from the eye2bids repo tests or bids-examples). Find out:
   - does it need EyeLink's `edf2asc` (proprietary developer kit)? Then: how do users get it, and does Studio detect it
     and say so?
   - Windows and macOS support; install size; whether it is a library (importable function) or only a CLI.
   - what it writes (folder, entities) and which options it needs (task name, `--metadata_file` for the fields the
     device does not provide, e.g. screen size/distance).
2. **BIDS version:** which `BIDSVersion` does Studio write and which bids-validator does it bundle? Eye tracking needs
   1.11.0; check `dataset_description` handling, `app/src/bids_integration.py` and the Deno validator version.
3. **Wheel/Docker/frozen build:** if eye2bids is an optional dependency, how is it installed (extras? separate install
   hint)? The validator image must not need it (validation never converts). Keep it out of the validator wheel.

Decision rule (ponytail): call eye2bids (import if it is a library, else subprocess with an argument list, never a shell
string) as an **optional** dependency of the converter; Studio detects "not installed" and prints the install command.
Do not copy its logic. If it cannot run without a proprietary tool, say so in the message and in the docs.

## Part A — prism-specification (branch `feat/retire-eyetracking`)

Files: delete `schemas/stable/eyetracking.schema.json` (archive it as `schemas/archive/eyetracking/1.1.0.schema.json`
per the repo's release rule, check `CONTRIBUTING.md`), `schemas/v0.2/eyetracking.schema.json`, `specs/eyetracking.md`;
edit `schemas/stable/entities.schema.json` (remove the `eyetracking` modality), `specs/entities.md`,
`scripts/generate_schema_reference.py`, `README.md`; tests that list modalities.

- [ ] Write failing tests (the modality list no longer has eyetracking; `check_schema_versions.py` is satisfied by the
      archive; the spec tables are in sync).
- [ ] Remove, run the full suite and `scripts/check_schema_versions.py`, `generate_schema_reference.py --check`.
- [ ] Docs: `CONTRIBUTING.md`/changelog note: "eye tracking is BIDS physio with `PhysioType: eyetrack`, see BIDS 1.11".
- [ ] **Ask the user** before merge/push/tag. Release tag: this is a content change, so a **minor** tag (the user wants
      patch tags for tooling and minor tags for content): v1.3.0, unless the user says otherwise.

## Part B — Studio (branch `feat/drop-eyetracking`, after Part A is released)

- [ ] **B1 Sync** `python scripts/sync_specification.py --tag v1.3.0`; fix `tests/test_vendored_specification.py` (lock tag).
- [ ] **B2 Validator:** an `eyetracking/` folder is reported like `physiological/` and `events/` (look at how the physio
      branch did it: `grep -rn "physiological" app/src/validator.py app/src/issues.py`): an error/warning with the exact
      conversion command. Remove `eyetracking` from the modality lists the validator, `project_manager.py`,
      `runner.py`, `stats.py`, `reporting*.py`, `path_utils.py`, `upload.py`, `bids_integration.py` still carry (per
      CLAUDE.md "Validation reads one current specification": derive from `current_specification()`, no hand lists).
      Test first: a project with `eyetracking/` gets the message; a project with BIDS physio `recording-eye1` in
      `func/` passes PRISM and the BIDS validator.
- [ ] ~~**B3 Converter (backend/CLI first):** a command, e.g. `prism_tools.py convert eyetracking --input <file or folder>
      --project <project> --task <task> [--session ...] [--datatype func|beh|eeg] [--metadata <json>] [--json]`, one function in
      `src/` that calls eye2bids and places the result in the project (BIDS names, `task-` required, raw file copied
      to `sourcedata/` unchanged, text-file/annex policy untouched). The GUI converter page
      (`converter_eyetracking.html`, `modules/converter/eyetracking.js`) becomes a thin caller of the same function
      (same options as the CLI). Not installed → exit 1 with the install command. Test first with a tiny fixture and a
      fake/stub of the eye2bids call; one real run is the spike.~~ **Deferred, see Later.**
- [ ] **B4 Remove the old code:** the `eyetracking` choice of `convert physio`, the physio batch converter/renamer
      parts for eyetracking, `readme_generator.py`, `fixer.py`, home/structure templates, `file_management` pieces,
      `app/schemas/README.md`, tests of the passthrough (`tests/test_eyetracking_bids_passthrough.py` becomes a test of
      the new rule, or is deleted), `project.schema.json` pin key if it is vendored (comes with the sync).
- [ ] **B5 Docs:** `docs/CLI_REFERENCE.md` (new command, removed choice), `docs/studio/` converter page, `docs/specs`
      (comes with the sync), `CHANGELOG.md`, memory note update.
- [ ] **B6 Checks:** full suite (`python3 -m pytest tests -q -p no:cacheprovider --ignore=tests/e2e`, about 3 minutes, run
      it in the background), e2e flows of the converter page, `python3 tests/verify_repo.py --check import-boundaries,dual-tree-drift,modality-docs,ruff,mypy,unsafe-patterns --no-fix`
      (delete the report file it writes), `python3 scripts/ci/check_specification_lock.py`, `/ponytail:ponytail-audit`
      on the branch, then ask before merging and pushing.

## Afterwards (separate, from the user's earlier idea)

Audit the other modalities against BIDS the same way (`environment`, `biometrics`, `events`, `biosample`), asking for
each: does BIDS already specify this? Then layer 1 of the specification contributions design (new modality).

## Where things stand (2026-10-23)

- Layer 2 (additions to a modality) is merged and pushed in Studio main; prism-specification is at v1.2.2, CI green.
- Memory note with the BIDS facts: `eyetracking-drop-bids.md` (Claude's project memory; it does not travel, this plan does).

## Later: eyetracking converter (spike findings 2026-10-23)

Do this only when someone has real `.edf` files. The old B3 text above is the design.
- eye2bids (https://github.com/bids-standard/eye2bids, MIT) is **not on PyPI**: `pip install eye2bids` fails. Install is
  `pip install git+https://github.com/bids-standard/eye2bids.git` (awkward for the frozen/bundled Studio).
- Converting EyeLink `.edf` needs the proprietary **EyeLink Developers Kit** (`edf2asc`); README gives an apt route for
  Ubuntu only. macOS/Windows route not checked.
- Interface is a CLI: `eye2bids --input_file F [--metadata_file meta.yml] [--output_dir D] [-f]`; without a metadata YAML
  `-f` writes invalid BIDS. Not checked whether it has an importable function. Deps: numpy, pandas>2, pyaml, rich.
- Studio should detect "not installed", print the install steps, and call it with an argument list (never a shell string).
