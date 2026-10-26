# Environment as a term modality, phase A (prism-specification) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Release a prism-specification version in which `environment` 2.0.0 is a term modality like biosample (one-level terms with a basic set, column time windows), and the term tooling works for any modality that declares terms.

**Architecture:** Each modality entry in `schemas/stable/entities.schema.json` may declare `terms` (its non-term columns and, optionally, the sidecar field that is the second level). The checks (`check_modalities.py`, `check_terms.py`, `term_proposal.py`) read that declaration instead of assuming biosample. Biosample keeps its two levels (`analyte`, `analyte-specimen`) unchanged; environment uses a new one-level kind `variable`.

**Tech Stack:** Python 3 stdlib (+ `jsonschema` where it is already used), JSON Schema draft-07, pytest, GitHub Actions.

**Spec:** `prism-studio/docs/superpowers/specs/2026-10-26-environment-term-modality-design.md`

**Repository:** `/Users/karl/work/github/prism-specification` (work in a worktree on branch `feat/environment-terms`; its CLAUDE.md applies: ponytail + superpowers, TDD, `ponytail:ponytail-audit` before merge). Phase B (Studio) is `2026-10-26-environment-terms-phase-b-studio.md`.

## Global Constraints

- The structure is fixed, the vocabulary is open: a new variable is a term file, never a schema change.
- Any unit is accepted as long as the sidecar declares it; a unit differing from the term's is only a notice (Studio). Nothing here makes a unit an error.
- A term is always the bare variable; `Window` and `Statistic` live only on the column. No term carries a window.
- Term IDs are unique within a modality (lookups stay per modality).
- Environment 1.1.0 is retired, not migrated: archive it, no compatibility code.
- Biosample's existing term files, levels and behaviour stay exactly as they are (its tests must pass unchanged).
- Scripts stay stdlib-only where they are today (`check_terms.py`, `term_proposal.py`) and keep loading siblings by path (`_sibling`); catch `ValueError`, not sibling exception classes.
- Content change = minor release: tag `v1.4.0`. Merging, tagging and pushing need the user's go (Task 6).

## Review Focus

1. A term with both `Units` and `Levels`, or neither → must be a problem from `check_terms.py` (Task 2 test `test_variable_needs_units_or_levels_not_both`).
2. A proposal for `terms/environment/<id>.json` with a dotted ID (`air-temperature.indoor`) → refused, environment has no second level (Task 3 test `test_environment_term_with_dot_is_refused`).
3. A proposal mixing biosample and environment terms → refused with a clear message, not a crash (Task 3 test `test_mixed_modalities_refused`).
4. A `Window` with a malformed duration (`3 days`, `-P3D`) → schema error (Task 4 test `test_window_duration_pattern`).
5. A `terms/<name>/` folder with no `terms` declaration in its entities entry (or the reverse) → `check_modalities.py` problem (Task 1 test `test_terms_folder_and_declaration_agree`).

---

### Task 1: Per-modality term declaration in entities

**Files:**
- Modify: `scripts/entities_entry.schema.json` (add optional `terms`)
- Modify: `schemas/stable/entities.schema.json` (the biosample entry gets `terms`; `version` 1.1.0 → 1.2.0; the environment entry is changed in Tasks 4 and 5, not here, so every commit stays green)
- Modify: `scripts/check_modalities.py`
- Test: `tests/test_check_modalities.py`

**Interfaces:**
- Produces: entry field `terms` = `{"nonTermColumns": [str, ...], "contextField": "Section.Field"}` (`contextField` optional; absent = one-level terms). Value for biosample: `{"nonTermColumns": ["sample_id", "collection_time", "fasting"], "contextField": "Technical.SpecimenType"}`. (Environment's `{"nonTermColumns": ["subject_id", "session_id"]}` arrives in Task 5 together with `terms/environment/`.)
- Produces: `check_modalities.check(entities: dict, schema_dir: Path, terms_dir: Path | None = None) -> list[str]`.

- [ ] **Step 1: Write the failing tests** in `tests/test_check_modalities.py`:
  - `test_terms_folder_and_declaration_agree`: a temp repo where `terms/environment/` exists but the entry has no `terms` → one problem containing `"environment"` and `"terms"`; and an entry declaring `terms` without a folder → one problem.
  - `test_context_field_must_be_an_enum`: entry with `"contextField": "Technical.Nope"` → problem naming `Technical.Nope`.
  - `test_shipped_entities_pass`: `check(real entities, schemas/stable, terms)` == `[]`.
- [ ] **Step 2: Run** `python3 -m pytest tests/test_check_modalities.py -q` — expect the three new tests to FAIL.
- [ ] **Step 3: Implement.** Entry schema: `"terms": {"type": "object", "additionalProperties": false, "required": ["nonTermColumns"], "properties": {"nonTermColumns": {"type": "array", "items": {"type": "string"}}, "contextField": {"type": "string", "pattern": "^[A-Z][A-Za-z]*\\.[A-Z][A-Za-z]*$"}}}`. `check()` gains the folder/declaration agreement and the "contextField resolves to an `enum` in the modality schema" rule; `main()` passes `REPO / "terms"`. Update the biosample entry and the version.
- [ ] **Step 4: Run** `python3 -m pytest -q` — all PASS (other tests reading entities must still pass).
- [ ] **Step 5: Commit** `feat: modalities declare their terms (non-term columns, optional second level)`.

### Task 2: `check_terms.py` for any term modality

**Files:**
- Modify: `scripts/check_terms.py`
- Modify: `.github/workflows/ci.yml` (the "terms" step checks every modality with `terms`)
- Test: `tests/test_check_terms.py`

**Interfaces:**
- Consumes: Task 1 `terms` declaration.
- Produces: `check_registry(registry: dict[str, dict], specimen_types: list[str] | None) -> list[str]` — `None` means a one-level registry (only `Level: "variable"` allowed); a list (possibly empty) keeps today's two-level biosample rules unchanged.
- Produces: `term_modalities(repo: Path) -> dict[str, dict]` (modality → its `terms` declaration, read from `repo/schemas/stable/entities.schema.json`); the one definition, reused by Task 3 and the CI loop.
- Produces: `context_values(schema_file: Path, field: str | None) -> list[str] | None` (the enum at `field`, `None` when `field` is `None`); `specimen_types(schema_file)` stays as `context_values(schema_file, "Technical.SpecimenType") or []` for old callers.
- Produces: CLI `python scripts/check_terms.py --modality NAME [--repo DIR]` (reads `DIR/schemas/stable/entities.schema.json`, `DIR/terms/NAME`, `DIR/schemas/stable/NAME.schema.json`); the old `--terms DIR --schema FILE` form keeps working as before.
- Produces: new term fields: `Levels` (object, string keys → string values), `CFStandardName` (string matching `^[a-z][a-z0-9_]*$`).

- [ ] **Step 1: Write the failing tests:**
  - `test_variable_term_ok`: `{"air-temperature": {"TermID": "prism:air-temperature", "Level": "variable", "Label": "air temperature", "Units": "degC", "CFStandardName": "air_temperature", "Status": "official"}}` with `None` → `[]`.
  - `test_variable_needs_units_or_levels_not_both`: one term with both → problem containing `"Units or Levels"`; one with neither → same text.
  - `test_variable_id_has_no_dot`: `prism:air-temperature.indoor` with `None` → problem.
  - `test_analyte_level_refused_in_one_level_registry`: an `analyte` term with `None` → problem `"Level must be 'variable'"`.
  - `test_levels_type_checked`: `"Levels": ["a"]` → `"Levels must be an object of strings"`.
  - `test_cf_name_pattern`: `"CFStandardName": "Air Temperature"` → problem.
  - `test_cli_modality_environment`: `main(["--modality", "environment", "--repo", <tmp repo>])` returns 0 for a valid tmp registry.
  - Existing biosample tests unchanged.
- [ ] **Step 2: Run** `python3 -m pytest tests/test_check_terms.py -q` — new tests FAIL.
- [ ] **Step 3: Implement** in `check_registry`: branch on `specimen_types is None`. `variable` rules: slug without dot (`_SLUG`), `Label` required, exactly one of `Units` / `Levels`. Add `Levels` and `CFStandardName` to `type_problems` (Levels: dict with str keys and str values). Add `--modality`/`--repo` to `main` (mutually exclusive with `--terms`). CI step: `for m in biosample environment` is NOT acceptable (hand-written list); loop over the entities entries that declare `terms` (a short `python3 -c` reading entities, or a `--all` flag; builder's call).
- [ ] **Step 4: Run** `python3 -m pytest -q` — PASS.
- [ ] **Step 5: Commit** `feat: check_terms handles one-level (variable) registries, Levels and CF standard names`.

### Task 3: `term_proposal.py` for any term modality

**Files:**
- Modify: `scripts/term_proposal.py`
- Modify: `.github/workflows/propose-metric.yml` (check step: drop `--terms/--schema`, pass `--repo .`)
- Modify: `.github/ISSUE_TEMPLATE/*metric*` if it names biosample only (wording: "a measurement of a kind of data")
- Test: `tests/test_term_proposal.py`, `tests/test_propose_metric_workflow.py`

**Interfaces:**
- Consumes: Task 1 declaration, Task 2 `check_registry(..., None)` and `context_values`.
- Consumes: `check_terms.term_modalities(repo)` (Task 2) in place of the constant `MODALITIES`; define no second reader of the declaration. A modality without `contextField` gets `specimens = None` (one-level), never `[]`.
- Produces: `check` subcommand where `--terms`/`--schema` are optional; when omitted, registry and schema come from `--repo` for the one term modality the proposal names. `ALLOWED_FIELDS` gains `Levels`, `CFStandardName`.
- Produces: `check_proposal(proposal, registry, specimens: list[str] | None, schema=None, *, schemas=None)` — `None` = one-level.

- [ ] **Step 1: Write the failing tests:**
  - `test_environment_variable_proposal_ok`: v2 proposal `{"format": ..., "files": {"terms/environment/noise-level.json": {"TermID": "prism:noise-level", "Level": "variable", "Label": "noise level", "Units": "dB", "Description": "Sound pressure level"}}}` checked against the real repo → no problems, term gets `"Status": "official"`.
  - `test_environment_term_with_dot_is_refused`: `terms/environment/air-temperature.indoor.json` → problem.
  - `test_mixed_modalities_refused`: one biosample term + one environment term → problem `"one kind of data per proposal"`.
  - `test_unknown_term_modality_refused`: `terms/physio/x.json` → path-not-allowed problem listing the declared modalities.
  - Workflow test: the check step no longer contains `terms/biosample`.
- [ ] **Step 2: Run** `python3 -m pytest tests/test_term_proposal.py tests/test_propose_metric_workflow.py -q` — FAIL.
- [ ] **Step 3: Implement** as in Interfaces; `_TERM_PATH` already matches any modality; `_LOCAL` stays (dot rule is enforced per modality by `check_registry`). Write-out (`write_terms`) unchanged.
- [ ] **Step 4: Run** `python3 -m pytest -q` — PASS.
- [ ] **Step 5: Commit** `feat: proposals for any term modality (environment variables)`.

### Task 4: Environment schema 2.0.0

**Files:**
- Create: `schemas/archive/environment/1.1.0.schema.json` (byte-identical copy of today's stable file)
- Modify: `schemas/stable/environment.schema.json`
- Modify: `schemas/stable/entities.schema.json` (environment entry: `describedColumns: true`, description `"Environmental conditions linked to a session (temperature, UV, noise, ...)"`)
- Modify: `specs/environment.md` (prose; regenerate the table with `python scripts/generate_schema_reference.py`)
- Test: `tests/test_environment_schema.py` (new)

**Interfaces:**
- Produces: schema `version` `2.0.0`, `$id` `https://prism.org/schemas/environment/v2.0.0`, required blocks `Technical`, `Study`, `Metadata`; no `Privacy`, no `Provenance`, no `Columns`. Column definitions are `additionalProperties` (top level, like biosample).
  - `Technical`: `Source` (string, required; description lists `open-meteo`, `room-sensor`, `manual`, `other` as usual values — free string), `SpatialResolution` (string), `TemporalResolution` (string).
  - `Study`: `EnvironmentName` (pattern `^[a-zA-Z0-9]+$`, must equal `recording-<label>`, required), `Description`, `Citation`, `DOI`, `Keywords` (as biosample).
  - `Metadata`: copy biosample's block.
  - Column: biosample's column properties minus the assay-only ones (`LOINC`, `LowerLimitOfDetection`, `LowerLimitOfQuantification`, `UpperLimitOfQuantification`, `ReferenceRange`, `IntraAssayCV`, `InterAssayCV`), plus `CFStandardName` (string, `^[a-z][a-z0-9_]*$`), `Window` = `{"type": "object", "additionalProperties": false, "properties": {"Start": D, "End": D}, "required": ["Start", "End"]}` with `D = {"type": "string", "pattern": "^P(?!$)(\\d+Y)?(\\d+M)?(\\d+W)?(\\d+D)?(T(?=\\d)(\\d+H)?(\\d+M)?(\\d+S)?)?$"}`, `Statistic` (enum `value`, `mean`, `min`, `max`, `sum`, `count`). `anyOf` as biosample (`Description`+`Units` or `Term`).
- Spec page prose: what the modality is for (session enrichment for questions like temperature vs. reaction time, season and heat days); file naming unchanged; one paragraph on `Window` (`Start`/`End` before the session, `PT0S` = the session) and `Statistic` with the example `temp_max_3d`; one sentence: do not store exact location or raw timestamps unless your governance allows it.

- [ ] **Step 1: Write the failing tests** (`tests/test_environment_schema.py`, `jsonschema` Draft7):
  - `test_minimal_sidecar_valid`: `{"Technical": {"Source": "open-meteo"}, "Study": {"EnvironmentName": "weather"}, "Metadata": {"SchemaVersion": "2.0.0", "CreationDate": "2026-10-26"}, "temp_max_3d": {"Term": "prism:air-temperature", "Window": {"Start": "P3D", "End": "PT0S"}, "Statistic": "max"}}` → valid.
  - `test_window_duration_pattern`: `Start` values `"3 days"`, `"-P3D"`, `"P"`, `"PT"` invalid; `"PT30M"`, `"P1W"`, `"P1DT12H"` valid.
  - `test_statistic_enum`: `"median"` invalid.
  - `test_old_privacy_block_not_required`: sidecar without `Privacy` valid; `test_version_and_id`: version `2.0.0`, `$id` ends `/v2.0.0`.
- [ ] **Step 2: Run** `python3 -m pytest tests/test_environment_schema.py -q` — FAIL.
- [ ] **Step 3: Implement** the schema, archive copy, spec prose, regenerate the table.
- [ ] **Step 4: Run** `python3 -m pytest -q && python3 scripts/check_modalities.py && python3 scripts/generate_schema_reference.py --check && python3 scripts/check_schema_versions.py origin/main HEAD` — all pass.
- [ ] **Step 5: Commit** `feat!: environment 2.0.0 - term columns with time windows, privacy block removed (1.1.0 archived)`.

### Task 5: Environment basic term set

**Files:**
- Create: `terms/environment/<id>.json` for each row below (`Level: "variable"`, `Status: "official"`, `Label`, `Description`, `Aliases` = the converter column name)
- Modify: `schemas/stable/entities.schema.json` (environment entry gets `"terms": {"nonTermColumns": ["subject_id", "session_id"]}`; declaration and folder arrive together)
- Modify: `CONTRIBUTING.md` (proposing a variable for a one-level kind of data: no sample type, `Units` or `Levels`, optional `CFStandardName`)
- Test: covered by `check_terms.py --modality environment` in CI; add `tests/test_environment_terms.py::test_converter_columns_all_have_terms` asserting the alias set equals the converter list below.

| Alias (converter column) | TermID | Units / Levels | CFStandardName |
|---|---|---|---|
| temp_c | prism:air-temperature | degC | air_temperature |
| apparent_temp_c | prism:apparent-temperature | degC | |
| dew_point_c | prism:dew-point-temperature | degC | dew_point_temperature |
| humidity_pct | prism:relative-humidity | % | relative_humidity |
| pressure_hpa | prism:surface-air-pressure | hPa | surface_air_pressure |
| precip_mm | prism:precipitation | mm | lwe_thickness_of_precipitation_amount |
| wind_speed_ms | prism:wind-speed | m/s | wind_speed |
| cloud_cover_pct | prism:cloud-cover | % | cloud_area_fraction |
| uv_index | prism:uv-index | 1 | ultraviolet_index |
| shortwave_radiation_wm2 | prism:shortwave-radiation | W/m2 | surface_downwelling_shortwave_flux_in_air |
| aqi | prism:european-aqi | 1 | |
| pm25_ug_m3 | prism:pm25 | ug/m3 | mass_concentration_of_pm2p5_ambient_aerosol_particles_in_air |
| pm10_ug_m3 | prism:pm10 | ug/m3 | mass_concentration_of_pm10_ambient_aerosol_particles_in_air |
| no2_ug_m3 | prism:nitrogen-dioxide | ug/m3 | mass_concentration_of_nitrogen_dioxide_in_air |
| o3_ug_m3 | prism:ozone | ug/m3 | mass_concentration_of_ozone_in_air |
| pollen_birch / _grass / _mugwort / _ragweed / _total | prism:pollen-birch / -grass / -mugwort / -ragweed / -total | grains/m3 | |
| pollen_risk_bin | prism:pollen-risk | Levels low, medium, high, very_high, unknown | |
| elevation_m | prism:elevation | m | height_above_mean_sea_level |
| sun_hours_today | prism:daylight-duration | h | |
| hours_since_sun | prism:hours-since-daylight | h | |
| moon_illumination_pct | prism:moon-illumination | % | |
| moon_phase | prism:moon-phase | Levels new_moon, waxing_crescent, first_quarter, waxing_gibbous, full_moon, waning_gibbous, last_quarter, waning_crescent | |
| hour_bin | prism:time-of-day | Levels night (00-05), morning (06-11), afternoon (12-17), evening (18-23), unknown | |
| season_code | prism:season | Levels spring, summer, autumn, winter, unknown | |
| sun_phase | prism:sun-phase | Levels night, dawn, day, dusk | |
| heatwave_status | prism:heat-status | Levels normal (<25 °C max), warm_day (≥25), hot_day (≥30), heatwave (≥30 on the day and the 2 days before), unknown | |
| weather_regime | prism:weather-regime | Levels high-pressure, low-pressure, frontal | |

- [ ] **Step 1: Write the failing test** `test_converter_columns_all_have_terms` (the alias set from the table; fails while the folder is empty).
- [ ] **Step 2: Run** it — FAIL.
- [ ] **Step 3: Create** the term files and the CONTRIBUTING section.
- [ ] **Step 4: Run** `python3 -m pytest -q && python3 scripts/check_terms.py --modality environment` — PASS, exit 0.
- [ ] **Step 5: Commit** `feat(terms): environment basic set (the converter's variables, CF standard names)`.

### Task 6: Audit, then stop for the user

- [ ] **Step 1:** Run `/ponytail:ponytail-audit` on the branch, apply what is worth it, re-run `python3 -m pytest -q`.
- [ ] **Step 2: STOP.** Report to the user and ask before: merge to `main`, tag `v1.4.0`, push, GitHub release. After release: one live bot check with an environment proposal (`noise-level`, dB) and a refused dotted ID; close the test issues/PRs and delete bot branches.
