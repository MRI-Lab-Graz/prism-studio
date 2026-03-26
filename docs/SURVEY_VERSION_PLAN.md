# Survey Version Planning by Session and Run

PRISM supports questionnaires that come in multiple variants — for example a 10-item long form and a 7-item short form of the same wellbeing measure. When a longitudinal study uses different variants at different sessions or runs, PRISM needs to know which variant applies where so it can validate data correctly.

This page explains how to configure that mapping in `project.json` and how PRISM resolves it during validation.

---

## Why This Exists

Many validated questionnaires have multiple official versions:

- Long form vs. short form (different item sets)
- Likert scale vs. visual analogue scale (same items, different response format)
- Adapted versions with different language or population targets

A single study might administer the 10-item wellbeing survey in session 1 and switch to the 7-item short form from session 2 onwards to reduce participant burden. Without explicit configuration, PRISM cannot know which variant's item set and response constraints to enforce for which session.

The **Survey Version Plan** in `project.json` closes this gap.

---

## Survey Library: Multi-Variant Templates

The survey library in `official/library/survey/` supports multi-variant schemas. A template like `survey-wellbeing-multi.json` declares all available variants inside `Study.VariantDefinitions`:

```json
{
  "Study": {
    "TaskName": "wellbeing-multi",
    "Versions": ["10-likert", "7-likert", "10-vas"],
    "VariantDefinitions": [
      {
        "VariantID": "10-likert",
        "ItemCount": 10,
        "ScaleType": "likert",
        "Description": { "en": "10-item form with a 5-point Likert response scale" }
      },
      {
        "VariantID": "7-likert",
        "ItemCount": 7,
        "ScaleType": "likert",
        "Description": { "en": "7-item short form with a 5-point Likert response scale" }
      },
      {
        "VariantID": "10-vas",
        "ItemCount": 10,
        "ScaleType": "vas",
        "Description": { "en": "10-item form with a 0-100 visual analogue scale" }
      }
    ]
  }
}
```

Each item carries `ApplicableVersions` to declare in which variants it appears, and `VariantScales` to declare per-variant response constraints.

→ See [Schema Versioning](SCHEMA_VERSIONING.md) for details on the multi-variant schema format.

---

## Configuration in `project.json`

Add a `survey_version_mapping` key to `project.json` with one entry per questionnaire used in the study.

### Minimal Example (Single Version for All Timepoints)

```json
{
  "survey_version_mapping": {
    "wellbeing-multi": {
      "default_version": "10-likert"
    }
  }
}
```

Every session and run uses `10-likert` unless an override is specified.

### Session-Level Overrides

```json
{
  "survey_version_mapping": {
    "wellbeing-multi": {
      "default_version": "10-likert",
      "by_session": {
        "ses-01": "10-likert",
        "ses-02": "7-likert",
        "ses-03": "7-likert"
      }
    }
  }
}
```

### Run-Level Overrides

```json
{
  "survey_version_mapping": {
    "wellbeing-multi": {
      "default_version": "10-likert",
      "by_run": {
        "run-01": "10-likert",
        "run-02": "10-vas"
      }
    }
  }
}
```

### Combined Session + Run Overrides

Use `by_session_run` when a specific session/run combination needs its own variant:

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
    },
    "phq9": {
      "default_version": "standard"
    }
  }
}
```

### Multiple Questionnaires

The top-level keys of `survey_version_mapping` are the task names (matching `Study.TaskName` in the library template). Each questionnaire is configured independently:

```json
{
  "survey_version_mapping": {
    "wellbeing-multi": {
      "default_version": "10-likert",
      "by_session": {
        "ses-02": "7-likert"
      }
    },
    "phq9": {
      "default_version": "standard",
      "by_session": {}
    },
    "stress-short": {
      "default_version": "4-item"
    }
  }
}
```

---

## Resolution Priority

When validating a file, PRISM resolves the active version with this priority (highest first):

| Priority | Key | Example |
|----------|-----|---------|
| 1 (highest) | `by_session_run[session][run]` | `ses-02 + run-02 → "7-likert"` |
| 2 | `by_session[session]` | `ses-02 → "7-likert"` |
| 3 | `by_run[run]` | `run-02 → "10-vas"` |
| 4 (fallback) | `default_version` | `"10-likert"` |
| Error | *(none configured)* | Validation error |

If no mapping exists at any level and no `default_version` is set, validation emits an error and stops processing that file.

---

## Auto-Discovery and Migration

When you open an existing project that has no `survey_version_mapping`, PRISM automatically:

1. Scans survey templates stored locally in `official/library/survey/` and any project-local copies.
2. Extracts the `TaskName` and available `Versions` from each template.
3. Pre-fills `survey_version_mapping` with a `default_version` taken from `Study.Version` (the declared default in the template schema).
4. Writes the enriched `project.json` back to disk.
5. Emits an info message identifying which surveys were auto-added.

This migration is **non-destructive**: existing configured entries are never overwritten.

If a survey template has only one version (single-variant), it is still added to the mapping with `default_version` equal to that single value. This keeps the structure consistent and makes future additions easier.

---

## Web Interface: Survey Plan Editor

The Survey Plan is editable in PRISM Studio without touching `project.json` directly.

### Where to Find It

**Projects → Survey Plan** section, or via the **Survey Plan** quick link in the project overview card.

### What You Can Do

- See all auto-discovered questionnaires and their configured versions.
- Change `default_version` via a dropdown showing all available variants from the library schema.
- Enable session or run overrides per questionnaire.
- Add rows to `by_session`, `by_run`, or `by_session_run` tables.
- Remove override rows that are no longer needed.
- Click **Refresh detected surveys** to re-scan after new templates are copied into the project.

### When the Mapping Is Empty

For new projects, the Survey Plan panel shows each auto-discovered survey with its default version pre-selected. No action is required if session/run overrides are not needed. You can start validation immediately.

### Saving

Changes are saved to `project.json` immediately on confirmation. No separate "save" step is needed.

---

## Validation Behavior

PRISM uses the resolved version to:

- Check that data columns match the `ApplicableVersions` item set for the resolved variant.
- Apply the correct `MinValue`, `MaxValue`, and `Levels` constraints from `VariantScales` for that variant.
- Warn if items from a different variant appear in the data file (cross-variant contamination).
- Error if the resolved version string does not match any entry in `VariantDefinitions`.

### Validation Messages

| Severity | Message | Cause |
|----------|---------|-------|
| Error | `Survey version 'X' not found in VariantDefinitions` | Configured version ID does not exist in the template |
| Error | `No version resolved for ses-02 / run-01` | No mapping at any level and no `default_version` |
| Warning | `Item WB08 is not applicable in version '7-likert'` | Data contains an item not in the resolved variant |
| Warning | `survey_version_mapping auto-initialized; please review` | Mapping was missing and was auto-created from defaults |
| Info | `Using version '10-likert' (default) for ses-01/run-01` | Default applied because no override matched |

---

## Backward Compatibility

Projects created before Survey Version Plan was introduced have no `survey_version_mapping` key. PRISM handles this transparently:

- If `survey_version_mapping` is absent, PRISM auto-discovers surveys and pre-fills it on first open or first validation run.
- If a template defines only one version, that version is used without any user action.
- The legacy `version` key inside `Study` (if present in project-specific copies) is accepted and treated as `default_version` during normalization.
- Old projects continue to validate as before; the new feature adds capability without removing existing behavior.

---

## Example: Longitudinal Wellbeing Study

**Study design**: 3 sessions, switching from long to short wellbeing form.

```
ses-01: 10-item Likert (baseline, full measure)
ses-02: 7-item Likert (follow-up, reduced burden)
ses-03: 7-item Likert (follow-up, reduced burden)
```

**`project.json`**:

```json
{
  "survey_version_mapping": {
    "wellbeing-multi": {
      "default_version": "10-likert",
      "by_session": {
        "ses-02": "7-likert",
        "ses-03": "7-likert"
      }
    }
  }
}
```

**Validation result** for `sub-001/ses-02/survey/sub-001_ses-02_task-wellbeing-multi_survey.tsv`:
- Resolved version: `7-likert` (from `by_session["ses-02"]`)
- Item set validated: WB01–WB07 (7 items)
- WB08–WB10 absence: not flagged (expected for 7-item form)
- Response range: 1–5 Likert enforced

---

## See Also

- [Survey Library & Workflow](SURVEY_LIBRARY.md)
- [Schema Versioning](SCHEMA_VERSIONING.md)
- [Validator](VALIDATOR.md)
- [Projects](PROJECTS.md)
