# Eye-tracking converter: design

Status: draft for review, 2026-10-31. Nothing is built. Implementation waits for more lab data (see "Open").
Follows `docs/superpowers/plans/2026-10-24-drop-eyetracking.md`, which dropped PRISM's own `eyetracking` modality and
deferred the converter ("no converter for now").

## Intent

Labs with an SR Research EyeLink tracker record one `.edf` per block. Studio should turn that recording into
BIDS-valid eye-tracking files (BEP20, part of BIDS 1.11.0) in the project, aligned to the task's existing `events.tsv`,
and keep the original untouched in `sourcedata/`. Eye tracking without a task is useless, so only the task-bound
BIDS form exists. PRISM's task-free `physio/` is not involved.

## What the data looks like (checked on a real lab file, 2026-10-31)

- Chain per subject and block: the paradigm writes the event file; the tracker writes the `.edf`; SR Research software
  (Data Viewer sample report, or eye2bids through `edf2asc`) turns the `.edf` into a TSV; that TSV is not BIDS.
- The sample file is a Data Viewer sample report: 467,703 rows at 1000 Hz, 106 trials, monocular right eye
  (`RECCFG ... R`), UTF-8 BOM, `.` for missing values, one row per sample.
- Columns that map to BIDS: `TIMESTAMP` -> `timestamp`, `AVERAGE_GAZE_X` -> `x_coordinate`, `AVERAGE_GAZE_Y` ->
  `y_coordinate`, `AVERAGE_PUPIL_SIZE` -> `pupil_size`. The lab confirms the `AVERAGE_` columns are the raw samples,
  not aggregates.
- The header message in the first row gives the screen (`GAZE_COORDS 0 0 1919 1079`) and the recorded eye.
- `SAMPLE_MESSAGE` holds the markers the stimulus program sent into the tracker (`fixation_onset`, `cue_*`, `target_*`,
  `end_trial N;TRIAL_RESULT 0`). `TRIAL_INDEX` and `IP_START_TIME` mark trials. Between trials there are gaps of about
  2 s with no samples.
- `TIMESTAMP` is the tracker's own clock (starts at an arbitrary value, 5,529,512 here). It is not the clock of
  `events.tsv`.

## Decisions (the user's)

1. The raw files (the `.edf` if the lab keeps it, and the exported TSV) go to `sourcedata/` unchanged. Not
   `derivatives/`: Studio did not change them, SR Research's software only reformatted them.
2. Studio converts the exported TSV to BIDS files in the task's datatype folder. Studio does not read `.edf`.
3. The paradigm's `events.tsv` is the time reference. It is not modified.
4. The event file is found by BIDS name from subject, session and task given by the user. No guessing.
5. Raw `.edf` through eye2bids stays an opt-in route later (`requirements-eyetrack.txt` exists); it needs SR Research's
   `edf2asc`, which Studio cannot bundle.

## Design

### One function, one CLI command

Per `CLAUDE.md` the logic exists once in `src/`, exposed as `prism_tools.py convert eyetracking`. The Studio converter
page (a new "Eye tracking" section) collects the same input, calls the same function and shows the result. Same
options, same defaults. Parity test: `tests/test_cli_studio_parity.py` runs both on identical project copies.

Inputs: the TSV export, `--project`, `--subject`, `--task`, optional `--session`, optional `--datatype func|beh|eeg`
(default: the datatype folder that holds the task's `events.tsv`), optional sidecar fields that the file cannot supply
(screen distance, screen size in cm, anything else BEP20 requires), `--json`. Session labels are free-form strings and
are never normalized, except by `src/session_map.py` in single-timepoint projects.

### Output

In the task's datatype folder:

- `sub-<l>[_ses-<l>]_task-<l>_recording-eye1_physio.tsv.gz` with columns `timestamp`, `x_coordinate`, `y_coordinate`,
  then `pupil_size`; `.` becomes `n/a`; the BOM is dropped.
- the matching `.json`: `PhysioType: eyetrack`, `SamplingFrequency`, `StartTime`, `Columns`, `RecordedEye`,
  `SampleCoordinateSystem: gaze-on-screen`, `Units`, and the screen fields in the task's `events.json`
  (`StimulusPresentation.ScreenResolution`, `ScreenDistance`, `ScreenSize`, `ScreenOrigin`).
- Fields read from the file's header message are filled in; the rest come from the user's input; a field neither can
  supply is reported, never invented.
- Text-file and annex policy untouched (`.gitattributes` rules stay as they are).

The raw inputs are copied byte for byte into `sourcedata/`.

### Alignment

The tracker clock is mapped to the clock of `events.tsv` through shared markers: a marker the stimulus program sent to
the tracker (`fixation_onset`, `cue_*`, `target_*`) and the same event in `events.tsv`. The offset is the median over
all matched markers. It becomes `StartTime` in the sidecar. The preview reports how many trials matched, the spread
of the offset across trials, and any unmatched trial. A large spread (drift) is a warning, a missing `events.tsv` or no
matched marker is an error and nothing is written. Problems appear in the preview summary, never silently.

### Events file

`physioevents.tsv.gz` and its sidecar (from the markers and the blink/saccade flags) are a second step after the
samples file works. The lab asked for the samples only.

### Gaps between trials

The recording is written as one continuous file with `n/a` in the gaps between trials, so `StartTime` stays one number.
Writing one file per trial is the alternative. This is my call; see "Open".

## Goals, non-goals, anti-goals

Goals: a lab member with the Data Viewer export, the project's `events.tsv` and a task name gets valid BEP20 files and
a clear report. CLI and Studio give the same files and messages.

Non-goals: reading `.edf` in Studio; bundling `edf2asc`; modifying `events.tsv`; fixation detection; calibration
quality metrics; other vendors in the first version.

Anti-goals (a failure even if it runs): a silent wrong offset; a conversion that writes files when no event file is
found; invented screen or distance values; any copy of the logic in the route or JavaScript.

## Constraints

- Imports on the converter path may use pandas (the converter is not on the validator path); the validator image has
  no pandas and must not import this code.
- Vendored specification files are not edited here. If BEP20 needs terms the vendored schemas lack, that is a
  prism-specification change first.
- TDD: first a failing test on the first ~3,000 rows of the lab file (the 39 MB file is not committed; it may be
  identifiable participant data).
- `/ponytail:ponytail-audit` before merging.

## Open (waiting for more lab data)

1. Whether the lab always has the `.edf` or only the Data Viewer export. Decides what goes into `sourcedata/`.
2. Whether `events.tsv` comes from the same program as the tracker messages, and what its time zero is (scan start?).
   The user believes the same program, not certain. If the clocks cannot be tied by markers, a scanner trigger message
   is needed, or `StartTime` becomes required input.
3. Whether Data Viewer exports always have the same columns (monocular `AVERAGE_*`, binocular `LEFT_*`/`RIGHT_*`).
4. One continuous file with gaps, or one file per trial.
5. How the user maps the tracker's `RECORDING_SESSION_LABEL` (`s17_nr_1`) to a BIDS subject/session. The converter
   takes subject and session as input and never parses the label.
6. Which marker names count as alignment anchors (lab-specific); likely a user-given list with `fixation_onset` as
   the default.

## Builder-check answers (2026-10-31)

Calls made by the writer (not the user's decisions; change them freely):

- Screen size: `GAZE_COORDS 0 0 1919 1079` is the inclusive last pixel, so the resolution is 1920x1080 (right + 1,
  bottom + 1). A missing or malformed header message leaves the header-derived fields unset and reported as missing;
  the user supplies them. `ScreenDistance` and `ScreenSize` are always user input; they are never invented.
- Sidecar fields the converter must fill or report (BEP20): `PhysioType`, `SamplingFrequency`, `StartTime`, `Columns`,
  `RecordedEye`, `SampleCoordinateSystem`, `Units`. Each CLI flag mirrors a field the file cannot supply.
- Existing outputs: refuse unless `--overwrite`. A `sourcedata/` file with the same name: skip if identical bytes,
  refuse if different. No matched marker: error, nothing written. Some trials unmatched: warning, files written.
- Binocular exports (`LEFT_*`/`RIGHT_*`): error naming the columns, no guessing; out of scope for version one.
- `sourcedata/` layout: `sourcedata/eyetracking/sub-<l>[/ses-<l>]/<original file name>`, written through the same
  DataLad path as the other converters. `.edf` is a binary and may be annexed; the TSV never is (text-file policy).
- Spec support is unverified: `docs/specs/entities.md` says eye tracking is BIDS physio, but no test in the repo
  validates `recording-eye1_physio` in `func/`. The first task of the plan is a failing test with a hand-made file
  against the PRISM validator and the BIDS validator. If either refuses it, a prism-specification change comes first.
- `timestamp` and `StartTime`: the first task also reads the BEP20 text for the exact definition of `StartTime` and
  whether gaps may stay implicit (raw timestamps kept) or must be filled with `n/a` rows. Default until then: keep the
  tracker's raw timestamps, no synthetic rows, one file. This replaces the earlier "n/a rows" idea, which would add rows
  the tracker never recorded.

Waiting for lab data (the user's): the alignment rule, see open item 2 and below.

- Which `events.tsv` column holds the marker names (`trial_type`?), whether the names equal the tracker messages
  exactly (`fixation_onset` in both, `cue_exo_right` vs `cue_exo`), whether matching is by name plus order within the
  run, and the unit (BIDS: seconds; tracker: ms).
- The drift threshold that turns the offset spread into a warning (a number to set from real data).

## Marker column (user, 2026-10-31)

No `events.tsv` is at hand yet; the user expects the marker names in `trial_type` and wants a pull-down in the GUI.

- `--marker-column`, default `trial_type`, is a flag of `convert eyetracking`. The pull-down only sets that flag.
- The candidate columns come from one function in `src/` that reads the header of the task's `events.tsv`, exposed as a
  CLI mode (name for the plan, e.g. `--list-columns`). The page calls it; the JavaScript reads no file and holds no
  default.
- Missing column, names that do not match, no matched marker: backend messages in the preview.
- The parity test runs the pull-down path and the flag path on identical project copies and compares the files.
- Still unverified: that the lab's column is `trial_type`; settled by the first real events file.

## Where things stand (2026-10-31)

- Done: the `eyetracking` modality is dropped (main, spec v1.2.3); `requirements-eyetrack.txt` is the opt-in eye2bids
  install; the old plan branch is deleted; this design exists and passed the builder check. No converter code yet.
- Spike result: eye2bids is not on PyPI, has no release tags, needs SR Research's `edf2asc` for `.edf`, returns exit
  code 0 when `edf2asc` is missing (the Studio command must check for it itself), and takes only EyeLink `.edf`.
  No open EDF reader exists (pyedfread, eyelinkio, MNE-BIDS all need the same SR Research library).
- Sample: `.claude/sampleReport_s17_nr_1.tsv` (39 MB, untracked, possibly identifiable; never commit). Data Viewer
  sample report, 1000 Hz, monocular right eye, 106 trials of a cue-target task.
- Next, when the lab sends more data: the `.edf` and its export, the paradigm's `events.tsv`, a binocular example.
  Then write the plan (writing-plans). First task: a failing validator test for `recording-eye1_physio` in `func/`,
  and reading the BEP20 text for `StartTime` and gaps.
