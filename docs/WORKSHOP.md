# Workshop

The [Getting Started tutorial](TUTORIAL_BEGINNER.md) packaged for a live,
instructor-led session. There is no separate workshop curriculum: participants
work through the same chapters, from the same example spreadsheet, at the same
pace you set. This page is the instructor's side of that — timing, delivery,
and what to cut.

Materials live in the repository under `examples/workshop/`, one folder per
chapter that needs files, with a run sheet in
`examples/workshop/README.md` and a pre-flight checklist in
`examples/workshop/PREPARATION.md`.

## What fits in the time you have

Published chapter times total ~100 minutes for chapters 1–5, and run closer to
120 in a room with questions.

| Slot | Hands-on | Demonstrated | Cut |
|---|---|---|---|
| 2 hours | Chapters 1–3 | Chapter 4 | Chapters 5–6 |
| 3 hours | Chapters 1–3 | Chapters 4–5 | Chapter 6 |
| Full day | Chapters 1–6 | — | — |

Chapter 0 is install; assume it is done before the session and push install
problems to an open block at the end, or the first broken virtual environment
will eat your first twenty minutes. Chapter 6 is the one to cut from any short
session — most of its 30 minutes is a dataset download, and it does not go
well multiplied by a full room.

## Delivering it without slides

A PC room usually has no projector, which is a better constraint than it
sounds: the tutorial is written to be read and followed at each person's own
pace, so it does the presenting and you do the helping.

- **Let them read, and walk the room.** Point everyone at
  [Getting Started](TUTORIAL_BEGINNER.md) and circulate. Don't narrate a
  chapter they already have in front of them.
- **Put checkpoints on the board**, not in speech — "`participants.tsv` exists
  at the project root". Someone who fell behind can locate themselves without
  having to ask.
- **A folded card per desk**, red side up for "stuck", beats raised hands when
  you are crouched at a machine on the other side of the room.
- **Announce the checkpoint, wait two minutes, move on.** A lockstep room
  stalls on its slowest machine; the tutorial lets stragglers catch up.
- **Recruit whoever finishes first** as a second pair of hands. With one
  instructor and twenty machines this is the only thing that scales.
- **Both launch commands on the board.** Room machines are Windows, personal
  laptops usually aren't.

For a demonstration without a projector, run
`python prism-studio.py --public` and have participants open
`http://<your-ip>:5001/?token=<token>` in a second browser tab (the token is
in the URL printed at startup; without it the server answers 401, so share it
only with people in the room). It is a single shared
session, so tell them explicitly to watch rather than click — their clicks
edit your project.

## Teaching order

Follow the chapter order as published, even where another order tempts you.
Validation before scoring arguably teaches metadata better, but participants
are reading the page while they work, and a room where the screen and the page
disagree is a room full of raised hands.

## What they leave with

A `wellbeing_study` project containing demographic data, imported survey
responses, at least one scoring recipe, and a validation pass they can
interpret — plus the same tutorial open in a tab, to finish the chapters you
cut.

## What's next

- [Getting Started](TUTORIAL_BEGINNER.md) — the tutorial this session teaches
- [Projects](studio/projects.md) · [Survey Import](studio/converter_survey.md) ·
  [Validator](studio/validator.md)
- [Recipes](RECIPES.md)
