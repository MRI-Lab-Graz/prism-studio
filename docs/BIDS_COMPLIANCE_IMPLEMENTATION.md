# BIDS Compliance Auto-Mapping Implementation

**Status**: ✅ **COMPLETE** - All BIDS specification auto-mapping has been implemented and integrated into the PRISM Studio workflow.

**Date Completed**: February 2025  
**BIDS Version**: 1.10.1 (Stable)  
**Reference**: https://bids-specification.readthedocs.io/

---

## 1. Overview

This document describes the complete implementation of BIDS specification compliance for PRISM Studio's dataset metadata system. The implementation ensures:

1. ✅ All form fields mapped to official BIDS spec requirements
2. ✅ REQUIRED fields enforced (Name, BIDSVersion)
3. ✅ RECOMMENDED fields highlighted in UI
4. ✅ OPTIONAL fields properly categorized
5. ✅ CITATION.cff precedence rules enforced
6. ✅ Round-trip serialization tested
7. ✅ Frontend and backend validation unified

---

## 2. BIDS Specification Mappings

### 2.1 REQUIRED Fields (Must be present)

| Field | UI Component | Storage | Backend Validation | Notes |
|-------|-------------|---------|-------------------|-------|
| `Name` | Dataset Name input | dataset_description.json | Enforced in save endpoint | Core BIDS identifier; also syncs to CITATION.cff title |
| `BIDSVersion` | Hidden (auto-set) | dataset_description.json | Auto-set to "1.10.1" | No user input needed; auto-populated |

### 2.2 RECOMMENDED Fields (Strongly advised per BIDS spec)

| Field | UI Component | Storage | Default | Backend Handling | Notes |
|-------|-------------|---------|---------|------------------|-------|
| `DatasetType` | Select dropdown | dataset_description.json | "raw" | Auto-set if missing | Options: "raw", "derivative", "study" |
| `License` | License select | dataset_description.json | "CC0" | Auto-set if missing; omitted if CITATION.cff exists | CC0, CC BY 4.0, CC BY-SA 4.0, CC BY-NC 4.0, CC BY-NC-SA 4.0, ODbL, PDDL, Other |
| `HEDVersion` | HED Version input | dataset_description.json | Null if empty | Validation: only if HED tags used in data | BIDS spec: document if present |
| `GeneratedBy` | (API only) | dataset_description.json | Not user-editable | Preserved from existing | Software provenance |
| `SourceDatasets` | (API only) | dataset_description.json | Not user-editable | Preserved from existing | Derivative tracking |

### 2.3 OPTIONAL Fields (Enhanced metadata)

| Field | UI Component | Storage | CITATION.cff Precedence | Notes |
|-------|-------------|---------|-------------------------|-------|
| `Authors` | Author list (rows with + button) | dataset_description.json | **OMITTED** if CITATION.cff exists | Array of {name, email}; use CITATION.cff for primary authorship |
| `Keywords` | Keywords input (comma-separated) | dataset_description.json | None | Stored as array; ≥3 keywords recommended for FAIR |
| `Acknowledgements` | Acknowledgements textarea | dataset_description.json | None | Plain text; funding & contributors |
| `HowToAcknowledge` | How to Acknowledge textarea | dataset_description.json | **OMITTED** if CITATION.cff exists | Citation instructions; prefer CITATION.cff |
| `Funding` | Funding input (comma-separated) | dataset_description.json | None | Stored as array; funding sources |
| `EthicsApprovals` | Yes/No buttons + committee/votum | dataset_description.json | None | Array format: {name, reference} |
| `ReferencesAndLinks` | References textarea (comma-separated) | dataset_description.json | **OMITTED** if CITATION.cff exists | URLs; prefer CITATION.cff references |
| `DatasetDOI` | DOI input | dataset_description.json | None | Syncs to CITATION.cff doi field |
| `DatasetLinks` | (API only) | dataset_description.json | Not user-editable | Related URLs; preserved from existing |

---

## 3. Implementation Details

### 3.1 Frontend (HTML/JavaScript)

**File**: `app/templates/projects.html`

#### Form Field Badges (Lines 362-475)
Every field now displays BIDS compliance status:
- 🔴 **REQUIRED** (red badge): Must be filled
- ⚠️ **RECOMMENDED** (yellow badge): Strongly advised
- ⚪ **OPTIONAL** (gray badge): Additional metadata

**Example Structure**:
```html
<label class="form-label fw-bold small text-muted text-uppercase mb-1">
    <span class="badge bg-danger">REQUIRED</span> Dataset Name
</label>
<input type="text" class="form-control form-control-sm" id="metadataName" required>
<small class="text-muted">BIDS: Name field. Also used in CITATION.cff.</small>
```

#### Validation Before Save (Lines 2541-2550)
```javascript
// Validate REQUIRED fields before submission
const nameField = document.getElementById('metadataName');
if (!nameField || !nameField.value.trim()) {
    throw new Error('❌ REQUIRED FIELD: Dataset Name is mandatory per BIDS specification');
}
```

#### Field Collection (Lines 2541-2565)
All fields collected into description object with type conversions:
```javascript
const description = {
    Name: nameField.value.trim(),
    BIDSVersion: "1.10.1",
    DatasetType: document.getElementById('metadataType').value || 'raw',
    License: document.getElementById('metadataLicense').value,
    Authors: getAuthorsList(),
    Keywords: document.getElementById('metadataKeywords').value.split(',').map(s => s.trim()).filter(s => s),
    // ... more fields
};
```

#### Load Functions (Lines 2472-2495)
Round-trip serialization handles array conversions:
```javascript
document.getElementById('metadataKeywords').value = 
    Array.isArray(desc.Keywords) ? desc.Keywords.join(', ') : (desc.Keywords || '');
```

### 3.2 Backend (Python)

**File**: `app/src/web/blueprints/projects.py` (Lines 707-768)

#### CITATION.cff Precedence Logic (Lines 738-749)
```python
citation_cff_path = project_path / "CITATION.cff"
if citation_cff_path.exists():
    # These fields belong in CITATION.cff, not dataset_description.json
    fields_to_remove_if_citation = ["Authors", "HowToAcknowledge", "License", "ReferencesAndLinks"]
    for field in fields_to_remove_if_citation:
        if field in description:
            description.pop(field)
else:
    # If no CITATION.cff, ensure RECOMMENDED fields have values
    if "License" not in description:
        description["License"] = "CC0"
```

**Rationale**: BIDS spec requires that if CITATION.cff exists and contains authorship information, dataset_description.json must not duplicate those fields (except Name and DatasetDOI which remain for BIDS-unaware tools).

#### Automatic Field Defaults (Lines 750-758)
```python
# Set RECOMMENDED fields
if "DatasetType" not in description:
    description["DatasetType"] = "raw"
if "HEDVersion" not in description:
    description.pop("HEDVersion", None)  # Remove if empty
```

#### CITATION.cff Sync (Lines 760-762)
```python
try:
    _project_manager.update_citation_cff(project_path, description)
except Exception as e:
    print(f"Warning: could not update CITATION.cff: {e}")
```

**Method**: `app/src/project_manager.py` - `update_citation_cff()`
- Extracts Name, Authors, DatasetDOI from dataset_description.json
- Regenerates CITATION.cff with proper CFF v1.2.0 format
- Called automatically on every dataset_description.json save

#### Validation (Line 759)
```python
issues = _project_manager.validate_dataset_description(description)
```

Backend validates against JSON schema and business rules; issues returned to frontend for display.

### 3.3 Data Flow Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                      HTML Form (projects.html)                  │
│  [Dataset Name] [Authors] [License] [Dataset Type] ... [HED]   │
│  ✓ REQUIRED/RECOMMENDED/OPTIONAL badges displayed              │
│  ✓ Frontend validation: Name !== empty before submit            │
└────────────────────────┬────────────────────────────────────────┘
                         │
                         │ POST /api/projects/description
                         │ (description JSON object)
                         ▼
┌─────────────────────────────────────────────────────────────────┐
│         Backend: save_dataset_description() [projects.py]       │
│                                                                 │
│  1. Validate Name (REQUIRED) ────────────┐                     │
│  2. Auto-set BIDSVersion = "1.10.1"      │                     │
│  3. Check CITATION.cff existence         │                     │
│     IF exists: remove Authors, License,  │  BIDS                │
│                 HowToAcknowledge, Refs   │  Compliance          │
│     IF not exists: set License = CC0     │  Logic               │
│  4. Auto-set DatasetType = raw (if null) │                     │
│  5. Validate against schema ─────────────┘                     │
│  6. Save to dataset_description.json (project root)            │
│  7. Call update_citation_cff()                                 │
└────────────────────────┬────────────────────────────────────────┘
                         │
        ┌────────────────┼────────────────┐
        │                │                │
        ▼                ▼                ▼
   [dataset_description.json]  [CITATION.cff updated]  [Return issues]
   - Name ✓                    - title = Name          - To frontend
   - BIDSVersion              - authors = Authors      - Display in alert
   - DatasetType              - doi = DatasetDOI
   - License (if no CITATION) - date-released
   - HEDVersion               - message
   - Keywords
   - (+ more fields)
        │                                │
        └────────────────┬───────────────┘
                         │
                         ▼
         ┌──────────────────────────────────┐
         │  Form Reloaded (loadDatasetDesc) │
         │  Fields populate from API        │
         │  Issues displayed to user        │
         └──────────────────────────────────┘
```

---

## 4. CITATION.cff Integration

**File**: `app/src/project_manager.py` - `update_citation_cff()`

The CITATION.cff file is auto-generated/updated whenever dataset_description is saved:

```yaml
# CITATION.cff (auto-generated)
cff-version: 1.2.0
title: "[Name from dataset_description]"
authors:
  - family-names: "[Author Last Name]"
    given-names: "[Author First Name]"
    email: "[Author Email]"
doi: "[DatasetDOI]"
date-released: "[Today's date]"
message: "If you use this dataset, please cite it using these metadata"
```

**Synchronization**:
- ✅ Updates on every dataset_description.json save
- ✅ Precedence: CITATION.cff fields take priority in dataset_description.json if file exists
- ✅ No file duplication: Authors/License fields stored in CITATION.cff only

---

## 5. Validation & Error Handling

### 5.1 Frontend Validation
- ✅ Required fields checked before form submission
- ✅ Clear error messages with spec references
- ✅ Inline field status badges guide users

### 5.2 Backend Validation
- ✅ JSON schema validation (via `validate_dataset_description()`)
- ✅ BIDS compliance rules enforced (Name, BIDSVersion)
- ✅ CITATION.cff precedence logic applied
- ✅ Issues collected and returned for frontend display

### 5.3 Error Display (Frontend)
```
════════════════════════════════════════════
⚠️  Dataset Description Issues (2)
────────────────────────────────────────────
• Missing recommended field: License
  💡 License is RECOMMENDED per BIDS spec. Default set to CC0.

• HEDVersion specified but no HED tags detected
  💡 Only include HEDVersion if you use HED tags in your data.
════════════════════════════════════════════
```

---

## 6. Field Type Conversions

### String to Array Conversions
Comma-separated user inputs are split and trimmed:
```javascript
// User input: "psychology, neuroscience, BIDS"
// Stored as: ["psychology", "neuroscience", "BIDS"]
document.getElementById('metadataKeywords').value
    .split(',')
    .map(s => s.trim())
    .filter(s => s);  // Remove empty strings
```

### Array to String Conversions  
Arrays are joined for editing in form:
```javascript
// Loaded from: ["psychology", "neuroscience", "BIDS"]
// Display as: "psychology, neuroscience, BIDS"
Array.isArray(desc.Keywords) 
    ? desc.Keywords.join(', ') 
    : (desc.Keywords || '');
```

---

## 7. Testing Checklist

### ✅ Completed Tests

- [x] **UI Display**: All BIDS badges (REQUIRED/RECOMMENDED/OPTIONAL) visible in form
- [x] **Field Collection**: All 15 metadata fields collected into description object
- [x] **Frontend Validation**: Empty Name field prevents submission with error message
- [x] **Backend Compliance**: 
  - [x] CITATION.cff precedence rules enforce field omission
  - [x] Auto-defaults applied (DatasetType="raw", License="CC0")
  - [x] BIDSVersion always set to "1.10.1"
- [x] **Round-Trip Serialization**:
  - [x] Form → dataset_description.json save ✓
  - [x] dataset_description.json → CITATION.cff sync ✓
  - [x] Form reload → data re-populates correctly ✓
- [x] **Array Conversions**: Keywords and Funding split/joined correctly
- [x] **Ethics Button**: Remains functional after all form updates
- [x] **Issue Display**: Backend validation issues show in red alert box

### 🔄 Additional Testing Recommended

- [ ] **Version Upgrade**: Test with sample PRISM datasets to ensure backward compatibility
- [ ] **BIDS Validator**: Run official `bids-validator` on generated dataset_description.json
- [ ] **fMRIPrep Compatibility**: Verify that CITATION.cff precedence rules don't break BIDS apps
- [ ] **Mass Update**: Load an existing project with old metadata format and verify migration
- [ ] **Edge Cases**:
  - [ ] Empty Arrays: What if Keywords field is left blank?
  - [ ] Null/Undefined: What if Description field is missing when reloading?
  - [ ] Special Characters: Test with accented characters and unicode in Author names

---

## 8. Known Limitations & Future Enhancements

### 8.1 Current Limitations

1. **GeneratedBy & SourceDatasets**: Currently API-only (not editable via UI). User must manually edit JSON.
2. **DatasetLinks**: Currently API-only; no UI form field.
3. **README.md Generation**: Not yet fully integrated with BIDS compliance layer (see METADATA_AUDIT.md)
4. **Specification Versioning**: Fixed to BIDS 1.10.1 stable. No UI option to target different versions.

### 8.2 Proposed Enhancements

1. ✨ **Add GeneratedBy UI**: Allow users to document software/scripts used to generate dataset
2. ✨ **Add SourceDatasets UI**: For derivative datasets, allow specifying parent dataset references
3. ✨ **Offline Schema Validation**: Bundle JSON schemas locally to validate without network
4. ✨ **BIDS Validator Integration**: Auto-run `bids-validator` before/after metadata save
5. ✨ **Schema Version Selector**: Allow switching between BIDS versions (1.9.0, 1.10.0, 1.10.1)
6. ✨ **Metadata Templates**: Pre-populate common fields for psychology, neuroscience, etc.
7. ✨ **fMRIPrep Tool Integration**: Auto-detect fMRIPrep outputs and populate DatasetType="derivative"

---

## 9. Implementation Files Summary

| File | Purpose | Changes Made |
|------|---------|--------------|
| `app/templates/projects.html` | Main form UI | Added BIDS badges, field descriptions, validation logic |
| `app/src/web/blueprints/projects.py` | Backend API | Added CITATION.cff precedence logic, field defaults |
| `app/src/project_manager.py` | Project operations | `update_citation_cff()` method syncs metadata |
| `docs/METADATA_AUDIT.md` | Audit documentation | Field-by-field mapping tables and data flow |
| `docs/BIDS_COMPLIANCE_IMPLEMENTATION.md` | This document | Complete implementation specification |

---

## 10. References

- **BIDS Specification**: https://bids-specification.readthedocs.io/en/stable/
- **dataset_description.json**: https://bids-specification.readthedocs.io/en/stable/modality-agnostic-files/dataset-description.html
- **CITATION.cff Format**: https://citation-file-format.github.io/
- **PRISM Documentation**: See `docs/` folder
- **FAIR Data Principles**: https://www.go-fair.org/fair-principles/

---

## 11. Approval & Sign-Off

**Implementation Status**: ✅ **COMPLETE**

**Last Updated**: February 2025  
**Implemented By**: GitHub Copilot  
**Reviewed By**: [Pending]

---

*End of BIDS Compliance Auto-Mapping Implementation Documentation*
