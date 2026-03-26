# Multi-Survey Variant Demo: Wellbeing Survey

This guide walks through three realistic scenarios for importing survey data when the same questionnaire exists in **multiple versions** (variants). The example dataset uses a fictional Wellbeing Survey (`wellbeing-multi`) with three registered variants:

| Variant ID | Items | Scale | Response Range |
|---|---|---|---|
| `10-likert` | 10 (WB01–WB10) | 5-point Likert | 1 = Strongly disagree → 5 = Strongly agree |
| `7-likert` | 7 (WB01–WB07) | 5-point Likert | 1 = Strongly disagree → 5 = Strongly agree |
| `10-vas` | 10 (WB01–WB10) | Visual Analogue Scale | 0 = Not at all → 100 = Completely |

The template `survey-wellbeing-multi.json` (in `code/library/survey/`) describes all three variants in one file. PRISM uses the **Survey Version Plan** in `project.json` to know which variant applies where, so it can validate items and response ranges correctly for every session and run.

---

## Prerequisites

- PRISM Studio is running (`./prism-studio.py` or the GUI launcher)
- This example project (`wellbeing_multi_demo/`) is open in the Projects view
- The template `code/library/survey/survey-wellbeing-multi.json` is present (it is included in this folder)
- Raw data files are in `code/rawdata/` (also included — see below)

---

## Raw Data Files

All raw data files live in `code/rawdata/`. They represent the export you would receive from a survey platform (LimeSurvey, Qualtrics, custom export, etc.) before import into PRISM.

| File | Scenario | Contents |
|---|---|---|
| `scenario1_single_version.tsv` | 1 | 8 participants, 1 session, 10-likert |
| `scenario2_session_versions.tsv` | 2 | 5 participants, 2 sessions, 10-likert + 7-likert |
| `scenario3_run01_10likert.tsv` | 3 | 6 participants, run-01 in ses-01, 10-likert |
| `scenario3_run02_10vas.tsv` | 3 | 6 participants, run-02 in ses-01, 10-vas |

---

## Where Is the Version Selection?

> **Before you import**, PRISM needs to know which variant to enforce.

The version selection lives in **two places** that work together:

### 1. Survey Plan (`project.json`)

The `survey_version_mapping` key in `project.json` tells PRISM which variant to use for validation. Without this, PRISM cannot know whether a file with 7 columns should be the 7-item short form or a truncated export of the 10-item form.

```json
{
  "survey_version_mapping": {
    "wellbeing-multi": {
      "default_version": "10-likert"
    }
  }
}
```

### 2. Survey Plan Editor (PRISM Studio Web UI)

You can edit the Survey Plan without touching `project.json` directly:

**Projects → [your project] → Survey Plan**

The panel shows:
- All auto-discovered multi-variant surveys in the project's library
- A dropdown to pick `default_version`
- Toggle controls to add **session-level** or **run-level** overrides
- A table to map each session or run to a specific variant

> **Tip:** If you open this project for the first time, click **"Refresh detected surveys"** in the Survey Plan panel. PRISM will scan `code/library/survey/` and pre-fill `default_version` from the template's declared default (`Study.Version`).

---

## Scenario 1 — Single Version (Whole Study)

**Study design:**
All participants completed the **10-item Likert** form in one session. You exported one TSV from your survey platform.

**Raw data file:** `code/rawdata/scenario1_single_version.tsv`

```
participant_id  WB01  WB02  WB03  WB04  WB05  WB06  WB07  WB08  WB09  WB10
P01             4     3     5     4     3     4     5     4     3     4
P02             3     4     4     3     4     3     4     3     4     3
...
```

### Step 1: Configure the Survey Plan

Open **Projects → wellbeing_multi_demo → Survey Plan**.

- Find the row for `wellbeing-multi`
- Set **Default Version** → `10-likert`
- No session or run overrides needed
- Click **Save**

This writes the following to `project.json`:

```json
{
  "survey_version_mapping": {
    "wellbeing-multi": {
      "default_version": "10-likert"
    }
  }
}
```

### Step 2: Import the Raw Data

Open **Converter → Survey Data Conversion**.

1. **Survey File**: upload `scenario1_single_version.tsv`
2. **Participant ID Column**: select `participant_id` (or leave on Auto-detect)
3. **Session ID**: type `1` → PRISM will create `ses-01`
4. Click **Preview (Dry-Run)** to verify the mapping, then **Convert**

PRISM will:
- Match columns WB01–WB10 against the `10-likert` variant of `survey-wellbeing-multi.json`
- Create `sub-P01/ses-01/survey/sub-P01_ses-01_task-wellbeing-multi_survey.tsv` for each participant

### Step 3: Validate

Open **Validator** and run validation on the project.
- PRISM resolves version `10-likert` (the `default_version`) for every file
- All 10 items (WB01–WB10) are validated with range 1–5

---

## Scenario 2 — Two Versions Across Sessions

**Study design:**
Participants completed the **10-item Likert** form at baseline (`ses-01`) and the **7-item Likert** short form at follow-up (`ses-02`) to reduce respondent burden in later sessions.

**Raw data file:** `code/rawdata/scenario2_session_versions.tsv`

```
participant_id  session  WB01  WB02  WB03  WB04  WB05  WB06  WB07  WB08  WB09  WB10
P01             1        4     3     5     4     3     4     5     4     3     4
P01             2        3     4     4     3     4     3     4     n/a   n/a   n/a
P02             1        3     4     4     3     4     3     4     3     4     3
P02             2        4     3     3     4     3     4     3     n/a   n/a   n/a
...
```

Session 2 rows have `n/a` for WB08–WB10 because the 7-item form does not include these items.

### Step 1: Configure the Survey Plan

Open **Projects → wellbeing_multi_demo → Survey Plan**.

- Set **Default Version** → `10-likert`
- Enable **Session Overrides**
- Add a row: `ses-02` → `7-likert`
- Click **Save**

This writes the following to `project.json`:

```json
{
  "survey_version_mapping": {
    "wellbeing-multi": {
      "default_version": "10-likert",
      "by_session": {
        "ses-02": "7-likert"
      }
    }
  }
}
```

### Step 2: Import the Raw Data

Open **Converter → Survey Data Conversion**.

1. **Survey File**: upload `scenario2_session_versions.tsv`
2. **Participant ID Column**: select `participant_id`
3. **Session ID**: expand **Advanced options**, look for the **Session Column** field, select `session`  
   *(PRISM reads the `session` column from the file and maps `1 → ses-01`, `2 → ses-02`)*
4. Click **Preview (Dry-Run)**, then **Convert**

PRISM will:
- Split the file by session
- Create `ses-01/` files (10 items) and `ses-02/` files (7 items) for each participant

> **Note:** If your raw file has textual session labels (e.g. `baseline`, `followup`) rather than numbers, use an **ID Mapping File** (Advanced options) or set the session column value to match PRISM session IDs directly.

### Step 3: Validate

Run validation. PRISM resolves:
- `ses-01` files → version `10-likert` → enforces WB01–WB10, range 1–5
- `ses-02` files → version `7-likert` (from `by_session["ses-02"]`) → enforces WB01–WB07, range 1–5

Missing WB08–WB10 in session-2 files is expected and not flagged.

---

## Scenario 3 — Two Versions Within the Same Session (Run-Level)

**Study design:**
In a single session (`ses-01`), participants completed **two runs** of the wellbeing survey: first the **10-item Likert** form (`run-01`) and then the **10-item VAS** form (`run-02`, with a 0–100 slider scale) to compare response formats head-to-head.

Because the two runs use completely different response scales (1–5 vs 0–100), they are exported as **two separate raw files** from the survey platform.

**Raw data files:**

`code/rawdata/scenario3_run01_10likert.tsv` — 10-item Likert, 1–5 scale:

```
participant_id  WB01  WB02  WB03  WB04  WB05  WB06  WB07  WB08  WB09  WB10
P01             4     3     5     4     3     4     5     4     3     4
P02             3     4     4     3     4     3     4     3     4     3
...
```

`code/rawdata/scenario3_run02_10vas.tsv` — 10-item VAS, 0–100 scale:

```
participant_id  WB01  WB02  WB03  WB04  WB05  WB06  WB07  WB08  WB09  WB10
P01             75    60    85    70    55    65    75    70    60    80
P02             55    65    68    52    70    45    60    50    65    55
...
```

### Step 1: Configure the Survey Plan

Open **Projects → wellbeing_multi_demo → Survey Plan**.

- Set **Default Version** → `10-likert`
- Enable **Run Overrides**
- Add a row: `run-02` → `10-vas`
- Click **Save**

This writes the following to `project.json`:

```json
{
  "survey_version_mapping": {
    "wellbeing-multi": {
      "default_version": "10-likert",
      "by_run": {
        "run-02": "10-vas"
      }
    }
  }
}
```

### Step 2: Import Run 01

Open **Converter → Survey Data Conversion**.

1. **Survey File**: upload `scenario3_run01_10likert.tsv`
2. **Participant ID Column**: select `participant_id`
3. **Session ID**: type `1` → creates `ses-01`
4. Open **Advanced options** → **Run ID**: type `1` → creates `run-01`
5. Click **Preview**, then **Convert**

### Step 3: Import Run 02

Repeat with the second file:

1. **Survey File**: upload `scenario3_run02_10vas.tsv`
2. **Participant ID Column**: select `participant_id`
3. **Session ID**: `1` → `ses-01`
4. Advanced options → **Run ID**: `2` → `run-02`
5. Click **Convert**

PRISM creates:
- `sub-P01/ses-01/survey/sub-P01_ses-01_run-01_task-wellbeing-multi_survey.tsv`
- `sub-P01/ses-01/survey/sub-P01_ses-01_run-02_task-wellbeing-multi_survey.tsv`

### Step 4: Validate

Run validation. PRISM resolves:
- `run-01` files → version `10-likert` (default) → enforces WB01–WB10, range 1–5
- `run-02` files → version `10-vas` (from `by_run["run-02"]`) → enforces WB01–WB10, range 0–100

A VAS value of `75` in `run-01` would trigger a range error. A Likert value of `4` in `run-02` would also trigger a range error. The version mapping ensures each run is validated with the correct scale.

---

## Version Resolution Priority

When PRISM resolves the active version for a given file, it checks these keys in `survey_version_mapping` in order (highest priority first):

| Priority | Key | Example |
|---|---|---|
| 1 (highest) | `by_session_run[session][run]` | `ses-02 + run-02 → "7-likert"` |
| 2 | `by_session[session]` | `ses-02 → "7-likert"` |
| 3 | `by_run[run]` | `run-02 → "10-vas"` |
| 4 (fallback) | `default_version` | `"10-likert"` |

This means you can combine session and run overrides. For example, in a 2×2 design:

```json
{
  "survey_version_mapping": {
    "wellbeing-multi": {
      "default_version": "10-likert",
      "by_session": {
        "ses-02": "7-likert"
      },
      "by_run": {
        "run-02": "10-vas"
      },
      "by_session_run": {
        "ses-02": {
          "run-02": "7-likert"
        }
      }
    }
  }
}
```

Here, `ses-02/run-02` uses `7-likert` (the most specific override wins), while `ses-01/run-02` uses `10-vas` (run override only), and `ses-02/run-01` uses `7-likert` (session override only).

---

## Project Structure After Import

After running all three scenarios against this demo project, the resulting structure would look like:

```
wellbeing_multi_demo/
├── project.json                          ← survey_version_mapping here
├── code/
│   ├── rawdata/
│   │   ├── scenario1_single_version.tsv
│   │   ├── scenario2_session_versions.tsv
│   │   ├── scenario3_run01_10likert.tsv
│   │   └── scenario3_run02_10vas.tsv
│   └── library/survey/
│       └── survey-wellbeing-multi.json   ← multi-variant template
├── sub-P01/
│   └── ses-01/
│       └── survey/
│           ├── sub-P01_ses-01_task-wellbeing-multi_survey.tsv          ← Scenario 1
│           ├── sub-P01_ses-01_run-01_task-wellbeing-multi_survey.tsv   ← Scenario 3
│           └── sub-P01_ses-01_run-02_task-wellbeing-multi_survey.tsv   ← Scenario 3
└── ...
```

---

## Troubleshooting

**"No version resolved for ses-02 / run-01"**  
→ `survey_version_mapping` has no entry for this combination and no `default_version`. Open the Survey Plan and set a default.

**"Survey version '10-likert' not found in VariantDefinitions"**  
→ The configured version ID does not match any `VariantID` in the template. Check the spelling in `project.json` against `Study.Versions` in the JSON template.

**"Item WB08 is not applicable in version '7-likert'"**  
→ The file contains items outside the declared item set for the resolved variant. This is a warning if the value is `n/a`, an error if it contains a real response.

**VAS values (e.g. 75) flagged in a Likert session**  
→ The wrong version is resolved for that file. Check that `by_run` or `by_session` is set correctly in the Survey Plan.

**Survey Plan shows no surveys**  
→ The template `survey-wellbeing-multi.json` may not be in `code/library/survey/`. Click **"Refresh detected surveys"** after placing the file there.

---

## See Also

- [Survey Version Plan](../../docs/SURVEY_VERSION_PLAN.md) — full reference for `survey_version_mapping`
- [Schema Versioning](../../docs/SCHEMA_VERSIONING.md) — how multi-variant templates are structured
- [Survey Library](../../docs/SURVEY_LIBRARY.md) — managing templates in the library
- [Converter](../../docs/CONVERTER.md) — all converter options including run and session columns
