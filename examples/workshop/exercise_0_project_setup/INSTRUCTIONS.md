# Exercise 0: Set Up Your PRISM Project (YODA Principles)

**⏱ Time:** 15 minutes  
**🎯 Goal:** Create a professional, reproducible project structure and activate it in PRISM Studio

**📚 Concepts:** YODA principles, project organization, workspace setup

---

## What is YODA?

YODA (Yet anOther Data Analysis) is a framework for organizing research projects in a way that:
- ✅ **Separates concerns** - raw data, analysis, and results are isolated
- ✅ **Enables reproducibility** - anyone can follow and understand your workflow
- ✅ **Supports collaboration** - team members can work clearly on different parts
- ✅ **Manages version control** - git-friendly structure for tracking changes
- ✅ **Preserves data integrity** - original files never get accidentally modified

**Many labs and funding agencies (NIH, NSF, EU) now require YODA-compliant structures!**

---

## YODA Folder Structure

A YODA project has these core folders:

| Folder | Purpose | What Goes Here |
|--------|---------|-----------------|
| `sourcedata/` | Original, raw files | Excel spreadsheets, CSV exports from your instruments |
| `rawdata/` | Standardized PRISM/BIDS format | Converted survey data with proper names and metadata |
| `code/` | Analysis scripts | Python, R, MATLAB notebooks and scripts |
| `derivatives/` | Processed outputs | Scored data, statistics, figures, SPSS exports |

**Key principle:** `sourcedata/` is READ-ONLY. You never modify files there. If something goes wrong, you always have the original data to return to!

---

## Getting Started: Launch PRISM Studio

### Step 1: Activate Your Python Environment

First, make sure PRISM is running with the correct Python environment.

**macOS/Linux:**
```bash
cd /path/to/prism-studio
source .venv/bin/activate
python prism-studio.py
```

**Windows (PowerShell):**
```powershell
cd C:\path\to\prism-studio
.venv\Scripts\Activate.ps1
python prism-studio.py
```

You should see terminal output starting the Flask server:
```
 * Running on http://127.0.0.1:5001
```

### Step 2: Open PRISM Studio in Your Browser

1. Open your web browser (Chrome, Firefox, Safari, or Edge)
2. Go to: **http://localhost:5001**
3. You should see the PRISM Studio home page

---

## Your Task: Create a New Project

### **Step 1: Navigate to Projects**

In the PRISM Studio interface:
1. Look for the navigation menu (usually on the left sidebar)
2. Click on **"Projects"** or **"Project Management"**
3. You can also go directly to: **http://localhost:5001/projects**

### **Step 2: Create a New Project**

You should see a **"New Project"** button or section. Click it.

Fill in these details:

| Field | Value | Notes |
|-------|-------|-------|
| **Project Name** | `Wellbeing_Study_Workshop` | Use underscores, avoid spaces & special chars |
| **Description** | (Optional) | e.g., "WHO-5 workshop analysis" |
| **Location** | Choose a folder | Desktop, Documents, or a dedicated `workshop` folder |
| **Project Template** | YODA | Select "YODA Structure" if available |

### **Step 3: Click "Create & Activate"**

PRISM will:
1. Create the folder at your chosen location
2. Build the YODA folder structure automatically
3. Set it as your **Active Project** (shown at the top of the screen)

### **Step 4: Verify the Structure**

After creation, your project folder should look like this (you can browse to it on your computer):

```
Wellbeing_Study_Workshop/
│
├── sourcedata/
│   └── (where original Excel files will go)
│
├── rawdata/
│   ├── dataset_description.json
│   ├── participants.tsv
│   └── (where converted PRISM data will live)
│
├── code/
│   └── (your analysis scripts will go here)
│
├── derivatives/
│   └── (scores, exported SPSS files, reports)
│
└── README.md
    └── (project documentation)
```

**Confirmation:**
- Look at the top of PRISM Studio
- It should say: **"Active Project: Wellbeing_Study_Workshop"**
- This means PRISM knows where to save everything!

---

## Why This Matters

Throughout this workshop, your workflow will look like this:

```
Step 1: sourcedata/wellbeing.xlsx
        (original data - never touch!)
            ↓
Step 2: Convert to PRISM format
            ↓
        rawdata/task-wellbeing_survey.tsv
        rawdata/task-wellbeing_survey.json
            ↓
Step 3: Validate & add metadata
            ↓
Step 4: Apply scoring recipes
            ↓
        derivatives/wellbeing_scores.csv
        derivatives/wellbeing_analysis.sav (SPSS)
```

**Result:** Everyone can see exactly what happened and reproduce your analysis!

---

## Bonus: Understanding Project Metadata

PRISM automatically creates a `dataset_description.json` file. Let's look at it:

1. In PRISM Studio, go to **"File Management"** or similar
2. Navigate to your `rawdata/` folder
3. Open `dataset_description.json` in a text editor (or PRISM's JSON viewer)
4. You'll see metadata like:
   - Dataset name
   - Authors
   - License information
   - BIDS version compatibility

This metadata makes your dataset discoverable and reusable!

---

## Checklist: Ready to Move On?

Before starting Exercise 1, confirm:

- [ ] PRISM Studio is running (http://localhost:5001 works)
- [ ] You created a project named `Wellbeing_Study_Workshop`
- [ ] The project appears as **"Active Project"** at the top of the screen
- [ ] You can see the folder structure on your computer
- [ ] You understand why separating sourcedata/rawdata/derivatives matters

---

## Next Steps

**Excellent!** Your project is now set up professionally. 

In **Exercise 1**, you'll:
- Take a raw Excel file with survey responses
- Convert it to PRISM/BIDS format using the GUI
- Save the structured data to your `rawdata/` folder

Ready? → Go to **`../exercise_1_raw_data/INSTRUCTIONS.md`**

---

## 💡 Tips & Troubleshooting

**Q: Can I change the project location later?**  
A: Currently, you'd need to move the folder manually or create a new project. It's best to choose carefully from the start.

**Q: What if I accidentally create the wrong project?**  
A: Just delete the folder from your computer. No problem! Create a new one.

**Q: Do I need to use these exact folder names?**  
A: YODA is flexible, but stick to lowercase with underscores. It's best for cross-platform compatibility and following community standards.

**Q: Why "YODA" and not just "BIDS"?**  
A: YODA is the broader organizational framework. BIDS (Brain Imaging Data Structure) is a specific data format standard. YODA uses BIDS in the `rawdata/` folder but adds the broader project structure.
