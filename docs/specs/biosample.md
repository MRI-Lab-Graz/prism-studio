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

```tsv
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

## BIDS compatibility

`biosample` is PRISM-only. PRISM adds `*_biosample.*` to the generated `.bidsignore`, so standard BIDS tools skip these files.

The authoritative machine-readable schema is [`app/schemas/stable/biosample.schema.json`](../../app/schemas/stable/biosample.schema.json).
