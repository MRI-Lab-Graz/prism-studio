# PRISM Documentation Rewrite Plan

## Goal
Create clear, user-focused documentation that emphasizes PRISM Studio (web interface) as the primary way to use PRISM, while maintaining CLI documentation for advanced users.

---

## Proposed Structure

### 1. **index.rst** - Landing Page
Complete rewrite with:
- What is PRISM? (1 paragraph)
- PRISM vs BIDS: An Add-On, Not a Replacement (key message!)
- Benefits at a glance (bullet list)
- Quick navigation to key sections

### 2. **Getting Started** (New section order)

#### 2.1 `WHAT_IS_PRISM.md` (NEW)
- **What is PRISM?**
  - BIDS-compatible validation tool for psychological experiments
  - Adds survey, biometrics, eyetracking support to BIDS
  - Ensures datasets remain compatible with fMRIPrep and other BIDS apps
  
- **PRISM vs BIDS**
  - PRISM is an ADD-ON, not a replacement
  - Standard BIDS datasets work with PRISM
  - PRISM adds stricter metadata requirements for reproducibility
  - `.bidsignore` integration keeps BIDS apps happy

- **Key Benefits**
  1. **Validation**: Catch errors early with structured error codes
  2. **Metadata**: Self-documenting datasets with item descriptions
  3. **Scoring**: Calculate questionnaire scores with recipes
  4. **Export**: SPSS-ready output with value labels
  5. **FAIR Compliance**: Machine-readable, reusable data

#### 2.2 `INSTALLATION.md` (Rewrite)
- **Quick Start (5 minutes)**
  ```bash
  git clone https://github.com/MRI-Lab-Graz/prism-studio
  cd prism-studio
  ./setup.sh  # or setup.ps1 on Windows
  python prism-studio.py
  ```
- **Detailed Installation**
  - Python requirements (3.9+)
  - Platform-specific notes (Windows, macOS, Linux)
  - Virtual environment setup
  - Troubleshooting common issues

#### 2.3 `QUICK_START.md` (Rewrite - Web-focused)
- Launch PRISM Studio
- Create your first project (YODA layout)
- Convert a simple Excel file
- Validate your dataset
- → Link to workshop for hands-on practice

### 3. **PRISM Studio Guide** (Web Interface - Main Section)

#### 3.1 `STUDIO_OVERVIEW.md` (NEW)
- Screenshot-based tour of the interface
- Navigation: Projects → Converter → Validator → Tools

#### 3.2 `PROJECTS.md` (NEW)
- Creating new projects (YODA layout explained)
- Opening existing projects
- Project metadata (dataset_description.json)
- Participants management (participants.tsv, participants.json)
- NeuroBagel compliance

#### 3.3 `CONVERTER.md` (NEW - dedicated page)
- **Data Sources**
  - Excel (.xlsx, .xls)
  - CSV/TSV
  - SPSS (.save)
  - LimeSurvey exports
  
- **Step-by-step conversion**
  1. Select source file
  2. Map columns to PRISM fields
  3. Preview transformation
  4. Save to project

- **Participants Mapping**
  - Custom demographic encodings
  - Auto-transformation rules
  - Link to detailed PARTICIPANTS_MAPPING.md

#### 3.4 `VALIDATOR.md` (NEW - dedicated page)
- Running validation
- Understanding results (errors, warnings, suggestions)
- Error codes reference (link to ERROR_CODES.md)
- Auto-fix feature
- BIDS validation integration

#### 3.5 `TOOLS.md` (NEW - overview of tools dropdown)

##### File Management
- Renamer by Example
- Folder Organizer
- Bulk operations

##### Survey Export
- Survey file generator
- Survey customizer
- Library browser

##### Recipes & Scoring
- What are recipes?
- Running recipes
- Creating custom recipes
- Export formats (SPSS, CSV)

##### Template Editor
- Creating survey templates
- Editing item descriptions
- Bilingual support (DE/EN)

### 4. **Workshop & Examples**

#### 4.1 `WORKSHOP.md` (NEW - landing page for workshop)
- Link to `examples/workshop/`
- Overview of exercises:
  - Exercise 0: Project Setup (YODA)
  - Exercise 1: Data Conversion
  - Exercise 2: Participant Mapping
  - Exercise 3: Recipes & Scoring
  - Exercise 4: Templates
- Downloadable materials

### 5. **Reference** (Keep but reorganize)

#### 5.1 `CLI_REFERENCE.md` (Keep)
- For advanced users
- All command-line options
- Batch processing

#### 5.2 `SPECIFICATIONS.md` (Keep)
- PRISM schema details
- Modality specifications

#### 5.3 `ERROR_CODES.md` (Keep)
- Complete error code reference

#### 5.4 `RECIPES.md` (Keep but enhance)
- Recipe format specification
- Creating custom recipes
- Official recipe library

### 6. **Advanced Topics** (Keep but demote)
- LIMESURVEY_INTEGRATION.md
- WINDOWS_BUILD.md
- RELEASE_GUIDE.md
- API documentation

---

## Files to Remove or Archive
- WALKTHROUGH.md (outdated, merge into QUICK_START)
- DEMO_DATA.md (merge into WORKSHOP)
- Multiple overlapping mapping docs (consolidate)
- IMPLEMENTATION_SUMMARY.md (developer-only)
- NEUROBAGEL_*.md (merge into PROJECTS.md)

---

## Priority Order for Writing

### Phase 1: Core Pages (Essential)
1. `WHAT_IS_PRISM.md` - New flagship intro
2. `INSTALLATION.md` - Rewrite
3. `QUICK_START.md` - Rewrite (web-focused)
4. `index.rst` - Update structure

### Phase 2: Studio Guide (Main Documentation)
5. `STUDIO_OVERVIEW.md`
6. `PROJECTS.md`
7. `CONVERTER.md`
8. `VALIDATOR.md`
9. `TOOLS.md`

### Phase 3: Workshop
10. `WORKSHOP.md` - Landing page

### Phase 4: Cleanup
11. Archive outdated files
12. Update cross-references
13. Add screenshots

---

## Key Messages to Emphasize Throughout

1. **PRISM is BIDS-compatible** - Your dataset will still work with fMRIPrep!
2. **Web interface first** - Most users should use PRISM Studio
3. **Self-documenting data** - Metadata makes research reproducible
4. **Workshop available** - Hands-on learning in `examples/workshop/`

---

## Questions to Resolve

1. Should we keep RST format or switch entirely to Markdown?
2. Do we need API documentation for external integrations?
3. Should screenshots be version-numbered?
