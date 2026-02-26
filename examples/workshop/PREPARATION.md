# Workshop Preparation (Instructor)

This is a pre-flight checklist for the 2-hour beginner workshop.

## Session plan (120 min)

1. Download/setup (Windows) — 15 min
2. Project setup — 10 min
3. Import participant data — 20 min
4. Import survey data — 20 min
5. Error hunting — 20 min
6. Recipes — 20 min
7. Templates — 15 min

## Must-have files

- `official/library/survey/survey-who5.json`
- `official/recipe/survey/recipe-who5.json`
- `examples/workshop/exercise_1_raw_data/raw_data/wellbeing.tsv`
- `examples/workshop/exercise_3_using_recipes/recipe-wellbeing.json`

## Instructor checks before class

- [ ] `Prism.exe` launches on workshop Windows machines
- [ ] Source launch works (`source .venv/bin/activate` then `./prism-studio.py`)
- [ ] App opens at `http://localhost:5001`
- [ ] Exercise order is clear in `WORKSHOP_README.md`
- [ ] Participant mapping step writes `code/library/participants_mapping.json`
- [ ] Survey import creates sidecar JSON files
- [ ] Recipe export creates `.save` or `.xlsx`

## Fast smoke test (10 min)

1. Create project (`Wellbeing_Study_Workshop`).
2. Import participants (mapping enabled).
3. Import `wellbeing.tsv`.
4. Validate once.
5. Run wellbeing recipe export.
6. Create one template in template editor.

If this passes, the workshop flow is ready.
