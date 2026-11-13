# Slimmer survey template: scoring facts live in the recipe

## Why
A survey template describes the instrument as it is administered: wording, languages, versions, items. Scoring
(subscales, reversal) belongs to the recipe. Today three fields blur that line, and two of them can drift from the
data they describe. Decided by the user on 2026-11-13.

## Decisions
- **Remove `Study.Subscales`.** Subscales are recipe `Scores`. The methods text reads them from the recipe.
- **Multiple languages:** a recipe `Scores[]` entry keeps `Name` (ASCII variable name) and gets `Label`, an object
  `{"en": "...", "de": "..."}` with `en` required (same rule as the template: general info English, other languages
  optional). `Description` stays as is unless the builder needs it localized (not in this change).
- **Remove `Study.ItemCount`** (and `VariantDefinitions[].ItemCount`): nothing checks it; it is derivable from the
  items and `ApplicableVersions`. Readers count the items.
- **Remove the item flag `Reversed`.** Reversal is a recipe fact (`Transforms.Invert`). Not a plain deletion: 103 of
  105 official templates carry it while 1 of 104 official recipes has `Transforms.Invert`, so the data is migrated
  into the recipes first.
- Out of scope: `Normative`, `Study.Reliability/Validity`, `Study.Translation` (per-language provenance idea noted).

## Ownership (what is vendored)
`app/schemas/stable/survey.schema.json` and `docs/specs/` are vendored from prism-specification
(`specification.lock.json`, tag v1.5.5): removing the three fields there is a pull request in that repository, then
`python scripts/sync_specification.py --tag <tag>` here. `recipe.survey.schema.json`, the official templates
(`official/library/survey`, not in the lock) and the official recipes (`official/recipe/survey`) are local.

## Order (each step keeps everything working)
1. Studio, no spec change: recipe `Label`, reporting reads the recipe, `ItemCount` derived, `Reversed` migrated into
   recipes and no longer read from templates. The old template fields are still accepted (schema unchanged).
2. prism-specification: remove the fields from the survey schema and docs; tag a release (needs the user's go-ahead:
   other repository, outward-facing).
3. Studio: sync the tag, strip the fields from the official templates (script, checked), delete leftover readers
   and allow-lists, release note.

## Anti-goals
- Never lose a reversal: the migration is idempotent, checked, and runs before any reader stops using the template flag.
- No second implementation: the migration and the draft logic live in `src/`, CLI first, Studio triggers (THE RULE).
- Existing user templates that still carry the fields keep loading (ignored) until the schema drops them.

## Left to the builder
Exact CLI command names; whether the questionnaire renderer's "(R)" marks are dropped (ruling: dropped, a printed
questionnaire for participants must not mark reversed items).
