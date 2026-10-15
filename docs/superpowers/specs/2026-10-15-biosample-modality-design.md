# Biosample modality — design

Date: 2026-10-15
Branch: `feat/biosample-modality`
Status: design approved in chat; awaiting written-spec review

## Goal

Add `biosample` as a new top-level PRISM modality for results of assays on
biological specimens (blood, serum, plasma, saliva, urine, hair, stool, CSF).
BIDS has no general place for this (only the PET-specific
`pet/*_recording-<label>_blood.tsv` for arterial input functions; we do not
reuse the `_blood` suffix). The modality is project-agnostic: it is prepared
before any concrete dataset exists, so nothing in it is tailored to one lab
or one export format.

`biosample` is its own modality, not a sub-type of `biometrics`, but it
mirrors `biometrics` structurally so the existing tabular machinery (template
lookup, column constraints, validation) carries over.

## Out of scope

- Omics (genotyping, methylation, RNA-seq): large files, not a value table.
  Would be a separate modality if ever needed.
- Biobank inventory (aliquots, freezer positions): not research data.
- Derived values (cortisol AUC, NLR, ...): phase 5, recipes, only once a
  concrete use case exists.
- A generated field-by-field "PRISM spec" website: separate project (see
  "Follow-ups").

## File layout and naming

```
sub-<label>/[ses-<label>/]biosample/
  sub-<label>[_ses-<label>]_biosample-<label>[_run-<index>]_biosample.tsv
  sub-<label>[_ses-<label>]_biosample-<label>[_run-<index>]_biosample.json   (optional, overrides template)
library/biosample/biosample-<label>.json                                       (template)
```

- `biosample-<label>`: the **assay panel** (e.g. `inflammation`, `cortisol`,
  `lipids`, `bloodcount`), alphanumeric. Not the specimen.
- Specimen type lives in the template (`Technical.SpecimenType`). The same
  analyte in two specimens = two labels (`cortisolsaliva`, `cortisolserum`).
  No `specimen-` entity (add only if this becomes common).
- `run-<index>`: repeated draws within one session (e.g. cortisol awakening
  response +0/+15/+30 min = run-1/2/3). One file per draw.
- Session labels are free-form strings, compared exactly (repo rule).

## Data format: wide

One file per subject/session/run; one row per sample; one column per
analyte, plus optional sample-level columns. Every column is described in the
template, like `biometrics`/`survey`.

Example `sub-02_ses-1_biosample-inflammation_biosample.tsv`:

```tsv
sample_id	collection_time	fasting	crp	il6	tnfa
B-0152	08:40	0	0.4	<LOD	1.12
```

Long format (`analyte, value, unit` rows) was rejected: it breaks the
"sidecar describes the columns" model the whole validator relies on. Lab
exports in long format are pivoted by the converter (phase 2).

### Missing and censored values

In numeric columns of `biosample` files the validator accepts, besides
`n/a`:

| Code    | Meaning                                         |
|---------|-------------------------------------------------|
| `n/a`   | not measured / sample failed / not applicable   |
| `<LOD`  | measured, below limit of detection              |
| `<LLOQ` | detected, below lower limit of quantification   |
| `>ULOQ` | above upper limit of quantification             |

Codes are always allowed in `biosample` numeric columns (not conditional on
the matching limit being declared). They are skipped by min/max range
checks. No substitution (e.g. LOD/√2) in raw data — that is an analysis
choice; the limits are in the template for anyone who wants to impute.
Other modalities are unaffected.

Readers: `pd.read_csv(..., sep="\t", na_values=["n/a", "<LOD", "<LLOQ", ">ULOQ"])`.

### Recommended sample-level columns

Not required; the validator does not enforce them. Documented in the example
template:

- `sample_id` — lab tube ID (pseudonymous).
- `collection_time` — clock time `hh:mm` only, **never a date** (dates are
  identifying).
- `fasting` — `Levels {"0": "no", "1": "yes"}`.

## Schema: `app/schemas/stable/biosample.schema.json`

Same top-level shape as `biometrics.schema.json`: `Technical`, `Study`,
`Metadata`, plus `additionalProperties` = column definitions.

### Required

| Path                      | Rule |
|---------------------------|------|
| `Technical.SpecimenType`  | enum `whole-blood`, `serum`, `plasma`, `dried-blood-spot`, `saliva`, `urine`, `hair`, `stool`, `csf`, `other` |
| `Study.BiosampleName`     | `^[a-zA-Z0-9]+$`, must equal the filename `biosample-` label |
| `Metadata.SchemaVersion`  | semver, as in every PRISM schema |
| `Metadata.CreationDate`   | `YYYY-MM-DD`, as in every PRISM schema |
| column `Description`      | string or i18n object |
| column `Units`            | string; `n/a` for non-numeric columns |

### Recommended `Technical` fields

Missing → validator **WARNING** (not error). No such mechanism exists yet
for other modalities; phase 1 adds a minimal one for biosample only (a list
of recommended keys checked against the resolved sidecar), not a generic
framework.


- `CollectionMethod`: enum `venipuncture`, `capillary`, `passive-drool`, `swab`, `other`, `""`
- `Anticoagulant`: enum `EDTA`, `heparin`, `citrate`, `none`, `other`, `""`
- `FastingRequired`: boolean
- `ProcessingProtocol`: string (free text: clotting, centrifugation, aliquoting)
- `StorageTemperature`: number, °C
- `Laboratory`: string
- `AssayMethod`: string (e.g. ELISA, CLIA, LC-MS/MS)
- `AssayKit`: string (kit name, manufacturer, lot)

### Optional `Study` fields

- `Description`, `Citation`, `DOI`, `Keywords` (as in biometrics).

Dropped vs. biometrics (not meaningful for a project-defined panel):
`OriginalName`, `Category`, `FileFormat` (always tsv), and the
biometrics-specific fields (`Equipment`, `Supervisor`, `WarmupProtocol`,
`Respondent`, `I18n`, `Scoring`, `Normative`).

### Column definition fields

Reused from biometrics: `Description`, `Units`, `DataType`, `MinValue`,
`MaxValue`, `WarnMinValue`, `WarnMaxValue`, `AllowedValues`, `Levels`,
`AliasOf`, `Aliases`.

New:

| Field                          | Type |
|--------------------------------|------|
| `LOINC`                        | string, `^\d+-\d$` |
| `LowerLimitOfDetection`        | number |
| `LowerLimitOfQuantification`   | number |
| `UpperLimitOfQuantification`   | number |
| `ReferenceRange`               | object `{min, max}` (numbers or null) |
| `IntraAssayCV`                 | number, percent |
| `InterAssayCV`                 | number, percent |

`ReferenceRange` is informational only (clinical normal range); it does not
trigger warnings. Use `WarnMin/MaxValue` for that.

## Integration (where `biosample` must be wired)

`"biometrics"` is hard-coded ~134 times in 25 files. We do **not** add a
parallel `"biosample"` literal at each site. In every file a phase touches,
membership checks like `modality in {"survey", "biometrics"}` are replaced by
one shared tuple in `app/src/constants.py` (e.g. `TABULAR_MODALITIES`), and
`biosample` is added there once. Files not touched by a phase stay as they
are (no unrelated refactor).

Known anchor points (phase 1):

- `app/schemas/stable/entities.schema.json` — register `biosample`
  (`kind: prism`, suffix `biosample`, extensions `tsv`, `json`). Drives
  `MODALITY_PATTERNS` / `PRISM_MODALITIES` in `app/src/validator.py`.
- `app/src/validator.py` — tabular content validation (`validate_data_content`),
  strict filename-pattern check, template lookup (`library/biosample/`),
  censoring codes.
- `app/src/bids_integration.py` — add `*_biosample.*` to the `.bidsignore`
  patterns so the BIDS validator skips the folder.
- Schema registry / version folders, so `biosample` resolves under `stable`.
- Run the dual-tree check (CLAUDE.md) for every non-route file touched in
  `app/src/`.

## Phases

Each phase: own implementation plan, TDD (failing test first), merged on its
own after `ponytail:ponytail-audit`.

1. **Schema + validation.** `biosample.schema.json`; entity registration;
   validator (naming, template lookup, column constraints, censoring codes);
   `.bidsignore`; shared modality tuple at touched sites; example template
   `official/library/biosample/biosample-inflammation.json`; works via
   `prism.py` and the GUI validator. Data is hand- or script-written.
2. **Converter.** Table (xlsx/csv/tsv, one row per subject[/session][/run],
   analyte columns) → biosample TSVs. Backend in `src/`, CLI in
   `prism_tools.py`. Generalise from `excel_to_biometrics` where it is shared
   logic; do not copy it. Long-format input pivoted here. Exact input shape
   finalised when a real lab export is available.
3. **Template Editor + library.** `biosample` in `SUPPORTED_MODALITIES`;
   create/edit biosample templates; library browsing.
4. **GUI conversion page.** Thin adapter over the phase-2 command (GUI/CLI
   parity rule).
5. **Recipes** (deferred until a concrete use case, e.g. cortisol AUCg/AUCi
   across `run-` draws).

## Testing (phase 1)

- Schema: valid example template passes; missing `SpecimenType`, bad
  `SpecimenType` value, `BiosampleName` mismatch with filename, bad `LOINC`
  pattern → errors.
- Validator on a fixture dataset with `sub-*/ses-*/biosample/`:
  - correct file validates clean;
  - `<LOD`/`<LLOQ`/`>ULOQ` accepted in numeric biosample columns and skipped
    by range checks;
  - the same codes in a `biometrics` numeric column still fail;
  - value below `MinValue` → error; above `WarnMaxValue` → warning;
  - column missing from template / template missing → reported as for
    biometrics;
  - bad filename (missing `biosample-` label) → error.
- Missing recommended `Technical` field (e.g. `AssayMethod`) → warning, not
  error.
- `.bidsignore` contains the biosample pattern.
- Validator image has no pandas: phase-1 imports must not need pandas
  (existing regression test must stay green).

## Follow-ups (not this spec)

- PRISM spec website: field-by-field reference pages generated from the
  JSON schemas' `description` fields (single source of truth), extending
  `docs/SPECIFICATIONS.md`. Separate brainstorm.
- Example-template LOINC codes must be checked against loinc.org before the
  template ships (hsCRP 30522-7 and IL-6 26881-3 are believed correct; TNF-α
  to be looked up).
