# Proposing a metric (term) — design

Date: 2026-10-23
Status: design agreed in chat except the calls marked (mine); awaiting written-spec review. Nothing built.
Builds on: `2026-10-22-biosample-term-registry-design.md` (the registry),
`2026-10-22-prism-specification-repo-design.md` (steps 4-5 of "Order of work").

## Why

User 0 meets a metric PRISM does not know (`cort_nmol`). The validator already says it is
not official and offers to share it. This design is what "share" does: a data-only
proposal that reaches the maintainers of `prism-specification`, is checked by a bot, and
becomes a reviewed pull request. No Studio code and no fork needed for the contributor.

## Goals

- `prism_tools.py terms propose` builds a **proposal** (one JSON document) from a sidecar
  column and sends it: it opens a prefilled "Propose a metric" issue form in
  `MRI-Lab-Graz/prism-specification`.
- A bot in `prism-specification` checks the proposal with the same rules as CI
  (`check_terms.py`) and, for trusted authors, opens a **draft pull request** with the term
  files; for everyone else it comments that a maintainer will take over.
- The contributor learns the outcome through the issue; once merged and released, their
  column name works as an alias of the official term.
- A contributor without a GitHub account can save the proposal and send it any other way;
  a maintainer turns it into a pull request with the same script (`--file`).

## Non-goals

- The Studio "Share" button (own step after this, a thin adapter over this command).
- Moving the modality-proposal form and bot (design step 5).
- Choosing the final ID automatically: the maintainer does, IDs are frozen once released.
- Proposals for modalities other than `biosample` (the registry has no other yet; the
  format carries a `modality` field so it will not need to change).

## Anti-goals

- Running anything from the issue body. It is untrusted text: parsed as JSON, size-capped,
  every field validated against an allow-list, file names derived only after the ID passed
  the slug rule.
- A proposal that cannot pass CI. The CLI checks it before sending, with the same script.

## The proposal format

One JSON object, defined and validated by `scripts/term_proposal.py` in
`prism-specification` (the single implementation; Studio runs its vendored copy):

```json
{"modality": "biosample",
 "terms": [
   {"TermID": "prism:cortisol", "Level": "analyte", "Label": "cortisol", "Aliases": ["cort_nmol"],
    "Description": "..."},
   {"TermID": "prism:cortisol.saliva", "Level": "analyte-specimen", "Parent": "prism:cortisol",
    "SpecimenType": "saliva", "Units": "nmol/L", "MinValue": 0}]}
```

- Allowed term fields: the ones `CONTRIBUTING.md` lists, except `Status` (always set to
  `official` by the maintainer's merge) and `ReplacedBy`. Anything else is an error.
- At most 2 terms for the first version (a parent and a child, or a child alone when the
  analyte is already official), at most 20 KB.
- `TermID`s use the `prism:` prefix only (`bids:` is a maintainer decision).
- The check runs the terms **together with the current registry** (written to a temporary
  copy), so ID, alias and label collisions with official terms are caught.

## `terms propose` (Studio, CLI first)

`python prism_tools.py terms propose --sidecar FILE --column NAME [--label TEXT] [--open] [--json]`

1. Reads the column from the sidecar (`Description`, `Units`, ranges, `LOINC`) and the
   specimen from `Technical.SpecimenType`.
2. Resolves the column against the registry (`resolve_column`): unknown analyte → parent +
   child; known analyte, new specimen → child only; already official → refuses and says
   which term to use (`Term`).
3. Builds the proposal. The proposed slug comes from `--label` (default: the column name,
   lowercased, non-alphanumerics to `-`); the user's column name goes into `Aliases`.
4. Validates the proposal with the vendored `term_proposal.py`; on errors it prints them
   and sends nothing.
5. Prints the proposal and states again that the maintainers may change the name. With
   `--open` it opens the issue form URL in the browser (`webbrowser`); the proposal is
   passed in the form's `proposal` field (GitHub prefills issue-form fields from query
   parameters named like the field id). If the URL would exceed 6000 characters it prints
   the proposal and the form URL separately instead (paste it in). Nothing is sent without
   `--open`.

## The bot (`prism-specification`)

- **Issue form** `.github/ISSUE_TEMPLATE/propose-metric.yml` (label `type: new-metric`):
  one textarea `proposal` (JSON), a checkbox "I agree that my contribution is licensed as
  stated in LICENSE (CC BY 4.0)", a checkbox "It contains no personal data".
- **Workflow** `.github/workflows/propose-metric.yml`, two jobs copied from the modality
  bot's structure:
  - `check` (read-only token, no credentials): `scripts/term_proposal.py check` reads
    `ISSUE_BODY`, extracts the JSON, validates it with the registry, writes the term files
    and a log into a bundle artifact.
  - `report` (write token, treats the bundle as data): on failure comments the log and
    labels `needs-changes`; on success, for `OWNER`/`MEMBER`/`COLLABORATOR` authors opens
    a **draft** pull request (`terms/<modality>/…`, checklist below), for others comments
    that a maintainer will take over.
- **Maintainer checklist in the PR**: ID is sensible and final (frozen once released); the
  user's name is in `Aliases`; units are UCUM; no invented ranges or LOINC codes; CI green.
- **Offline path**: `python scripts/term_proposal.py check --file proposal.json --out
  terms/` does the same without GitHub.

## Where the code lives

| Piece | Repository | Notes |
|---|---|---|
| Format, validation, issue-body parsing, `--file` | `prism-specification` `scripts/term_proposal.py` + tests | MIT, stdlib only; vendored into Studio as `scripts/specification/` |
| Issue form, workflow, PR template text | `prism-specification` | released as `v1.1.0` |
| `terms propose`, sidecar → proposal | Studio `src/term_proposal.py` + `app/src/cli/commands/terms.py` | uses the registry (`resolve_column`) and the vendored validation |

Order: (A) `prism-specification` v1.1.0, (B) Studio syncs it and adds the command.

## Testing (TDD)

A: parser extracts the JSON from an issue-form body; rejects a missing/duplicate/oversize
proposal, unknown fields, `bids:` IDs, bad slugs, collisions with the current registry,
path-traversal attempts in IDs; writes the expected files; `--file` equals the issue path.
B: the builder for the three resolution cases (unknown analyte, new specimen, official →
refused); the proposal passes the vendored validation; the issue URL carries the proposal
and stays within the length cap, otherwise the fallback text; nothing is opened without
`--open`; `--json` output; the full suite stays green.

## Decisions (mine, check them)

- The proposal travels as JSON text in the issue body, not as an attachment (no download
  step in the bot; smaller attack surface than the modality bot).
- `terms propose` sends nothing unless `--open`, and never calls the GitHub API (no token
  in Studio).
- At most 2 terms and 20 KB per proposal.
- Final IDs and names are the maintainer's; the proposed slug is only a suggestion.
- The Studio Share button comes after this, as its own plan.
