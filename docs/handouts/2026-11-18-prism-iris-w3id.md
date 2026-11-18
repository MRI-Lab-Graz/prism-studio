# Handoff: PRISM IDs, w3id and the stub work (2026-11-18)

Follows `2026-11-18-survey-stubs-studio.md`. Start a fresh chat; read this file only.

## State

- PR #275 (merged): a survey stub is a **warning** "texts missing" (once per sidecar, also when the schema fails), no
  empty-label noise, Levels keys still range-check the data.
- PR #276 (open, merge after CI): a stub must map to known PRISM IDs. IDs are read from the **official** survey
  templates (`src/instrument_ids.py`), no ID list; a project-only template is a `local:` instrument. Unknown
  instrument, unknown item or missing `Fingerprint` is an error. The wheel and the Docker image carry
  `official/library/survey`.
- Deferred: fingerprint linking (local survey to library ID): own feature (CLI command, Studio trigger, parity test).
- Still open in Studio: converters, import and the template editor do not know stubs (only the validator does).
- Note: `term-ids.txt` has about 2250 IDs, the library 23 templates (about 780 IDs). The other IDs only become known
  to the validator when their stubs are in the library.

## w3id: why

w3id PR #7217 is merged. `https://w3id.org/prism-specification/` redirects (302) to the repository; deeper paths all
land on the front page, so **nothing per term resolves yet and nothing may link to a term IRI until it does**.
`prism:<slug>` only means something inside PRISM; an IRI gives outside tools a unique, persistent, resolvable identity
(mappings, citations, FAIR). The base stays while the redirect target can move.

## w3id: settled decisions (brief for a design note in prism-specification, not started)

1. Pattern `https://w3id.org/prism-specification/<slug>`; a short reserved list (`schemas`, `terms`, `docs`, ...) that
   no slug may use, enforced in the slug rule; the redirect rules for those paths come before the slug rule.
2. Items keep the dot form `<slug>.<item>`.
3. Official IDs are `prism:`; project-only IDs are `local:<slug>`. A `local:<slug>` that is also an official slug gets
   a warning ("now official, use prism:<slug>"); the same check when a local term is created (promotion path).
   A specification change: `spec_overlay` still validates local terms as `prism:<slug>` today.
4. Redirect target is the template or stub file; an item goes to its instrument's file; one regex rule in the w3id
   `.htaccess`, no per-term entries.

Gets an IRI: official instruments, items, biosample and environment terms; schemas (`$id`, now
`https://prism.org/schemas/...`, not owned) with the next schema version bump; the `prism:` prefix defined once
(prefix map or JSON-LD context), never full IRIs written into templates.
Gets none: project-local IDs, data, projects, Studio pages, raw GitHub URLs, the private item store (an IRI for a
restricted instrument resolves to its stub, never to full texts).

## External links (SNOMED, LOINC, ...) today: three styles

- `official/library/mappings/<modality>/*.json`: full IRIs under `SameAs`, keyed by PRISM ID; allowed vocabularies and
  URL patterns in `mappings/vocabularies.json`. **The one to build on.**
- `official/library/terms/biosample/*.json`: a bare `"LOINC": "30522-7"` field.
- `official/participants.json`: short `snomed:123` IDs and its own prefix map; it has two different SNOMED bases
  (looks like a bug).
- Surveys have no links yet. Move the other two styles to `mappings/` once the prefix map exists.

## Order

1. Design note in prism-specification: settle the decisions above, add the prefix definition.
2. Per-term redirect PR to perma-id (one regex rule).
3. Schema `$id` change together with the next schema change (needs a version bump per modality).
4. Only then IRIs in mappings, exports and Studio.

## Process reminders

Sonnet 5.5 for every subagent; `ponytail:ponytail-audit` once before merge, plus `/code-review`; worktree per branch.
