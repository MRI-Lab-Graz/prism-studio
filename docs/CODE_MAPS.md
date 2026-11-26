# Participant code maps

## Why a code map

In many studies people type a self-chosen code into the survey (letters of a name, a birth month),
while the dataset uses participant numbers such as `sub-004`. The number cannot be worked out from
the code. A **code map** is the table that links the two. Keep it in the project's `code/` folder and
`survey convert` (and Studio, which runs the same command) uses it by itself.

Today only the **survey** import reads code maps. Biometrics, environment, biosample, participants
and batch imports do not yet.

## File names

| File in `code/` | Applies to |
|---|---|
| `survey_code_map.tsv` | all survey imports |
| `survey_task-ads_code_map.tsv` | task `ads` only |
| `survey_ses-3_code_map.tsv` | every task in session 3 |
| `survey_task-ads_ses-3_code_map.tsv` | task `ads` in session 3 only |

`task-` comes before `ses-`. The session label is the one written to the dataset (after your
project's session mapping), compared exactly: `1` and `01` are different sessions. In a project
with one timepoint the session is `1`.

Any other file in `code/` whose name starts with `survey_` and contains `code_map` stops the import,
including a copy such as `survey_code_map - Kopie.tsv`. Move backups to a subfolder.

## File format

A UTF-8, tab-separated table with these two column names:

```text
code	participant_id
AAAA0101	sub-001
BBBB0202	sub-002
BBBB0203	sub-002
```

Capitals and surrounding spaces in codes do not matter. Several codes may point to one participant,
for example when someone typed a second spelling. A row with an empty `participant_id` counts as not
listed.

## Which file wins

For one code, one task and one session, the first of these that lists the code decides:

1. `task-` and `ses-`
2. `task-` or `ses-` (if both list the code with different participants, the import stops)
3. the general map

A narrower file only needs the codes that differ.

`--id-map FILE` (Studio: the ID map upload) replaces all project maps for that run, and the import
says which maps it did not use.

## One row, one participant

One response row is one person. If a row holds several questionnaires and the maps send them to
different participants, the import stops and writes nothing. This is checked for every
questionnaire in the file, also those you left out with `--survey`. A task map can therefore only
give a different result when that questionnaire comes in its own file.

## Worked example

```text
code/survey_code_map.tsv            AAAA0101 -> sub-001
code/survey_ses-3_code_map.tsv      AAAA0101 -> sub-002
```

Sessions 1 and 2 of `AAAA0101` are written to `sub-001`, session 3 to `sub-002`.

```bash
python prism_tools.py survey convert --input responses.lsa --output /path/to/project \
  --id-column Code --session 3 --dry-run
```

A dry run reports each map it used: `Applied code map survey_ses-3_code_map.tsv: 1 code(s).`

## When the import stops

| Message | What to do |
|---|---|
| `ID mapping incomplete: ...` | Add the listed codes to a map. |
| `the questionnaires of one row belong to different participants` | Make the named files agree. |
| `different participants in equally specific maps` | Make the `task-` and `ses-` files agree, or add a `task-`+`ses-` file. |
| `listed in ..., but this row has no session` | Give `--session` or a session column. Sessions numbered from response dates (`--duplicate-handling sessions`) cannot be used with session maps. |
| `is not a code map name` | Rename the file, or move it out of `code/`. |
| `must name the columns 'code' and 'participant_id'` | Add the header line. |
| `is listed with two different participants` | Remove one of the two rows. |
| `is not a participant ID` | Write `sub-` plus letters and digits. |
| `the task is written task-...` | Rename the file with the task name spelled as in the dataset. |

A warning `the project has no session ...` means a session map names a label your project never
writes (for example `pre` instead of the mapped `1`), so the map has no effect.

## Privacy

A code map can re-identify your participants. Therefore:

- No export or share contains a file under `code/` whose name contains `code_map`, even when `code/`
  is included. The export names what it left out.
- The files are kept out of git. A colleague who receives the project does not get them; hand them
  over separately if the import must be repeated. PRISM tells git to ignore them the first time it
  imports, exports or saves the project. If another program saves the project before that, check
  that the map was not committed.
- A map that was committed earlier stays in the git history. The import warns about it.

**Not protected:** other files that hold codes next to participant numbers, for example a
spreadsheet in `sourcedata/`, or a map you pass with `--id-map` from elsewhere in the project. Check
them yourself before sharing.
