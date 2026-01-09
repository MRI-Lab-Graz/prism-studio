# PRISM Studio UI Improvement Plan

## Overview
This document outlines the UI/UX improvements for PRISM Studio, organized by priority and implementation complexity.

---

## Phase 1: Quick Wins (Immediate)

### 1.1 Rename "Recipes & Scoring" to "Data Processing"
**Files to modify:**
- `templates/base.html` - Navigation link (line 127-128)
- `templates/home.html` - Tool card (line 103-117)
- `templates/recipes.html` - Page title if needed

**Rationale:** Consistent naming throughout the app. "Data Processing" is clearer and matches the internal route naming.

### 1.2 Standardize Button Colors
**Color Scheme:**
| Action Type | Class | Color | Usage |
|-------------|-------|-------|-------|
| Primary Action | `btn-primary` | Blue | Main CTA, navigation |
| Success/Validate | `btn-success` | Green | Validation, confirm |
| Secondary | `btn-outline-secondary` | Gray outline | Cancel, back |
| Warning | `btn-warning` | Yellow | Conversion, careful actions |
| Danger | `btn-danger` | Red | Delete, destructive |
| Info | `btn-info` | Cyan | Help, information |

**Files to audit:**
- All template files for button consistency

### 1.3 Improve Home Page
**Changes:**
- Add "Quick Actions" section at top (if project selected)
- Make "Key Highlights" collapsible or more compact
- Add "Recent Projects" quick access

### 1.4 Add Consistent Page Headers
**Standard format:**
```html
<div class="text-center mb-4">
    <h2><i class="fas fa-icon me-2"></i>Page Title</h2>
    <p class="text-muted">Brief description of what this page does</p>
</div>
```

---

## Phase 2: Navigation Consolidation (Medium Priority)

### 2.1 Proposed Navigation Structure
**Current (8 items):**
Home | Projects | Specifications | Validator | Recipes & Scoring | Survey & Boilerplate | Converter | Template Editor | Docs

**Proposed (5 items with dropdowns):**
```
Projects | Import & Convert | Validate | Process | Help
            ↓                                       ↓
    - Converter                              - Specifications
    - Template Editor                        - Documentation
    - Survey & Boilerplate
```

### 2.2 Implementation Steps
1. Create dropdown navigation in base.html
2. Group related features logically
3. Update all internal links
4. Add breadcrumbs for sub-pages

---

## Phase 3: Workflow Improvements (Lower Priority)

### 3.1 Project Context Bar
Add persistent project info below navigation:
```html
<div class="bg-light border-bottom py-2" id="project-context">
    <div class="container d-flex align-items-center">
        <i class="fas fa-folder-open text-primary me-2"></i>
        <span class="fw-bold">my-study-2024</span>
        <span class="badge bg-success ms-2">Library OK</span>
        <a href="/projects" class="ms-auto btn btn-sm btn-outline-primary">Change</a>
    </div>
</div>
```

### 3.2 Wizard-Style Converter
Convert the tabbed interface to a step-by-step wizard:
1. Select Modality
2. Choose Mode (Data Conversion / Template Generation)
3. Configure Options
4. Review & Convert

### 3.3 Dashboard Home Page
Replace marketing content with:
- Recent projects list
- Quick actions (Validate, Convert, New Project)
- Activity feed / last validation results

---

## Phase 4: Visual Polish (Ongoing)

### 4.1 Spacing Consistency
- Standardize margins: `mb-4` for sections, `mb-3` for elements
- Card padding: `p-4` standard, `p-5` for hero cards

### 4.2 Warning/Alert Consolidation
- Max 2 alerts visible at once
- Use collapsible for multiple warnings
- Consistent alert styling

### 4.3 Form Design
- Floating labels where appropriate
- Better field grouping
- Progress indicators for multi-step forms

---

## Implementation Checklist

### Quick Wins (Phase 1)
- [ ] Rename "Recipes & Scoring" to "Data Processing"
- [ ] Standardize button colors
- [ ] Add Quick Actions to home page
- [ ] Make Key Highlights collapsible

### Navigation (Phase 2)
- [ ] Design dropdown navigation
- [ ] Implement grouped navigation
- [ ] Add breadcrumbs
- [ ] Update all links

### Workflow (Phase 3)
- [ ] Add project context bar
- [ ] Implement wizard converter
- [ ] Create dashboard home

### Polish (Phase 4)
- [ ] Spacing audit
- [ ] Alert consolidation
- [ ] Form improvements

---

## Files Reference

| Template | Purpose | Priority Changes |
|----------|---------|------------------|
| `base.html` | Navigation, footer | Nav consolidation |
| `home.html` | Landing page | Quick actions, highlights |
| `converter.html` | Data conversion | Wizard flow |
| `projects.html` | Project management | Recent projects |
| `template_editor.html` | Template editing | Combine with Survey |
| `survey_generator.html` | LimeSurvey export | Combine with Template |
| `recipes.html` | Data processing | Rename |
| `index.html` | Validator | Already good |

---

## Notes

- All changes must preserve existing functionality
- Test in browser with Chrome extension after each change
- Maintain BIDS compatibility messaging
- Keep accessibility in mind (contrast, labels, etc.)
