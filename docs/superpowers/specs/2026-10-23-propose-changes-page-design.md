# Propose changes: a central, guided page that works without a project

Date: 2026-10-23. Builds on `2026-10-23-specification-contributions-design.md` and
`2026-10-23-metric-proposal-design.md` (local terms and patches, sharing as a prefilled GitHub issue).

## Intent

Today "Propose changes" is the last link in the sidebar of the Specs page, four clicks from anywhere, and
every part of it needs an open project (each route answers "Open a project first"). Someone who finds out
*before a project even exists* that PRISM lacks a value or a measurement cannot tell the community.
The page also reads technically (modality, patch, additions) and shows its three tabs at one level.

Goal: a lab member who hits something PRISM does not support can say so in a minute, with or without a
project, by choosing from dropdowns that show what exists today and where their entry will land.

## What the user sees

1. **Entry points.** A "Propose changes" item in the Docs menu (own entry, with a hint such as "Tell the
   PRISM community what is missing"), a short call-to-action on the Specs overview, and the existing sidebar
   link. The URL stays `/specifications/contribute`. No project is needed to open it.
2. **Step 1 is one dropdown, forced choice.** It starts on "Choose what is missing…" and nothing else is
   shown until a choice is made. Options:
   - "A whole new kind of data" (greyed out, "coming soon": the old *New modality* tab, still unavailable)
   - "A missing choice in a list" (was *Addition to a modality*)
   - "A missing measurement" (was *New metric*)
3. **A missing choice in a list.**
   1. Dropdown: which kind of data (Biosample, … every modality that has a list a project may extend).
   2. Dropdown: which list (human label, for example "Specimen type"; today the dotted field names such as
      `Technical.SpecimenType` are shown). Right under it, the values allowed today, so the user sees what
      exists and where theirs will land.
   3. Text field for the new value, **Add**. Added values collect in a visible list ("Your new choices")
      with **Remove**.
   4. Buttons: **Share with the PRISM community…** (always) and **Use in my open project** (only when a
      project is open).
4. **A missing measurement.**
   1. Dropdown: which kind of data (only kinds with a measurement list; today Biosample, the others greyed
      "no measurement list yet").
   2. The measurements PRISM knows today for it (all, searchable).
   3. Dropdown "Is your measurement in this list?": *Choose…* / *Yes, it is there* / *No, it is still
      missing*. *Yes* shows "Nothing to propose" plus how to use the existing one in a column. *No* opens
      the form.
   4. Form: name; other names people use (optional); one-sentence description; unit (dropdown); sample type
      (dropdown of the specimen types PRISM allows, plus the open project's own additions when there is a
      project; a hint points to "A missing choice in a list" if theirs is not there).
   5. Same two buttons as above. With a project open, a **Found in your data** shortcut lists unknown
      columns of the project and prefills the form from one (this is today's *New metric* behaviour).
5. **Wording.** Plain language throughout: "kind of data", "list", "measurement", "choice". The words
   modality, patch, TermID, specimen enum do not appear in the page text (they stay in code, docs and CLI).
6. **Sharing stays as it is.** Nothing is sent from Studio: the user sees the proposal, then opens the
   prefilled GitHub form or downloads `proposal.json`.

## Goals

- Reachable in one click from the main navigation; usable with no project.
- Every choice that has a finite answer is a dropdown that shows what exists.
- One implementation: every new behaviour exists as a backend function and a CLI command; the page and
  the Flask routes only call them (CLAUDE.md "One implementation", GUI/CLI parity).

## Non-goals and anti-goals

- No "new modality" flow (still announced as coming soon).
- No project-less storage: without a project nothing is written to disk. Choices live in the page until
  shared or the page is left.
- No measurements for modalities without a term registry (only biosample has one).
- Studio must never send anything on its own.
- Anti-goal: a form that lets an invalid proposal through, or that needs a maintainer to guess what was meant.

## Constraints (from the repository)

- The vendored scripts decide what is valid (`scripts/specification/check_terms.py`, `schema_patch.py`,
  `term_proposal.py`); the new code calls them through `src/term_proposal.py` / `src/spec_overlay.py` and
  adds no rules of its own. Do not edit vendored files here.
- Validation-path code reads `current_specification()` and never frozen modality lists; the modality and
  list dropdowns are derived (`patchable_fields`, registries), not hand-written.
- Project data is untrusted; page text is written with `textContent` only. Names typed by hand go through
  the same ID rules as today (`prism:<slug>[.<specimen>]`, `slugify`, `re.fullmatch`).
- Files in `app/src/` that are not Flask glue: run the dual-tree check from CLAUDE.md before assuming an
  edit is live. Prefer putting new logic in `src/` and keeping routes thin.
- TDD for every piece; write the failing test first. Extend `tests/test_specification_contribute_routes.py`,
  `tests/test_spec_overlay_*.py`, `tests/test_cli_dispatch_routing.py`, `tests/e2e/test_specification_contribute_flows.py`.
- Update `docs/studio/specifications.md` and `docs/CLI_REFERENCE.md`.

## How it fits together (the builder's call, with these pointers)

- **Backend (`src/`, no project argument):** a catalog (kinds of data with their lists and allowed values,
  known measurements per kind, units in use by official terms, allowed sample types), plus two stateless
  builders: a proposal from `(modality, field, values)` and a proposal from a hand-typed measurement.
  Both return the existing result shape (`document`, `issue_url`, `problems`, `skipped`) and run the same
  checks the project-based path runs. The existing project-based functions keep working unchanged.
- **CLI:** `spec propose` without `--project` for the two cases (a field and values; a new measurement with
  name, description, unit, sample type, optional aliases), and a way to list the catalog. Same options as the page.
- **Routes:** a catalog route and a stateless propose route with no project check; existing
  project routes unchanged. "Use in my open project" calls the existing add-values / add-term routes.
- **Page:** the three tabs become the step-1 dropdown plus one panel per choice; the existing dialog for the
  proposal text, download and GitHub link is reused.

## Calls I made (change any of them)

- Without a project, added choices are kept only in the page, never written to disk.
- Unit dropdown lists the units already used by official terms plus "Other…" with a free-text field.
- "Is your measurement in this list?" is a three-option dropdown with a forced "Choose…" start.
- The old three tabs are removed, not kept next to the dropdown.
- The measurement list is shown in full for biosample (11 entries today); a search box is added only if
  the list grows.

## Out of scope for the plan

Release/tagging of the specification and any change to vendored files.
