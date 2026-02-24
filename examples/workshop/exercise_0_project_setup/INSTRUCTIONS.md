# Exercise 0: Project Setup (Metadata First)

**Time:** 15 minutes  
**Goal:** Initialize your PRISM project and adopt a metadata-first workflow so your dataset is complete, reusable, and analysis-ready.

![Exercise 0 UI (Light Mode)](../../../docs/_static/screenshots/prism-studio-exercise-0-project-setup-light.png)

---

## What You'll Learn

By the end of this exercise, you will:
- ✓ Launch the PRISM Studio application
- ✓ Create a PRISM project with proper folder structure
- ✓ Set up your active workspace
- ✓ Understand why filling out metadata early saves time later

---

## Metadata-First Mindset

In this workshop, the main objective is not only to create files, but to create **well-documented data**.

Focus on this from the start:
- Keep metadata complete (dataset-level + participant-level + sidecar JSON)
- Prefer clear variable names and clear descriptions
- Treat missing metadata as a real issue, not a minor detail

Good metadata now means easier validation, easier scoring, and cleaner exports later.

---

## Launching PRISM

### Windows Users
1. Locate the **`Prism.exe`** file in your workshop folder.
2. Double-click to launch it.
3. A terminal window will open—keep this open! It runs the backend server.
4. Your default web browser should open automatically to **http://localhost:5001**.

### Manual Launch (if browser doesn't open)
1. Open your web browser (Chrome or Edge recommended).
2. Go to: **http://localhost:5001**

### If You See a Converter Error Here
Exercise 0 only uses the **Projects** page. If you see an error like:
**"No survey item columns matched the selected templates"**, you are in the converter tool too early.

Go back to **Projects** and finish this setup exercise first.

---

## Your Task: Create a Project Ready for Complete Metadata

Before conversion and validation, we need a project workspace where metadata files will be created and maintained.

### Step 1: Go to Projects
1. In the sidebar or top navigation, click on **"Projects"**.
2. Alternatively, go directly to: **http://localhost:5001/projects**

### Step 2: Create a New Project
1. Look for the **"Create New Project"** section.
2. **Project Name:** Enter `Wellbeing_Study_Workshop`.
3. **Location:** Choose a folder on your computer where you want to store your data (e.g., your Desktop or a dedicated `workshop_results` folder).
4. **Template:** Select **"YODA Structure"** (if available) to automatically create proper folders.
5. Click **"Create & Activate"**.

### Step 3: Explore Your Project Structure
Your new project should have this structure:
```
Wellbeing_Study_Workshop/
├── sourcedata/          # Original raw files (Excel, CSV) go here
├── rawdata/             # PRISM-formatted data will be created here
│   ├── dataset_description.json
│   └── participants.tsv
├── code/                # Your analysis scripts (Python, R, etc.)
├── derivatives/         # Processed outputs (SPSS files, scores, reports)
└── README.md            # Project documentation
```

**Why this structure matters:**
- `sourcedata/` preserves your original data files - you can always go back to the start
- `rawdata/` contains BIDS/PRISM formatted data that tools and apps can understand
- `code/` keeps your analysis separate from data
- `derivatives/` stores computed results without mixing them with raw data

### Step 4: Verify Your Workspace
1. Notice the **"Active Project"** label at the top of the screen. It should now show `Wellbeing_Study_Workshop`.
2. PRISM now knows where to save all your conversions and exports!
3. If you browse to your chosen location, you'll see the folder structure was created.

### Step 5: Metadata Completeness Checklist (Important)
Use this checklist throughout the workshop:

- [ ] `dataset_description.json` exists and is filled
- [ ] `participants.tsv` exists and required columns are present
- [ ] Each data `.tsv` has a matching `.json` sidecar
- [ ] Sidecars include item descriptions and level labels
- [ ] Validation has no unresolved metadata errors

---

## Understanding the Workflow

Throughout this workshop, you'll follow this path:

1. **Start:** Excel file with wellbeing survey responses
2. **Step 1 (Next):** Convert to PRISM format → saves to `rawdata/`
3. **Step 2:** Validate and add metadata → improves `rawdata/`
4. **Step 3:** Apply recipes and export → saves results to `derivatives/`

This workflow keeps your dataset complete and reusable, not just technically valid.

---

## YODA (Context, Not Main Focus)

PRISM can use a YODA-like project structure to separate source files, standardized data, code, and results:
- `sourcedata/` for original files
- `rawdata/` for PRISM/BIDS-compatible data and metadata
- `code/` for scripts
- `derivatives/` for outputs

This structure supports reproducibility, but in this workshop the priority is still **metadata completeness**.

---

**Next Steps:**
Now that your project is ready, let's bring in data and fill metadata properly from the beginning.

**Ready for Exercise 1?** → Go to `../exercise_1_raw_data/`
