# Studio GUI → Backend Command Audit (2026-08-07)

## Why this audit exists

CLAUDE.md documents a recurring bug class in this repo: `app/src/` (the Flask
Studio GUI) is supposed to be thin routes/adapters over the canonical `src/`
business-logic tree that the CLI (`prism.py`, `prism_tools.py`,
`python -m src.cli.entrypoint`) also uses. That boundary has repeatedly been
violated — sometimes as dead/shadowed duplicate files (`excel_base.py`,
`web/utils.py`, both fixed 2026-08-04), sometimes as genuinely independent
reimplementations that silently diverge (`survey_base.py`'s three-way fork).

Rule going forward: **every GUI button should trigger a real backend command**,
so the CLI and GUI always exercise the same code path. The one deliberate,
permanent exception is the Projects page family (GUI-only by design). A
second page, **PRISM App Runner, is being deprecated** (users are steered to
the dedicated desktop app instead) and was excluded from this audit entirely.

This document is the result of a button-by-button audit of every other page,
run as parallel per-page sweeps that traced each action from
template/JS → Flask route → handler → `src/*` logic → CLI command (if any),
verifying ambiguous cases with the `python3 -c "import src.<module> as m;
print(m.__file__)"` check from CLAUDE.md. **No code was changed in this
pass** — this is the findings report; remediation is scoped separately below
and should be prioritized top-down.

## Scope

Audited: Validate Dataset, Converter (Survey/Biometrics/Physio/Eyetracking/
Environment-MRI/Participants tabs + Neurobagel widget), Recipes, Recipe
Builder, Survey Generator, Survey Customizer, Template Editor, File
Management, JSON Editor. Home and Specifications were confirmed to be static
navigation-only pages with no server-calling actions.

Excluded: Projects page family (GUI-only by design), PRISM App Runner
(deprecated, not maintained going forward).

---

## P0 — Shipped bug (fix first, independent of the drift-cleanup effort)

### Template Editor → "Import .lsq/.lsg" is broken (HTTP 500 on every click)

- Button: Template Editor page, Import .lsq/.lsg.
- Route: `POST /api/template-editor/import-lsq-lsg` →
  `app/src/web/blueprints/tools_template_editor_blueprint.py:700`, which does
  `from src.converters.limesurvey import parse_lsq_xml, parse_lsg_xml`.
- **These two functions do not exist anywhere in the repo.** They were added
  to `app/src/converters/limesurvey.py` in commit `8c8b96ee`, then deleted
  from that file in commit `ab5f22a2` (a modularization/canonicalization
  refactor that made `src/converters/limesurvey.py` the canonical file) —
  without being ported to the now-canonical file.
- Verified live: `python3 -c "from src.converters.limesurvey import
  parse_lsq_xml, parse_lsg_xml"` → `ImportError`.
- No test exercises the real backend call —
  `tests/test_template_editor_workflow_wiring.py` only greps JS source text,
  so this regression shipped silently.
- **Fix**: restore `parse_lsq_xml`/`parse_lsg_xml` (and whatever
  `_build_prism_template_from_parsed` needs) into
  `src/converters/limesurvey.py`, the canonical file, and add a real
  integration test that calls the route/function, not just greps JS.

---

## P1 — Confirmed drift: independently-maintained duplicate implementations

These are the `survey_base.py` failure pattern recurring: real, separately-
maintained logic on both the CLI side and the Flask side for what's supposed
to be one operation.

1. **Environment enrichment algorithm, duplicated with confirmed schema
   divergence.** `app/src/environment/builder.py` (+`aggregator.py`,
   `cache.py`, `providers/`) independently reimplements the same season/
   sun-phase/daylight/pollen-risk formulas as
   `app/src/web/blueprints/conversion_environment_handlers.py`
   (`season_code`/`_season_code`, `estimate_daylight_hours`/
   `_estimate_daylight`, `sun_phase`/`_sun_phase`,
   `hours_since_sun`/`_hours_since_sun`, `pollen_risk_bin`/
   `_pollen_risk_bin` — algorithm identical line-for-line). `builder.py` is
   reached only by the legacy `prism.py --build-environment
   --scans-tsv ... --lat ... --lon ...` path; the GUI and
   `prism_tools.py environment convert` both go through
   `conversion_environment_handlers.py` instead. **Already diverged**:
   `builder.py`'s `CORE_COLUMNS` has no `moon_phase`/
   `moon_illumination_pct` fields, while the GUI/`environment convert` path
   emits them. Two CLI-reachable code paths produce different output
   schemas for "the same" operation today. No `src/environment` (top-level)
   package exists — collapse to one canonical implementation, per the
   `excel_base.py`/`survey_base.py` precedent.

2. **Neurobagel schema merge, duplicated (identical today, will drift).**
   `app/src/web/blueprints/conversion_participants_blueprint.py:314-354`
   defines a private `_merge_neurobagel_schema_for_columns` that is
   currently byte-identical to the canonical
   `src.participants_backend.merge_neurobagel_schema_for_columns` — which
   is *already imported into the same file* for other symbols. CLI imports
   and calls the canonical function directly
   (`app/src/cli/commands/participants.py:17,460-462`). Fix: delete the
   local copy, import the canonical function instead.

3. **`recipes --anonymized` flag name collision — CLI and GUI do different
   things under the same name.** Recipes page's "Anonymize" checkbox does
   real per-participant ID masking (via
   `tools_recipes_surveys_handlers.py:369-639`, partly using
   `src.anonymizer.create_participant_mapping`). The CLI's `--anonymized`
   flag on `recipes surveys`/`recipes biometrics`
   (`app/src/cli/parser.py:747-845`) only appends `_anon` to the output
   folder name (`src/recipes_surveys.py:2130`) — **it does not anonymize
   anything**. A CLI user passing `--anonymized` gets unanonymized data in
   a misleadingly-named folder. This is actively misleading, not just an
   absent feature — highest priority in this group after the P0 bug.

4. **Template Editor "Validate" uses a different pipeline than CLI
   `survey validate`.** GUI validate normalizes the template first (paper/
   software platform mapping via `src.converters.survey_io`, implicit
   numeric level ranges via `src.survey_scale_inference`, single-version
   VariantID autofill) before schema-checking
   (`tools_template_editor_blueprint.py` + `tools_helpers.py:172-300`). CLI
   `survey validate` → `library_validator.check_uniqueness` does a bare
   `jsonschema.validate` with none of that normalization. A template can
   pass in one path and fail in the other. Either port the normalization
   into the shared validator, or document why CLI validation is
   intentionally stricter/different.

5. **Validate Dataset page silently mutates `participants.tsv`; CLI
   validate does not.** `run_validation()`
   (`app/src/web/validation.py:291-294`) calls `_apply_participants_mapping`
   (→ `src.derivatives.participants_mapping.apply_participants_mapping`,
   which writes to `participants.tsv`) before running the core validator —
   but only inside the web wrapper. `prism.py`'s CLI validate calls
   `core.validation.validate_dataset` directly, bypassing this wrapper, so
   clicking "Start Validation" mutates a file that
   `python prism.py <dataset>` never touches. Confirmed at the
   `run_validation()` level, so it affects all of `/validate_folder`,
   `/upload`, `/revalidate`, and `/api/validate`.

6. **Validate Dataset: GUI and CLI resolve different default library
   paths.** The blueprint's `_get_default_validation_library_path`
   (3-tier fallback: project `library/` → `code/library/` → configured
   global library → bundled `survey_library`) only exists in
   `app/src/web/blueprints/validation.py:180-225` and is used whenever the
   GUI form's library field is blank. `prism.py --library` has no default
   at all — omitting it leaves `library_path=None`, and
   `app/src/validator.py:173-233`'s `resolve_sidecar_path` then only
   searches `root_dir/`, `root_dir/surveys`, `root_dir/biometrics`. Same
   dataset, same "no library specified" intent, different sidecars
   resolved depending on GUI vs. CLI.

7. **File Management "Edit BIDS Filename Parts" (entity rewrite) is a
   second, CLI-unreachable rewrite engine.** Uses
   `src.bids_entity_rewriter.BidsEntityRewriter` +
   `repo_rewrite_datalad_runner.apply_entity_rewrite`
   (`tools.py:1350,1385`). The CLI's `dataset rename-subjects` uses a
   different module, `src.subject_code_rewriter.SubjectCodeRewriter`
   (`app/src/cli/commands/dataset.py:24,41`) — same
   `repo_rewrite_datalad_runner.py` transactional machinery underneath, but
   two independent engines. `BidsEntityRewriter` explicitly excludes the
   `sub` entity, so scope doesn't literally overlap with
   `rename-subjects` today, but it duplicates the DataLad-aware rewrite
   machinery for every *other* BIDS entity (task/acq/run/ses/etc.) with
   zero CLI parity — grepped `app/src/cli/**`, `parser.py`, `prism.py`:
   no caller found anywhere outside Flask.

---

## P2 — Needs a CLI command (real logic, CLI-unreachable, no divergence detected yet)

Grouped by page. "Backend logic" is `src.*`/`app/src.*` unless marked inline.

**File Management**
- Delete Files (preview/apply) → `src.bids_file_deleter.BidsFileDeleter` — no CLI equivalent.
- "Delete all scans.tsv" → `project_manager.remove_scans_tsv_files` — no CLI equivalent.
- Physio Renamer (dry-run/copy/download) → inline regex logic in `conversion_physio_handlers.py:1319` — no CLI equivalent (also needs extraction, see below).

**Recipe Builder** (entire page)
- Template browse, item/range extraction, Save (recipe authoring) → mix of `src.survey_scale_inference` (shared, good) and substantial inline logic in `tools_recipe_builder_handlers.py`. There is **no CLI path to interactively author a recipe JSON at all** — only `validate_recipe` (used at save time) is shared with the CLI's runtime validation. Recipe JSON files must be hand-authored or built via this GUI only.

**Recipes page**
- Mask-questions / ID-length / Random-IDs options — inline, no CLI flags exist at all (paired with the `--anonymized` collision above, P1 item 3).

**Survey Generator / Survey Customizer**
- "Quick Export" (`src.limesurvey_exporter.generate_lss`) — zero CLI callers.
- Customizer "Export" (`generate_lss_from_customization`) — zero CLI callers.
- "Export Word" questionnaire (`src.questionnaire_renderer.render_questionnaire_docx`, also used by Template Editor's export-questionnaire button) — zero CLI callers.
- Customizer page-load (LimeSurvey property → customization-groups mapping) — inline in `tools_survey_customizer_handlers.py:15-153`, no CLI equivalent (also needs extraction).

**Template Editor**
- Save / Delete (single library template CRUD) — inline file I/O, no CLI command creates/edits/removes one template outside the GUI.
- Export questionnaire (.docx) — see Survey Customizer above, same function.

**Converter → Environment/MRI tab**
- "Scan Project MRI Data" / "Rescan & Re-enrich" (`build_mri_acquisition_table`, `resolve_bids_rawdata_root`) — no CLI subcommand calls these anywhere.
- Location-picker "Find" (geocoding convenience, inline `requests.get`) — no CLI equivalent; low severity.
- Physio tab's "Generate HTML report" checkbox — the underlying `batch_convert_folder(..., generate_physio_reports=...)` param is real and shared, but no CLI flag exposes it, so CLI users can't request the report.

**Converter → Participants tab / Neurobagel**
- Neurobagel widget's vocabulary fetch/augment (`fetch_neurobagel_participants`, `augment_neurobagel_data`) and local-TSV column sampling (`get_local_participants`, inline pandas in `neurobagel.py:56-88`) — the widget's actual value beyond a raw `--neurobagel-schema <json>` passthrough flag on `participants convert/merge/save-mapping` is entirely GUI-only. Needs an explicit decision: add a CLI command (e.g. `participants neurobagel-schema --project <p>`) or document this as an intentional GUI-only convenience, the same way Projects is.
- Neurobagel "Save Annotations" button → `POST /api/projects/participants` → `projects_participants_handlers.py:17-123`, mostly inline schema canonicalization/merge logic (only the `survey_selected` branch delegates to `src.participants_backend`). No CLI equivalent; also needs extraction.

**JSON Editor**
- "Save to Project" (writes `participants.json`/`dataset_description.json`/`samples.json`/`task-*.json` via real validation logic in `backend/file_manager.py` + `json_validator.py`) — no CLI command edits these sidecars generically. Needs an explicit decision (CLI command vs. documented GUI-only exception, like Projects).

**Validate Dataset**
- `/api/validation/default-library-path` — standalone form of P1 item 6's resolution logic; no CLI equivalent at all.
- "Download Report" — inline JSON serialization, an independent report shape from the CLI's own `format_output`. Minor; low risk since it's presentation-only.

---

## Needs extraction (real logic inline in a Flask handler, not delegated to `src/`)

Distinct from "needs CLI command" — these should move into `src/` regardless
of whether a CLI command is added next, since inline logic in a blueprint
file is exactly the shape that produced the `excel_base.py`/`survey_base.py`
incidents:

- Recipe Builder's template-discovery and item/range-extraction logic (`tools_recipe_builder_handlers.py:75-529`, mostly inline).
- Survey Customizer's page-load LimeSurvey-property mapping (`tools_survey_customizer_handlers.py:106-153`).
- Converter → Environment tab's preview/convert logic
  (`conversion_environment_handlers.py`) — flagged doubly: it's inline
  *and* the CLI reaches it only by importing **private** (`_`-prefixed)
  symbols directly from a Flask blueprint module
  (`app/src/cli/commands/environment.py:171,229`). This is the inverse of
  the intended architecture — business logic should live in a real
  `src.environment` module that both sides import from a public API.
- File Management's physio renamer (`conversion_physio_handlers.py:1319`).
- Neurobagel "Save Annotations" handler (`projects_participants_handlers.py:17-123`).
- Neurobagel local-participants TSV sampling (`neurobagel.py:56-88`).

---

## Confirmed OK — properly shared, no action needed

Listed to show these were checked, not skipped:

- Validate Dataset's core validator call chain (`run_validation` →
  `core.validation.validate_dataset` → `runner.validate_dataset`), aside
  from the two divergences in P1 items 5–6.
- Converter tabs — Survey, Biometrics, Physio, and Eyetracking all properly
  delegate to canonical `src/` modules also used by the CLI
  (`src.converters.survey`, `src.converters.biometrics`,
  `src.batch_convert` — the last one via a verified `load_canonical_module`
  shim). Eyetracking has no dedicated backend by design — it's the same
  `batch_convert_folder(modality_filter="eyetracking")` call as Physio,
  correctly shared, not a stub.
- Participants tab — preview, detect-id, merge, save-mapping, and
  convert-start/status all cleanly map to their respective CLI subcommands
  (`participants detect-id/preview/convert/merge/save-mapping`).
- Recipes page "Run" (core scoring) — shared with `recipes surveys`/
  `recipes biometrics` via `run_recipes_job`.
- Survey Generator "Generate Boilerplate" — shares
  `src.reporting.generate_methods_text` with `library
  generate-methods-text`.
- File Management's subject-rewrite and wide-to-long — both verified to
  use the same physical files as their CLI equivalents
  (`dataset rename-subjects`, `wide-to-long`).
- Template Editor's Excel/CSV/TSV import — corrects an earlier assumption:
  `src.converters.excel_template_import.parse_excel_groups` is an explicit
  thin wrapper around the same core parser (`excel_to_survey.
  extract_excel_templates`) that `survey import-excel` uses, not a separate
  reimplementation.

---

## Dead/orphaned code found (bonus — not "missing backend," but worth cleaning up)

- JSON Editor's entire bundled legacy frontend
  (`app/src/json_editor/src/frontend/js/{app.js,api.js,form-builder.js}` +
  `index.html`) is dead — never loaded by the live template, and its
  `validateBtn` targets a route shape (`/api/validate/<type>`) that doesn't
  exist server-side. Its `BIDSFormGenerator` is referenced defensively by
  the live JS but never actually loads, so schema-driven form generation
  silently never fires.
- JSON Editor's `/editor/api/status` route has no caller anywhere.
- Participants tab's synchronous `/api/participants-convert` route is dead,
  superseded by the async start/status pair everything now uses.
- Neurobagel's `/api/neurobagel/save-json` route is dead — the widget
  actually saves via `/api/projects/participants` instead.
- `/neurobagel` is referenced in nav/guard config but no route serves it as
  a page (the real UI lives inside Converter → Participants).

---

## Excluded from this audit

- **Projects page family** (`projects`, `projects_library`,
  `projects_export`, `projects_datalad_server`, `projects_rsync_server`,
  `projects_remote_browse` blueprints) — GUI-only by design, per explicit
  product decision.
- **PRISM App Runner** (`/prism-app-runner`) — being deprecated; users are
  directed to the dedicated desktop app instead. Not audited, not a
  candidate for CLI-parity work.
- **Home** (`/`) and **Specifications** (`/specifications`) — confirmed
  static/navigation-only, no server-calling actions to audit.

---

## Suggested remediation order

1. Fix the P0 shipped bug (`import-lsq-lsg`) — user-facing, unrelated to
   the broader cleanup effort, small and isolated.
2. Fix the `recipes --anonymized` collision (P1-3) — actively misleading
   CLI behavior, not just a gap.
3. Collapse the environment-enrichment duplication (P1-1) — two CLI paths
   with different output schemas is a correctness bug waiting to surface
   in a user's dataset.
4. Work through the remaining P1 drift items (Neurobagel merge duplicate,
   Template Editor validation pipeline, Validate Dataset's two
   divergences, File Management's entity-rewrite engine) using the
   `excel_base.py`/`survey_base.py` symlink-or-canonicalize pattern from
   CLAUDE.md.
5. Batch the P2 "needs CLI command" items by page as separate follow-up
   work, starting with File Management (Delete Files, scans.tsv cleanup)
   since that page already had the highest concentration of gaps.
6. Sweep the "needs extraction" list opportunistically whenever those
   handler files are next touched, per CLAUDE.md's existing guidance not
   to do large opportunistic refactors unrelated to the task at hand.
