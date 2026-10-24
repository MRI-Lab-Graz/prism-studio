# Propose page as a drill-down, and proposing a new kind of data — design

Date: 2026-10-24. Changes the built page of `2026-10-23-propose-changes-page-design.md` and replaces phase 4
(layer 1) of `2026-10-23-specification-contributions-design.md`. Layers 2 (additions) and 3 (metrics) and
their local overlay stay as built.

## Intent

A researcher planning a study wants PRISM to know their data *before* the study starts. Today the Propose
page asks first "what is missing?" (a choice in a list, a measurement, or a whole new kind of data, the last
one still "coming soon"). The user's view is the other way round: they start from their data and look for it
in what PRISM supports, and the first place where it is not there decides what they propose.

The maintainer (the specification's owner) reviews and merges every proposal. Users therefore give what they
know; the maintainer decides where it lands and does the schema work.

"All modalities should follow the biosample idea": every PRISM modality is shown the same way (kind of data →
its lists of allowed values → its measurements), and the specification describes each modality as data, so a
new one needs no Python.

## What the user sees

One page (`/specifications/contribute`, reachable as today, no project needed), a chain of **pull-down menus**.
Each pull-down appears only after the one above has a choice, so the user looks at one decision at a time.
Under each pull-down, one line shows what PRISM supports at that level.

1. **What kind of data?** Every modality of the current specification (PRISM ones with a one-line human
   description, BIDS ones marked as passed through to BIDS), then **"Nothing fits: a new kind of data"**.
   Next to the choice: a **"Not sure"** tick. The user picks the closest modality and ticks it; the proposal
   carries the flag and the maintainer decides at merge. No search, no automatic suggestion.
   BIDS modalities cannot be drilled into (choosing one says PRISM passes them to BIDS unchanged).
2. **An accepted example beside the user's proposal** (agreed with a mockup on 2026-10-24). Left: an accepted
   example of the chosen kind of data with every entry filled (an official library template, for biosample
   `official/library/biosample/biosample-inflammation.json`). Right: the same entries for the user's proposal.
   Every entry with a fixed list of allowed values is a **pull-down**: the allowed values, then
   **"Missing: add a value…"** (a text box for the new value) and **"Unknown"**. Free-text entries get a text
   box or "Unknown". **Every** list is offered, none is hidden (licence codes included); the maintainer filters
   at merge. Only "Missing" entries become proposed additions (layer 2); the filled and "Unknown" entries go
   along as context for the maintainer.
3. **Measurements**, in the same right-hand column, for modalities with a term registry (today biosample):
   pull-downs of the official measurements (with ID and unit, for biosample those of the specimen chosen
   above when there is one) and **"Missing: add a measurement…"**, which opens today's measurement form (layer 3).
4. **Nothing fits: a new kind of data** (layer 1) opens a form with exactly two required things:
   - a **text description**: what is measured, how, with which device or lab, what one file holds;
   - a **dummy sample file**: made-up data in the format their device or lab produces, pasted or picked
     (text only, within the proposal size limit), with the agreement box that it holds no real participant data.
   The page says before sending: *"A new kind of data is added by the maintainer. Until it is merged and in a
   PRISM release, PRISM cannot validate these files. Plan for this before your study starts."*
5. **Sharing as today:** the user sees the proposal, then opens the prefilled GitHub issue form on
   `prism-specification` or downloads it. Studio sends nothing itself.

Plain-language wording rules of the current page stay (no "modality", "patch", "enum" in page text).

## What can be used before the merge

- **Measurements (layer 3) and added values (layer 2):** as today, *Use in my open project* writes them to the
  project's `code/specification/` and the data validates at once. They live inside the sidecar and need no
  new file name, which is why they can be local (the user's rule).
- **A new kind of data (layer 1): nothing local.** No local modality schema, no local entity rules. The user
  waits for the merge and the next Studio release that carries it. Validation keeps reporting unknown folders
  or file names as it does today.

## Goals

- The drill-down replaces the step-1 "what is missing" choice; every level is a pull-down derived from the
  current specification, never a hand-written list.
- A new kind of data can be proposed in a minute: description plus dummy sample, nothing technical.
- The "not sure" flag reaches the maintainer in the issue text.
- The specification can describe a new modality fully as data: once the maintainer adds the schema and the
  entities entry in `prism-specification`, Studio validates it (file names, sidecar schema, column values)
  with no Studio code change.
- GUI/CLI parity: every page action is a backend function and a `prism_tools.py spec ...` command.

## Non-goals

- Local validation of a not-yet-merged modality (the project overlay keeps layers 2 and 3 only; drop the
  overlay paths `schemas/stable/<name>.schema.json` and `entities/<name>.json` from the contributions design).
- Users writing schemas, suffixes or column definitions for a new modality.
- Term registries for modalities other than biosample (each is its own later design, like biosample was).
- Automatic placement or matching for "not sure".

## Anti-goals

- A proposal that makes the user guess technical names.
- Real participant data in a public issue.
- A hand-written list of modalities or fields anywhere in the page, routes or commands.

## Specification changes this needs (prism-specification first, then Studio with the new tag)

Found by registering a test modality (`bloodwork`, from `examples/modality_proposal/`) by data alone on
2026-10-24: file names and the sidecar schema were enforced, but column values were not.

1. **Column checks as data.** The validator checks column values (`AllowedValues`, `Levels`, `MinValue`, ...)
   only for the hand-written `TABULAR_MODALITIES = ("survey", "biometrics", "biosample")`
   (`app/src/constants.py`). Add a field to each `entities.schema.json` modality entry that says its TSV has a
   header row whose columns the sidecar describes (true for survey, biometrics, biosample; false for physio,
   whose TSV has no header; environment has its own check). Studio derives the set from
   `current_specification()` and the constant goes. The same set also drives the strict file-name pattern
   check (`app/src/validator.py`, "strict for survey/biometrics", and the biosample-entity check inside it),
   exactly as the constant does today, so no existing dataset gets new errors. Values: true for survey,
   biometrics, biosample; false for physio, events and environment (today's behaviour).
2. **A meta-schema for an entities entry** (`kind`, `suffixes`, `extensions`, `folder`, `allowedEntities`,
   `requiredEntityValues`, `optionalEntityValues`, `example`, plus the new field and the description below),
   checked in prism-specification CI. Today unknown keys are silently ignored by `src/entity_rules.py`.
3. **Modality schema conventions checked in prism-specification.** The check lives only in Studio
   (`tests/verify_repo.py`, `check_modality_schema_conventions`) with a stale hand-written list
   (`COMMUNITY_MODALITY_SCHEMAS` still names `eyetracking`, misses `biosample`). Move it to
   `prism-specification/scripts/`, run it on every modality the entities file lists, and keep Studio's
   `verify_repo` calling the vendored copy or drop it there.
4. **Proposals for every modality's lists.** The vendored checks assume a `Technical.SpecimenType` list
   (`check_terms.py` `specimen_types`, `term_proposal.py` `_specimens_of`), so a proposal for another
   modality crashes on share; `src/spec_contribute.py::spec_catalog` skips those modalities for that reason.
   Fix it upstream so a patch for any modality's lists is checked and shared; then drop the skip.
5. **The proposal carries context.** The filled and "Unknown" entries from step 2 reach the maintainer:
   as an optional context field in the issue form, prefilled like "not sure" (the proposal JSON stays as is).
6. **A short human description per modality** for the step-1 pull-down. Take it from the modality schema's
   `title`/`description` where they read well; BIDS passthrough entries need one line each in the entities file.

## The maintainer's side

- The issue form on `prism-specification` gets a "new kind of data" variant: description, pasted sample,
  an optional "closest kind of data" field, agreement box. No attachments (the bot downloads nothing, as for
  metrics). It is plain form fields, not a `prism-proposal` JSON document: Studio prefills the description and
  closest kind through the issue URL and tells the user to paste the sample into its field (a sample does not
  fit the 6,000-character URL); *Download* saves description and sample as one text file. The sample size
  limit (50,000 bytes, as for proposals) is one function in the vendored scripts, used by Studio and the bot.
- **"Not sure" in proposals:** for layers 2 and 3 the existing issue form gets an optional "not sure" field
  that Studio prefills through the URL (the proposal JSON format does not change). On the layer-1 form the
  "closest kind of data" field is a pull-down of the current modalities on the page, prefilled with the
  step-1 choice if the user had made one before choosing "Nothing fits".
- The bot only checks size and form fields and labels the issue; it opens no PR for layer 1. The maintainer
  writes the schema, entities entry and spec page by hand in a normal PR (`prism_tools.py modality propose`
  stays as the maintainer's tool to draft them from a workbook and the sample).
- Studio's own `propose-modality` issue form and workflow (`.github/ISSUE_TEMPLATE/propose-modality.yml`,
  `.github/workflows/propose-modality.yml`, `scripts/ci/modality_issue_to_files.py`) are retired in favour of
  the one on `prism-specification`. `modality propose`'s `REGISTRATION.md` is updated to say: edit
  `prism-specification`, tag, sync (today it says to edit Studio's vendored `app/schemas/stable`).

## Constraints (from the repository)

- Vendored files are never edited in Studio; specification changes are a separate PR, tag and
  `scripts/sync_specification.py --tag <tag>`.
- Validation-path code reads `current_specification()`; `tests/test_specification_boundaries.py` lists the files.
- The vendored scripts decide what a valid proposal is; Studio adds no rules of its own.
- Project data and issue text are untrusted; page text via `textContent`.
- TDD for every piece; `ponytail:ponytail-audit` before every merge.

## Phases (each its own plan)

A. **Specification (prism-specification):** changes 1–6, the new issue form variant and bot check; release.
B. **Studio, validator:** vendor the release; derive the column-check set; drop `TABULAR_MODALITIES` and the
   stale conventions list; regression test: a modality added by data only gets its column values checked.
C. **Studio, page and commands:** the drill-down; the "not sure" flag in proposals; the new-kind-of-data form
   and a `spec propose` option for it; retire the Studio modality form and workflow; docs.

## Calls I made (check them)

- "Not sure" is a tick next to the step-1 choice, not an entry in the list.
- The left-hand example is the modality's official library template; a modality without one (physio,
  environment, events today) shows its entries with the schema's own descriptions and no example values.
- With several templates (survey, biometrics) the first one alphabetically is shown, with a pull-down to
  switch; the example is read-only.
- Context (filled and "Unknown" entries) is an issue-form field, not part of the proposal JSON.
- BIDS modalities appear in step 1 but cannot be drilled into.
- Step 3 for biosample filters by the specimen chosen in step 2 when there is one.
- The layer-1 bot opens no PR; the maintainer builds the modality by hand.
- Studio's modality issue form and workflow are retired, not kept beside the new one.
- The column-check field is a boolean on the entities entry (name left to phase A); it also drives the strict
  file-name check, as `TABULAR_MODALITIES` does today; events and environment get false.
- A new kind of data is shared as plain issue-form fields, not as a proposal JSON document.
- "Not sure" travels as an issue-form field, not inside the proposal JSON.
