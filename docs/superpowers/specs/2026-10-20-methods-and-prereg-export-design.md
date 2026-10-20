# Richer Methods section + Word/Markdown/TeX export (design)

Date: 2026-10-20. Status: draft, awaiting approval.

## Intent

The user writes papers from PRISM projects. "Generate method section" should
produce a Methods section that is close to paste-ready for a manuscript, using
everything PRISM knows about the project, so nothing has to be retyped. The
same Word/Markdown/TeX export should exist for the preregistration draft.

Today `generate_full_methods` (`app/src/reporting.py`) reads only
`project.json`, `dataset_description.json`, participants stats and library
templates, and only downloads as Markdown/HTML. The `Preregistration` block,
session structure, real recorded data, acquisition parameters, scoring recipes
and software versions are not used.

## Goals

1. Methods text in a journal-style order: Participants, Design, Procedure,
   Measures, Data acquisition, Data processing and scoring, Ethics, Data
   availability, Funding. PRISM/BIDS boilerplate shrinks to one or two sentences
   (a short "Data organisation" note), no longer a section of its own.
2. Use more of what PRISM knows (the builder checks each source exists and how
   to read it; skip silently-absent sources, warn on missing required facts):
   - project.json: `Procedure`, `DataCollection`, `Sessions`, `Conditions`,
     `Eligibility` (target N, power analysis) in addition to what is used now.
   - Actual data: subjects per task/session, excluded subjects and reasons,
     missing data (modules such as `eligibility`, `cleaning_notes`,
     `participants_sessions`, `session_map`).
   - Acquisition: MRI/EEG/physio/eyetracking parameters from sidecars
     (`modality_versions`, `environment_*`, `physio_bids`).
   - Instruments from library templates: items, scales/subscales, reliability,
     translation, licence, references.
   - Scoring: which recipes ran and their formulas.
   - Software: PRISM and validator versions, BIDS version.
3. Export formats for the Methods text: Markdown, HTML (existing), Word
   (`.docx`), TeX (`.tex` plus `.bib` for instrument references). Same formats
   for the preregistration draft (Markdown stays as is).
4. One implementation: backend functions + CLI first, GUI buttons call the same
   code (repo rule). CLI offers the same options as the GUI (`--format`,
   language, detail level).
5. Gaps are reported, never silent: missing N, instrument without citation,
   session without timing, etc. appear as warnings in the preview (and CLI
   output), per the "report problems in the preview" rule.

## Non-goals / anti-goals

- Methods and preregistration stay **separate documents**. The prereg block does
  not feed the Methods text; no "deviations from preregistration" section.
- No Results section, no statistics on outcome data.
- No new dependency for TeX (plain string rendering). Word uses `python-docx`,
  already an optional dependency; if missing, the command fails with the
  existing "install python-docx" style message and the GUI hides/disables the
  Word button.
- Do not invent facts. If PRISM does not know something, the sentence is
  omitted and a warning is reported; no placeholder prose that could be
  published by accident (an explicit `[TODO: ...]` marker is acceptable and
  must be loud in all formats).
- Session labels are free-form strings; never normalise them.

## Design

### Structured document in the middle

The backend builds a small document model (sections -> paragraphs -> inline
text, plus a reference list), then thin renderers produce each format:

- `src/methods_document.py` (new, canonical `src/` tree): the model and the
  renderers `to_markdown`, `to_html`, `to_docx`, `to_tex` (+ `to_bib`).
- `generate_full_methods` is refactored (extract sections into small functions,
  per the "prefer extracting functions" rule) to build the model instead of
  concatenating Markdown. Existing Markdown/HTML output must stay equivalent
  where content is unchanged (existing tests in `tests/` guard this).
- The preregistration draft builds the same model in `src/preregistration.py`
  (its AsPredicted question order is kept), so it gets docx/tex/html for free.
  Its Markdown output must remain byte-identical to today's.

### CLI and GUI

- `prism_tools library generate-methods-text` stays; add a project-level
  command for the full methods (builder: find the right place in
  `app/src/cli/`; there is currently no CLI for `generate_full_methods`, which
  is a parity gap to close) with `--format md|html|docx|tex`, `--lang`,
  `--detail brief|standard|detailed`, `--output`.
- `prism_tools preregistration draft` gets `--format md|html|docx|tex`.
- Flask: the existing methods route returns md/html as now; new download route(s)
  return docx/tex(+bib) by calling the same backend functions. Binary/zip
  handling for tex+bib is the builder's call (suggested: `.tex` and `.bib` as
  two downloads, or a single zip).
- GUI: add Word and TeX download buttons next to the existing Markdown/HTML
  ones in `methods_section.html` / `metadata-methods.js`; add the same set to the
  preregistration download in `study_metadata.html`. Warnings are listed in the
  preview.

### Citations

- Instrument references are collected once into the reference list.
  Markdown/HTML/Word: author-year inline plus reference list (APA, as the
  existing `_get_apa_citation` does). TeX: `\citep{key}` plus generated `.bib`.
- Citation keys are deterministic (author+year, de-duplicated) so re-export
  does not change keys.

## Constraints

- Follow repo rules: TDD (failing test first), `src/` is canonical (check the
  dual-tree drift one-liner for `reporting.py` before editing: it lives in
  `app/src/`; confirm which file answers for `src.reporting`), GUI/CLI parity,
  text files never annexed, no symlinks.
- Language: `en` and `de` as now.
- Output must not leak identifiable data (only aggregate participant stats, as
  today; no subject IDs in the text).

## Left to the builder

- Exact wording of each new paragraph (follow the tone of existing ones).
- Which sidecar fields count as "acquisition parameters" per modality; start
  with the common ones (MRI: TR/TE/flip angle/voxel size/scanner; EEG: system,
  sampling rate, reference, channels; physio/eyetracking: device, sampling rate).
- Order of work. Suggested: model + renderers with tests -> port existing
  sections -> prereg through the model -> CLI -> GUI buttons -> new sources one
  at a time (participants/sessions first, acquisition, scoring, software).
- Zip vs two downloads for TeX+bib.

## Open questions for the user

None blocking. Calls made without asking: section order, boilerplate shrink,
deterministic citation keys, loud TODO markers over silent omission.
