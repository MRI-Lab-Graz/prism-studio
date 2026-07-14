# BIDS Compatibility Quick Reference

A short reminder of how PRISM stays compatible with BIDS and what that means for
day-to-day project metadata — a public-facing quick reference, not a deep developer
note.

## At a glance

PRISM Studio keeps project metadata aligned with BIDS expectations while adding
PRISM-specific structure where psychology workflows need more detail: BIDS
compatibility remains the baseline, PRISM-specific metadata shouldn't break standard
BIDS-oriented usage, and project metadata should stay internally consistent across
files like `dataset_description.json` and `CITATION.cff`.

- **Required baseline fields** (matter most for basic dataset validity): `Name`,
  `BIDSVersion`.
- **Common recommended fields** (improve compatibility/interpretability/reusability):
  `DatasetType`, `License`, `Keywords`, contributor/reference info.
- **Project-specific fields** (depend on the study): acknowledgements, funding,
  ethics approvals, dataset DOI and related links.

## Keeping `dataset_description.json` and `CITATION.cff` in sync

Metadata can end up duplicated across files if you're not careful. The practical
rule: avoid duplicating citation-oriented information unnecessarily, treat
`CITATION.cff` as the citation-focused file when present, and keep
`dataset_description.json` aligned with the broader BIDS dataset metadata. This
reduces drift and makes exported metadata easier to trust — drifted metadata leads
to confusing validation results, inconsistent exports, harder-to-reuse datasets, and
extra cleanup before sharing.

## Recommended workflow

Create/open the project in **Projects** → complete the important dataset metadata
there → let PRISM manage the resulting project files → validate → review the
exported/generated metadata before sharing.

If you're changing metadata behavior in the codebase, verify: save/reload behavior
stays consistent, `dataset_description.json` remains valid, `CITATION.cff` stays in
sync when relevant, and validation/export flows still behave as expected.

**Common pitfalls**: filling only the minimum required fields and forgetting the
recommended ones; manually editing multiple metadata files and letting them drift
apart; assuming citation metadata and dataset metadata are interchangeable;
validating too late, after multiple metadata edits have accumulated.

## Field reference

| Field | Type | Required | Default | Array | CITATION.cff | Notes |
|-------|------|----------|---------|-------|-------------|-------|
| Name | string | ✅ | - | ❌ | ✅ Synced | BIDS core identifier |
| BIDSVersion | string | ✅ | "1.10.1" | ❌ | ❌ | Auto-set by backend |
| DatasetType | string | ⚠️ | "raw" | ❌ | ❌ | raw, derivative, study |
| License | string | ⚠️ | "CC0" | ❌ | Omitted if CITATION.cff | SPDX identifier |
| Authors | array | ❌ | [] | ✅ | Omitted if CITATION.cff | {name, email} format |
| Keywords | array | ❌ | [] | ✅ | ❌ | ≥3 for FAIR |
| Acknowledgements | string | ❌ | "" | ❌ | ❌ | Free text |
| HowToAcknowledge | string | ❌ | "" | ❌ | Omitted if CITATION.cff | Citation instructions |
| Funding | array | ❌ | [] | ✅ | ❌ | Free text |
| EthicsApprovals | array | ❌ | [] | ✅ | ❌ | {name, reference} |
| ReferencesAndLinks | array | ❌ | [] | ✅ | Omitted if CITATION.cff | URLs |
| DatasetDOI | string | ❌ | "" | ❌ | ✅ Synced | DOI URI |
| HEDVersion | string | ❌ | "" | ❌ | ❌ | If HED tags used |

Quick debugging:

```bash
ls -la <project_path>/
cat <project_path>/dataset_description.json | python3 -m json.tool
cat <project_path>/CITATION.cff
```

## What's next

- [Projects](studio/projects.md) · [Specifications](SPECIFICATIONS.md) ·
  [Validator](studio/validator.md) · [What is PRISM](WHAT_IS_PRISM.md)
- Official BIDS spec: <https://bids-specification.readthedocs.io/>
