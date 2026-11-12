# Biosample Legacy-Sheet Migration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** `prism_tools.py biosample migrate-wide` turns a legacy wide biosample sheet (one row per patient and visit, three columns per analyte) into the filled Excel template that `biosample import` reads, and reports everything it could not map.

**Architecture:** One new module `src/biosample_migrate.py` (read the legacy table, find the analyte column groups, write the template with `write_biosample_template`, return a report) and one thin CLI command. The importer is not changed: the migration copies cell text as written and lets the importer's reader normalise `<0,05`, comma decimals and float noise. CLI only; Studio is not touched in this plan.

**Tech Stack:** Python stdlib, pandas and openpyxl (already used), `src/converters/file_reader.read_tabular_file`, `src/converters/wide_to_long.find_empty_data_rows`, pytest. No new dependency.

**Spec:** `docs/superpowers/specs/2026-11-11-biosample-importer-design.md` (section "The migration"). This plan replaces two details of that section: (1) the fixture is a **synthetic copy with changed values**, never the real file (the real file holds per-patient hormone values and the repository is public; it lives in the git-ignored `.claude/` and is never committed); (2) `--panel-map` stays out (YAGNI, as the spec's audit note says).

## Global Constraints

- Command: `prism_tools.py biosample migrate-wide --input <csv|tsv|xlsx> --output <xlsx> [--panel <name>] [--specimen <type>] [--id-column <col>] [--session-column <col>] [--overwrite]`. Defaults: panel `bloodhormones`, specimen unset (written as `serum` and reported as "assumed, unverified"), overwrite False. `--specimen` choices come from `src.biosample_template.specimen_types()`.
- Analyte column groups in the source header: `<Analyte> Results`, `<Analyte> Unit`, and an optional `<Analyte> clin. significant...` column (case-insensitive; runs of spaces count as one; the analyte name is written as in the header, whitespace-normalised, e.g. `Free Testosterone`, `Prolaktin`). A group needs its `Results` column; `Unit` and the significance column are optional.
- `id_column` and `session_column`: the two source columns that belong to no analyte group, in that order, when exactly two exist (fixture: `Patient No.`, `Visit`); otherwise an error naming the candidates and asking for the flags.
- Output = the template of `write_biosample_template` with: one `panels` row (`panel`, `SpecimenType`); one `data` row per non-empty Results cell: `participant_id` = id cell, `session` = session cell **exactly as written** (`T4.1` stays `T4.1`), `panel`, `run`/`sample_id`/`collection_time` empty, `analyte`, `value` = cell text stripped **and otherwise untouched** (`<0,05` and `2.0099999999999998` stay as they are), `unit` = the unit cell after mojibake repair, `comment` = the significance cell text.
- Mojibake: a unit like `¬µU/ml` is Mac-Roman-decoded UTF-8; repair with `text.encode("mac_roman").decode("utf-8")` only when that round trip succeeds and differs; the report lists each distinct repair once; a unit that cannot be repaired is left as written.
- Rows with no value in any Results column are skipped via `find_empty_data_rows` (reused, not re-implemented) and listed in the report (`b004 T0`).
- Analytes whose Results column is empty in the whole file are listed as "dropped, empty in this file" (fixture: the genetics/receptor columns and the drug levels) and get no `data` rows.
- Reading: `.xlsx`/`.csv`/`.tsv` through `read_tabular_file` (all cells as text), plus the legacy export quirk: when the table has a single column whose header contains tab characters (each source line quoted as one CSV cell), split every line on tabs. A BOM and CRLF must not matter.
- Never raises on bad content: `MigrationError(ValueError)` with a readable message for an unreadable file, no analyte groups found, undeterminable id/session column, invalid panel (must match `[A-Za-z0-9]+`), refused overwrite.
- Report (`MigrationReport`) never hides data: skipped rows, dropped analytes, repaired units, assumed values, and warnings are all listed. Exit code non-zero only for `MigrationError`.
- Logic in `src/`; the command is a thin wrapper (`app/src/cli/commands/biosample.py`); check `import src.biosample_migrate` resolves to `src/biosample_migrate.py` and the dual-tree-drift check stays clean. TDD per `CLAUDE.md`. Before the merge: `/ponytail:ponytail-audit`, `/code-review`, `/security-review` (the command reads a project file), `superpowers:verification-before-completion`. Work in the worktree `../prism-studio-biosample-migrate` (branch `feat/biosample-migrate-wide`).
- Fixture: `tests/data/biosample/legacy_wide_blood.csv`, a synthetic file with the real file's quirks (UTF-8 BOM, CRLF, every line one quoted cell with tabs, the 73 real header names, `¬µU/ml` units, `<5` / `<0,05` / `<0,3` cells, empty visits, visit labels `T0`..`T6` and `T4.1`/`T4.2`, ids like `s001`) but invented values and ids. Build it with a small script once and commit the file, not the script.

## Review Focus

1. A comma, semicolon or plain tab file (no quirk): reads as normal, not as one column (Task 1).
2. A header with `Results` but no matching `Unit`: rows are written with an empty unit and the report warns that the importer will need a unit or a term (Task 3).
3. The same (participant, session) twice in the source: reported as a warning naming the pairs, because the importer will refuse them as "measured twice" (Task 3).
4. A Results cell holding text such as `n.a.` or `-`: copied as written, not dropped; the importer's reader will name the row (Task 3).
5. The output path already exists: refused without `--overwrite`, nothing written (Task 4).

---

### Task 1: Read the legacy table and repair units

**Files:**
- Create: `src/biosample_migrate.py`, `tests/data/biosample/legacy_wide_blood.csv`
- Test: `tests/test_biosample_migrate.py`

**Interfaces:**
- Produces:
  - `class MigrationError(ValueError)`
  - `read_legacy_wide(path: Path) -> "pandas.DataFrame"`: all cells as `str`, column names stripped; handles the one-quoted-cell-per-line quirk (above) and `.csv`/`.tsv`/`.xlsx`.
  - `repair_mojibake(text: str) -> str`: returns the repaired text, or `text` unchanged.

- [ ] **Step 1: Create the fixture** (script run once, not committed) with the properties in Global Constraints; 12 rows are enough: two ids, visits including `T4.1` and `T4.2`, three empty visits, a value `<5`, `<0,05`, `<0,3`, `2.0099999999999998`, and `¬µU/ml` for Prolaktin.
- [ ] **Step 2: Failing tests:** `test_reads_the_quirk_file_as_73_columns` (73 columns, `Patient No.` and `Visit` first, no BOM in the first header), `test_reads_a_plain_comma_csv_and_a_tab_file_normally` (Review Focus 1), `test_repair_mojibake` (`"¬µU/ml" -> "µU/ml"`, `"pg/ml"` and `"ng/ml"` unchanged, a string that cannot round-trip unchanged), `test_unreadable_file_is_a_migration_error`.
- [ ] **Step 3: Run, expect FAIL** (`python -m pytest tests/test_biosample_migrate.py -v`: module missing).
- [ ] **Step 4: Implement** the three names; use `read_tabular_file` for normal files and unwrap when the result has one column containing tabs.
- [ ] **Step 5: Run, expect PASS; commit** `feat(biosample): read the legacy wide sheet`.

### Task 2: Find the analyte column groups

**Files:**
- Modify: `src/biosample_migrate.py`
- Test: `tests/test_biosample_migrate.py`

**Interfaces:**
- Produces:
  - `@dataclass(frozen=True) class AnalyteColumns: name: str; value: str; unit: str | None; flag: str | None` (column names exactly as in the table).
  - `detect_analytes(columns: Sequence[str]) -> tuple[list[AnalyteColumns], list[str]]`: (groups in header order, the columns that belong to no group).

- [ ] **Step 1: Failing tests** with the fixture header: `test_detects_24_analyte_groups` (count from the fixture; `Free Testosterone` has `flag is None`; `Levonorgestrel  clin.` with a double space still matches), `test_other_columns_are_patient_and_visit` (`["Patient No.", "Visit"]`), `test_results_without_unit_still_a_group` (unit `None`), `test_no_groups_is_a_migration_error` (via the id/session resolver in Task 3, assert the message names the columns it saw).
- [ ] **Step 2: Run, expect FAIL.**
- [ ] **Step 3: Implement** `detect_analytes`: match the `Results` columns first, then attach `Unit` and `clin` columns by analyte name after whitespace normalisation and case folding.
- [ ] **Step 4: Run, expect PASS; commit** `feat(biosample): detect the analyte column groups`.

### Task 3: Migrate to the template

**Files:**
- Modify: `src/biosample_migrate.py`
- Test: `tests/test_biosample_migrate.py`

**Interfaces:**
- Consumes: `write_biosample_template(path)` and `DATA_COLUMNS`, `PANEL_COLUMNS` from `src.biosample_template`; `find_empty_data_rows(df, *, id_column, data_columns)` from `src.converters.wide_to_long`; `read_template(path, specimen=None)` from `src.biosample_template_reader` and `import_biosample` from `src.biosample_import` (end-to-end test only).
- Produces:
  - `@dataclass class MigrationReport: rows_read: int; rows_skipped_empty: list[str]; data_rows: int; analytes_mapped: list[str]; analytes_dropped_empty: list[str]; unit_repairs: list[str]; assumptions: list[str]; warnings: list[str]`
  - `migrate_wide(input_path: Path, output_path: Path, panel: str = "bloodhormones", specimen: str | None = None, id_column: str | None = None, session_column: str | None = None, overwrite: bool = False) -> MigrationReport`

- [ ] **Step 1: Failing tests** on the fixture: `test_data_rows_hold_the_cell_text_untouched` (a `<0,05` and a `2.0099999999999998` value are in the output exactly so; session `T4.1` stays), `test_empty_visits_are_skipped_and_listed` (`"s002 T0"` style entries; `rows_read` counts all rows), `test_empty_analytes_are_dropped_and_listed` (genetics and drug columns in `analytes_dropped_empty`, none in `analytes_mapped`), `test_units_are_repaired_and_reported` (`µU/ml` in the sheet, one entry in `unit_repairs`), `test_specimen_default_is_serum_and_assumed` (`SpecimenType` cell is `serum`, `assumptions` names it unverified; with `specimen="plasma"` no such assumption), `test_missing_unit_column_warns` (Review Focus 2, a tiny in-test table), `test_duplicate_participant_session_warns` (Review Focus 3), `test_text_in_a_value_cell_is_copied_as_written` (Review Focus 4), `test_invalid_panel_name_is_an_error`, `test_id_and_session_columns_must_be_determinable` (three non-group columns and no flags: the message names them).
- [ ] **Step 2: Failing end-to-end test** `test_migrated_template_imports_into_a_project`: migrate the fixture, build a minimal project like `tests/test_biosample_import.py` does (a `multiple` project with a session map from `T0`..`T6`, `T4.1`, `T4.2` to themselves or to numbers), run `import_biosample` on the output, assert `errors == []` and that one TSV per patient and visit with data exists, that a `<5` Estradiol cell is `<LOD` in the TSV and the sidecar has `LowerLimitOfDetection`, and that the sidecar `Technical.SpecimenType` is `serum`.
- [ ] **Step 3: Run, expect FAIL.**
- [ ] **Step 4: Implement `migrate_wide`** with `openpyxl` filling the template's two sheets; resolve id/session columns as in Global Constraints; reuse `find_empty_data_rows`.
- [ ] **Step 5: Run, expect PASS; commit** `feat(biosample): migrate a legacy wide sheet to the template`.

### Task 4: CLI command `biosample migrate-wide`

**Files:**
- Modify: `app/src/cli/commands/biosample.py`, `app/src/cli/parser.py`, `app/src/cli/dispatch.py`, `app/src/cli/entrypoint.py`, `docs/CLI_REFERENCE.md`
- Test: `tests/test_biosample_cli.py`

**Interfaces:**
- Consumes: `migrate_wide`, `MigrationError`, `MigrationReport` (Task 3); the existing `biosample` subparser and its `specimen_types()` choices.
- Produces: `cmd_biosample_migrate_wide(args)` registered as handler `biosample_migrate_wide`: prints `Wrote <output>`, then each report section (skipped rows, dropped analytes, repaired units, assumptions, warnings) as indented lines with a heading, to stdout; a `MigrationError` goes to stderr as `Error: <message>` with exit 1.

- [ ] **Step 1: Failing tests** in `tests/test_biosample_cli.py` (call the handler in-process, as the existing tests do): `test_cli_migrate_wide_writes_the_template_and_prints_the_report` (heading for the assumed specimen present), `test_cli_migrate_wide_refuses_an_existing_output` (Review Focus 5: exit 1, file unchanged), `test_cli_migrate_wide_error_exits_nonzero` (unreadable input).
- [ ] **Step 2: Run, expect FAIL.**
- [ ] **Step 3: Implement** the handler and register it next to `biosample import`; add the command, flags and defaults to `docs/CLI_REFERENCE.md`.
- [ ] **Step 4: Run the new tests, `tests/test_biosample_*.py`, `tests/test_cli_parity_commands.py`, `python scripts/check_cli_studio_parity.py` and `python tests/verify_repo.py --check dual-tree-drift --no-fix` (delete the report txt it leaves); expect PASS and 0 new baseline entries.**
- [ ] **Step 5: Commit** `feat(biosample): CLI command migrate-wide`.
