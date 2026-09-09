# Chapter 4: Languages and Scales

**Time:** ~25 minutes | **Outcome:** a bilingual EN/DE `survey-recovery.json`
template with both a Likert and a VAS scale correctly represented.

```{mermaid}
flowchart LR
    I["📝 rec_pain item"]
    I --> EN["🇬🇧 Description_en<br/>'Pain intensity'"]
    I --> DE["🇩🇪 Description_de<br/>'Schmerzintensität'"]
    I --> S["🎚️ DataType / MinValue / MaxValue<br/>shared across languages"]
```

Language and scale are independent axes of the same item: translating an
item's text doesn't change how it's measured, and changing how it's measured
doesn't require touching its translations. This chapter adds German
alongside the English text Chapter 2 entered, then looks at why `rec_pain`
needed a different kind of scale definition from the other nine items all
along.

## Two ways to add a language

Chapter 2 left `General.I18nLanguages` set to `en` and every `Description_de`/
`Scale_de` cell blank. There are two ways to fill those in — through the
workbook, or without touching the workbook at all.

### Excel path

1. Reopen `recovery_survey_template.xlsx` and fill `Description_de` for all
   10 items, plus `Scale_de` for the 9 Likert items (leave `rec_pain`'s
   `Scale_de` blank, matching its blank `Scale_en` — it has no value=label
   map to translate).
2. On the `General` sheet, change `I18nLanguages` from `en` to `de;en`.
3. Back in the Template Editor, **Import Template Source** the updated
   workbook, as in [Chapter 2](TUTORIAL_SURVEY_2_EXCEL_TEMPLATE.md).

```{note}
Re-importing replaces the template's current state with whatever is in the
workbook — including reverting the `rec_mood` wording tweak and Bulk Edit
change you made directly in the Template Editor back in Chapter 3, since
those changes were never written back into the `.xlsx` file. If you want to
keep them, either make the same wording change in the workbook before
re-importing, or use the in-editor language-bar path below instead of
re-importing for this step.
```

### In-editor path

The language bar sits above the item list once a template is loaded,
showing the languages it currently detects. Click **"Add Language"**
(tooltip "Add a language to all questions") and enter `de`. This adds an
empty `de` slot to every item's
`Description` (and to every Likert item's `Levels` value map) in one action
— all 10 items at once, no workbook involved. The text itself still needs
filling in afterward, one item at a time or through Bulk Edit, but the
language *keys* are now in place everywhere.

```{note}
Either path gets you to the same place: `de` and `en` keys on every item.
Excel is faster for typing out ten rows of translated text at once;
"Add Language" is faster when you're already in the Template Editor and just
need the language slots created before filling them in by hand.
```

## The language-consistency warning

Click **Validate** after adding German. If any item still has an
English-only field somewhere — say you used "Add Language" and then filled
in `Description` for nine items but forgot the tenth — Validate doesn't
reject the template. Instead you'll see something like:

```
Language 'de' is missing from 1 question(s) that have multilingual
descriptions
```

This is a **warning**, not a schema error: the template is structurally
valid either way, but PRISM flags a translation that looks incomplete. In
the Validate response these are two genuinely separate lists — schema
`errors` (missing required fields, wrong types — the kind of thing that
blocks **Save to Project**) and `language_warnings` (content-completeness
checks like this one, internally tagged `i18n_validation`, which don't block
saving). Chapter 7 comes back to this distinction in full; for now, the
takeaway is just that a language warning here means "go fill in that field,"
not "something is broken."

## Likert vs. VAS

The 9 mood/soreness-style items — `rec_mood`, `rec_sore`, `rec_sleep`,
`rec_motiv`, `rec_stress`, `rec_fatigue`, `rec_appetite`, `rec_hydration`,
`rec_satisf` — all carry a value=label map in `Scale_en`/`Scale_de`:
`1=not at all;2=slightly;3=moderately;4=very;5=extremely`. That's a
**Likert** scale — a small, fixed set of ordered choices — and the Template
Editor's Preview renders it accordingly, as radio buttons (a dropdown
instead, once a scale has more than ten options).

`rec_pain` isn't a bigger or smaller Likert scale — it's a different kind of
measurement. It carries no `Scale_en`/`Scale_de` at all, only `MinValue: 0`
and `MaxValue: 100` (the row you filled in back in
[Chapter 2](TUTORIAL_SURVEY_2_EXCEL_TEMPLATE.md)): a continuous **VAS**
(visual analogue scale), where a respondent marks a point along a line
rather than picking from a short list. Having no `Levels` map is the
schema-level tell for "this is a VAS item" — there's nothing to turn into
radio buttons or a dropdown. The next chapter builds directly on this when
it gives `rec_pain` an explicit `ScaleType: vas` Variant Scale, which is what
turns its Preview into an actual slider control instead of a plain numeric
field.

## Reusing a scale with Copy Style

Adding an eleventh Likert item that shares the same 1–5 scale as the
existing nine doesn't mean retyping `MinValue`, `MaxValue`, and `DataType`
by hand. In the item list, set `#newItemMode` to **"Copy style from item"**,
pick `rec_mood` in `#copyStyleSourceItem`, type a demo ID such as
`rec_demo` into the box above the item list, and click **Add**. It starts
with `rec_mood`'s entire scale definition already filled in — `Levels`,
`MinValue`, `MaxValue`, `DataType` — with only `Description` cleared out for
you to write.

```{note}
Copy Style is copy-based reuse, not a live reference. It clones `rec_mood`'s
scale definition once, at creation time; there's no shared "scale library"
object linking the two items afterward, by design. Editing `rec_mood`'s
scale later does not change the new item's copy, and vice versa.
```

`rec_demo` was only for demonstration — type `rec_demo` back into the box
above the item list and click **Delete** to remove it again. The template
should be back to exactly 10 items before moving on.

## What you just did

You added German alongside English across all 10 items — via the Excel
workbook, via the Template Editor's "Add Language" button, or both — saw how
Validate reports incomplete translations as warnings rather than errors, and
looked at why `rec_pain`'s `MinValue`/`MaxValue` scale is a fundamentally
different kind of measurement from the other nine items' `Levels` map, not
just a longer one. You also saw how Copy Style reuses an existing Likert
scale on a new item without hand-typing its scale definition again, then
deleted that demo item, leaving the template at its original 10 items.

## What's next

- [Chapter 5: Variants](TUTORIAL_SURVEY_5_VARIANTS.md) — give `rec_pain` an
  explicit `ScaleType: vas` and build the Full/Short version split
