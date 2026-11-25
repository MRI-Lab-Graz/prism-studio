# Design note: IDs for physio, eye tracking, events (roadmap step 0b)

Date: 2026-11-25. **Approach 1 and the term list approved 2026-11-25. No code yet.** Based on specification v1.5.27.

## Summary

| Kind | IDs? | What gets one |
|---|---|---|
| physio | yes, shared terms | each measured signal (a column) |
| eye tracking | yes, as physio terms | gaze position, pupil size |
| events | not now | nothing |
| anat, func, fmap, dwi, eeg, beh | no | BIDS passthrough, PRISM does not describe their columns |

The roadmap expected "same mechanism, no new code". **For physio that is not true**: see the next section.

## What the code does today

- A term is looked up per **top-level** sidecar key (`term_registry.term_columns`). Top-level keys that are blocks of
  the modality's schema are skipped.
- PRISM physio sidecars describe columns **inside `Channels`**, which is such a block. Declaring `terms` for physio
  would therefore check nothing.
- BIDS-shaped physio sidecars (`physio_bids.write_bids_physio`) have `Columns` and describe columns at top level.
- A column with `Units: "n/a"` is skipped, even if it has a `Term`. The batch physio converter writes `"n/a"` for
  every channel.
- Signal names come from three lists that do not agree: the filename `recording-` values (open list, with `puls` and
  `ppg`, `cardiac` and `ecg`), `Recording.Type` (15 values, with synonyms `resp`/`respiratory`, `eda`/`gsr`) and
  `Channels.<name>.Type` (11 upper-case values).

## Approaches

1. **A term per signal, referenced by the column (recommended).** Works like every other term modality: `Term` on the
   column; a matching name or alias only suggests. Costs one small general rule (below).
2. **Derive the ID from `Channels.Type` or `recording-`.** No annotation needed, but `OTHER` and `mixed` give
   nothing, the three lists disagree, and it applies a meaning nobody confirmed.
3. **No physio IDs yet.** No cost; physio stays outside the "every measurement has an ID" goal.

## Design for approach 1

### One general rule (specification and Studio)

A `terms` declaration may name `columnsField`, the sidecar object that holds the column descriptions (physio:
`"Channels"`). It works like `contextField`. Without that object in a sidecar, or without the declaration, columns are
the top-level keys as today. This covers both physio shapes and any later modality; no physio code path.

And: a column that has a `Term` is always checked, whatever its `Units`.

### Physio terms

```json
"physio": {"terms": {"columnsField": "Channels", "nonTermColumns": ["time", "timestamp", "trigger", "marker"]}}
```

| ID | Aliases |
|---|---|
| `prism:ecg` | |
| `prism:cardiac-signal` | `cardiac` (source signal not stated) |
| `prism:ppg` | `puls` |
| `prism:respiration` | `resp`, `respiratory` |
| `prism:eda` | `gsr` |
| `prism:emg` | |
| `prism:body-temperature` | `temp` (`air-temperature` is the environment term) |
| `prism:blood-pressure-signal` | `bp` |
| `prism:oxygen-saturation` | `spo2` |

- One ID per quantity, not per sensor place, channel number or processing level; those are already sidecar fields.
- Variants (`prism:emg.<muscle>`) are added only when real data needs one.
- Triggers and device status are not measurements: no ID.
- Units are not fixed in the term where devices differ (arbitrary units are common in PPG and respiration).

### Eye tracking

It is BIDS physio (`PhysioType: "eyetrack"`), so its terms live under `terms/physio/`: `prism:gaze-position` with
`.x` and `.y` (aliases `x_coordinate`, `y_coordinate`) and `prism:pupil-size` (`pupil_size`). `timestamp` is not a term.
Left and right eye are separate files, so no per-eye IDs.

**Limit:** the validator picks the modality by folder. Eye tracking and task-bound physio live in `beh/`, `func/` or
`eeg/`, so as far as I read the code their sidecars get no term check. Reaching them means deciding the modality by
the `_physio` suffix. Verify before building; I suggest it as a separate step.

## Events: no IDs now

- `onset`, `duration`, `stim_file` are structure, not measurements.
- `trial_type` values mean something only within one task. They would need IDs derived from a task template, as survey
  items have; there are no task templates.
- `response_time` is a real measurement, but one shared ID for it tells a consumer little without the task.

Revisit when someone has a task template to share. This stays consistent with "every template of every modality has
IDs": events have no templates.

## Done when (for the later build step)

- A physio column in either sidecar shape resolves to its term, with the same result from `terms coverage`, the
  validator and the Contribute page.
- A column with `Term` and `Units: "n/a"` is checked.
- No new physio-specific code; the other term modalities behave as before.
- Existing projects get notices only, never new errors.

## Decisions and open points

- **Approved (2026-11-25):** approach 1 and the term list above.
- **My call, not yet confirmed:** converters do not write `Term` for channels they recognise; names only suggest, as
  elsewhere.
- **Open:** is the folder limit for eye tracking acceptable for a first version?
