# Exercise 1 — Participants First, Then Survey

**Time:** 20 min  
**Goal:** Import `wellbeing.tsv` in two passes: participant data first (dedicated tab), questionnaire data second.

![Exercise 1 Converter Screenshot](../../../docs/_static/screenshots/prism-studio-exercise-1-data-conversion-light.png)

## Input

- `raw_data/wellbeing.tsv`
- Active project from Exercise 0

## Why this is split

Most real datasets store socio-demographics and questionnaire responses in one file.  
PRISM handles this cleanly with a two-step workflow:

1. **Participants tab** → build clean `participants.tsv`
2. **Survey tab** → convert questionnaire items into survey files

## Do this

### A) Participant import (dedicated tab)

1. Go to **Converter** → **Participants** tab.
2. Load `raw_data/wellbeing.tsv`.
3. Map participant fields (for example):
   - `participant_id` → participant id
   - `session` → session
   - `age`, `sex`, `education`, `handedness` → participant variables
4. Apply/confirm value mappings where needed (for example sex codes).
5. Run participant import.

### B) Survey conversion (questionnaire)

1. Stay in **Converter**, switch to **Survey** tab.
2. Load `raw_data/wellbeing.tsv` again.
3. Use questionnaire columns only (`WB01`–`WB05`).
4. Set task name `wellbeing`, modality `survey`.
5. Enable sidecar generation.
6. Convert survey data.

## Done when

- `rawdata/participants.tsv` exists and contains clean participant columns.
- Survey files exist under `rawdata/sub-*/ses-*/survey/`.
- Each survey `.tsv` has a matching `.json` sidecar.
- Filename pattern looks like:
   `sub-<id>_ses-<id>_task-wellbeing_survey.tsv`

## Quick check

Run **Validate** once after both steps. Structure should pass; metadata warnings are expected and fixed later.

## Next

Go to `../exercise_2_hunting_errors/INSTRUCTIONS.md`.
