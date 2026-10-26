# Environment as a term modality, phase B (Studio) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Studio uses the environment 2.0.0 term modality from prism-specification v1.4.0: generic term tooling, a validator without fixed environment columns, a converter that writes term columns and computes time windows of any duration, and a Propose page that treats environment like biosample.

**Architecture:** Every term question asks the modality's `terms` declaration (vendored `entities.schema.json`, read through `src/entity_rules.py`) instead of assuming biosample. The validator keeps one registry per term modality; environment files go through the same described-columns path as biosample. Windowed values are computed in the backend from hourly provider data and exposed through `prism_tools.py environment convert --window`, which the GUI only calls.

**Tech Stack:** Python 3, Flask (thin adapters), vanilla JS, pytest, Playwright e2e.

**Spec:** `docs/superpowers/specs/2026-10-26-environment-term-modality-design.md`
**Depends on:** phase A (`2026-10-26-environment-terms-phase-a-specification.md`) released as `v1.4.0`. Do not start before the tag exists.

## Global Constraints

- CLAUDE.md applies in full: TDD, one implementation (backend/CLI first, GUI is an adapter), `src/` vs `app/src/` drift check before editing any non-route module in `app/src/`, never edit vendored spec files, validator path must not import pandas, `ponytail:ponytail-audit` before merge.
- Any unit is accepted if declared; a unit differing from the term's is INFO (as biosample today). No new unit errors anywhere.
- Unknown columns are allowed: INFO with the offer to propose (as biosample).
- Values outside a term-inherited `Levels` are WARNING, never ERROR. A sidecar's own `Levels` keep today's behaviour.
- Formerly forbidden environment columns (date, timestamp, lat, lon, location, ...) are WARNING, not ERROR.
- Environment 1.1.0 files are retired: an old sidecar (has a `Privacy` or `Columns` block, or `Metadata.SchemaVersion` starting with `1.`) is one ERROR: `"<file>: environment format 1.1.0 is retired; re-create it with: python prism_tools.py environment convert ..."`. No migration code.
- Window durations: any ISO 8601 duration accepted by the 2.0.0 schema pattern; statistics `mean`, `min`, `max`, `sum`, `count` (`value` = no window).
- Biosample behaviour and tests stay unchanged.

## Review Focus

1. A session near midnight with `--window temp_c:P1D:max` → the window spans two calendar days and must fetch both (Task 5 test `test_window_crosses_midnight`).
2. Provider returns gaps (`None`) inside the window → statistic over the present values; all missing → empty cell plus a preview warning, never a crash or a 0 (Task 5 test `test_window_all_missing_is_empty_with_warning`).
3. A window longer than the air-quality/pollen archive reaches → empty cells with a warning naming the variable (Task 5 test `test_window_beyond_provider_history_warns`).
4. Two sessions of the same location on overlapping days → each day fetched once (cache hit counted in Task 5 test `test_window_days_fetched_once`).
5. A project with a local environment term (`code/specification/terms/environment/noise-level.json`) → validator uses it and reports it as local, as for biosample (Task 3 test `test_local_environment_term_used`).

---

### Task 1: Sync v1.4.0 and read term declarations

**Files:**
- Run: `python scripts/sync_specification.py --tag v1.4.0` (updates vendored schemas, terms, `scripts/specification/`, `specification.lock.json`)
- Modify: `src/entity_rules.py` (`ModalityRule.terms: dict | None = None`, read from `data.get("terms")`; `EntityRules.term_modalities -> dict[str, dict]`)
- Modify: `src/specification.py` (drop `_TERM_MODALITIES`; loop over `self.rules.term_modalities`; add `Specification.term_modalities` property)
- Modify: `tests/test_specification_boundaries.py` if it lists `_TERM_MODALITIES`
- Test: `tests/test_entity_rules.py` (or the existing rules test file), `tests/test_specification.py`

**Interfaces:**
- Produces: `EntityRules.term_modalities -> dict[str, dict]` (e.g. `{"biosample": {"nonTermColumns": [...], "contextField": "Technical.SpecimenType"}, "environment": {"nonTermColumns": ["subject_id", "session_id"]}}`); `Specification.term_modalities` same; `current_specification().terms["environment"]` filled.

- [ ] **Step 1: Write the failing tests:** `test_term_modalities_from_entities` (both entries, exact dicts above); `test_specification_loads_environment_terms` (`"air-temperature" in load_specification().terms["environment"]`).
- [ ] **Step 2: Run** `pytest tests/test_entity_rules.py tests/test_specification.py -q` — FAIL.
- [ ] **Step 3: Sync and implement** as in Interfaces. Studio's own `src/term_proposal.py::check_with_specification` calls the vendored `check_proposal`: pass `modalities=current_specification().term_modalities` and, for a modality without `contextField`, `specimens=None` (never `[]`, which would apply biosample's two-level rules to environment). The vendored scripts sit in `scripts/specification/` with no `schemas/` beside them, so they must never be asked to read the repository layout: Studio passes everything explicitly. Add a test: a one-level environment proposal through `check_with_specification` has no problems. The sync will also break the environment tests that assert the 1.1.0 format; leave them red for Tasks 3-4 only if they are about environment content, otherwise fix here.
- [ ] **Step 4: Run** `pytest tests/test_entity_rules.py tests/test_specification.py tests/test_check_terms.py -q` — PASS.
- [ ] **Step 5: Commit** `feat: sync specification v1.4.0; term modalities come from entities`.

### Task 2: Generic term registry helpers

**Files:**
- Modify: `src/term_registry.py`
- Modify: `src/spec_overlay.py` (every `modality="biosample"` default keeps working; the specimen helpers return `None` for a modality without `contextField`)
- Modify: `src/term_proposal.py` (proposing an unknown column of a one-level modality builds one `variable` term: `TermID`, `Level: "variable"`, `Label`, `Aliases: [column]`, `Description`, `Units` or `Levels` from the column)
- Test: `tests/test_term_registry.py`, `tests/test_spec_overlay.py`, `tests/test_term_proposal.py` (Studio's)

**Interfaces:**
- Consumes: Task 1 `term_modalities`.
- Produces: `term_columns(sidecar_data: dict, modality: str) -> list[tuple[str, dict]]` replacing `analyte_columns` (keep `analyte_columns = lambda s: term_columns(s, "biosample")` only if callers remain after this task; prefer updating callers). Excludes sidecar blocks (keys whose value is a dict and that start with an uppercase letter: `Technical`, `Study`, `Metadata`) and the modality's `nonTermColumns`.
- Produces: `resolve_column(registry, column, col_def, specimen: str | None)` — a `variable` term resolves to `Resolution("term", term)` regardless of `specimen`; `_similar` also returns `variable` terms.
- Produces: `context_value(sidecar_data: dict, modality: str) -> str | None` (the value at the modality's `contextField`; `None` when the modality has none) replacing `_sidecar_specimen` uses in term code.

- [ ] **Step 1: Write the failing tests:**
  - `test_variable_term_resolves_without_specimen`: registry with `prism:air-temperature` (`variable`), column `temp_c` with `{"Term": "prism:air-temperature"}` → kind `"term"`.
  - `test_alias_suggests_variable`: column `temp_c` without `Term` → kind `"suggestion"` naming `prism:air-temperature`.
  - `test_term_columns_environment_skips_ids`: sidecar with `Technical`, `Study`, `Metadata`, `subject_id`, `session_id`, `temp_c` → only `temp_c`.
  - `test_term_columns_biosample_unchanged`: today's biosample fixture gives the same list as `analyte_columns` did.
  - `test_propose_unknown_environment_column`: `terms propose --data <env tsv> --column noise_db` → one `variable` term with `Units` `dB`.
- [ ] **Step 2: Run** `pytest tests/test_term_registry.py tests/test_spec_overlay.py tests/test_term_proposal.py -q` — FAIL.
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Run** the same — PASS; then `pytest -q -k "term or overlay or spec_"` — PASS.
- [ ] **Step 5: Commit** `feat: term registry helpers for any term modality (one-level variables)`.

### Task 3: Validator: environment through the term path

**Files:**
- Modify: `app/src/validator.py` — run the drift check first: `find src -name validator.py` and `python3 -c "import src.validator as m; print(m.__file__)"`.
  - `self._terms` → `self._registries = current_specification().terms` and a modality argument wherever a registry is needed (`_effective_column_defs` third pass, the term check).
  - `TERM_INHERITED_FIELDS` += `"Levels"`.
  - `_check_biosample_terms` → `_check_terms(sidecar_data, key, file_path, root_dir, modality)`; called for every modality in `current_specification().term_modalities`. Biosample's specimen messages stay in the branch for modalities with a `contextField`.
  - Delete `ENV_REQUIRED_COLUMNS`, `ENV_NUMERIC_COLUMNS`, the hard-coded level sets and `_validate_environment_content`'s fixed checks; environment content goes through the described-columns path. Keep the forbidden-column check as WARNING (`ENV_FORBIDDEN_COLUMNS` stays the list).
  - Retired-format ERROR (exact text in Global Constraints).
  - Values outside term-inherited `Levels` → WARNING.
- Test: `tests/test_validator_environment_terms.py` (new); update `tests/test_validator_no_fake_environment.py` and any test asserting the removed errors.

**Interfaces:**
- Consumes: Task 2 `term_columns`, `resolve_column`, `context_value`; Task 1 `term_modalities`.

- [ ] **Step 1: Write the failing tests** (build a tiny project in `tmp_path` with `sub-01/ses-1/environment/sub-01_ses-1_recording-weather_environment.tsv` + root sidecar):
  - `test_v2_environment_file_valid`: columns `temp_c`, `temp_max_3d`, `season_code`; sidecar 2.0.0 with `Term`s, `temp_max_3d` with `Window {"Start": "P3D", "End": "PT0S"}` and `Statistic "max"` → no ERROR/WARNING.
  - `test_unit_differs_is_info`: `temp_c` with `{"Term": "prism:air-temperature", "Units": "degF"}` → one INFO containing `"degF"`, no ERROR.
  - `test_unknown_column_is_info`: column `noise_db` (`Units "dB"`, `Description`) → INFO containing `"not an official"`.
  - `test_level_outside_term_levels_warns`: `season_code` value `monsoon` → WARNING, not ERROR.
  - `test_timestamp_column_warns`: extra column `timestamp` → WARNING.
  - `test_old_format_is_retired`: a 1.1.0 sidecar (with `Privacy`) → exactly the retired-format ERROR.
  - `test_local_environment_term_used` (Review Focus 5).
  - Biosample term tests unchanged.
- [ ] **Step 2: Run** `pytest tests/test_validator_environment_terms.py -q` — FAIL.
- [ ] **Step 3: Implement** as listed under Files.
- [ ] **Step 4: Run** `pytest tests/test_validator_environment_terms.py tests/test_validator*.py tests/test_biosample*.py -q` — PASS.
- [ ] **Step 5: Commit** `feat: validator checks environment like biosample (terms, no fixed columns); 1.1.0 retired`.

### Task 4: Converter writes 2.0.0

**Files:**
- Modify: `src/environment_conversion.py` (`OUTPUT_COLUMNS` without `filename`, `relative_time`; `_build_environment_sidecar()` returns the 2.0.0 sidecar), `src/environment_provider_helpers.py` (`weather_regime` codes `high-pressure`, `low-pressure`, `frontal` instead of `hochdruck`, `tiefdruck`, `frontal`), `src/environment_result_helpers.py` if it names removed columns
- Modify: `app/src/hostile_demo_generator.py` (writes environment directly: make it 2.0.0)
- Test: `tests/test_environment_conversion.py`, `tests/test_environment_cli.py`

**Interfaces:**
- Consumes: `load_registry("environment")` (Task 1).
- Produces: `_build_environment_sidecar() -> dict` = `{"Technical": {"Source": "open-meteo", "SpatialResolution": "city", "TemporalResolution": "hourly"}, "Study": {"EnvironmentName": "weather", "Description": "Weather, air quality, pollen and sun/moon context at each session (Open-Meteo)"}, "Metadata": {"SchemaVersion": "2.0.0", "CreationDate": <today>, "Creator": "PRISM Environment Converter"}, <column>: {"Term": <TermID whose Aliases contain column>} for each value column, "subject_id": {"Description": "BIDS subject identifier"}, "session_id": {"Description": "BIDS session identifier"}}`. Term lookup by alias through `find_term`, so the converter never carries its own column→term table.

- [ ] **Step 1: Write the failing tests:** `test_sidecar_is_v2_and_valid` (validates against the vendored 2.0.0 schema with jsonschema; every value column has a `Term` found in the registry); `test_no_privacy_or_relative_time`; `test_weather_regime_codes_english`.
- [ ] **Step 2: Run** `pytest tests/test_environment_conversion.py -q` — FAIL.
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Run** `pytest tests/test_environment*.py tests/test_validator_environment_terms.py -q` — PASS; plus one end-to-end: convert the fixture, then validate the project → no ERROR.
- [ ] **Step 5: Commit** `feat: environment converter writes 2.0.0 term columns`.

### Task 5: Time windows of any duration (backend + CLI)

**Files:**
- Create: `src/environment_windows.py`
- Modify: `src/environment_provider_helpers.py` (fetch an arbitrary day range; per-day cache keys stay `handle_cache_key_for_day(date, lat, lon)`, so each day is fetched once per location)
- Modify: `src/environment_conversion.py` (`perform_environment_conversion(..., windows: list[WindowSpec] = ())`)
- Modify: `app/src/cli/parser.py` (`environment convert --window VAR:DURATION:STAT`, repeatable), `app/src/cli/commands/environment.py`
- Test: `tests/test_environment_windows.py` (new), `tests/test_environment_cli.py`

**Interfaces:**
- Produces in `src/environment_windows.py`:
  - `@dataclass(frozen=True) class WindowSpec: column: str; duration: str; statistic: str` (`column` is a converter value column with hourly provider data: the weather, air-quality and pollen numeric columns).
  - `parse_window(text: str) -> WindowSpec` — `"temp_c:P3D:max"`; raises `ValueError` with a plain message for an unknown column, a duration not matching the 2.0.0 schema pattern, a statistic outside `mean|min|max|sum|count`.
  - `duration_to_timedelta(duration: str) -> timedelta` — `Y` and `M` (months) refused with a message (not a fixed length); `W`, `D`, `H`, `M` (minutes), `S` accepted.
  - `window_column_name(spec: WindowSpec) -> str` — `f"{spec.column}_{spec.statistic}_{spec.duration.lower()}"`, e.g. `temp_c_max_p3d`.
  - `compute_window(hourly: dict[str, float | None], end: datetime, spec: WindowSpec) -> float | None` — values whose hour lies in `[end - duration, end]`, `None` values skipped, `None` when nothing is left.
  - Sidecar entry per window column: `{"Term": <term of spec.column>, "Window": {"Start": spec.duration, "End": "PT0S"}, "Statistic": spec.statistic}`.
- CLI: `--window` errors exit non-zero with the `ValueError` message.

- [ ] **Step 1: Write the failing tests:** `test_parse_window_ok` (`"temp_c:P3D:max"` → `WindowSpec("temp_c", "P3D", "max")`); `test_parse_window_refuses` (`"temp_c:3d:max"`, `"temp_c:P1M:max"`, `"temp_c:P1D:median"`, `"foo:P1D:max"`); `test_compute_window_max` (hourly temps over 3 days, known max); `test_window_crosses_midnight`; `test_window_all_missing_is_empty_with_warning`; `test_window_beyond_provider_history_warns`; `test_window_days_fetched_once` (stub `fetch_provider_json`, count calls); `test_cli_window_option` (`environment convert ... --window temp_c:P3D:max` writes column `temp_c_max_p3d` and its sidecar entry).
- [ ] **Step 2: Run** `pytest tests/test_environment_windows.py tests/test_environment_cli.py -q` — FAIL.
- [ ] **Step 3: Implement.** Fetch range = from `(session - longest duration).date()` to `session.date()`; reuse the existing per-day cache; no network in tests (stub the fetch function).
- [ ] **Step 4: Run** the same — PASS.
- [ ] **Step 5: Commit** `feat: environment time windows of any duration (CLI)`.

### Task 6: Windows in the GUI (adapter only)

**Files:**
- Modify: `app/templates/converter_environment.html`, `app/static/js/modules/converter/environment.js` (a "Time windows" list: variable pull-down from the window-capable columns, duration text field with an example `P3D`, statistic pull-down; add/remove rows)
- Modify: `app/src/web/blueprints/conversion_environment_handlers.py` / `..._job_handlers.py` (pass the rows as the same `VAR:DURATION:STAT` strings through `parse_window`; a bad row returns its `ValueError` text)
- Test: `tests/test_conversion_environment_windows_route.py` (new, Flask test client); one Playwright check in `tests/e2e/` for the add-row flow if the environment page has e2e coverage

**Interfaces:**
- Consumes: Task 5 `parse_window`, `WindowSpec`, `perform_environment_conversion(..., windows=...)`. A route that lists window-capable columns returns the same list `parse_window` accepts (one source).

- [ ] **Step 1: Write the failing tests:** `test_route_passes_windows` (POST with `windows=["temp_c:P3D:max"]` → output has `temp_c_max_p3d`); `test_route_bad_window_message` (`"temp_c:3d:max"` → 400 with the `parse_window` message).
- [ ] **Step 2: Run** — FAIL.
- [ ] **Step 3: Implement** (DOM text via `textContent`; no logic in JS beyond collecting rows).
- [ ] **Step 4: Run** the route tests — PASS; then check the page in the running app (run skill) with one window row.
- [ ] **Step 5: Commit** `feat: time windows on the Environment converter page`.

### Task 7: Propose page and `spec propose-metric` for environment

**Files:**
- Modify: `src/spec_contribute.py` (`spec_catalog`: `metrics` include `variable` terms with `units` or `levels`; `proposal_for_new_metric(..., specimen: str | None = None, levels: dict[str, str] | None = None)` — for a modality without `contextField` it builds one `variable` term and refuses `specimen`; needs exactly one of `units` / `levels`); drop `"Privacy"` and `"Provenance"` from `_SECTION_TITLES` (the blocks are gone)
- Modify: `app/src/cli/parser.py` (`propose-metric`: `--specimen` and `--units` no longer `required=True`; add `--level CODE=LABEL`, repeatable), `app/src/cli/commands/spec.py`
- Modify: `app/src/web/blueprints/specification_contribute.py`, the Propose page template/JS: for a kind without second level, the measurement form hides the sample type and offers unit or levels, plus an optional CF standard name field
- Test: `tests/test_spec_contribute.py`, `tests/test_cli_spec.py` (or the existing spec CLI tests), e2e propose-page test if present

**Interfaces:**
- Consumes: Task 1 `term_modalities` (whether a kind has a `contextField`), Task 2 helpers.

- [ ] **Step 1: Write the failing tests:** `test_catalog_environment_metrics` (environment kind lists `prism:air-temperature` with units `degC`, and no `Privacy` section in `example_entries("environment")`); `test_new_environment_metric` (`proposal_for_new_metric("noise level", "Sound pressure level", "dB", modality="environment")` → one term `prism:noise-level`, `Level "variable"`, no problems); `test_environment_metric_refuses_specimen`; `test_units_or_levels_required`; `test_cli_propose_metric_environment` (`spec propose-metric --modality environment --name "noise level" --description ... --units dB --json` exit 0); biosample `propose-metric` without `--specimen` still fails with a clear message.
- [ ] **Step 2: Run** — FAIL.
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Run** the tests — PASS; open the Propose page in the app (run skill), pick environment: no Privacy section, measurement form without sample type.
- [ ] **Step 5: Commit** `feat: propose environment variables (page and CLI)`.

### Task 8: Docs, audit, finish

- [ ] **Step 1:** Update Studio docs that describe the environment format (`docs/` pages mentioning `Privacy`/`AnchorField`/`relative_time`; `grep -rn "AnchorField\|relative_time\|hochdruck" docs app/templates`), CHANGELOG entry (breaking: environment 1.1.0 retired; re-run the converter).
- [ ] **Step 2:** `/ponytail:ponytail-audit` on the branch; apply what is worth it.
- [ ] **Step 3:** Targeted tests (`pytest -q -k "environment or term or spec_ or validator"`) and the e2e environment/propose tests; full suite runs nightly (memory: test cadence).
- [ ] **Step 4:** Ask the user before merging to `main` and pushing.
