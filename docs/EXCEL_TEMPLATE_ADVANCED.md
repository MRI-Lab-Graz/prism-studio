# Excel Survey Template — Multiple Versions

Extends [Excel Survey Template — Basics](EXCEL_TEMPLATE_BASICS.md) to instruments with
more than one variant — a long form and a short form, different scale wordings per
version, or any other case where the same instrument needs more than one declared
"shape". Complete the basics tutorial first if you haven't; this page assumes you
already know the `Items`/`General` sheets and the Template Editor import flow.

**Time:** ~20 minutes. **Outcome:** one validated, project-saved survey template with
two variants (a 10-item long form and a 5-item short form) and one item that's worded
differently in the short form.

## When you need the `Variants` sheet

Only when either is true:

- Your instrument has multiple official versions/forms (long/short, different
  administration modes) that should share one `TaskName` but be selectable separately.
- One or more items need a different scale, wording, or numeric range in a specific
  variant, without duplicating the whole item.

If neither applies, skip `Variants` entirely — see the basics tutorial.

## 1. Get the workbook

Follow along with
[examples/excel_template/advanced/survey_import_advanced_example.xlsx](../examples/excel_template/advanced/survey_import_advanced_example.xlsx)
— a 10-item "Brief Wellbeing Check" with a 5-item short form.

Like the basics workbook, headers are locked and `DataType`/`Units` are dropdowns.
This workbook adds one more: `Items.ApplicableVersions` and `General.Version` are also
dropdowns, sourced live from whatever `VariantID`s you've defined in the `Variants`
sheet — so once you've named your variants there, picking one elsewhere is a click,
not free typing. Like the other dropdowns, this is a convenience, not a hard gate: it
only offers one `VariantID` at a time, so for an item that belongs to *multiple*
variants (step 2 below) you still type the semicolon-separated list by hand.

## 2. `Items`: tag every row with `ApplicableVersions`

The workbook declares 10 items (`wellcheck01`–`wellcheck10`). Five are shared between
both forms; five appear only in the long form:

| ItemID | `ApplicableVersions` |
|---|---|
| `wellcheck01`–`wellcheck05` | `10-item;5-item` |
| `wellcheck06`–`wellcheck10` | `10-item` |

> [!IMPORTANT]
> The Help sheet says a blank `ApplicableVersions` means "applies to all variants" —
> that's true for what actually gets *imported*, but the validator's
> `VariantDefinitions.ItemCount` consistency check only counts items that **explicitly**
> list a given variant ID. Leaving shared items blank produces a passing import but a
> `ItemCount=10 but 5 item(s) have this version in ApplicableVersions`-style validation
> warning. Tag every item explicitly with every variant it belongs to (as in the table
> above) and the counts line up cleanly.

## 3. `General`: declare the variants

Two extra fields beyond the basics tutorial:

| Field | Value | Meaning |
|---|---|---|
| `Version` | `10-item` | The active/default variant when the template is used without picking one explicitly. |
| `Versions` | `10-item;5-item` | Every variant ID this instrument supports. |

## 4. `Variants`: definitions and one override

The `Variants` sheet supports two distinct row shapes — same sheet, `ItemID` present
or absent is what tells them apart:

**Row type A — variant definitions** (leave `ItemID` empty):

| Group | VariantID | ItemCount | ScaleType | Description_en |
|---|---|---|---|---|
| wellcheck | 10-item | 10 | likert | Full 10-item form |
| wellcheck | 5-item | 5 | likert | Short 5-item form |

**Row type B — item-level override** (set both `ItemID` and `VariantID`): the example
reworks `wellcheck01`'s response scale for the short form only — a simpler 3-point
scale instead of the full 5-point one, since the short form uses lighter-weight
wording elsewhere too:

| Group | VariantID | ItemID | DataType | AllowedValues | MinValue | MaxValue | Scale_en |
|---|---|---|---|---|---|---|---|
| wellcheck | 5-item | wellcheck01 | integer | `0;1;2` | 0 | 2 | `0=rarely;1=sometimes;2=often` |

This only changes `wellcheck01`'s scale *when the 5-item variant is selected*; the
10-item variant keeps the original 5-point scale. The override does **not** remove the
item from the other variant — that's controlled by `ApplicableVersions` (step 2), not
by whether an override row exists.

## 5. Import, validate, save

Same Template Editor flow as the basics tutorial: **Import Template Source** → pick the
`wellcheck` group if prompted → **Validate** → **Save to Project**. Because this
template declares multiple versions, the Survey Import converter will later show a
**Questionnaire Version Selection** card so you can pick which variant(s) to include
when converting response data (see the Advanced options step in
[Converter — Survey Import](studio/converter_survey.md)).

Resulting `wellcheck01` (trimmed) — note `ApplicableVersions` lists both variants even
though only one has an override, and `VariantScales` carries just the 5-item override:

```json
{
  "wellcheck01": {
    "Description": { "en": "I felt cheerful and in good spirits", "de": "..." },
    "Levels": {
      "0": { "en": "at no time", "de": "..." },
      "4": { "en": "all of the time", "de": "..." }
    },
    "DataType": "integer",
    "MinValue": 0.0,
    "MaxValue": 4.0,
    "AllowedValues": [0, 1, 2, 3, 4],
    "ApplicableVersions": ["10-item", "5-item"],
    "VariantScales": [
      {
        "VariantID": "5-item",
        "Levels": { "0": { "en": "rarely" }, "1": { "en": "sometimes" }, "2": { "en": "often" } },
        "DataType": "integer",
        "MinValue": 0.0,
        "MaxValue": 2.0,
        "AllowedValues": [0, 1, 2]
      }
    ]
  }
}
```

And the `Study` block gains `Versions` plus a `VariantDefinitions` entry per variant:

```json
{
  "Study": {
    "Version": "10-item",
    "Versions": ["10-item", "5-item"],
    "VariantDefinitions": [
      { "VariantID": "10-item", "ItemCount": 10, "ScaleType": "likert",
        "Description": { "en": "Full 10-item form" } },
      { "VariantID": "5-item", "ItemCount": 5, "ScaleType": "likert",
        "Description": { "en": "Short 5-item form" } }
    ]
  }
}
```

Full output for comparison:
[examples/excel_template/advanced/survey-wellcheck.json](../examples/excel_template/advanced/survey-wellcheck.json).

## Common mistakes

- **Relying on blank `ApplicableVersions` for shared items** — passes import, but
  triggers `ItemCount` mismatch warnings on validation (see step 2). Tag explicitly.
- **`VariantDefinitions.ItemCount` not matching tagged items** — recount after any
  edit; the validator checks this and warns if they drift.
- **Typo'd `VariantID`** between `Items.ApplicableVersions`, `General.Versions`, and
  `Variants.VariantID` — these must match exactly (case-sensitive) or the variant
  won't line up, and the validator will flag a `VariantID` not present in
  `Study.Versions`.
- **Putting an override row's `VariantID` in the wrong sheet position** — `Variants`
  row type is inferred from whether `ItemID` is filled in, not from a separate flag;
  an accidental value in `ItemID` turns a definition row into an override row.

## What's next

- [Excel Survey Template — Basics](EXCEL_TEMPLATE_BASICS.md) if you haven't done it yet
- [Schema Versioning](SCHEMA_VERSIONING.md) — how `Study.Versions` drives multi-variant
  behavior elsewhere in PRISM (recipes, exports)
- [Template Editor](studio/template_editor.md) · [Survey Templates](TEMPLATES.md)
- [Converter — Survey Import](studio/converter_survey.md) — using a multi-version
  template to import actual respondent data
