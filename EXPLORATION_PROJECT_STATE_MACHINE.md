# Project State Machine & Workflow Exploration

**Comprehensive analysis of how PRISM Studio manages project transitions between draft/preliminary and saved states.**

---

## Executive Summary

PRISM Studio implements a **two-tier save system**:

1. **Preliminary State** - Project saved with incomplete/invalid metadata
   - Triggered by user confirmation through modal dialog
   - Allows creating/saving projects before all requirements are met
   - Can be resumed and completed later

2. **Full/Saved State** - Project saved with all requirements met
   - Automatic transition when all mandatory fields are valid
   - Button changes from "Save Preliminary" to "Save Changes"
   - Meets BIDS compliance for export/analysis

---

## Architecture Overview

### Backend (Single Source of Truth)

**Key Files:**
- `src/project_manager.py` - Creates projects, validates structure
- `app/src/web/blueprints/projects_lifecycle_handlers.py` - Sets/clears active project
- `app/src/web/blueprints/projects_study_metadata_handlers.py` - Saves study metadata to `project.json`
- `app/src/web/blueprints/projects_description_handlers.py` - Saves `dataset_description.json` + `CITATION.cff`

**Key Principle:** All business logic centralized in `src/`. Frontend (`app/src/`) is thin adapter layer.

### Frontend (UX Adapter)

**Key Files:**
- `app/static/js/modules/projects/core.js` - Project load/create UI, state transitions
- `app/static/js/modules/projects/metadata.js` - Study metadata form, validation, save workflows
- `app/static/js/modules/projects/validation.js` - Field validation, badge updates
- `app/static/js/shared/project-state.js` - Project state store management

---

## "Current Requirements" - What Must Be Completed

### Mandatory Fields for Full Save

| Section | Field | Requirement |
|---------|-------|-------------|
| **Basics** | Dataset Name | Min. 3 characters |
| **Basics** | Authors | ≥1 author with first+last name |
| **Basics** | Corresponding Author | ≥1 author marked as corresponding |
| **Basics** | Author Email | Corresponding author must have email |
| **Basics** | Keywords | ≥3 comma-separated values |
| **Basics** | Ethics Approvals | Select "Yes" or "No"; if Yes: committee + votum required |
| **Basics** | Funding | Select "Yes" or "No"; if Yes: funding details required |
| **Overview** | Dataset Overview | Non-empty text |
| **Study Design** | Type | Must select a value |
| **Recruitment** | Method | ≥1 method selected |
| **Recruitment** | Location | Either "Online" checked OR ≥1 specific location |
| **Recruitment** | Period Start | Both year and month selected |
| **Recruitment** | Period End | Both year and month selected (≥ Start date) |
| **Recruitment** | Compensation | Non-empty value |
| **Eligibility** | Criteria | ≥2 total across Inclusion + Exclusion |
| **Procedure** | Overview | Non-empty text |

### Format Validations (Non-Blocking for Preliminary)

- **DOI Format:** `10.xxxx/...` or full URL (if provided)
- **ORCID Format:** `0000-0000-0000-0000` (if provided)
- **Email Format:** Basic RFC5322 (if provided)
- **Website URL:** Valid http(s) protocol (if provided)
- **Dataset Name:** Min. 3 characters (checked)

### Conditional Requirements

**If Study Design Type is Experimental:**
- Randomized-Controlled Trial, Quasi-Experimental, or Case-Control
- Additional fields become required:
  - Blinding
  - Randomization
  - Control Condition

---

## State Transitions & Project Lifecycle

```
┌─────────────────────────────────────────────────────────────────┐
│                    PROJECT STATE MACHINE                         │
└─────────────────────────────────────────────────────────────────┘

NO PROJECT
    │
    ├─→ [CREATE MODE]
    │   ├─→ User enters: project name, output path
    │   ├─→ Fills mandatory metadata fields
    │   │
    │   ├─→ ALL VALID? ─→ [FULL SAVE] ─→ Create + Save Complete
    │   │   └─→ Button: "Create Project" (green)
    │   │
    │   └─→ INCOMPLETE? ─→ [PRELIMINARY SAVE] ─→ Create + Save Partial
    │       └─→ Button: "Create Preliminary" (warning)
    │           User confirms: "OK, create with incomplete metadata"
    │
    └─→ [OPEN PROJECT]
        ├─→ User selects existing project directory
        ├─→ Validates project structure
        └─→ Load all metadata
            └─→ [LOADED/EDIT MODE]

[LOADED/EDIT MODE]
    │
    ├─→ User edits form fields
    │   ├─→ Every keystroke: computeLocalCompleteness()
    │   │   └─→ Updates completion % (red→blue→yellow→green)
    │   │
    │   ├─→ validateAllMandatoryFields()
    │   │   ├─→ Check all required filled
    │   │   ├─→ Check all formats valid
    │   │   └─→ Return {isValid, emptyFields[], invalidFields[]}
    │   │
    │   ├─→ ALL VALID? ─→ [FULL SAVE]
    │   │   └─→ Button: "Save Changes to Project" (blue)
    │   │       Click → /api/projects/description + /api/projects/study-metadata
    │   │       Result: Project marked [SAVED]
    │   │
    │   └─→ INCOMPLETE? ─→ [PRELIMINARY SAVE]
    │       └─→ Button: "Save Preliminary Project State" (warning)
    │           Click → Modal: "Issues found: [list]"
    │           User: "OK, save anyway"
    │           Result: Project marked [PRELIMINARY]
    │
    ├─→ Switch to Different Project
    │   ├─→ /api/projects/current POST {path: newPath}
    │   └─→ Go to [LOADED/EDIT MODE] for new project
    │
    └─→ New Project Mode
        ├─→ clearCurrentProjectForNewDraft()
        ├─→ /api/projects/current POST {path: ""}
        └─→ Go to [CREATE MODE]
```

---

## How Requirements Are Validated

### Frontend Validation (Real-Time Feedback)

**1. Field-Level Validation** (`validateProjectField()`)
- Runs on every `input`, `change`, `blur` event
- Updates individual field badge: RED (empty) → GREEN (filled)
- Format checks for email, DOI, ORCID, website

**2. Section-Level Completeness** (`computeLocalCompleteness()`)
- Computes ALL fields' state every keystroke
- Returns per-section breakdown:
  - Total fields, filled fields
  - Required_filled / required_total
  - Optional_filled / optional_total
- Drives section badge colors and progress bar

**3. Mandatory Requirements Check** (`validateAllMandatoryFields()`)
- Called when user clicks save/create
- Returns:
  - `isValid: boolean` - All required fields present + valid
  - `emptyFields: string[]` - List of missing mandatory fields
  - `invalidFields: string[]` - List of format/logic errors
- If `!isValid`: Shows modal with issues, user confirms proceed

**4. Button State Updates** (`updateCreateProjectButton()`)
- **Create Mode + All Valid:**
  - Button: "Create Project" (green)
  - Preliminary button: hidden
  - Action Hint: "All required fields complete"

- **Create Mode + Incomplete:**
  - Button: "Create Project" (gray)
  - Preliminary button: "Create Preliminary" (yellow, enabled if path selected)
  - Action Hint: "X required fields missing"

- **Edit Mode + All Valid:**
  - Button: "Save Changes to Project" (blue)
  - Action Hint: "Save metadata updates"

- **Edit Mode + Incomplete:**
  - Button: "Save Preliminary Project State" (yellow)
  - Title: "X required fields missing — save preliminary and finish later"
  - Action Hint: "X required fields missing"

### Backend Validation (Pre-Write Check)

**1. Path Resolution** (`_resolve_requested_or_current_project_root()`)
- Validates `project_path` exists and is valid
- Rejects stale/invalid paths before writing

**2. Project Structure Validation** (`validate_dataset_description()`)
- Checks BIDS/PRISM compliance
- Returns list of issues (NOT blocking)
- Issues displayed in UI for user awareness

**3. Author/Governance Sync** (`_sync_authors_to_project_json()`)
- Persists author roles, ORCID, corresponding status to `project.json::governance.contacts`
- Preserves existing roles not supplied in update
- Removes legacy contributor files

**4. Citation Management** (`update_citation_cff()`)
- Auto-generates/updates CITATION.cff from dataset metadata
- Moves citation-owned fields (Authors, License, References) to CITATION.cff
- Keeps dataset_description.json BIDS-compliant

---

## Save Workflow: From Form to Disk

### Full/Preliminary Save Flow (Identical Backend, Different Frontend Trigger)

```
1. Frontend: User clicks save button
   ├─→ validateAllMandatoryFields()
   ├─→ If !isValid: Show modal, user confirms OR cancel
   └─→ If confirmed or isValid: Proceed to step 2

2. Frontend: Collect form data
   ├─→ Basics: {Name, Authors, Keywords, EthicsApprovals, Funding, ...}
   ├─→ Dataset Description: {License, DOI, HowToAcknowledge, ...}
   └─→ Study Metadata: {Overview, StudyDesign, Recruitment, ...}

3. Frontend: POST /api/projects/description
   ├─→ Body: {project_path, description, citation_fields}
   ├─→ Backend resolves project_path
   ├─→ Backend validates dataset_description
   ├─→ Backend syncs authors to project.json::governance
   ├─→ Backend updates CITATION.cff
   └─→ Backend writes dataset_description.json (citation fields removed)

4. Frontend: POST /api/projects/study-metadata
   ├─→ Body: {project_path, Basics, Overview, StudyDesign, ...}
   ├─→ Backend loads existing project.json
   ├─→ Backend merges changes (preserves non-editable sections)
   ├─→ Backend updates Metadata.LastModified
   ├─→ Backend refreshes CITATION.cff from new Basics data
   └─→ Backend writes project.json

5. Frontend: Update UI
   ├─→ Clear submit lock (button re-enabled)
   ├─→ Show success feedback
   ├─→ Update completeness badges
   └─→ Update project state if name changed
```

### What Gets Written to Disk

**Primary Files:**
- `project.json` - Study metadata container (Recruitment, Eligibility, Procedure, etc.)
- `dataset_description.json` - BIDS metadata (BIDSVersion, Name, DatasetType)
- `CITATION.cff` - Citation metadata (Authors, License, DOI, References)

**Metadata Distribution:**
- `dataset_description.json` ← Name, BIDSVersion, DatasetType, Description
- `CITATION.cff` ← Authors, License, HowToAcknowledge, ReferencesAndLinks
- `project.json::governance.contacts[]` ← Full author records with roles, ORCID, email

**Configuration Files (Created Once):**
- `.bidsignore` - Standard BIDS ignore patterns
- `.prismrc.json` - Project-wide validation config
- `README.md` - Auto-generated study overview

---

## Key Design Patterns

### 1. Explicit Project Path in API Calls

Every save endpoint requires explicit `project_path` parameter:
```
POST /api/projects/description
{
  "project_path": "/full/path/to/project",  // ← Always required
  "description": {...}
}
```

**Why:** Prevents stale writes after project changes. Session state alone is not trusted.

### 2. Preliminary vs. Full Save = Same Backend, Different Trigger

The **backend doesn't distinguish** between preliminary and full saves. Only the frontend does:

- **Full Save:** Only triggered when `validateAllMandatoryFields().isValid === true`
- **Preliminary Save:** Triggered when `!isValid` but user confirms in modal

Both write to same endpoints. Backend always succeeds. Issues returned to UI for display.

### 3. Completeness Score Is Frontend-Only

Backend doesn't track/return completeness. Frontend computes on every keystroke:
- Drives badging (red/yellow/green)
- Drives button state
- Drives progress bar

Backend only validates at save time and returns issues.

### 4. Authors Persist With Rich Metadata

Author data synced to TWO places:
1. **dataset_description.json** (display names list)
2. **project.json::governance.contacts[]** (full records with roles, ORCID, corresponding flag)

Allows roundtrip: Load from disk → Edit in UI → Save back with all metadata preserved.

### 5. State Machine Ensures Single Source of Truth

Project state stored in backend session:
- `/api/projects/current GET` - Fetch active project
- `/api/projects/current POST {path}` - Set active project
- `/api/projects/current POST {path: ""}` - Clear active project

UI syncs with backend to prevent race conditions.

---

## Edge Cases & Stale State Prevention

### Project Switch During Edit

1. User edits Project A
2. User switches to Project B (via project selector)
3. `/api/projects/current POST {path: B}` - Backend session updated
4. User clicks save in Project A form
5. Backend receives explicit `project_path: A` from form
6. Backend checks: Does Project A == current session project? NO
7. Saves fail with "Project path mismatch" error
8. Frontend shows: "Project was changed before save"

**Prevention:** Always pass explicit `project_path`, never trust session alone.

### Browser Back Button After Save

1. User saves Project A metadata
2. User clicks browser back button
3. Form shows old values (from browser cache)
4. User edits and clicks save again
5. Backend ignores duplicate edits, updates Metadata.LastModified
6. UI updates correctly

**No issue:** Idempotent saves. Multiple updates OK.

### Incomplete Project Reopened Later

1. User creates Preliminary Project (Name + Authors only)
2. User switches to another project
3. User reopens Preliminary Project
4. Form loads with Name + Authors, rest empty
5. Button shows "Save Preliminary" (X issues remaining)
6. User completes more fields
7. Once all required valid → Button changes to "Save Changes"
8. Full save possible

**Workflow:** Prelim projects can be resumed and upgraded to full saves.

---

## Frontend → Backend API Contract

### POST /api/projects/description

**Request:**
```json
{
  "project_path": "/path/to/project",
  "description": {
    "Name": "My Study",
    "Authors": ["Smith, John", "Doe, Jane"],
    "Keywords": ["psychology", "survey", "emotion"],
    "License": "CC0",
    "...": "..."
  },
  "citation_fields": {
    "Authors": [{"given-names": "John", "family-names": "Smith", "orcid": "..."}],
    "License": "CC0"
  }
}
```

**Response (Success):**
```json
{
  "success": true,
  "message": "dataset_description.json saved successfully",
  "issues": [
    {
      "message": "Authors list empty",
      "fix_hint": "Add at least one author"
    }
  ]
}
```

### POST /api/projects/study-metadata

**Request:**
```json
{
  "project_path": "/path/to/project",
  "Basics": {"Name": "...", "Authors": [...]},
  "Overview": {"Main": "...", "IndependentVariables": [...]},
  "StudyDesign": {"Type": "..."},
  "Recruitment": {"Method": [...], "Location": [...]},
  "Eligibility": {"InclusionCriteria": [...]},
  "Procedure": {"Overview": "..."},
  "...": {}
}
```

**Response (Success):**
```json
{
  "success": true,
  "message": "Study metadata saved",
  "completeness": {
    "score": 65,
    "filled_fields": 20,
    "total_fields": 31,
    "sections": {...}
  }
}
```

---

## Testing & Validation Checklist

### Preliminary Save Path
- [ ] Create new project with only Name + Authors (incomplete)
- [ ] Verify "Create Preliminary" button appears
- [ ] Click button → Modal shows issues
- [ ] Confirm modal → Project created
- [ ] Reopen project → Form loads partial data
- [ ] Badge shows "Preliminary" on project card

### Full Save Path
- [ ] Fill ALL mandatory fields
- [ ] Verify "Create Project" button is green
- [ ] Click → No modal, direct save
- [ ] Project created with complete metadata

### Edit & Upgrade to Full
- [ ] Load preliminary project
- [ ] Add more fields
- [ ] When all mandatory valid → Button changes to "Save Changes"
- [ ] Click → Full save, project upgraded

### Stale Project Prevention
- [ ] Load Project A
- [ ] Switch to Project B
- [ ] Go back to Project A form
- [ ] Click save → Should fail or silently use Project B
- [ ] Check logs for explicit project_path mismatch

### Author Role Persistence
- [ ] Add author with first + last name
- [ ] Mark as corresponding author
- [ ] Add ORCID + email
- [ ] Add CRediT roles
- [ ] Save → Close → Reopen
- [ ] Verify all author metadata persisted

---

## Files Involved in State Machine

### Backend
- `src/project_manager.py` - Create, validate
- `app/src/web/blueprints/projects_lifecycle_handlers.py` - Set/clear current
- `app/src/web/blueprints/projects_study_metadata_handlers.py` - Save study metadata
- `app/src/web/blueprints/projects_description_handlers.py` - Save description + citation

### Frontend
- `app/static/js/modules/projects/core.js` - Create/load UI, state transitions
- `app/static/js/modules/projects/metadata.js` - Form state, validation, save flows
- `app/static/js/modules/projects/validation.js` - Field validation, badging
- `app/static/js/shared/project-state.js` - State store management

### Templates
- `app/templates/projects.html` - Project management UI
- `app/templates/base.html` - Project state store initialization

---

## Summary

PRISM Studio's project state machine is built on these principles:

1. **Two-Tier Saves** - Preliminary (incomplete) and Full (complete) states
2. **Frontend-Driven Validation** - Real-time feedback via badges and button state
3. **Backend-Agnostic Saves** - Backend always succeeds; validation issues returned to UI
4. **Explicit Project Paths** - No stale writes via session state
5. **Incremental Workflows** - Users can save incomplete projects and finish later
6. **Rich Author Metadata** - Full records persisted to project.json + CITATION.cff
7. **Single Source of Truth** - Backend session + explicit path params prevent race conditions

This design allows for flexible, user-friendly project creation while maintaining data integrity and BIDS compliance.
