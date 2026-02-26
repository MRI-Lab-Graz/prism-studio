# Exercise 5 — Import Participant Data

**Time:** 20 min  
**Goal:** Convert demographic columns into a clean `participants.tsv` with standard values.

![Participant Mapping](../../../docs/_static/screenshots/prism-studio-exercise-5-participant-mapping-light.png)

## Input

- `raw_data/wellbeing.tsv`
- Active project from Exercise 0

## Do this

1. Go to **Converter**.
2. Load `raw_data/wellbeing.tsv`.
3. Confirm column mappings:
   - `participant_id` → participant id
   - `session` → session
4. Add/confirm participant value mapping:
   - `sex`: `1 -> M`, `2 -> F`, `4 -> O`
   - `handedness`: `1 -> R`, `2 -> L`
   - `education` → `education_level`
5. Save mapping as `code/library/participants_mapping.json`.
6. Run conversion.

## Done when

- `rawdata/participants.tsv` exists.
- Sex and handedness are recoded (letters, not raw numeric codes).
- Validation has no participant-column naming errors.

## If stuck

- Mapping file must be exactly `participants_mapping.json`.
- Column names are case-sensitive.
- Keep mapping file in `code/library/`.

## Next

Go to `../exercise_1_raw_data/INSTRUCTIONS.md` (survey import).

