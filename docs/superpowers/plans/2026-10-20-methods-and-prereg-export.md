# Richer Methods section + Word/Markdown/TeX export Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A paper-ready Methods section using everything PRISM knows, exportable as Markdown/HTML/Word/TeX(+.bib), plus the same export formats for the preregistration draft, from CLI and GUI.

**Architecture:** Markdown stays the intermediate (the generator already emits a tiny subset). `src/text_export.py` converts Markdown to docx/tex and builds a `.bib`. `src/methods_project.py` gathers all inputs for a project (extracted from the Flask handler, so CLI and GUI share it). New content sources are added as small section functions in `app/src/reporting.py` fed by small backend modules.

**Tech Stack:** Python, python-docx (optional dep, already used in `app/src/questionnaire_renderer.py`), Flask, pytest.

**Spec:** `docs/superpowers/specs/2026-10-20-methods-and-prereg-export-design.md`

## Pick-up note (2026-10-20)

- Branch: `feat/methods-prereg-export` (pushed). Execution mode chosen: **native** (implement every task in one session via `superpowers:executing-plans`, then one fresh reviewer on the whole branch). Start the next session with the CLAUDE.md mandatory skills, then `git checkout feat/methods-prereg-export` and resume at the first unchecked task below.
- Design changed vs. the first draft: Markdown is the intermediate (no document model); see the spec's "Revised" paragraph.
- **Status: Tasks 1-9 done. Resume at Task 10. (Task 8 rulings: recipes read directly from code/recipes/*/recipe-*.json, not via recipes_surveys loader (heavy, validating); eligibility_flags omitted since check_eligibility yields messages, not a participant count.) (Task 6 ruling: reordered by moving existing section blocks, not splitting into functions; old Data Collection block stays as its own section until Task 7 adds sidecar-based acquisition.) (Task 5 GUI buttons not clicked in a browser; pre-existing e2e failure tests/e2e/test_projects_layout.py::test_a_dataset_description_error_links_to_the_field_it_names fails on a clean checkout too.)** Ruling in Task 2: `build_methods` takes optional `project_data` and `compute_participant_stats` (the Flask handler injects its own); default `app_root` is the repo's `app/` dir. The SDD ledger lives in git-ignored `.superpowers/` and does not travel; recreate it (`sdd-workspace`) and trust these checkboxes and `git log`.
- Progress is tracked by the checkboxes in each task and by the commit log (`git log --oneline main..HEAD`).
- Before merging: `/ponytail:ponytail-audit` (standing rule), targeted tests, dual-tree check.

## Global Constraints

- Methods and preregistration stay separate documents; prereg does not feed Methods.
- Preregistration Markdown output stays byte-identical to today's.
- No new dependency; TeX is plain string rendering; Word needs `python-docx` and fails with an "install python-docx" message when missing (GUI Word button hidden/disabled then).
- Never invent facts: unknown data -> sentence omitted + warning. A loud `[TODO: ...]` marker is allowed.
- Session labels are free-form strings, compared exactly, never normalised.
- No subject IDs in output; aggregate counts only.
- Languages `en` and `de`; detail levels `brief|standard|detailed`.
- Repo rules: failing test first (TDD); new logic in top-level `src/`; `reporting.py` exists only in `app/src/` (`src.reporting` resolves there; verify with `python3 -c "import src.reporting as m; print(m.__file__)"` run from `app/`); GUI calls the same backend function as the CLI; no symlinks; check branch before commit (`feat/methods-prereg-export`).
- Commit trailer: `Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>`.

## Review Focus

- TeX special characters in text and citations (`& % $ # _ { } ~ ^ \`, umlauts) must not break compilation: escaped.
- Project with no `TaskDefinitions`, no `Sessions`, no participants.tsv, no sidecars: no crash, no empty headings.
- Session labels `"1"`, `"01"`, `"pre"` appear exactly as given in the text.
- `python-docx` missing: clear error (CLI exit code 2), not a traceback.
- `brief` level stays short: none of the new sections appear.
- `de` output: new sentences are translated or omitted, never mixed-language.

---

### Task 1: Format converters

**Files:**
- Create: `src/text_export.py`
- Test: `tests/test_text_export.py`

**Interfaces:**
- Produces:
  - `md_to_tex(md: str) -> str` (article body with `\section`/`\subsection`/`itemize`/`\textbf`/`\emph`, all special characters escaped, wrapped in a minimal compilable `\documentclass{article}` document)
  - `md_to_docx(md: str) -> bytes` (headings, paragraphs, bullet list, bold/italic runs)
  - `convert(md: str, fmt: str) -> bytes` for `fmt in {"md","html","docx","tex"}`; unknown -> `ValueError`; `docx` without python-docx -> `RuntimeError` containing "python-docx"
  - `FORMATS: tuple[str, ...] = ("md", "html", "docx", "tex")` and `MIME: dict[str, str]`

- [x] **Step 1: Write failing tests** in `tests/test_text_export.py`:
  - `test_tex_escapes_specials`: `md_to_tex("Smith & Co. 50% of a_b")` contains `Smith \& Co. 50\% of a\_b`.
  - `test_tex_structure`: `"## Participants\n\nText *n* = 5 and **bold**.\n\n- a\n- b"` -> contains `\section{Participants}`, `\emph{n}`, `\textbf{bold}`, `\begin{itemize}`, two `\item`.
  - `test_docx_roundtrip`: `convert(md, "docx")` re-opened with `docx.Document(io.BytesIO(...))` has a heading "Participants" and a paragraph containing "Text" (`pytest.importorskip("docx")`).
  - `test_convert_md_passthrough` (utf-8 bytes of input), `test_convert_html_contains_h2`, `test_convert_unknown_raises`.
  - `test_docx_missing_dependency`: monkeypatch `sys.modules["docx"] = None`; `convert(..., "docx")` raises `RuntimeError` matching "python-docx".
- [x] **Step 2:** Run `pytest tests/test_text_export.py -v`; expect FAIL (module missing).
- [x] **Step 3:** Implement. Parse line by line exactly like `_md_to_html` in `app/src/reporting.py:359` (`## `, `### `, `- `, blank, paragraph); inline `**bold**` before `*italic*` (same regexes as `_md_inline`); html format imports `_md_to_html` lazily from `src.reporting`. Escape TeX text before inserting commands.
- [x] **Step 4:** Run tests; expect PASS.
- [x] **Step 5:** `git add src/text_export.py tests/test_text_export.py && git commit -m "feat(export): md to tex/docx converters"`.

### Task 2: One backend entry point for methods (extract from the Flask handler)

**Files:**
- Create: `src/methods_project.py`
- Modify: `app/src/web/blueprints/projects_methods_handlers.py` (use the new function; keep response JSON unchanged)
- Test: `tests/test_methods_project.py`, existing `tests/test_projects_methods_handlers.py` must still pass

**Interfaces:**
- Consumes: `generate_full_methods` (existing, `src.reporting`), `compute_participant_stats` (callable, optional; default lazily imports `_compute_participant_stats` from `app/src/web/blueprints/projects_metadata_helpers.py`).
- Produces: `build_methods(project_path: Path, *, lang: str = "en", detail_level: str = "standard", app_root: str | None = None, compute_participant_stats=None) -> MethodsResult` where `MethodsResult` is a dataclass `(md: str, sections_used: list[str], warnings: list[str], template_data: dict[str, dict])`. Raises `FileNotFoundError("No project metadata available...")` when project.json is missing/empty.

- [x] **Step 1: Write failing tests**: tmp project with `project.json` (one survey task, Participants info), `participants.tsv` absent -> `build_methods(...)` returns md containing "Procedure" or the task name, `warnings == []` for now; empty folder -> `FileNotFoundError`; project with `code/library/survey/survey-ads.json` -> template found and its name is in md (move the template-discovery behaviour from the handler, including `_candidate_template_names`).
- [x] **Step 2:** Run; expect FAIL.
- [x] **Step 3:** Move the template lookup (library dirs, candidate names), `dataset_description.json` loading and the call to `generate_full_methods` from `handle_generate_methods_section` into `build_methods`; `app_root=None` means skip the external/global library dirs. The handler becomes: resolve project, call `build_methods`, return `md`, `_md_to_html(md)`, `filename_base`, `sections_used`, plus new key `warnings`.
- [x] **Step 4:** Run `pytest tests/test_methods_project.py tests/test_projects_methods_handlers.py tests/test_reporting_methods_generation.py -v`; expect PASS.
- [x] **Step 5:** Commit `refactor(methods): shared build_methods for CLI and GUI`.

### Task 3: CLI for methods and `--format` for preregistration

**Files:**
- Create: `app/src/cli/commands/methods.py`
- Modify: `app/src/cli/parser.py` (new `methods generate` subparser; `--format` on `preregistration draft`), `app/src/cli/dispatch.py` (route; add `"methods"` to the not-gated list next to `"preregistration"` only if the gate would otherwise block drafts, otherwise leave gated), `app/src/cli/entrypoint.py` (register handler), `app/src/cli/commands/preregistration.py`
- Test: `tests/test_cli_methods.py`, extend `tests/test_preregistration_draft.py`

**Interfaces:**
- Consumes: `build_methods`, `convert`, `FORMATS`.
- Produces: `prism_tools methods generate --project P [--lang en|de] [--detail brief|standard|detailed] [--format md|html|docx|tex|bib] [--output FILE]`; `prism_tools preregistration draft --project P [--format md|html|docx|tex] [--output FILE]`. Warnings go to stderr. Binary formats (`docx`) require `--output`, otherwise exit code 2 with a message. `bib` is added in Task 4.

- [x] **Step 1: Write failing tests** (call `main([...])`/subprocess like the existing CLI tests in `tests/test_cli_dispatch_routing.py`): `methods generate --format tex --output x.tex` writes a file starting with `\documentclass`; `--format docx` without `--output` exits 2; missing project exits 2; `preregistration draft --format md` output equals current `load_draft(...)`; `--format docx` writes a valid zip.
- [x] **Step 2:** Run; expect FAIL.
- [x] **Step 3:** Implement handlers as thin adapters over `build_methods`/`load_draft` + `convert`; map `RuntimeError` (python-docx) to exit 2.
- [x] **Step 4:** Run the new tests plus `tests/test_cli_dispatch_routing.py`; expect PASS.
- [x] **Step 5:** Commit `feat(cli): methods generate and multi-format preregistration draft`.

### Task 4: BibTeX for instrument references

**Files:**
- Modify: `src/text_export.py`; CLI `--format bib` in `app/src/cli/commands/methods.py`
- Test: `tests/test_text_export.py`

**Interfaces:**
- Produces: `references_bib(template_data: dict[str, dict]) -> str`. One `@misc` entry per distinct reference in each template's `Study.References` (fields from `Citation`, `DOI`, `URL`, `Year`; the `Citation` text goes in `note`). Key = lower-case first author surname + year (from `Study.Authors`/`Year` or parsed from the citation), de-duplicated with `a`, `b` suffixes in sorted order, so re-export gives identical keys.

- [x] **Step 1: Write failing tests**: two templates citing the same paper -> one entry; two different papers by "Smith 2020" -> keys `smith2020a`, `smith2020b`; output for the same input twice is identical; `&` and `_` in a citation are escaped for BibTeX; empty input -> `""`.
- [x] **Step 2:** Run; expect FAIL. **Step 3:** Implement. **Step 4:** Run; PASS.
- [x] **Step 5:** Wire `--format bib` (uses `MethodsResult.template_data`); add a CLI test; commit `feat(export): bib file for instrument references`.

### Task 5: GUI routes and buttons

**Files:**
- Modify: `app/src/web/blueprints/projects.py` (new `POST /api/projects/export-methods`; `format` query on `GET /api/projects/preregistration-draft`), `app/src/web/blueprints/projects_methods_handlers.py`, `app/templates/includes/projects/methods_section.html`, `app/static/js/modules/projects/metadata-methods.js`, `app/templates/includes/projects/study_metadata.html:593`
- Test: `tests/test_projects_methods_handlers.py`, `tests/test_preregistration_draft.py` (route tests), e2e smoke in `tests/e2e/test_projects_flows.py` only if the existing methods flow already has one

**Interfaces:**
- Consumes: `build_methods`, `convert`, `references_bib`.
- Produces: `POST /api/projects/export-methods` body `{language, detail_level, format}` with `format in {docx, tex, bib}` returns the file with `Content-Disposition` (`methods_section_<lang>.<ext>`); invalid format -> 400; missing python-docx -> 501 JSON `{success:false,error}`. Preregistration route: `?format=md|html|docx|tex` (default `md`, unchanged behaviour).

- [x] **Step 1: Write failing route tests** with the Flask test client used in the existing handler tests: docx response starts with `PK`; tex response contains `\documentclass`; `format=pdf` -> 400; prereg `?format=tex` -> tex, no format -> unchanged Markdown.
- [x] **Step 2:** Run; FAIL. **Step 3:** Implement routes (adapters only). Add Word/TeX/BibTeX buttons beside the existing MD/HTML ones, reusing the blob-download helper pattern in `downloadMethods`; show `warnings` returned by `generate-methods` as a yellow list in the preview; add Word/TeX links to the prereg download.
- [x] **Step 4:** Run the route tests; PASS. Open the page in the app and click each button once (state what you saw in the commit/PR).
- [x] **Step 5:** Commit `feat(gui): word/tex/bib downloads for methods, formats for prereg`.

### Task 6: Journal-order sections, shorter boilerplate, warnings

**Files:**
- Modify: `app/src/reporting.py` (split `generate_full_methods` into `_participants_section`, `_design_section`, ... each `(project_data, ctx) -> str`; reorder; shrink boilerplate; add `methods_warnings`)
- Test: `tests/test_reporting_methods_generation.py`

**Interfaces:**
- Produces: section order (headings only when not continuous): Participants, Design, Procedure, Measures, Data acquisition, Data processing and scoring, Ethics, Data availability, Funding. `sections_used` keys keep existing names. The "Data Standardization and Validation" paragraph becomes one sentence (PRISM + BIDS citation + `PRISM Studio v{prism_version}`) appended to Data availability. `methods_warnings(project_data: dict, participant_stats: dict | None, template_data: dict[str, dict]) -> list[str]`, called from `build_methods`.

- [x] **Step 1: Write failing tests** (keep the 5 existing tests green): `test_section_order` (sections_used index order Participants < Procedure < Measures < Funding); `test_boilerplate_is_short` (no "enforcing standardized filename patterns"); `test_warnings_missing_n` (no participant stats and no `TargetSampleSize` -> warning mentioning sample size); `test_warnings_instrument_without_citation` (template without references -> warning naming the task); `test_no_warnings_complete_project` -> `[]`.
- [x] **Step 2:** Run; FAIL. **Step 3:** Refactor by extraction first (tests green), then reorder/shrink/add warnings. **Step 4:** Run all `tests/test_reporting_methods_generation.py tests/test_methods_project.py`; PASS.
- [x] **Step 5:** Commit `feat(methods): journal order, shorter boilerplate, gap warnings`.

### Task 7: Acquisition parameters and recorded-data counts

**Files:**
- Create: `src/methods_acquisition.py`
- Modify: `app/src/reporting.py` (new "Data acquisition" section function), `src/methods_project.py` (collect and pass in)
- Test: `tests/test_methods_acquisition.py`, `tests/test_reporting_methods_generation.py`

**Interfaces:**
- Produces: `acquisition_summary(project_path: Path) -> dict` with `{"modalities": {"<modality>": {"n_subjects": int, "sessions": {"<label>": int}, "params": {"<field>": [distinct values]}}}}`. Counts from `sub-*/ses-*/<modality>/` folders in the BIDS root (use `src.project_root`/`resolve_bids_rawdata_root` conventions already used by `src/environment_mri_scan.py`); params from the first sidecar per modality plus distinct values across all: MRI `RepetitionTime, EchoTime, FlipAngle, MagneticFieldStrength, Manufacturer, ManufacturersModelName`; EEG/physio/eyetracking `SamplingFrequency, EEGReference, Manufacturer, ManufacturersModelName`. Session keys are the folder labels exactly as found. Absent -> `{"modalities": {}}`.
- Reporting: `_acquisition_section(summary, lang, detail_level) -> str`, empty for `brief` or empty summary; sentences only for fields present (e.g. "Functional MRI data were acquired on a 3 T Siemens Prisma scanner (TR = 2000 ms, TE = 30 ms)." ), numbers formatted from the data, `de` variant for each sentence.

- [x] **Step 1: Write failing tests**: tmp BIDS tree with `sub-01/ses-1`, `sub-02/ses-01` func sidecars -> `sessions == {"1": 1, "01": 1}` (labels not merged); sidecar values surfaced; empty tree -> `{"modalities": {}}`; section text contains "TR = 2000"; `brief` -> `""`; `de` contains no English template words from the `en` sentence.
- [x] **Step 2:** Run; FAIL. **Step 3:** Implement (stdlib `json`/`pathlib` only, no pandas). **Step 4:** Run; PASS.
- [x] **Step 5:** Commit `feat(methods): data acquisition section from sidecars`.

### Task 8: Scoring recipes, software versions, exclusions

**Files:**
- Create: `src/methods_processing.py`
- Modify: `app/src/reporting.py`, `src/methods_project.py`
- Test: `tests/test_methods_processing.py`, `tests/test_reporting_methods_generation.py`

**Interfaces:**
- Produces: `processing_summary(project_path: Path) -> dict` with keys `recipes: list[{"task": str, "scores": list[str]}]` (from the project's `recipes/` or `code/recipes/` JSON, use the loader already in `src/recipes_surveys.py`; builder confirms the folder and field names), `software: {"prism_version": str, "modality_schemas": dict[str,str]}` (PRISM version as in `reporting.py`; pins via `src.modality_versions.read_pins`), `eligibility_flags: int` (number of distinct subjects flagged by `src.eligibility.check_eligibility`; builder confirms the return shape, omit the key if no count can be derived). Reporting: `_processing_section(summary, lang, detail_level) -> str` ("Data processing and scoring": which instruments were scored into which scales; software versions; "N participants did not meet the preregistered/declared eligibility criteria" only when the key exists), empty for `brief`.

- [x] **Step 1: Write failing tests**: project with one recipe -> sentence names the task and its scores; no recipes and no flags -> only the software sentence (standard) / `""` (brief); eligibility count absent -> no exclusion sentence; `de` sentences.
- [x] **Step 2:** Run; FAIL. **Step 3:** Implement. **Step 4:** Run; PASS.
- [x] **Step 5:** Commit `feat(methods): scoring, software and exclusion sentences`.

### Task 9: Richer participants, procedure and measures from existing data

**Files:**
- Modify: `app/src/reporting.py`
- Test: `tests/test_reporting_methods_generation.py`

**Interfaces:**
- Consumes: `project_data` fields already read plus `DataCollection`, `Procedure.*`, instrument `Study.Subscales/Reliability/Validity/License/AdministrationTime`.
- Behaviour: at `standard` level also state subscales, administration time and licence per instrument (today `detailed` only for subscales/reliability); Procedure states session order and timing for every session (labels verbatim); Participants states per-session N when `acquisition_summary` gives different counts per session ("N = 40 at 1, N = 35 at 01" style, labels verbatim).

- [x] **Step 1: Write failing tests** for each bullet above (assert exact sentences for a small fixture; one test with sessions `"1"` and `"01"` asserting both labels appear and no merged count).
- [x] **Step 2:** Run; FAIL. **Step 3:** Implement in the section functions from Task 6. **Step 4:** Run the whole file; PASS.
- [x] **Step 5:** Commit `feat(methods): richer participants/procedure/measures text`.

### Task 10: Docs and finish

**Files:**
- Modify: user docs page that mentions the methods generator (grep `docs/` for "methods"), `docs/superpowers/specs/...` if behaviour deviated
- No new test.

- [ ] **Step 1:** Document `prism_tools methods generate` and the new `--format` options where the preregistration command is documented.
- [ ] **Step 2:** Run targeted tests: `pytest tests/test_text_export.py tests/test_methods_project.py tests/test_cli_methods.py tests/test_methods_acquisition.py tests/test_methods_processing.py tests/test_reporting_methods_generation.py tests/test_projects_methods_handlers.py tests/test_preregistration_draft.py tests/test_preregistration_block.py -q`; expect all pass. Also `python tests/verify_repo.py --check dual-tree-drift --no-fix`.
- [ ] **Step 3:** Run `/ponytail:ponytail-audit` on the branch (standing rule), apply worthwhile findings, re-run the tests, then finish via `superpowers:finishing-a-development-branch`.
