# The meaning block

The meaning block gives every described variable the same small set of optional facts, so that any reasoning tool can start from the same ground. PRISM describes; it does not reason. It stores no diagnoses and no cutoffs as truth, only named and sourced statements about what a variable is about. Every field is optional, and a file without the block stays valid.

The definition lives once in `schemas/shared/meaning-block.json` and is added to each modality schema by `scripts/meaning_block.py`. The descriptions below are copied from it.

## Where it appears

- **File level**: `IsAbout` on the study or recording description (for example `Study` in a sidecar).
- **Column level**: `IsAbout`, `ValueMappings` and `TermURL` on a described column or variable.
- **Value level**: concept links for single values, only where the column has `Levels`. A column without `Levels` has no value level.

BIDS passthrough data (MRI, EEG and others) does not get the block: BIDS owns those names.

## Fields

| Field | Where | Description |
| --- | --- | --- |
| `IsAbout` | file, column | What this is about: one or more concepts, each with how close the match is and which way a higher value points. |
| `LevelIsAbout` | column with `Levels` | Concept links for single values, keyed by the level code of `Levels`. |
| `ValueMappings` | column | Named, sourced rules that turn a value into a state a reasoner can use. Several may exist and may disagree; none is the truth. |
| `TermURL` | column | A string is a URL of a definition (the BIDS reading). An object maps a vocabulary name to the URL of this same thing in that vocabulary. |

Each entry of an `IsAbout` list (and of each `LevelIsAbout` value) has these fields:

| Field | Required | Description |
| --- | --- | --- |
| `Concept` | yes | A PRISM concept ID (`prism:<slug>`) or the absolute URL of a concept in an external vocabulary. |
| `Match` | no | How closely the concept matches. Default: `exact`. |
| `Higher` | no | Whether a higher value means `more` or `less` of the concept. |
| `Source` | no | Who or what made the link (a person, a paper, a tool). |
| `Checked` | no | Date the link was last checked (YYYY-MM-DD). |
| `Status` | no | `reviewed` or `unreviewed`. Default: `unreviewed`. |

### `Match`

The words follow the SKOS mapping vocabulary:

| `Match` | SKOS |
| --- | --- |
| `exact` | exactMatch |
| `broader` | broadMatch |
| `narrower` | narrowMatch |
| `related` | relatedMatch |

### `Higher`

`Higher` is relative to one concept, so it sits in the link, not on the variable. The same item can be `more` of one concept and `less` of another.

### `Status` and `Checked`

`Status` says whether a person has confirmed the link; `Checked` says when someone looked at it, and `Source` says who or what. A link written by a tool starts as `unreviewed`.

## `ValueMappings`

A mapping turns a value into a state. Each mapping has a `Name`, an optional `Source` and a list of `Rules`; each rule has a `When` (an `Op` such as `>=` and a `Value`) and the `State` it gives. Several mappings may exist for one column, from different sources, and they may disagree. None of them is the truth: a consumer picks one by `Name`.

```json
"ValueMappings": [
  {
    "Name": "example-rule",
    "Source": "made-up example, not a real criterion",
    "Rules": [
      {"When": {"Op": ">=", "Value": 2}, "State": "present"},
      {"When": {"Op": "<", "Value": 2}, "State": "absent"}
    ]
  }
]
```

## `TermURL`

A string is the BIDS reading: the URL of a definition. An object maps a vocabulary name to the URL of this same thing in that vocabulary. The vocabulary name is always written out; it is never guessed from the URL.

## Data states

The intent is that a reasoner sees every value in one of three states: an observed value, not applicable, or missing. Missing is not "no": a missing answer says nothing about whether something is present. An export that reports these states comes in a later step; this page does not describe one yet.
