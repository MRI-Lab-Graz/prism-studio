# Exercise 0: Setting Up Your PRISM Project with YODA Principles

**Time:** 15 minutes  
**Goal:** Initialize your workspace following YODA (Yet anOther Data Analysis) principles and create your first PRISM project.

---

## What You'll Learn

By the end of this exercise, you will:
- ✓ Understand YODA principles for project organization
- ✓ Launch the PRISM Studio application
- ✓ Create a PRISM project with proper folder structure
- ✓ Set up your active workspace

---

## Background: YODA Principles

**YODA** (Yet anOther Data Analysis) is a project organization framework that helps you:
- **Separate concerns**: Keep raw data, analysis code, and results in separate folders
- **Version control**: Make your project git-friendly
- **Reproducibility**: Anyone can understand and rerun your analysis
- **Collaboration**: Clear structure makes teamwork easier

**Key YODA folders:**
- `sourcedata/` - Original, unmodified raw data (never edit these!)
- `rawdata/` - BIDS/PRISM formatted data ready for analysis
- `code/` - Analysis scripts and notebooks
- `derivatives/` - Processed outputs (scores, statistics, figures)

PRISM Studio can automatically create this structure for you!

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

---

## Your Task: Create a YODA-Compliant Project

Before we can convert or validate data, we need a "Project" with proper folder structure.

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

---

## Understanding the Workflow

Throughout this workshop, you'll follow this path:

1. **Start:** Excel file with wellbeing survey responses
2. **Step 1 (Next):** Convert to PRISM format → saves to `rawdata/`
3. **Step 2:** Validate and add metadata → improves `rawdata/`
4. **Step 3:** Apply recipes and export → saves results to `derivatives/`

This separation keeps your workflow clean and reproducible!

---

**Next Steps:**
Now that your project is ready with YODA structure, let's bring in some data!

**Ready for Exercise 1?** → Go to `../exercise_1_raw_data/`
