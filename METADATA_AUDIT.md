# PRISM Studio Metadata Field Audit

## Overview
This document maps all metadata fields from the Study Metadata form in the web UI to their destinations in:
- `dataset_description.json` (BIDS)
- `project.json` (PRISM project metadata)
- `README.md` (auto-generated documentation)
- `CITATION.cff` (citation metadata)

---

## 📋 UI Form Fields → Data Model Mapping

### Basics Section (Study Metadata → dataset_description.json + project.json)

| Field Name (UI) | UI ID | dataset_description.json | project.json | README.md | CITATION.cff | Notes |
|---|---|---|---|---|---|---|
| **Dataset Name** | `metadataName` | `Name` | (title) | `DATASET_NAME` | `title` | **CRITICAL**: Required for BIDS |
| **Authors** | `metadataAuthorsList` | `Authors[]` | (list) | `CONTACT_NAME` (first) | `authors[]` | Can have multiple authors |
| **License** | `metadataLicense` | `License` | (reference) | `LICENSE` | ❌ Not in CITATION.cff | BIDS required field |
| **Acknowledgements** | `metadataAcknowledgements` | `Acknowledgements` | (reference) | (not used) | ❌ Not in CITATION.cff | Optional BIDS field |
| **Dataset DOI** | `metadataDOI` | `DatasetDOI` | (reference) | (not used) | `doi` | Syncs to CITATION.cff |
| **Ethics Approvals** | `metadataEthicsYes/No` buttons + committee/votum | `EthicsApprovals[]` | (reference) | `ETHICS_APPROVALS` | ❌ Not in CITATION.cff | Format: "Committee, Ref#" |
| **Keywords** | `metadataKeywords` | `Keywords[]` | (reference) | (not used) | ❌ Not in CITATION.cff | Comma-separated → array |
| **Dataset Type** | `metadataType` | `DatasetType` | (reference) | (not used) | ❌ Not in CITATION.cff | "raw" or "derivative" |
| **HED Version** | `metadataHED` | `HEDVersion` | (reference) | (not used) | ❌ Not in CITATION.cff | e.g., "8.2.0" |
| **Funding** | `metadataFunding` | `Funding[]` | (reference) | `FUNDING` | ❌ Not in CITATION.cff | Comma-separated → array |
| **How to Acknowledge** | `metadataHowToAcknowledge` | `HowToAcknowledge` | (reference) | (not used) | ❌ Not in CITATION.cff | BIDS optional field |
| **References** | `metadataReferences` | `ReferencesAndLinks[]` | (reference) | `REFERENCES` (fallback) | ❌ Not in CITATION.cff | Comma-separated → array |

---

### Overview Section (project.json → README.md)

| Field (UI) | UI ID | → project.json | → README.md | CITATION.cff | Notes |
|---|---|---|---|---|---|
| Main Overview | `smOverviewMain` | `Overview.Main` | `DATASET_DESCRIPTION` (fallback) | ❌ | Replaces Description if empty |
| Independent Variables | `smOverviewIV` | `Overview.IndependentVariables` | `INDEPENDENT_VARIABLES` | ❌ | |
| Dependent Variables | `smOverviewDV` | `Overview.DependentVariables` | `DEPENDENT_VARIABLES` | ❌ | |
| Control Variables | `smOverviewCV` | `Overview.ControlVariables` | `CONTROL_VARIABLES` | ❌ | |
| Quality Assessment | `smOverviewQA` | `Overview.QualityAssessment` | `QUALITY_ASSESSMENT` | ❌ | |

---

### Study Design Section (project.json → README.md)

| Field (UI) | UI ID | → project.json | → README.md | Notes |
|---|---|---|---|---|
| Study Design Type | `smSDType` | `StudyDesign.Type` | (experimental metadata) | randomized-controlled-trial, quasi-experimental, etc. |
| Type Description | `smSDTypeDesc` | `StudyDesign.TypeDescription` | (experimental metadata) | |
| Blinding | `smSDBlinding` | `StudyDesign.Blinding` | (experimental metadata) | |
| Randomization | `smSDRandomization` | `StudyDesign.Randomization` | (experimental metadata) | |
| Control Condition | `smSDControl` | `StudyDesign.ControlCondition` | (experimental metadata) | |

---

### Conditions Section (project.json)

| Field (UI) | UI ID | → project.json | → README.md | Notes |
|---|---|---|---|---|
| Condition Type | `smSDConditionType` | `Conditions.Type` | (not currently used) | |

---

### Recruitment Section (project.json → README.md)

| Field (UI) | UI ID | → project.json | → README.md | Notes |
|---|---|---|---|---|
| Recruitment Method | `smRecMethod[]` | `Recruitment.Method` (joined with "; ") | `RECRUITMENT_INFO` | Multiple entries comma-separated |
| Recruitment Locations | `smRecLocation[]` | `Recruitment.Location` (joined with "; ") | `RECRUITMENT_INFO` + `LOCATION_INFO` | Multiple entries |
| Period Start | `smRecPeriodStartYear/Month` | `Recruitment.Period.Start` | `RECRUITMENT_INFO` | YYYY-MM format |
| Period End | `smRecPeriodEndYear/Month` | `Recruitment.Period.End` | `RECRUITMENT_INFO` | YYYY-MM format |
| Compensation | `smRecCompensation` | `Recruitment.Compensation` | `RECRUITMENT_INFO` | |

---

### Eligibility Section (project.json → README.md)

| Field (UI) | UI ID | → project.json | → README.md | Notes |
|---|---|---|---|---|
| Inclusion Criteria | `smEligInclusion` | `Eligibility.InclusionCriteria[]` | `INCLUSION_CRITERIA` | One per line → array |
| Exclusion Criteria | `smEligExclusion` | `Eligibility.ExclusionCriteria[]` | `EXCLUSION_CRITERIA` | One per line → array |
| Target Sample Size | `smEligSampleSize` | `Eligibility.TargetSampleSize` | `SUBJECT_DESCRIPTION` | Integer |
| Power Analysis | `smEligPower` | `Eligibility.PowerAnalysis` | `SUBJECT_DESCRIPTION` | |

---

### Data Collection Section (project.json → README.md)

| Field (UI) | UI ID | → project.json | → README.md | Notes |
|---|---|---|---|---|
| Platform/Software | `smDCPlatform` | `DataCollection.Platform` | `APPARATUS_DESCRIPTION` | |
| Platform Version | `smDCPlatformVersion` | `DataCollection.PlatformVersion` | `APPARATUS_DESCRIPTION` | |
| Equipment | `smDCEquipment` | `DataCollection.Equipment` | `APPARATUS_DESCRIPTION` | |
| Method | `smDCMethod` | `DataCollection.Method` | `APPARATUS_DESCRIPTION` | |
| Supervision Level | `smDCSupervisio` | `DataCollection.SupervisionLevel` | `APPARATUS_DESCRIPTION` | |
| Location | `smDCLocation` | `DataCollection.Location` | `LOCATION_INFO` | |

---

### Procedure Section (project.json → README.md)

| Field (UI) | UI ID | → project.json | → README.md | Notes |
|---|---|---|---|---|
| Overview | `smProcOverview` | `Procedure.Overview` | (not currently used) | |
| Informed Consent | `smProcConsent` | `Procedure.InformedConsent` | (not currently used) | |
| Quality Control | `smProcQC` | `Procedure.QualityControl[]` | (not currently used) | One per line → array |
| Missing Data Handling | `smProcMissing` | `Procedure.MissingDataHandling` | (not currently used) | |
| Debriefing | `smProcDebriefing` | `Procedure.Debriefing` | (not currently used) | |
| Additional Data Acquired | `smProcAdditionalData` | `Procedure.AdditionalData` | `ADDITIONAL_DATA` | |
| Notes | `smProcNotes` | `Procedure.Notes` | `ADDITIONAL_NOTES` | Fallback: "created with PRISM Studio" |

---

### Missing Data & Known Issues Section (project.json → README.md)

| Field (UI) | UI ID | → project.json | → README.md | Status | Notes |
|---|---|---|---|---|---|
| Missing Data Description | `smMissingDesc` | `MissingData.Description` | `MISSING_DATA_DESCRIPTION` | ⚠️ **POST-ACQUISITION ONLY** | |
| Missing Files (Table) | `smMissingFiles` | `MissingData.MissingFiles` | `MISSING_FILES_TABLE` | ⚠️ **POST-ACQUISITION ONLY** | Format: "sub-001 \| T1w" |
| Known Issues (Table) | `smKnownIssues` | `MissingData.KnownIssues` | `KNOWN_ISSUES_TABLE` | ⚠️ **POST-ACQUISITION ONLY** | Format: "filename \| issue description" |

---

### References Section (project.json → README.md)

| Field (UI) | UI ID | → project.json | → README.md | Notes |
|---|---|---|---|---|
| References | `smReferences` | `References` | `REFERENCES` | One per line; formatted as bulleted list |

---

## 🔄 Data Flow Diagram

```
┌─────────────────────────────────────────────┐
│   Study Metadata UI Form (projects.html)   │
│   (Basics, Overview, Design, Recruitment) │
└────────────┬────────────────────────────────┘
             │
    ┌────────┴────────┬──────────────┬──────────────┐
    │                 │              │              │
    ▼                 ▼              ▼              ▼
┌──────────┐  ┌─────────────┐  ┌──────────┐  ┌─────────┐
│ project  │  │  dataset_   │  │ README   │  │CITATION │
│ .json    │  │ description │  │   .md    │  │  .cff   │
│          │  │    .json    │  │ (auto)   │  │(synced) │
└──────────┘  └─────────────┘  └──────────┘  └─────────┘
  (study      (BIDS basics)     (docs)       (cite)
   metadata)
```

---

## 📝 Form Submission Flow (saveDatasetDescription)

```javascript
document.getElementById('studyMetadataForm')?.addEventListener('submit', ...)

// Step 1: Collects from Basics section → dataset_description
await saveDatasetDescription()
  ↓
POST /api/projects/description
  ↓
// Step 2: Updates CITATION.cff from new metadata
_project_manager.update_citation_cff(project_path, description)
  ↓
// Step 3: Saves study metadata → project.json
```

---

## ✅ Validation Checklist

### Required for BIDS Compliance (dataset_description.json)
- ✅ `Name` - Set in UI
- ✅ `License` - Set in UI
- ✅ `BIDSVersion` - Auto-set to "1.10.1"
- ⚠️ `Authors` - Optional but recommended
- ⚠️ `Acknowledgements` - Optional
- ⚠️ `HowToAcknowledge` - Optional
- ⚠️ `Funding` - Optional

### PRISM Enhancements (dataset_description.json)
- ✅ `EthicsApprovals` - Set in UI (Yes/No toggle)
- ✅ `DatasetDOI` - Set in UI
- ✅ `HEDVersion` - Set in UI
- ✅ `Keywords` - Set in UI
- ✅ `DatasetType` - Set in UI (raw/derivative)
- ✅ `ReferencesAndLinks` - Set in UI

### README Generation
- ✅ Pulls from `dataset_description.json` (Name, License, Authors, Funding, EthicsApprovals)
- ✅ Pulls from `project.json` (StudyDesign, Recruitment, Eligibility, Procedure, MissingData)
- ✅ Combines multiple sources for complete docs
- ⚠️ Some Procedure fields not yet in README (e.g., QualityControl)

### CITATION.cff Sync
- ✅ Title (from `Name`)
- ✅ Authors (from `Authors[]`)
- ✅ DOI (from `DatasetDOI`)
- ✅ Date-released (today's date)
- ⚠️ Message (hardcoded: "If you use this dataset, please cite it.")

---

## ⚠️ Known Gaps & Improvements Needed

### Missing from CITATION.cff
- License (not currently synced)
- Acknowledgements (not in CFF spec, but in README)
- Keywords (not in CFF spec)
- Funding information (more complete sync needed)

### README Fields Not Yet Populated
1. **Procedure Section** - Not fully rendered:
   - `INITIAL_SETUP` - Collects but unused
   - `Procedure.Overview` - Collects but unused
   - `Procedure.InformedConsent` - Collects but unused
   - `Procedure.QualityControl` - Collects but unused
   - `Procedure.MissingDataHandling` - Collects but unused
   - `Procedure.Debriefing` - Collects but unused

2. **Data Collection** - Not fully used in README:
   - Multi-field apparatus data exists but template may not render all

3. **Study Design Experimental Fields** - Collected but not in README:
   - Blinding info
   - Randomization details
   - Control conditions

### Governance Fields (not in form)
- Governance contacts
- Governance funding
- Governance ethics approvals
- Governance data access agreements

These are fallbacks if not in dataset_description/project.json.

---

## 📚 Implementation Notes

### Data Validation Pipeline
```
Form Input (JS) 
  ↓
getFormData() [form-builder.js]
  ↓
saveDatasetDescription() [projects.html]
  ↓
POST /api/projects/description [projects.py]
  ↓
BIDS validation (_project_manager.validate_dataset_description)
  ↓
File system write (desc_path)
  ↓
CITATION.cff sync (update_citation_cff)
```

### Field Type Mapping
- **Text fields** → Single string
- **Comma-separated fields** → Split and trim, store as `array`
- **Newline-separated fields** → Split by `\n`, trim, store as `array`
- **Yes/No toggle** → Store as array (empty if "No", populated if "Yes")
- **Year/Month selectors** → Combined to "YYYY-MM" format
- **Multi-row inputs** (authors, methods, locations) → Joined with "; " or stored as array

---

## 🔧 Future Recommendations

1. **Expand README Template** to include all Procedure section fields
2. **Add Governance Block** to Study Metadata form for contacts/data agreements
3. **Sync Funding/Ethics to CITATION.cff** for complete citation metadata
4. **Validate field cardinality** (which fields are 1-to-1 vs many-to-many)
5. **Create field documentation** for each form section explaining BIDS vs PRISM mapping
6. **Add reverse-mapping test** to ensure all dataset_description fields round-trip correctly

---

## Last Updated
**2026-02-14** - Full audit of metadata field paths and synchronization logic.
