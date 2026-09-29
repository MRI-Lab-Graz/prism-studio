# Workshop Materials

The files a live workshop hands out. **The teaching lives in the
[Getting Started tutorial](../../docs/TUTORIAL_BEGINNER.md)** — these folders
only supply the data each chapter needs, named after the chapter that uses
them. Nothing here re-explains a step; if you want the explanation, read the
chapter.

Instructors: see [PREPARATION.md](PREPARATION.md) for the pre-flight checklist.

## Chapters and their files

| Chapter | Files you need |
|---|---|
| 0 — Install and First Launch | none |
| 1 — Create a Project | none |
| 2 — Import Sociodemographic Data | `raw_data/wellbeing.xlsx`, `chapter_2_participants/` |
| 3 — Import Survey Response Data | `raw_data/wellbeing.xlsx`, `chapter_3_survey_import/survey-wellbeing.json` |
| 4 — Prepare a Recipe | `chapter_4_recipe/recipe-wellbeing.json` |
| 5 — Use the Validator | `chapter_5_validator/` (13 optional challenges) |
| 6 — Enrich an Existing BIDS Dataset | downloads its own dataset |

`raw_data/wellbeing.xlsx` sits outside the chapter folders on purpose: it is
the study's one source spreadsheet, shared by chapters 2 and 3, and it exists
exactly once so the two chapters can never drift apart. `wellbeing.tsv` beside
it is the identical data as plain text, if you want to show that the importer
doesn't care about the format.

## Running a 3-hour session

Chapters 1–5 are ~100 minutes as written, and closer to 120 in a room. A
3-hour slot fits chapters 1–3 hands-on, chapters 4–5 demonstrated, and a long
open block at the end — which is where install problems belong, not at the
start.

| Time | Block |
|---|---|
| 0:00–0:10 | Launch check — everyone reaches `http://localhost:5001` |
| 0:10–0:25 | Chapter 1 — create `wellbeing_study` |
| 0:25–0:50 | Chapter 2 — import demographics |
| 0:50–1:00 | Break |
| 1:00–1:30 | Chapter 3 — import survey responses |
| 1:30–1:45 | Chapters 4 and 5, demonstrated |
| 1:45–3:00 | Open questions, installs, participants' own data |

Swap in more hands-on time by moving chapter 4 into the room and demonstrating
only chapter 5. Drop chapter 6 from a live session entirely — most of its 30
minutes is a dataset download, and twenty machines downloading at once will
not go well.

## Checkpoints

Write these on the board. They let someone who fell behind find themselves
without asking, which matters in a room where you can't project a screen.

1. Project `wellbeing_study` appears in the project list
2. `participants.tsv` and `participants.json` exist at the project root
3. `sub-*/ses-baseline/survey/*_survey.tsv` exist, one per participant
4. A recipe is saved and produces a score column
5. The validator runs and its findings are understood

## Launching PRISM

Put both of these on the board — a workshop room is usually Windows while
personal laptops are not.

```bash
# macOS / Linux
source .venv/bin/activate && python prism-studio.py

# Windows
install.cmd        # first time only, then use the "PRISM Studio" Desktop shortcut
                   # (ZIP download: double-click PrismStudio.exe)

# both: http://localhost:5001
```

No projector? Run `python prism-studio.py --public` and have participants
open `http://<your-ip>:5001` in a second tab to watch your instance. It is one
shared session — tell them to look, not click, because their clicks edit your
project.

## Bringing your own laptop

Chapters 2 and 3 read files from this folder, so a machine without the repo
checked out needs `examples/workshop/` copied to it. A USB stick is faster
than twenty people cloning the repo and installing dependencies at 0:05.
