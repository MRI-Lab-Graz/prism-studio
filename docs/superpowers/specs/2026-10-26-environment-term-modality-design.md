# Environment as a term modality (the biosample pattern for every PRISM modality)

Date: 2026-10-26. Status: design, not yet planned.

## Intent

Environment data enriches each session so that research questions can be asked across
studies, for example "does reaction time go with outside temperature?" or "does resting
state change with season and heat days?". Which environmental variables future users
will collect is unknown, so the modality must be open to any variable while still giving
everyone the same names and units for what is already known.

The user's goal for every PRISM modality: **fixed and flexible at the same time.** If a
modality is set up, everybody uses it; where nothing official exists yet, PRISM stays
open and the proposal path makes new things official.

Today's environment schema (1.1.0) does not do this: it was built around the Open-Meteo
enrichment converter, has a fixed list of columns, and is mostly about privacy
(`Privacy.AnchorField`, `IncludesRawDatetime`, ...). That is why the Propose page shows a
"Privacy" section for environment. Privacy is not the focus of this modality.

## The pattern (shared by every PRISM modality except survey)

Decided with the user:

- **Fixed: the structure.** Sidecar layout, column format, file names and each
  modality's own context fields. Small, changes rarely, only through a specification
  release; the validator enforces it with errors.
- **Flexible: the vocabulary.** Which variables exist lives in term files
  (`terms/<modality>/<local-id>.json`), not in the schema. A new term needs no schema
  change, only a proposal.
- **Rule:** a known term gives a column its official meaning. Any unit is accepted as
  long as the sidecar declares it (inch or cm, the user does not mind); a unit that
  differs from the term's gives a notice, as biosample does today. A numeric column
  bound to a term with no unit in the sidecar inherits the term's unit. An unknown
  column is allowed and gets a notice plus the offer to propose it.
- **What is shared is the pattern, not the fields.** Each modality has its own context
  fields (biosample: specimen and collection; environment: time window and source).
  Survey is outside the pattern: it is defined by its questionnaire.
- Biosample is the model. Other modalities (biometrics, physio, ...) move to the
  pattern later, one at a time, as separate projects.

## Goals

1. Environment schema 2.0.0 in prism-specification, built on the pattern.
2. A basic set of official environment terms, seeded from what the converter produces
   today.
3. Studio follows: the term tooling works for any modality that has terms (not only
   biosample), the converter writes the new format, the validator checks it, the Propose
   page treats environment like biosample.

## Non-goals

- Moving biometrics, physio or other modalities to the pattern (later projects).
- Survey (never; it is defined by its questionnaire).
- Keeping old environment files valid. The user decided the 1.1.0 format is retired: no
  migration, no dual support. Old files fail validation with a message that says to
  re-run the converter.
- New data providers beyond Open-Meteo.

## Anti-goals (would be a failure even if it works)

- A fixed column list in the schema again (every new variable needs a schema release).
- Privacy dominating the modality or the Propose page.
- A second copy of the term logic for environment next to biosample's (CLAUDE.md: one
  implementation).
- Blocking users whose variables are not official yet.

## Environment 2.0.0: structure

Files stay as today: `sub-<label>[_ses-<label>]_recording-<label>_environment.tsv`
(+ `.json`), linked to subject and session through the file name. One row per point in
time the values refer to (normally one row: the session).

Sidecar blocks, mirroring biosample:

- `Technical` (environment's own context, file level):
  - `Source` (required): where the values come from, e.g. `open-meteo`, `room-sensor`,
    `manual`. Free string plus a short list of suggested values (enum with `other` is the
    builder's call).
  - `SpatialResolution` (optional): e.g. `city`, `site`, `room`.
  - `TemporalResolution` (optional): e.g. `hourly`, `daily`.
- `Study`: `EnvironmentName` equal to the `recording-<label>` (as `BiosampleName` equals
  `biosample-<label>`), `Description`, optional citation fields.
- `Metadata`: `SchemaVersion`, `CreationDate`, `Creator` (as biosample).
- One entry per TSV column (`additionalProperties`), with biosample's column fields
  (`Term`, `Description`, `Units`, `Levels`, aliases) **plus environment's time window**:
  - `Window`: when the value refers to, relative to the session. `Start` and `End` as
    ISO 8601 durations before the session (`P3D` = 3 days before, `PT0S` = the session
    itself). Absent or both `PT0S` = at the session.
  - `Statistic`: how values in the window were summarised: `value` (single reading),
    `mean`, `min`, `max`, `sum`, `count`.
  - Example: `temp_max_3d` = `{"Term": "prism:air-temperature", "Window": {"Start": "P3D",
    "End": "PT0S"}, "Statistic": "max"}`.
- The `Privacy` block is removed. The spec page keeps one sentence: do not store exact
  location or raw timestamps unless your governance allows it.

The window sits on the column, not the file, because one file holds both "temperature
at the session" and "highest temperature over the 3 days before" (heat days are about the
days before, not the moment of the scan).

## Environment terms

- One level only: a term is the variable (`prism:air-temperature`). Biosample's second
  level (the analyte in a specimen) has no natural counterpart here; distinctions such as
  indoor vs. outdoor are part of the term's name and description where they matter.
  *(My call, following the user's "second level optional, modality-specific".)*
- Terms may be numeric (`Units`, ranges) or categorical (`Levels`, e.g. `prism:season`,
  `prism:sun-phase`). Biosample terms are numeric only; the term format gains `Levels`.
- External equivalents: where one exists, a term names its CF Standard Name
  (climate/forecast conventions; e.g. `air_temperature`, `relative_humidity`,
  `ultraviolet_index`), the way biosample terms name LOINC codes.
- Basic set: one term for each value column the converter writes today (temperature,
  apparent temperature, dew point, humidity, pressure, precipitation, wind speed, cloud
  cover, UV index, shortwave radiation, AQI, PM2.5, PM10, NO2, O3, the pollen counts,
  season, sun phase, daylight hours, hours since sun, moon phase and illumination,
  elevation, hour bin). Columns that only identify rows (`subject_id`, `session_id`,
  `filename`, `relative_time`) are not terms.

## Making the term tooling modality-generic

Today the term code is biosample-only: levels are hard-coded as `analyte` /
`analyte-specimen`, the second level is `Technical.SpecimenType`, default arguments are
`modality="biosample"`, the column filter (`NON_ANALYTE_COLUMNS`) is biosample's, and the
Propose page's measurement form builds analyte + specimen terms.

Required: each modality declares in its `entities.schema.json` entry what its terms look
like (at least: has terms, which sidecar keys are not term columns, and the context field
of the second level or none). The checks in prism-specification (`check_terms.py`,
`term_proposal.py`) and Studio (`src/term_registry.py`, `src/spec_overlay.py`,
`src/spec_contribute.py`, `src/term_proposal.py`, the validator's term notices) read that
declaration instead of assuming biosample. Biosample's existing term files keep working
unchanged. How the declaration is spelled is the builder's call.

## Studio

- Sync the new specification release (`scripts/sync_specification.py --tag <tag>`).
- Converter (`src/environment_conversion.py`, `prism_tools.py environment ...`, the
  Environment tab): writes the 2.0.0 sidecar (`Technical`, `Study`, `Metadata`, columns
  with `Term`), no `Privacy` block. Existing values stay at-session (`Window` absent).
- Time windows in the converter (in this project, decided by the user): the user picks a
  variable, **any ISO 8601 duration** before the session and a statistic (`mean`, `min`,
  `max`, `sum`, `count`); the converter fetches the hourly provider data for that range
  and writes the windowed column with its `Window` and `Statistic`. CLI first, the same
  options in the GUI. The per-day provider cache is extended to cover multi-day ranges
  (each day fetched once per location, reused across sessions).
- Validator: 2.0.0 schema, term notices for environment, `Window`/`Statistic` checked by
  the schema. Old 1.1.0 sidecars fail with a message pointing to the converter.
- Propose page: environment shows like biosample (accepted terms beside the proposal, a
  "missing measurement" form proposing a term with name, unit or levels, description,
  optional CF Standard Name). The Privacy section disappears with the block.

## Order of work

1. prism-specification: environment 2.0.0 (archive 1.1.0), term declaration per modality,
   generic checks, environment basic term set, `Levels` in terms, spec page; tag a minor
   release (content change). Separate PR, released first (CLAUDE.md: specification first,
   then Studio with the new tag).
2. Studio: sync, generic term tooling, converter, validator.
3. Studio: Propose page for environment.

## Calls made in writing this (not discussed with the user)

- **Fixed column lists go.** The validator's `ENV_REQUIRED_COLUMNS` is removed; no
  column is required (subject and session come from the file name).
  `ENV_FORBIDDEN_COLUMNS` (date, timestamp, lat, lon, ...) drops from error to warning,
  so a room-sensor file with a timestamp can pass.
- **Every value column the converter writes becomes a term**, including
  `weather_regime`, `pollen_risk_bin` and `heatwave_status` (categorical), so PRISM's
  own output never triggers "propose this term" notices. `relative_time` (a privacy
  token without meaning for analysis) is dropped from the output.
- **Categorical levels:** a value outside the term's `Levels` is a warning, never an
  error (open by default). A sidecar may describe levels (e.g. `00-05` for `night`) but
  not give an official level a different meaning.
- **Term IDs are unique within a modality**, as lookups are today; no check across
  modalities.
- **A term is always the bare variable.** Window and statistic live only on the column.
  "Heat days" is a column (`prism:air-temperature`, `max`, window `P3D`), not a term.

## Left to the builder

- Exact spelling of the per-modality term declaration and of `Technical.Source` values.
- Term IDs and descriptions of the basic set; which CF Standard Names fit.
- How the validator words the "old format" error.
