# Workshop Preparation (Instructor)

Pre-flight for a live session. Participant-facing material is
[README.md](README.md); the teaching is the
[Getting Started tutorial](../../docs/TUTORIAL_BEGINNER.md).

## Must-have files

- `raw_data/wellbeing.xlsx` (chapters 2 and 3)
- `chapter_3_survey_import/survey-wellbeing.json`
- `chapter_4_recipe/recipe-wellbeing.json`
- `official/library/survey/survey-who5.json`
- `official/recipe/survey/recipe-who5.json`

## Checks before class

- [ ] PRISM Studio launches (Desktop shortcut from `install.cmd`, or `PrismStudio.exe` from the ZIP) on the **workshop** machines, in a normal user
      account — not just on yours. The unsigned-binary warnings differ per
      machine policy, and that is the failure you care about.
- [ ] Source launch works (`source .venv/bin/activate && python prism-studio.py`)
- [ ] App opens at `http://localhost:5001`
- [ ] `--public` reaches a second machine, if you plan to demo that way
- [ ] `examples/workshop/` staged on a USB stick for people bringing laptops

## Smoke test (10 min)

Walk chapters 1–5 yourself on a workshop machine:

1. Create project `wellbeing_study`.
2. Import demographics from `raw_data/wellbeing.xlsx` with mapping enabled —
   confirm `participants.tsv` **and** `participants.json` appear.
3. Import survey responses — confirm one `.tsv` per participant plus one
   shared sidecar JSON.
4. Save the wellbeing recipe and export.
5. Validate once and read the findings.

If that passes, the session is ready.
