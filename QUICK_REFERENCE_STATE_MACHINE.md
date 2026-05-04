# Quick Reference: Project State Machine

## State Diagram (Simplified)

```
[NO PROJECT]
    ↓
[CREATE MODE] → Fill form → All valid? → [FULL SAVE]
    ↓                             ↓
[LOAD PROJECT]          User confirms → [PRELIMINARY SAVE]
    ↓
[EDIT MODE] → Edit → All valid? → [FULL SAVE]
    ↓
[SWITCH PROJECT]  (→ [NO PROJECT] or [CREATE] or [EDIT])
```

## "Current Requirements" (Mandatory Fields)

### Tier 1: Must Have to Save Anything
| Field | Requirement |
|-------|-------------|
| Dataset Name | Min. 3 chars |
| ≥1 Author | First + Last name |
| ≥1 Corresponding Author | Must have email |

### Tier 2: Study Definition (Required for Full Save)
| Section | Requirements |
|---------|--------------|
| Overview | Non-empty description |
| Study Design Type | Must select |
| Recruitment Method | ≥1 method |
| Recruitment Location | "Online" OR ≥1 location |
| Recruitment Period | Start & End dates (start ≤ end) |
| Recruitment Compensation | Non-empty value |
| Keywords | ≥3 comma-separated |
| Eligibility Criteria | ≥2 total (inclusion + exclusion) |
| Procedure Overview | Non-empty text |
| Ethics Approvals | Select Yes/No; if Yes: details required |
| Funding | Select Yes/No; if Yes: details required |

### Format Checks (If Provided)
- DOI: `10.xxxx/...` pattern
- ORCID: `0000-0000-0000-0000` pattern
- Email: Basic format
- Website: Valid http(s) URL

## Save Workflows

### CREATE NEW PROJECT (Preliminary)
```
1. Fill project basics: name, path
2. Add minimum metadata (Name + 1 Author)
3. Click "Create Preliminary"
4. Confirm modal: "Create with X fields missing"
5. Result: Project created, can reopen & complete later
```

### CREATE NEW PROJECT (Full)
```
1. Fill project basics: name, path
2. Fill ALL mandatory fields (16+)
3. Click "Create Project" (button turns green)
4. No confirmation needed
5. Result: Project created, fully complete
```

### EDIT & SAVE EXISTING (Full)
```
1. Open project
2. Edit fields
3. When all mandatory complete → Button changes to "Save Changes"
4. Click save
5. Result: project.json + dataset_description.json updated
```

### EDIT & SAVE EXISTING (Preliminary)
```
1. Open project (may be incomplete)
2. Edit fields (but don't complete all mandatory)
3. Click "Save Preliminary Project State"
4. Confirm modal: "Continue with X fields missing"
5. Result: Partial metadata saved, can resume later
```

## API Endpoints (Frontend Calls)

### Create Project
```
POST /api/projects/create
{
  "name": "My Study",
  "path": "/path/to/project",
  "sessions": 0,
  "modalities": ["survey", "biometrics"]
}
```

### Set Active Project
```
POST /api/projects/current
{
  "path": "/path/to/project",
  "name": "My Study"
}
```

### Save Dataset Description
```
POST /api/projects/description
{
  "project_path": "/path/to/project",
  "description": {
    "Name": "My Study",
    "Authors": ["Smith, John"],
    "Keywords": ["psychology", "survey"],
    "License": "CC0",
    ...
  },
  "citation_fields": { ... }
}
```

### Save Study Metadata
```
POST /api/projects/study-metadata
{
  "project_path": "/path/to/project",
  "Overview": {...},
  "StudyDesign": {...},
  "Recruitment": {...},
  ...
}
```

## Frontend State Management

### Validation Function Chain
1. **On every keystroke:** `computeLocalCompleteness()`
   - Scores all sections 0-100%
   - Marks fields as red/yellow/green

2. **When saving:** `validateAllMandatoryFields()`
   - Returns: `{isValid, emptyFields[], invalidFields[]}`
   - If `!isValid` → Show modal, user confirms

3. **Button state:** `updateCreateProjectButton()`
   - Sets button to Create/Save/Preliminary based on state

### State Store
- **Location:** `window.prismProjectStateStore` (or window globals)
- **Contains:** `{path, name}`
- **Used by:** All pages to know active project
- **Synced via:** `/api/projects/current` endpoint

## Common Issues & Solutions

### "Project path mismatch" Error
**Cause:** User switched projects mid-edit
**Solution:** Reload page or switch back to correct project

### Form shows old data after browser back
**Cause:** Browser cache + form pre-filled
**Solution:** Normal behavior; form is idempotent (safe to re-save)

### "Preliminary" badge won't go away
**Cause:** Incomplete mandatory fields still exist
**Solution:** Fill all red-badged fields until all mandatory complete

### Author not saved with ORCID/roles
**Cause:** Backend didn't sync due to schema mismatch
**Solution:** Ensure author has both first+last name before adding roles

### CITATION.cff not generated
**Cause:** No first save completed yet
**Solution:** Save dataset description first to trigger CITATION.cff generation

## Files That Matter

### Backend
- `src/project_manager.py` - Creates projects, validates
- `app/src/web/blueprints/projects_*.py` - Save handlers

### Frontend  
- `app/static/js/modules/projects/metadata.js` - Form logic & validation
- `app/static/js/shared/project-state.js` - State store

### Templates
- `app/templates/projects.html` - Project UI

## Key Rule: Explicit Path Always

Every save must include `project_path` in the JSON body:

```json
{
  "project_path": "/full/path/to/project",  // ← ALWAYS
  "description": {...}
}
```

**Why?** Prevents stale writes when user switches projects between load and save.

## Testing Checklist

- [ ] Create prelim project → Reopen → Complete → Full save
- [ ] Create full project → Verify all metadata saved
- [ ] Edit existing → Change mandatory field → Save
- [ ] Edit existing → Leave incomplete → Try save → Shows issues
- [ ] Switch projects mid-edit → Verify no stale writes
- [ ] Add author with ORCID → Reopen → ORCID persisted
- [ ] Fill form → Browser back → Form still has data (OK)
- [ ] Load prelim → Completion badge shows correct %
