# Biosample

The `biosample` modality is a PRISM extension for laboratory results from biological samples (blood, saliva, urine, hair, ...). It describes the *assay results* of a sample, not the sample's storage. Standard BIDS has no modality for this.

## File Name Structure

Biosample data files MUST follow this naming convention:

`sub-<label>[_ses-<label>]_biosample-<label>[_run-<index>]_biosample.<extension>`

| Entity | Description |
| --- | --- |
| `sub` | **Required**. The subject identifier. |
| `ses` | **Optional**. The session identifier (any string, compared exactly). |
| `biosample` (entity) | **Required**. The **assay panel**, alphanumeric (for example `inflammation`, `cortisol`, `lipids`, `bloodcount`). It names the panel, not the specimen. |
| `run` | **Optional**. Repeated draws within one session, one file per draw (a cortisol awakening response at +0, +15 and +30 minutes is `run-1`, `run-2`, `run-3`). |
| `biosample` (suffix) | **Required**. The suffix indicating the modality. |
| `extension` | **Required**. `.tsv` for data, `.json` for the sidecar. |

The specimen type lives in the sidecar (`Technical.SpecimenType`). The same analyte measured in two specimens is two panels, for example `cortisolsaliva` and `cortisolserum`.

**Example:**
`sub-02_ses-1_biosample-inflammation_biosample.tsv`

A file name without the `biosample-<label>` entity is an error.

## Data format

One file per subject, session and run. One row per sample, one column per analyte, plus optional sample-level columns. Every column is described in the sidecar.

```text
sample_id	collection_time	fasting	crp	il6	tnfa
B-0152	08:40	0	0.4	<LOD	1.12
```

Recommended sample-level columns (not enforced): `sample_id` (a pseudonymous lab tube ID), `collection_time` (clock time `hh:mm` only, **never a date**, because dates are identifying) and `fasting` (`Levels` `0` = no, `1` = yes).

### Missing and censored values

In numeric `biosample` columns the validator accepts these codes besides `n/a`. They are skipped by the minimum/maximum checks. Categorical columns (with `Levels` or `AllowedValues`) still reject them, and other modalities are unaffected.

| Code | Meaning |
| --- | --- |
| `n/a` | not measured, sample failed or not applicable |
| `<LOD` | measured, below the limit of detection |
| `<LLOQ` | detected, below the lower limit of quantification |
| `>ULOQ` | above the upper limit of quantification |

Raw data are never substituted (for example LOD/√2); that is an analysis decision. The limits are in the sidecar for anyone who wants to impute. Reading in pandas: `pd.read_csv(..., sep="\t", na_values=["n/a", "<LOD", "<LLOQ", ">ULOQ"])`.

## Sidecar JSON (`*_biosample.json`)

Each panel is described once, as a template named `biosample-<label>.json`. It is looked up in the project library (`library/biosample/`), and a subject- or session-specific sidecar next to the TSV overrides it. An example template is shipped as `official/library/biosample/biosample-inflammation.json`.

### Top-Level Objects

| Object | Requirement | Description |
| --- | --- | --- |
| `Technical` | **REQUIRED** | How the sample was taken, processed and measured. |
| `Study` | **REQUIRED** | The panel and its scientific context. |
| `Metadata` | **REQUIRED** | Administrative metadata about the file itself. |

Every other key of the sidecar is a column definition (`Description`, `Units`, and optionally `DataType`, `Levels`, `LowerLimitOfDetection`, `MinValue`, `WarnMaxValue`, `LOINC`, ...).

### `Technical` Object Fields

| Key | Requirement | Type | Description |
| --- | --- | --- | --- |
| `SpecimenType` | **REQUIRED** | `string` | `whole-blood`, `serum`, `plasma`, `dried-blood-spot`, `saliva`, `urine`, `hair`, `stool`, `csf` or `other`. |
| `CollectionMethod` | RECOMMENDED | `string` | `venipuncture`, `capillary`, `passive-drool`, `swab`, `other` or empty. |
| `Anticoagulant` | RECOMMENDED | `string` | `EDTA`, `heparin`, `citrate`, `none`, `other` or empty (blood specimens). |
| `FastingRequired` | RECOMMENDED | `boolean` | Whether participants had to fast before collection. |
| `ProcessingProtocol` | RECOMMENDED | `string` | Free text: clotting, centrifugation, aliquoting. |
| `StorageTemperature` | RECOMMENDED | `number` | Storage temperature in degrees Celsius (for example `-80`). |
| `Laboratory` | RECOMMENDED | `string` | The laboratory that ran the assay. |
| `AssayMethod` | RECOMMENDED | `string` | For example ELISA, CLIA or LC-MS/MS. |
| `AssayKit` | RECOMMENDED | `string` | Kit name, manufacturer and lot. |

A missing recommended field is a **warning**, reported once per sidecar, not an error.

### `Study` Object Fields

| Key | Requirement | Type | Description |
| --- | --- | --- | --- |
| `BiosampleName` | **REQUIRED** | `string` | The panel identifier (`^[a-zA-Z0-9]+$`). It MUST equal the `biosample-<label>` of the file name, otherwise the validator reports an error. |
| `Description` | OPTIONAL | `string` or `object` | What the panel measures. |
| `Citation` | OPTIONAL | `string` | Citation for the assay protocol. |
| `DOI` | OPTIONAL | `string` | DOI for the assay protocol. |
| `Keywords` | OPTIONAL | `array` | Keywords describing the panel. |

### `Metadata` Object Fields

| Key | Requirement | Type | Description |
| --- | --- | --- | --- |
| `SchemaVersion` | **REQUIRED** | `string` | Semantic version of the template, for example `1.0.0`. |
| `CreationDate` | **REQUIRED** | `string` | `YYYY-MM-DD`. |
| `Creator` | OPTIONAL | `string` | Who created the template. |

## Terms

A column can be mapped to a shipped *term* (`terms/biosample/`) with the optional key `Term`. A term is identified by a stable, prefixed ID that never changes once released (`prism:cortisol` for the analyte, `prism:cortisol.saliva` for the analyte in one specimen); the label is only a name and may change.

```json
"cort": {"Term": "cortisol"}
```

- `Term` accepts the full ID, the local name (`cortisol`), a label, an alias or an external equivalent (for example `loinc:2143-6`). With `SpecimenType: saliva` it resolves to `prism:cortisol.saliva`.
- The column inherits `Units`, `DataType`, `MinValue`, `MaxValue`, `WarnMinValue`, `WarnMaxValue` and `LOINC` from the term. Anything you set on the column wins. With a `Term`, `Description` and `Units` are optional.
- Any metric may be used without a term. Nothing is blocked: a metric the registry does not know passes with an **info** that lists similar official terms (it may just be named differently) and offers to share it with the PRISM community. The maintainers may choose a different name; your files keep working through an alias. To share it, run `python prism_tools.py terms propose --sidecar <sidecar> --column <column> --open` in PRISM Studio: it builds the proposal from your column and opens a prefilled issue form in the specification repository, where a bot checks it and a maintainer takes it from there. Nothing is sent without `--open`.
- A column named like an alias (`cort`) gets an info suggesting `Term`; the validator never applies a match silently and never rewrites your files.

| Situation | Severity |
| --- | --- |
| Metric not in the registry | info (similar terms listed) |
| Declared unit differs from the term's recommended unit | info (any declared unit is accepted) |
| Known analyte, no term for this specimen yet | info |
| Term for another specimen than `Technical.SpecimenType` | **error** |
| Term is deprecated | warning, names the replacement |
| `Term` not in the registry and no `Units` | **error** |

Look terms up on the command line: `python prism_tools.py terms list|show|suggest` (see the [CLI reference](https://prism-studio.readthedocs.io/en/latest/CLI_REFERENCE.html)).

## BIDS compatibility

`biosample` is PRISM-only. PRISM adds `*_biosample.*` to the generated `.bidsignore`, so standard BIDS tools skip these files.

The authoritative machine-readable schema is [`schemas/stable/biosample.schema.json`](../../app/schemas/stable/biosample.schema.json).

<!-- BEGIN SCHEMA REFERENCE (generated by scripts/generate_schema_reference.py; do not edit) -->

## Field reference (`biosample.schema.json`, version 1.1.0)

Generated from [`schemas/stable/biosample.schema.json`](../../app/schemas/stable/biosample.schema.json). Nested fields are shown as `Block.Field`; `[]` marks list items. *Required* applies within its parent block.

| Field | Type | Required | Description |
| --- | --- | --- | --- |
| `Technical` | object | yes | Specimen, collection, storage and assay properties |
| `Technical.SpecimenType` | string | yes | Type of biological specimen the assay was run on Allowed: `whole-blood`, `serum`, `plasma`, `dried-blood-spot`, `saliva`, `urine`, `hair`, `stool`, `csf`, `other`. |
| `Technical.CollectionMethod` | string | no | How the specimen was collected Allowed: `venipuncture`, `capillary`, `passive-drool`, `swab`, `other`, ``. |
| `Technical.Anticoagulant` | string | no | Anticoagulant in the collection tube (blood specimens) Allowed: `EDTA`, `heparin`, `citrate`, `none`, `other`, ``. |
| `Technical.FastingRequired` | boolean | no | Whether participants were required to fast before collection |
| `Technical.ProcessingProtocol` | string | no | Free-text processing steps (clotting, centrifugation, aliquoting) |
| `Technical.StorageTemperature` | number | no | Storage temperature in degrees Celsius (e.g. -80) |
| `Technical.Laboratory` | string | no | Laboratory that ran the assay |
| `Technical.AssayMethod` | string | no | Assay method (e.g. ELISA, CLIA, LC-MS/MS) |
| `Technical.AssayKit` | string | no | Assay kit name, manufacturer and lot |
| `Study` | object | yes | Panel-level information |
| `Study.BiosampleName` | string | yes | Assay panel identifier; must equal the biosample-<label> in the filename (e.g. inflammation) |
| `Study.Description` | string / object | no | What this panel measures |
| `Study.Citation` | string | no | Citation for the assay protocol |
| `Study.DOI` | string | no | DOI for the assay protocol |
| `Study.Keywords` | array | no | Keywords describing the panel |
| `Metadata` | object | yes | Administrative metadata |
| `Metadata.SchemaVersion` | string | yes |  |
| `Metadata.CreationDate` | string | yes | Date of creation |
| `Metadata.Creator` | string | no |  |

<!-- END SCHEMA REFERENCE -->
