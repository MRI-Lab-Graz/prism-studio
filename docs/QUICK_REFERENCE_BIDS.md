# BIDS Compatibility Quick Reference

Use this page when you need a short reminder of how PRISM stays compatible with
BIDS and what that means for day-to-day project metadata.

This is a public-facing quick reference, not a deep developer implementation
note.

## At a glance

PRISM Studio tries to keep project metadata aligned with BIDS expectations while
adding PRISM-specific structure where psychology workflows need more detail.

Core idea:

- BIDS compatibility remains the baseline
- PRISM-specific metadata should not break standard BIDS-oriented usage
- project metadata should stay internally consistent across files such as
    `dataset_description.json` and `CITATION.cff`

## Key metadata groups

### Required baseline fields

These are the fields users should think about first because they matter most for
basic dataset validity.

- `Name`
- `BIDSVersion`

### Common recommended fields

These often improve compatibility, interpretability, or reusability.

- `DatasetType`
- `License`
- `Keywords`
- contributor and reference information where applicable

### Project-specific or workflow-specific fields

These depend on the study and are not equally relevant for every project.

- acknowledgements
- funding
- ethics approvals
- dataset DOI and related links

## `dataset_description.json` and `CITATION.cff`

One recurring theme in PRISM projects is that metadata may exist in more than one
place if you are not careful.

The practical rule is simple:

- avoid duplicating the same citation-oriented information unnecessarily
- treat `CITATION.cff` as the citation-focused file when present
- keep `dataset_description.json` aligned with the broader BIDS dataset metadata

This reduces drift between files and makes exported metadata easier to trust.

## Why this matters for PRISM users

If study-level metadata drifts, you can end up with:

- confusing validation results
- inconsistent exports
- harder-to-reuse datasets
- extra cleanup work before sharing

## Good user workflow

Recommended order:

1. create or open the project in **Projects**
2. complete the important dataset metadata there
3. let PRISM manage the resulting project files
4. validate the dataset
5. review the exported or generated metadata before sharing

## Good developer workflow

If you are changing metadata behavior in the codebase, verify:

- save and reload behavior stay consistent
- `dataset_description.json` remains valid
- `CITATION.cff` stays in sync when relevant
- validation and export flows still behave as expected

## Common pitfalls

- filling only the minimum required field set and forgetting the recommended fields
- manually editing multiple metadata files and letting them drift apart
- assuming citation metadata and dataset metadata are interchangeable
- validating too late, after multiple metadata edits have accumulated

## Related pages

- [PROJECTS.md](studio/projects.md)
- [SPECIFICATIONS.md](SPECIFICATIONS.md)
- [VALIDATOR.md](studio/validator.md)
- [WHAT_IS_PRISM.md](WHAT_IS_PRISM.md)
- **Status Summary**: See `docs/BIDS_AUTO_MAPPING_COMPLETE.md` (overview)
- **Official BIDS**: https://bids-specification.readthedocs.io/

---

## 🚀 Quick Debugging Commands

```bash
# Check project structure
ls -la <project_path>/

# View dataset_description.json
cat <project_path>/dataset_description.json | python3 -m json.tool

# View CITATION.cff
cat <project_path>/CITATION.cff

# Run validation tests
python3 scripts/ci/test_bids_compliance.py

# Check Flask logs
grep -i "dataset_description\|citation" prism-studio.log
```

---

## 📊 Field Summary Table

| Field | Type | Required | Default | Array | CITATION.cff | Notes |
|-------|------|----------|---------|-------|-------------|-------|
| Name | string | ✅ | - | ❌ | ✅ Synced | BIDS core identifier |
| BIDSVersion | string | ✅ | "1.10.1" | ❌ | ❌ | Auto-set by backend |
| DatasetType | string | ⚠️ | "raw" | ❌ | ❌ | raw, derivative, study |
| License | string | ⚠️ | "CC0" | ❌ | **Omitted if CITATION.cff** | SPDX identifier |
| Authors | array | ❌ | [] | ✅ | **Omitted if CITATION.cff** | {name, email} format |
| Keywords | array | ❌ | [] | ✅ | ❌ | ≥3 for FAIR |
| Acknowledgements | string | ❌ | "" | ❌ | ❌ | Free text |
| HowToAcknowledge | string | ❌ | "" | ❌ | **Omitted if CITATION.cff** | Citation instructions |
| Funding | array | ❌ | [] | ✅ | ❌ | Free text |
| EthicsApprovals | array | ❌ | [] | ✅ | ❌ | {name, reference} |
| ReferencesAndLinks | array | ❌ | [] | ✅ | **Omitted if CITATION.cff** | URLs |
| DatasetDOI | string | ❌ | "" | ❌ | ✅ Synced | DOI URI |
| HEDVersion | string | ❌ | "" | ❌ | ❌ | If HED tags used |

---

**Last Updated**: February 2025  
**For questions**: See full documentation in `docs/BIDS_COMPLIANCE_IMPLEMENTATION.md`
