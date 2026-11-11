# Biosample Template and Importer Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A user can generate an Excel template, fill it with biosample results of any specimen type, and import it into a project as valid `biosample` TSV + sidecar files, from the CLI and from the Studio importer page with identical results.

**Architecture:** One backend module family in `src/` (template generator, template reader/normaliser, pivot-and-write importer) exposed as `prism_tools.py biosample template|import`. The Studio route only saves the upload, calls the same function and shows its result. The migration of the legacy wide sheet is a separate plan (Step 2 of the spec).

**Tech Stack:** Python stdlib, pandas and openpyxl (already used by the biometrics Excel importer), pytest. No new dependency.

**Spec:** `docs/superpowers/specs/2026-11-11-biosample-importer-design.md` (this plan = "Order of work" step 1; the migration is not in this plan).

## Global Constraints

- Template sheet `data`: `participant_id, session, panel, run, sample_id, collection_time, analyte, value, unit, comment`. Sheet `panels`: `panel, SpecimenType, CollectionMethod, Anticoagulant, FastingRequired, StorageTemperature, Laboratory, AssayMethod, AssayKit, Description`.
- Output file names: `sub-<label>[_ses-<label>]_biosample-<panel>[_run-<n>]_biosample.<tsv|json>`; panel is alphanumeric; one file per subject/session/run/panel; one row per sample, one column per analyte; sidecar per file.
- Cell codes: `n/a`, `<LOD`, `<LLOQ`, `>ULOQ`. A bare `<5` is written `<LOD`, with `LowerLimitOfDetection` (the highest limit seen in that column) in the sidecar and every limit seen in the report (provisional, to be confirmed with the lab; one place in the normaliser).
- Comma decimals become points; float noise is rounded (`2.0099999999999998` becomes `2.01`); raw values are never substituted.
- `collection_time` is `hh:mm` only; a date in it is an error (dates identify people).
- A sample is one distinct `(sample_id, collection_time)` pair, either may be empty. Empty `run` means no `run-` entity. The same subject/session/run/panel/sample/analyte twice is an error.
- Sessions are exact strings (`T4.1`, `1`, `01` differ); single-timepoint projects map through `src/session_map.py` (`resolve_import_session`), which reports it. In a `multiple` project an empty session is an error.
- Unit: a column with neither `Term` nor `Units` is an error; a unit different from the term's recommended unit is accepted with an info, never converted; two units for one analyte in one panel are an error.
- Specimen type: from the `panels` sheet, else `--specimen`, else an error. `SpecimenType`, `CollectionMethod`, `Anticoagulant` pull-downs come from `app/schemas/stable/biosample.schema.json`, never hand-listed.
- Re-import refuses to overwrite existing biosample files unless `--overwrite`; `--dry-run` writes nothing and lists the files.
- Text-file policy: nothing written is annexed (do not touch `.gitattributes` logic).
- Logic in `src/`; the Studio route in `app/src/web/**` holds none. Check `find src -name '<file>.py'` against `app/src/` before editing any shared module. The vendored specification is not edited.
- TDD per `CLAUDE.md`. Before the merge: `/ponytail:ponytail-audit`, `/code-review`, `superpowers:verification-before-completion`. Work in a worktree branched from `docs/biosample-importer-design`.

## Review Focus

1. A `value` cell with a comma decimal, a trailing space, an Excel date or a float like `2.0099999999999998`: becomes a clean number or an error naming the row, never a mangled value (Task 2).
2. A sheet with extra, missing or renamed columns, or a missing `panels` sheet: one message naming the problem, no traceback (Task 2).
3. Two different limits (`<5` and `<2`) for one analyte: sidecar keeps the highest, report lists both (Task 2).
4. Re-running the same import: refused without `--overwrite`, byte-identical files with it (Task 3).
5. A participant that is not in `participants.tsv`: written, with a warning, no participant created (Task 3).

---

### Task 1: Generate the Excel template

**Files:**
- Create: `src/biosample_template.py`
- Test: `tests/test_biosample_template.py`

**Interfaces:**
- Produces: `write_biosample_template(path: Path) -> None`. Writes the two sheets above with a header row and pull-downs (openpyxl data validation) for `SpecimenType`, `CollectionMethod`, `Anticoagulant` read from the schema, and for `FastingRequired` (`true`/`false`).

- [ ] **Step 1: Failing test** `test_template_has_both_sheets_and_schema_pulldowns`: after `write_biosample_template`, the workbook has sheets `data` and `panels`, the header rows equal the lists in Global Constraints, and the `SpecimenType` validation list equals the schema enum (`whole-blood` ... `other`).
- [ ] **Step 2: Run it, expect FAIL** (`pytest tests/test_biosample_template.py -v`: module missing).
- [ ] **Step 3: Implement `write_biosample_template`** reading the enums from the schema file at call time.
- [ ] **Step 4: Run it, expect PASS.**
- [ ] **Step 5: Commit** `feat(biosample): Excel template generated from the schema`.

### Task 2: Read, normalise and validate the template

**Files:**
- Create: `src/biosample_template_reader.py`
- Test: `tests/test_biosample_template_reader.py`

**Interfaces:**
- Consumes: Task 1's column lists (export them as `DATA_COLUMNS`, `PANEL_COLUMNS` tuples from `src/biosample_template.py`).
- Produces:
  - `normalise_value(raw: object) -> tuple[str, float | None]`: `("<LOD", 5.0)` for `"<5"` and `"<0,05"`, `("2.01", None)` for `2.0099999999999998`, `("n/a", None)` for empty, `("<LLOQ", None)`, `(">ULOQ", None)` kept; raises `ValueError` with a readable message otherwise.
  - `read_template(path: Path, specimen: str | None = None) -> tuple[list[dict], dict[str, dict], list[str]]`: (measurement rows, panel definitions by name, problems). Accepts `.xlsx`, `.csv` (data only, panels from `specimen`). Problems are strings with sheet and row; never raises for bad content.

- [ ] **Step 1: Failing tests** for each Review Focus 1 to 3 case plus: unknown columns, missing `panels` sheet with no `--specimen`, a date in `collection_time`, mixed units for one analyte in one panel, empty specimen.
- [ ] **Step 2: Run, expect FAIL.**
- [ ] **Step 3: Implement** both functions; limits collected per analyte and returned with the panel (`panels[name]["limits"][analyte]` = every limit seen).
- [ ] **Step 4: Run, expect PASS.**
- [ ] **Step 5: Commit** `feat(biosample): read and normalise the template`.

### Task 3: Pivot and write into a project

**Files:**
- Create: `src/biosample_import.py`
- Test: `tests/test_biosample_import.py`

**Interfaces:**
- Consumes: `read_template` (Task 2); `src.term_registry.load_registry("biosample")` and `resolve_column(registry, column, col_def, specimen)`; `src.session_map.resolve_import_session(project, label)`; `src.subject_id_matching.load_existing_participant_ids` for the participant check.
- Produces: `import_biosample(input_path: Path, project: Path, specimen: str | None = None, overwrite: bool = False, dry_run: bool = False) -> ImportResult` where `ImportResult` is a dataclass `(written: list[str], skipped: list[str], warnings: list[str], errors: list[str])` of project-relative paths and messages. Sidecar keys per analyte column: `Description`, `Units`, `Term` (when resolved), `LowerLimitOfDetection`; `Technical`, `Study` (`BiosampleName` = panel), `Metadata` (`SchemaVersion`, `CreationDate` = today).

- [ ] **Step 1: Failing tests** with a small template built in `tmp_path` and a minimal project (`project.json` with `StudyDesign.Timepoints`, `participants.tsv`): `test_writes_one_tsv_and_sidecar_per_subject_session_panel`, `test_two_runs_give_two_files`, `test_duplicate_measurement_is_an_error`, `test_reimport_refused_then_identical_with_overwrite` (Review Focus 4), `test_unknown_participant_written_with_warning` (5), `test_dry_run_writes_nothing`, `test_single_timepoint_project_maps_session_and_reports_it`, `test_written_files_pass_the_validator` (run the project validator on the output).
- [ ] **Step 2: Run, expect FAIL.**
- [ ] **Step 3: Implement `import_biosample`**: group rows by (subject, session, run, panel), pivot to one row per sample, write via temp files then move so a failure leaves nothing half-written.
- [ ] **Step 4: Run, expect PASS.**
- [ ] **Step 5: Commit** `feat(biosample): import the template into a project`.

### Task 4: CLI `biosample template` and `biosample import`

**Files:**
- Create: `app/src/cli/commands/biosample.py` (mirror `app/src/cli/commands/biometrics.py`)
- Modify: `app/src/cli/parser.py`, `app/src/cli/dispatch.py`, `app/src/cli/entrypoint.py` (register next to `biometrics`), `docs/CLI_REFERENCE.md`
- Test: `tests/test_biosample_cli.py`

**Interfaces:**
- Produces: `prism_tools.py biosample template --output <xlsx>`; `prism_tools.py biosample import --input <xlsx|csv> --project <path> [--specimen <type>] [--overwrite] [--dry-run]`. Handlers `cmd_biosample_template(args)`, `cmd_biosample_import(args)` print the `ImportResult` messages and exit non-zero on errors.

- [ ] **Step 1: Failing test** `test_cli_template_then_import_round_trip`: run `template`, fill one row with openpyxl, run `import` on a tmp project, assert the file names and the exit code; plus `test_cli_refuses_without_specimen`.
- [ ] **Step 2: Run, expect FAIL.**
- [ ] **Step 3: Implement** the commands as thin wrappers; add the rows to the CLI reference.
- [ ] **Step 4: Run, expect PASS.**
- [ ] **Step 5: Commit** `feat(biosample): CLI commands template and import`.

### Task 5: Studio importer page and parity test

**Files:**
- Create: `app/src/web/blueprints/conversion_biosample_handlers.py`, `app/templates/converter_biosample.html`
- Modify: the converter navigation and blueprint registration (follow `conversion_biometrics_handlers.py` and `converter_biometrics.html`), `scripts/cli_studio_baseline.json` only if the guard script says so
- Test: `tests/test_biosample_cli_studio_parity.py`

**Interfaces:**
- Consumes: `import_biosample` (Task 3) and the template writer (Task 1). The route saves the upload, calls them with the same arguments and defaults as the CLI flags (`specimen`, `overwrite`, `dry_run`), and returns `ImportResult` as JSON; a download route serves `write_biosample_template`. The page uses the project-page widgets (pull-down for specimen) and the theme macros, no own widget code.

- [ ] **Step 1: Failing test** `test_studio_and_cli_write_the_same_files`: copy one project twice, run the CLI on one and Studio's route (Flask test client) on the other with the same template, compare every written file and the messages (pattern: `tests/test_biometrics_convert_saves_into_the_project.py`). Also `test_studio_option_defaults_match_cli_flags`.
- [ ] **Step 2: Run, expect FAIL.**
- [ ] **Step 3: Implement** route and page; run `python scripts/check_cli_studio_parity.py` and `tests/test_cli_studio_guard.py`.
- [ ] **Step 4: Run all new tests, the guard test and `python tests/verify_repo.py --check dual-tree-drift --no-fix`, expect PASS.**
- [ ] **Step 5: Commit** `feat(biosample): Studio importer page, parity proven`.
