# Biosample importer and Excel template (design)

Date: 2026-11-11. Status: draft for review.

## Intent

Labs have no common format for biosample results (blood, saliva, urine, ...) and no
software export to read; results are typed by hand into Excel. The one real example
(`blood_subset.csv`, a serum hormone sheet from before an MRI session, handed over
without study background) is wide by analyte, mixes units per cell, and carries
censored values (`<5`, `<0,05`) and comma decimals.

PRISM already defines the output (`biosample` modality, `docs/specs/biosample.md`, schema
1.1.0): per subject/session/run/panel, one TSV with one row per sample and one column per
analyte, plus a sidecar JSON. What is missing is the way in. So we define one **Excel
template** as the guiding structure for new projects, an **importer** that turns it
into PRISM files, and a **migration** that fills the template from the legacy sheet.

## Goals

1. One Excel template, for every specimen type (serum, plasma, saliva, urine, hair, ...),
   with pull-downs fed from the schema's allowed values.
2. An importer (CLI command first; the Studio importer page only triggers it) that
   validates the template and writes biosample TSV + sidecar into a project.
3. A migration command for the legacy wide CSV/Excel, producing a filled template plus
   a report of what could not be mapped.
4. Analyte names resolve through the existing term registry (`terms/biosample`), the way
   survey columns do (`terms resolve`).

## Non-goals

- Reading any lab-system export format (none is known to be used).
- Changing the `biosample` schema or spec. Anything that needs it (e.g. a "clinically
  significant" field) is a separate pull request in prism-specification first.
- Inventing panels, specimen types or sample times that the source does not hold.
- Imputing censored values (the spec forbids substituting LOD/√2).

## Anti-goals (a failure even if it technically works)

- Studio and the CLI giving different files or messages for the same input.
- Silently normalising session labels (`T4.1`, `1`, `01` are different; exact strings).
- Silently dropping data: every column or row not written must be named in the report.
- Dates in the data (collection time is `hh:mm` only).

## The template (two sheets)

**Sheet `data`**: one row per measurement (long format, so a new analyte never needs a
new column).

| Column | Required | Notes |
| --- | --- | --- |
| `participant_id` | yes | becomes `sub-<label>` |
| `session` | per project | exact string; follows `src/session_map.py` rules (single-timepoint projects map to `ses-1`, reported) |
| `panel` | yes | alphanumeric; becomes `biosample-<label>` |
| `run` | no | repeated draws in one session (e.g. cortisol awakening response) |
| `sample_id` | no | pseudonymous tube ID |
| `collection_time` | no | `hh:mm` |
| `analyte` | yes | resolved through the term registry; unknown names pass with the registry's info |
| `value` | yes | number, or `n/a`, `<LOD`, `<LLOQ`, `>ULOQ` |
| `unit` | no | taken from the term if empty |
| `comment` | no | free text; stays in the template and is **not** written to PRISM files |

**Sheet `panels`**: one row per panel, the sidecar `Technical`/`Study` fields:
`panel`, `SpecimenType` (pull-down), `CollectionMethod`, `Anticoagulant`,
`FastingRequired`, `StorageTemperature`, `Laboratory`, `AssayMethod`, `AssayKit`,
`Description`.

The user may choose the specimen type at import (`--specimen`), which fills panels that
leave it empty; a value in the sheet wins. Pull-downs and the template file are generated
from the schema, never hand-maintained, so they cannot drift from it.

## The importer

- Command `prism_tools.py biosample import --input <xlsx|csv> --project <path>
  [--specimen <type>] [--dry-run]`; name and flags are the builder's call but the rule
  holds: same options and defaults in Studio, one function in `src/`, route and JS only
  collect input and show the result.
- Pivot long to the schema layout, group by subject/session/run/panel; write TSV and
  sidecar per file, with the sidecar built from the `panels` sheet and `Term` entries from
  the registry.
- Normalise per cell: comma decimals, float noise (`2.0099999999999998` becomes `2.01`),
  a bare `<5` becomes `<LOD`, with the limit `5` kept in the sidecar
  (`LowerLimitOfDetection`) and the choice reported (see Decisions and Open points).
- Text-file policy: written files are plain git (never annexed); keep the invariant in
  `CLAUDE.md` for anything that touches `.gitattributes`.
- Output is validated with the standard validator and its result shown; a parity test
  (`tests/test_cli_studio_parity*.py`) runs CLI and Studio on identical project copies
  and compares the written files.

## The migration (legacy wide sheet to template)

- Command `biosample migrate-wide --input <csv|xlsx> --output <template.xlsx>
  [--panel <name>] [--specimen <type>]`.
- Recognises the pattern `<Analyte> Results | <Analyte> Unit | <Analyte> clin. significant
  ...`; `Patient No.` and `Visit` become `participant_id` and `session`.
- Not the existing `wide_to_long` converter: that one splits session-coded columns
  (`T1_x`), this one is wide by analyte. Reuse `find_empty_data_rows` for the empty visit
  rows. Do not duplicate it.
- Defaults (all reported, none silent): one panel, default name `bloodhormones`;
  specimen `serum` (the only background is a verbal "serum, before an MRI"; the report
  marks it **unverified**); no panel mapping in v1 (YAGNI: the grouping is unknown). Splitting panels later is a re-run
  with a mapping option added when someone who knows the study can give one.
- Empty visit rows (e.g. `b004 T0`) are skipped and counted. Visit strings like `T4.1`
  stay exact.
- Columns that look like genetic or receptor markers (COMT, MAO, 5HTT, BDNF, AR, ER1,
  ER2, PR, MR) and are empty in the subset are listed as "unmapped" and dropped; if the
  full file has values they are mapped like any other analyte (a decision for the data
  owner, not the code).
- "clin. significant? (+comment)" goes into `comment`.
- `blood_subset.csv` is the test fixture. Encoding must be handled (the file has
  mojibake `µ` read as `¬µ`): detect and report, fix only when unambiguous.

## Constraints

- THE RULE: the CLI executes, Studio triggers. A migration or import option in Studio
  without a CLI flag is a bug. Studio code in `app/src/web/**` holds no logic.
- Follow the project page's widgets and the theme for the importer page; reuse the
  helpers in `chip-list.js` and the theme macros.
- Dual-tree check (`src/` vs `app/src/`) before editing any shared function; put new
  logic in `src/`.
- TDD per `CLAUDE.md`; `/security-review` not required unless the importer reads
  `code/specification/` or uploads in a new way (it reads uploads: the builder decides).
- The vendored specification is not edited here.

## Order of work

1. Template generator + importer + parity test + importer page.
2. Migration command, built on the fixture.
Each is its own branch and plan.

## Open points

- `<5` (no LOD/LLOQ distinction in the source): decided 2026-11-11 by the project owner,
  provisionally: treat as LOD, write `<LOD` and record the number in the sidecar as
  `LowerLimitOfDetection`. **To confirm later** with the lab/data owner; if it turns out to
  be LLOQ, only the code and sidecar key change (one place in the cell normaliser).
- Whether `clin. significant` should be a real field in the specification (future
  prism-specification change; out of scope here).
- Panel grouping of the full file: unknown; needs someone who knows the study.
- Mixed units per cell: the importer takes the unit per measurement; a panel column
  has one unit in the sidecar, so mixed units for one analyte within a panel are an error
  the builder must define a message for (not converted silently).

## Decisions from review (marked: from the spec, or the designer's call)

- **Censored values** (from the spec): the cell holds the code (`<LOD`, `<LLOQ`, `>ULOQ`);
  the numeric limit is a per-column sidecar key (`LowerLimitOfDetection`). Designer's call:
  if one analyte column holds different limits, the sidecar gets the highest (most
  conservative) one and the report names every limit seen. `>ULOQ` without a number is
  written as is. A bare `<5` becomes `<LOD` (see Open points).
- **Unit** (from the spec): a column with neither `Term` nor `Units` is an **error**; a
  unit different from the term's recommended one is accepted with an **info**, never
  converted. Units are per measurement in the template; two units for one analyte in one
  panel are an error.
- **Pivot** (designer's call): a *sample* is one distinct `(sample_id, collection_time)`
  pair; either may be empty, so two empty ones give one sample per subject/session/run/panel.
  Empty `run` means no `run-` entity in the file name. The same
  subject/session/run/panel/sample/analyte twice is an error, never "last wins".
- **Re-import** (designer's call): refuse to overwrite existing biosample files unless
  `--overwrite`; `--dry-run` lists what would be written. One sidecar per file, as the spec
  describes, so overrides stay local.
- **Subjects** (designer's call): `participant_id` goes through the project's existing
  subject-label helper (alphanumeric, `sub-` added if missing). The importer does not create
  participants; unknown subjects are reported as warnings.
- **Session**: in a `multiple` project an empty session is an error; the session map is read
  from the project, as other importers do (`src/session_map.py`).
- **Pull-downs** (from the spec): `SpecimenType`, `CollectionMethod` and `Anticoagulant` are
  schema enums; the others are free text or numbers. With neither sheet nor `--specimen`
  giving a specimen type, the import is an error (it is required in the schema).
- **Fixture:** a copy of `.claude/blood_subset.csv` goes into the test data, with the
  pseudonymous patient numbers kept as they are.

## What is left to the builder

CLI names and flags, the template's file name and location, error wording, how the
template's pull-downs are generated, and the module layout inside `src/`.
