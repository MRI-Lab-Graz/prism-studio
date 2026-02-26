# Exercise 0 — Download, Setup, Project

**Time:** 25 min total (Setup 15 + Project 10)  
**Goal:** Get everyone running PRISM Studio and create one active workshop project.

![Project Setup](../../../docs/_static/screenshots/prism-studio-exercise-0-project-setup-light.png)

## Step A: Launch (Windows-first)

1. Open workshop folder.
2. Double-click `Prism.exe`.
3. Keep terminal window open.
4. Open `http://localhost:5001`.

If running from source:

```powershell
scripts\setup\setup-windows.bat
.\.venv\Scripts\Activate.ps1
python prism-studio.py
```

```bash
source .venv/bin/activate
./prism-studio.py
```

## Step B: Create project

1. Go to **Projects**.
2. Create project name: `Wellbeing_Study_Workshop`.
3. Choose location.
4. Keep the default **YODA layout** (it is built in, no extra selection needed).
5. Complete all mandatory **Study Metadata** fields until the create button is enabled.
6. Click **Create Project**.

## Done when

- Active project shows `Wellbeing_Study_Workshop`.
- Project has `sourcedata/`, `rawdata/`, `code/`, `derivatives/`.
- `rawdata/dataset_description.json` exists.

## Next

Go to `../exercise_1_raw_data/INSTRUCTIONS.md` (participant import comes first).