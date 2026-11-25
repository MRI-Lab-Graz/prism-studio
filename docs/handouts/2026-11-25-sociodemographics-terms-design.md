# Design: term IDs for sociodemographics (roadmap step 0c)

Date: 2026-11-25. **Approved 2026-11-25. No code yet.** Based on specification v1.5.27.

## Intent

Participant columns have a stable `prism:` ID, so studies can be combined and vocabularies (mainly Neurobagel) can
be linked to it. Agreed: columns get a shared term (not
`participant_id`, and not free text for now), `bmi` reuses `prism:bmi`, an external term is never the ID, and
links are added only where someone has checked them.

Not goals: harmonising each study's value codes, moving the questionnaire wording of `participants.json`, term IDs for
anything else.

## What exists today

Links to vocabularies live in three places that do not agree:

| Place | Content |
|---|---|
| `official/participants.json`, `Annotations` | `IsAbout` SNOMED/NCIt codes on 13 of the 33 columns, no value links |
| `src/neurobagel.py`, `augment_neurobagel_data` | hard-coded SNOMED/NCIt/PATO value links |
| `src/participant_columns.py`, `_generate_neurobagel_schema` | a second hard-coded list with `nb:` terms and values |

`participants.js` also decides things from `nb:` strings, which belongs in the backend.

**Bug found:** that second list matches column names by substring, so `native_language` and `language` are described as
"Age" and typed `Continuous` (reproduced). It should be fixed whatever happens to this design.

## Approaches for the links

1. **`mappings/` is the one source (recommended).** Code builds `Annotations` from it when it writes a project's
   `participants.json`; the three lists above go away.
2. **Keep `Annotations` in the template as the source.** Least work, but participants would be the only kind of data
   curated differently, and partners could not link it the way they link everything else.
3. **No `Annotations` at all; a Neurobagel file only on export.** Cleanest, but it breaks the annotation panel and the
   eligibility check, which read `Annotations` today. Possible later, on top of 1.

`Annotations` a user has written or approved in a project are project data: never overwritten, whichever approach.

## Design for approach 1

### Terms (specification)

- `terms/participants/<slug>.json`, `Level: "variable"`. The slug is the column name with `-` for `_`
  (`prism:education-level`, alias `education_level`). `sex` and `gender` are separate terms.
- `height`, `weight` and `bmi` are body measurements, so they live in `terms/biometrics/` (`bmi` already does;
  `height` and `weight` are new). The folder is part of the IRI, so an existing term is never moved.
- A term has `Levels` only where the codes are meant to be standard (`sex`, `handedness`, `gender`). Others, such as
  `ethnicity` or `income_bracket`, depend on country and study: no `Levels`.
- Of the 33 columns, only `bmi` collides with a released ID.

### Where `terms` is declared

Participants is not a modality (no folder, no suffix), and adding it as one would affect filename validation. So
`entities.schema.json` gets a second block that term loading reads like the modalities:

```json
"tables": {"participants": {"terms": {"nonTermColumns": ["participant_id"], "termsFrom": ["biometrics"]}}}
```

`termsFrom` is general: this table may also resolve to another folder's terms. The validator checks
`participants.json` with the same notices as other sidecars. Never new errors.

### Links

- `mappings/vocabularies.json` gets a `neurobagel` entry. **To verify** against Neurobagel: the URL form and which
  variables it really standardises (as far as I know: age, sex, diagnosis, assessment, participant and session ID).
- `mappings/participants/<id>.json` holds `SameAs`. The codes in today's three lists are moved in only after someone
  has looked each one up; unchecked ones are dropped, not copied.
- **Values:** a `Levels` entry in a mapping may also hold `SameAs` (today only `Measures` and `ValueRules`). General for
  every kind of data.
- A study may code `sex` as `1`/`2`. A value link is applied only when the project's code is the term's code;
  otherwise it is reported, never guessed.

### Studio and CLI

- `participants.json` stays Studio's file; each column gets `"Term"`. The terms and links come from the specification.
- `terms list|show|coverage` and `export-links` include participants with no new command.
- Writing `Annotations` from mappings happens in `src/`, used by the CLI and Studio; a parity test covers it.

## Delivery

1. Fix the substring bug (Studio, small, independent).
2. Specification: `tables`, `termsFrom`, level `SameAs`, term files, vocabulary entry, checked links. One release.
3. Studio: sync, resolve participant columns, `Term` in `participants.json`.
4. Studio: build `Annotations` from mappings, delete the two hard-coded lists and the `nb:` logic in JavaScript.

## Done when

- Every column of `official/participants.json` resolves to a term, except `participant_id` and the free-text
  `*_details` columns.
- No vocabulary code is hard-coded in `src/` or JavaScript.
- Existing projects validate as before, plus notices.

## Decisions (2026-11-25)

- Approach 1: `mappings/` is the one source of links.
- `participant_id` gets no term.
- Free-text columns (`medication_details`, `psychiatric_diagnosis_details`, `neurological_diagnosis_details`) get no
  term for now. They are not listed in `nonTermColumns`, so a term can be added later without other changes.

**Still open:** who checks the links. It does not block the build: the terms ship first, links follow when checked.
