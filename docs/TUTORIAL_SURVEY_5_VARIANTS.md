# Chapter 5: Multiple Versions (Variants)

**Time:** ~25 minutes | **Outcome:** one template that serves both the Full
and Short Recovery Check-In forms, without maintaining two separate files.

```{mermaid}
flowchart LR
    W["📄 survey-recovery.json"]
    W --> F["🗂️ Variants: full<br/>ItemCount 10"]
    W --> S["🗂️ Variants: short<br/>ItemCount 5"]
    W --> O["🎚️ Variants override row<br/>rec_pain → ScaleType: vas"]
    F --> V["🔀 Survey Variant selector"]
    S --> V
    O --> P["👁️ Preview: rec_pain renders as a slider"]
    V --> P
```

## Why one template, not two files

The Short Recovery Check-In isn't a different instrument that happens to
share a name with the Full one — it's a genuine subset: five of the Full
form's ten items (`rec_mood`, `rec_sore`, `rec_pain`, `rec_fatigue`,
`rec_sleep`), asked with the exact same wording and scales, on same-day
follow-up. Maintaining that as a second, independent template would mean
every future wording tweak or scale change gets made twice, forever, with no
mechanism to notice when the two copies drift apart. A **variant** is PRISM's
answer to that: the same item set, with a declared subset of items per
version and, where needed, a per-item scale override — one file, one source
of truth.

## Add the Variants sheet

Reopen `recovery_survey_template.xlsx`. The `Variants` sheet has two row
shapes: a **definition row** declares a version (`ItemID` left blank); an
**override row** changes one item's scale for one version (`ItemID` filled
in, matched to a `VariantID`).

Add two definition rows:

| Group | VariantID | ItemCount | ScaleType | Description_en |
|---|---|---|---|---|
| recovery | full | 10 | likert | Full evening check-in |
| recovery | short | 5 | | Same-day quick follow-up |

`ScaleType` here describes the *predominant* scale across the variant's
items, not a hard rule — the Full form is mixed (nine Likert items plus one
VAS item), so `likert` just names the majority; each item still keeps its
own `DataType`/`MinValue`/`MaxValue` regardless of what its variant's
`ScaleType` says.

Then tag every `Items` row's `ApplicableVersions` column: the five shared
items get `full;short`, the other five (`rec_motiv`, `rec_stress`,
`rec_appetite`, `rec_hydration`, `rec_satisf`) get `full` only.

### The override row `rec_pain` needs

Chapter 4 left a promise open: `rec_pain` has no `Levels` map, only
`MinValue: 0`/`MaxValue: 100` — the schema-level tell for a VAS item — but
its Preview still rendered as a plain numeric field, not an actual slider.
That's because nothing in the template yet says `ScaleType: vas` anywhere;
`MinValue`/`MaxValue` alone describe the numeric range, not the widget.

Add a third `Variants` row — an override row, the sheet's second row shape:

| Group | VariantID | ItemID | ScaleType | DataType | AllowedValues | MinValue | MaxValue | Unit |
|---|---|---|---|---|---|---|---|---|
| recovery | full | rec_pain | vas | integer | `0;100` | 0 | 100 | points |

This mirrors the shipped `official/create_new_survey/survey_import_template.xlsx`'s
own example override row (`Group: test, VariantID: 10-vas, ItemID: test001,
ScaleType: vas, ...`) — the same row shape, applied to this study's own pain
item.

This isn't cosmetic. In `app/static/js/template-editor.js`,
`detectQuestionType()` checks a fixed sequence of signals in order, and case
3 — checked before the fallback that looks at a `Levels` map — is exactly
this:

```js
// 3. VariantScale ScaleType
const activeVariantId = getActiveVariantId(template);
const scale = getVariantScaleForItem(item, activeVariantId);
if (scale?.ScaleType === 'vas' || scale?.ScaleType === 'visual-analogue') return 'slider';
```

An item's `VariantScales` entry with `ScaleType: vas` for the active variant
is the *only* thing that makes this function return `'slider'`. Without this
override row, `rec_pain` keeps falling through to the numeric-field default
no matter how the `MinValue`/`MaxValue` are set — the override row is the
mechanism, not a formality.

## Re-import and confirm both versions

Re-import the updated workbook (**Import Template Source**), or, if you
still have `survey-recovery.json` open from Chapter 3, apply the same three
rows via **"Bulk Edit Items"** instead — whichever you already have in
front of you. Then:

1. Click **Validate**.
2. Click **Save to Project**.
3. Check the **Survey Variant:** selector (`#activeVariantSelect`), which now
   appears above the item list showing both `full` and `short`. Switching it
   filters the item list to that version's `ApplicableVersions`.
4. Open the **Preview** tab with `full` active. `rec_pain` now renders as a
   slider, not a plain numeric input — the payoff from the override row
   above.

## A note on repeated administrations

Variants solve "the same instrument, asked in different-length forms." A
related but separate need is "the same form, asked more than once" — a
pre/post design, for example. That's what the **Run** number in Survey
Export (next chapter) and the item-level `SessionHint`/`RunHint` fields are
for: Converter output for a repeated administration writes separate
`run-01`/`run-02` files rather than overwriting the first pass. This
tutorial doesn't walk through a repeated-administration example hands-on;
see `docs/specs/survey.md` and `docs/LIMESURVEY_INTEGRATION.md` for the full
mechanics.

```{note}
For a more complex, already-finished multi-version example than this
tutorial builds by hand, see `examples/wellbeing_multi_demo` in the
repository.
```

## What you just did

You added `full` and `short` definition rows to the `Variants` sheet, tagged
every item's `ApplicableVersions` so the ten-item Full form and its five-item
subset are one template instead of two files, and gave `rec_pain` an
explicit `ScaleType: vas` override for the `full` variant — closing the loop
from Chapter 4 and turning its Preview into an actual slider control.

## What's next

- [Chapter 6: LimeSurvey Export](TUTORIAL_SURVEY_6_LIMESURVEY_EXPORT.md) —
  export this two-version, bilingual template to LimeSurvey, picking which
  version to include
- [Excel Survey Template — Multiple Versions](EXCEL_TEMPLATE_ADVANCED.md) —
  the full `Variants` sheet reference this chapter only used a slice of
