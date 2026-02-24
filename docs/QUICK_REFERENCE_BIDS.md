# BIDS Compliance Quick Reference

**For Developers & Contributors**

---

## 🎯 At a Glance

**What**: PRISM Studio now enforces BIDS compliance automatically  
**Where**: `app/templates/projects.html` (UI) + `app/src/web/blueprints/projects.py` (Backend)  
**How**: Form → dataset_description.json → CITATION.cff sync → Form reload  
**Why**: Ensures metadata consistency and BIDS-app compatibility

---

## 📋 Field Categories

### REQUIRED (⚠️ Will fail validation if missing)
- ✅ `Name`: Dataset name (MUST be provided by user)
- ✅ `BIDSVersion`: Auto-set to "1.10.1" (no user input)

### RECOMMENDED (⚠️ Will get auto-defaults)
- 🟡 `DatasetType`: Auto-set to "raw" if missing
- 🟡 `License`: Auto-set to "CC0" if missing (unless CITATION.cff exists)
- 🟡 `HEDVersion`: Only include if you use HED tags
- 🟡 `GeneratedBy`: API-only (preserved from existing)
- 🟡 `SourceDatasets`: API-only (preserved from existing)

### OPTIONAL (No auto-defaults)
- ⚪ `Authors`: Array of {name, email}
- ⚪ `Keywords`: Array of strings (≥3 recommended)
- ⚪ `Acknowledgements`: Free text
- ⚪ `HowToAcknowledge`: Free text
- ⚪ `Funding`: Array of strings
- ⚪ `EthicsApprovals`: Array of {name, reference}
- ⚪ `ReferencesAndLinks`: Array of URLs
- ⚪ `DatasetDOI`: DOI URI
- ⚪ `DatasetLinks`: Array of URLs (API-only)

---

## 🔄 CITATION.cff Precedence Rules

### If CITATION.cff EXISTS:
```
dataset_description.json will NOT contain:
  ❌ Authors
  ❌ HowToAcknowledge
  ❌ License
  ❌ ReferencesAndLinks

BUT will still contain:
  ✅ Name
  ✅ DatasetDOI
```

### If CITATION.cff NOT FOUND:
```
dataset_description.json will contain all fields:
  ✅ Authors
  ✅ License (defaults to CC0)
  ✅ HowToAcknowledge
  ✅ ReferencesAndLinks
```

**Why?**: Avoid duplication. BIDS spec says these fields belong in CITATION.cff when it exists.

---

## 🔢 Field Type Conversions

```javascript
// USER INPUT in form (string) → STORAGE in JSON (array)
"psychology, neuroscience, BIDS"  →  ["psychology", "neuroscience", "BIDS"]
"NSF #123, Other Grant"           →  ["NSF #123", "Other Grant"]

// RELOAD from JSON (array) → FORM DISPLAY (string)
["psychology", "neuroscience"]    →  "psychology, neuroscience"
```

**Fields that convert**: Keywords, Funding, ReferencesAndLinks  
**Fields that don't**: Name, License, DatasetType, DOI, etc. (stored as strings)

---

## 🛠️ Code Locations

### Frontend Form Fields (HTML)
**File**: `app/templates/projects.html`

```html
<!-- REQUIRED -->
<label><span class="badge bg-danger">REQUIRED</span> Dataset Name</label>
<input id="metadataName" required>

<!-- RECOMMENDED -->
<label><span class="badge bg-warning">RECOMMENDED</span> License</label>
<select id="metadataLicense">...</select>

<!-- OPTIONAL -->
<label><span class="badge bg-secondary">OPTIONAL</span> Keywords</label>
<input id="metadataKeywords" placeholder="psychology, experiment, BIDS">
```

**Pattern**: `<input id="metadata{FieldName}">` or `<select id="metadata{FieldName}">`

### Frontend Save Function
**File**: `app/templates/projects.html` (Line 2541)

```javascript
async function saveDatasetDescription() {
    // 1. Validate REQUIRED fields
    // 2. Collect form values into description object
    // 3. Convert strings to arrays (Keywords, Funding, etc.)
    // 4. POST to /api/projects/description
    // 5. Display validation issues if any
}
```

### Frontend Load Function
**File**: `app/templates/projects.html` (Line 2472)

```javascript
async function loadDatasetDescriptionFields() {
    // 1. GET /api/projects/description
    // 2. Populate form fields from response
    // 3. Convert arrays to strings for editing
    // 4. Call field-specific setters (setEthicsApprovals, setAuthorsList)
    // 5. Display validation issues
}
```

### Backend Save Endpoint
**File**: `app/src/web/blueprints/projects.py` (Line 707)

```python
@projects_bp.route("/api/projects/description", methods=["POST"])
def save_dataset_description():
    # 1. Extract description JSON from request
    # 2. Validate REQUIRED fields (Name)
    # 3. Auto-set BIDSVersion = "1.10.1"
    # 4. Check if CITATION.cff exists
    # 5. Apply precedence rules (omit/keep fields)
    # 6. Set auto-defaults for RECOMMENDED fields
    # 7. Validate against BIDS schema
    # 8. Write dataset_description.json
    # 9. Call update_citation_cff()
    # 10. Return success/issues
```

### CITATION.cff Sync
**File**: `app/src/project_manager.py`

```python
def update_citation_cff(self, project_path, description):
    """Generate/update CITATION.cff from dataset_description."""
    # 1. Extract Name, Authors, DatasetDOI
    # 2. Generate CITATION.cff content (CFF v1.2.0)
    # 3. Write to <project_path>/CITATION.cff
```

---

## 📝 Adding a New Metadata Field

To add a new BIDS field (e.g., `NewField`):

### 1. **Add UI Component** (projects.html, line 360-475)
```html
<div class="col-md-12">
    <label class="form-label fw-bold small text-muted text-uppercase mb-1">
        <span class="badge bg-secondary">OPTIONAL</span> New Field
    </label>
    <input type="text" class="form-control form-control-sm" id="metadataNewField" 
           placeholder="Example value">
    <small class="text-muted">Description of this field.</small>
</div>
```

### 2. **Add to Save Function** (projects.html, line 2541-2565)
```javascript
const description = {
    // ... existing fields ...
    NewField: document.getElementById('metadataNewField').value,
};
```

### 3. **Add to Load Function** (projects.html, line 2472-2495)
```javascript
document.getElementById('metadataNewField').value = desc.NewField || '';
```

### 4. **Update Backend** (projects.py, line 707+)
- If REQUIRED: Add to validation check
- If RECOMMENDED: Add logic to set default value
- If OPTIONAL: No backend changes needed (just validate)

### 5. **Test**
```bash
python3 scripts/test_bids_compliance.py
```

---

## 🧪 Testing Your Changes

### Unit Test
```bash
python3 scripts/test_bids_compliance.py
```

### Manual Test
1. Open PRISM Studio
2. Create/select a project
3. Fill in the metadata form
4. Click Save
5. Verify `dataset_description.json` created correctly
6. Verify `CITATION.cff` generated correctly
7. Click form reload
8. Verify all fields repopulated

### Visual Check
```bash
# Check dataset_description.json structure
cat <project>/rawdata/dataset_description.json | python3 -m json.tool

# Check CITATION.cff syntax
cat <project>/CITATION.cff
```

---

## ⚠️ Common Issues & Solutions

### Issue: "REQUIRED FIELD: Dataset Name is mandatory"
**Cause**: Name field is empty  
**Fix**: Enter a dataset name in the "Dataset Name" field

### Issue: Authors field in dataset_description.json when CITATION.cff exists
**Cause**: Backend didn't apply precedence rules  
**Fix**: Ensure `citation_cff_path.exists()` check in `save_dataset_description()`

### Issue: Keywords not parsing correctly
**Cause**: User entered "keyword1, keyword2" but it stored as string instead of array  
**Fix**: Check that `.split(',').map(s => s.trim()).filter(s => s)` is being applied

### Issue: CITATION.cff not updating
**Cause**: `update_citation_cff()` not called or threw exception  
**Fix**: Check Flask logs for error; ensure `project_manager` is initialized

### Issue: Backend issues array shows "License is RECOMMENDED"
**Cause**: This is just a warning, not an error  
**Fix**: This is expected behavior; you can ignore it or set a License value

---

## 🔗 Related Documentation

- **Full Spec**: See `docs/BIDS_COMPLIANCE_IMPLEMENTATION.md` (300+ lines)
- **Field Audit**: See `docs/METADATA_AUDIT.md` (detailed mappings)
- **Status Summary**: See `docs/BIDS_AUTO_MAPPING_COMPLETE.md` (overview)
- **Official BIDS**: https://bids-specification.readthedocs.io/

---

## 🚀 Quick Debugging Commands

```bash
# Check project structure
ls -la <project_path>/

# View dataset_description.json
cat <project_path>/rawdata/dataset_description.json | python3 -m json.tool

# View CITATION.cff
cat <project_path>/CITATION.cff

# Run validation tests
python3 scripts/test_bids_compliance.py

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
