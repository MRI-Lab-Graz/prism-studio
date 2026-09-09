# Design: Pavlovia/PsychoPy export from the Survey Customizer

Date: 2026-09-09
Status: Approved, pending implementation plan

## Problem

PRISM Studio has two survey-export surfaces:

1. **Survey Export** (`app/templates/survey_generator.html`) — select
   template files, pick a Target Tool, click export. Both LimeSurvey and
   Pavlovia/PsychoPy work here today (`/api/generate-lss`,
   `/api/generate-pavlovia`).
2. **Customize Export** (`app/templates/survey_customizer.html`) — load
   selected templates into an editable `groups` model (per-question
   enable/disable, reorder, multi-run duplication, matrix grouping, tool
   overrides), then export. Only LimeSurvey works here: the Target Tool and
   Export Format `<select>` elements are hardcoded to a single
   `limesurvey` option (`survey_customizer.html:90-94,111-113`), and the
   backend hard-rejects anything else
   (`tools_survey_customizer_handlers.py:213-218`,
   `if export_format != "limesurvey": return 400`).

The user wants Pavlovia available from the Customize Export screen too,
with the customization (question selection, order, multi-run, combining
several questionnaires into one output) actually reflected in the
exported experiment — not a stripped-down pass-through.

## Research basis

- `src/converters/pavlovia.py::export_to_pavlovia` (the function backing
  the *working* Survey Export → Pavlovia path) takes a single raw PRISM
  JSON file path and reads it itself
  (`load_prism_json` → `extract_questions` → `build_psyexp_xml`). It has
  no notion of the customizer's `groups` model, and the endpoint that
  calls it (`tools_generation_handlers.py::handle_generate_pavlovia_endpoint`)
  explicitly rejects more than one selected file
  (`"Pavlovia export supports one survey file at a time"`).
- `build_psyexp_xml(task_name, questions, prism_metadata)` currently
  builds exactly **one** question `Routine` (hardcoded name `"questions"`)
  holding a component per item in the flat `questions` list, bracketed by
  fixed `welcome`/`thanks` routines in the `Flow`. `prism_metadata` is
  accepted but never read inside the function (pre-existing, out of scope
  to fix here).
- The LimeSurvey side of the customizer already has the shape this needs:
  `src/limesurvey_exporter.py::generate_lss_from_customization(groups, ...)`
  consumes the browser's `groups` list directly (each group = one
  questionnaire's customized question set) and is called from
  `handle_survey_customizer_export`. This is the pattern to mirror, not
  invent.
- Each question in a customizer group (built by
  `handle_survey_customizer_load`, `tools_survey_customizer_handlers.py:16-203`)
  carries `enabled`, `displayOrder`, a possibly UI-overridden `mandatory`,
  and `originalData` — the untouched raw PRISM question dict as loaded
  from the template file. `originalData` is what lets a new extraction
  function reuse `pavlovia.py`'s existing `_resolve_text`/`_extract_condition`
  helpers unchanged.
- `tests/test_pavlovia_exporter.py::test_build_psyexp_xml_single_routine_for_all_questions`
  and seven other tests call `build_psyexp_xml(task_name, questions, {})`
  directly with the current flat-list signature — this signature must keep
  working unmodified.

## Scope decision (confirmed with user)

Full multi-questionnaire combination: a customized export with several
selected questionnaires produces **one PsychoPy experiment with one
routine per questionnaire**, in the customizer's group order — matching
what LimeSurvey combination already does structurally (one `.lss` with
multiple question groups). This is bigger than a single-file pass-through
but reuses `build_psyexp_xml`'s existing per-question component logic
without duplicating it.

Explicitly out of scope:
- The CLI (`survey export-pavlovia`) and the Survey Export screen's own
  `/api/generate-pavlovia` endpoint stay single-file, unchanged.
- REDCap/Qualtrics (still commented-out placeholders in the template).
- Multi-language Pavlovia export — `export_to_pavlovia` already documents
  itself as single-language-scoped; the customizer path inherits that
  constraint rather than lifting it.

## Design

### 1. `src/converters/pavlovia.py`

**Generalize the routine builder, don't duplicate it.**

```python
def build_psyexp_xml_grouped(
    task_name: str,
    routine_groups: List[Tuple[str, List[Dict[str, Any]]]],
    prism_metadata: Dict[str, Any],
) -> str:
    """Like build_psyexp_xml, but one Routine per (routine_name, questions)
    pair, inserted into Flow in the given order between welcome/thanks."""
    # body = current build_psyexp_xml body, generalized: the section that
    # builds the single "questions" Routine + its Flow entry becomes a loop
    # over routine_groups; form_items resets per group.

def build_psyexp_xml(
    task_name: str,
    questions: List[Dict[str, Any]],
    prism_metadata: Dict[str, Any],
) -> str:
    """Single-routine entry point used by the CLI/single-file export path."""
    return build_psyexp_xml_grouped(task_name, [("questions", questions)], prism_metadata)
```

This keeps every existing caller and test byte-for-byte compatible (a
single group named `"questions"` reproduces today's exact output) while
giving the customizer path a real multi-routine builder with zero copied
component logic.

**New extraction adapter**, parallel to `extract_questions` but reading
the customizer's data model instead of a raw template file:

```python
def extract_questions_from_customized_group(
    group: Dict[str, Any], language: Optional[str]
) -> List[Dict[str, Any]]:
    """Build the same question-dict shape extract_questions() produces,
    from one customizer group: filters to enabled questions, orders by
    displayOrder, and honors the UI's own `mandatory` override instead of
    trusting originalData['Mandatory']."""
```

Implementation: sort `group["questions"]` by `displayOrder`, drop
`enabled is False`, and for each item call the existing `_resolve_text`
on `originalData.get("Description")`/`Levels`, `_extract_condition` on
`originalData`, but take `mandatory` from the customizer's own
`question["mandatory"]` field (falls back to `originalData.get("Mandatory", True)`
only if the key is absent — matching how the customizer itself treats it).
No `_resolve_item_for_variant` call: the customizer has no active-variant
concept, so `originalData` is already the question the user is exporting.

**New top-level export function:**

```python
def generate_pavlovia_from_customization(
    groups: List[Dict[str, Any]],
    output_dir: Path,
    experiment_name: str,
    language: Optional[str] = None,
) -> Path:
    """Build a multi-routine Pavlovia/PsychoPy experiment from customizer
    groups -- one routine per non-empty group, in group order."""
```

Steps: for each group, run it through `extract_questions_from_customized_group`;
skip groups that come back empty (all questions disabled — same silent-skip
behavior `generate_lss_from_customization` already has for an
all-filtered-out questionnaire); build a unique, PsychoPy-safe routine name
per surviving group (sanitize via the existing `_safe_component_name`,
de-duplicate collisions with a numeric suffix — two groups can share a
display name, e.g. "Run 1"/"Run 2" of the same questionnaire); call
`build_psyexp_xml_grouped`; write a **combined** `conditions.csv` across all
groups. Extend `create_conditions_csv` with an optional `routine_labels`
parameter (parallel list of one label per question, or `None`): when given,
adds a `routine` column identifying which group a row came from; when
omitted (the existing single-file callers), output is unchanged. Write
`.psyexp`, reuse `create_readme` for `README.md`, return the `.psyexp` path
— exact same return contract as `export_to_pavlovia`.

If every group ends up empty after filtering, raise the same kind of
error `generate_lss_from_customization` raises for that case (checked
error, not a silent empty export) — the handler in step 2 turns it into a
400.

### 2. `app/src/web/blueprints/tools_survey_customizer_handlers.py`

`handle_survey_customizer_export`: replace the current

```python
export_format = data.get("exportFormat", "limesurvey")
if export_format != "limesurvey":
    return jsonify({"error": ...}), 400
```

with a branch: keep today's LimeSurvey body under
`if export_format == "limesurvey":`, add an
`elif export_format == "pavlovia":` that calls
`generate_pavlovia_from_customization` into a temp directory, zips it
(same `zipfile.ZIP_DEFLATED` + `rglob` pattern already used in
`tools_generation_handlers.py:150-164`), and `send_file`s the zip with
`download_name=f"{safe_title}_{date_str}.zip"` and
`mimetype="application/zip"` — mirroring the `.lss` branch's filename
sanitizing (`safe_title`/`date_str` computation stays shared). Unknown
formats still 400. The existing `saveToProject` template-copy behavior
(lines 242-278) is format-agnostic already and needs no change.

`get_survey_customizer_formats_payload`: add a `pavlovia` entry
(`id: "pavlovia"`, `name: "Pavlovia/PsychoPy"`, `extension: ".zip"`,
`description`, `options: []` — no format-specific options exist for
Pavlovia today) so this endpoint (not currently wired to the frontend, but
real and reachable) stays accurate rather than silently lying about what
formats exist.

### 3. `app/templates/survey_customizer.html`

- Add `<option value="pavlovia">Pavlovia/PsychoPy</option>` to `#targetTool`
  (`:90-94`) and `<option value="pavlovia">Pavlovia (.zip)</option>` to
  `#exportFormat` (`:111-113`).
- Wrap the LimeSurvey Version/Matrix row (`:116-...`) and the "LimeSurvey
  Survey Settings (optional)" section in a single container
  (`id="limesurveyOnlyOptions"`) so it can be hidden as one unit — no new
  Pavlovia-specific options panel is needed since none exist.
- Update the Survey Name helper text (currently "This name will appear as
  the survey title in LimeSurvey") to be tool-neutral, since it now also
  names the PsychoPy experiment.

### 4. `app/static/js/survey-customizer.js`

- New `change` listener on `#exportFormat`: toggle
  `#limesurveyOnlyOptions` (`hidden = value !== 'limesurvey'`), and toggle a
  small note near the Languages tags — "Pavlovia export uses the base
  language only" — visible only when `value === 'pavlovia'`. No new
  language-selection control; the payload already carries
  `survey.language`/`base_language`, which the backend passes straight to
  `generate_pavlovia_from_customization`'s `language` parameter.
- No change to the export POST payload shape — `customizationState`
  already carries `groups`/`survey`/`exportOptions`/`exportFormat`
  wholesale; the backend branch is the only thing that changes what it
  does with `exportFormat`.
- Run the same listener once on page load (in case a target tool was
  handed off from Survey Export as `pavlovia`, `:436-437`) so the panel
  opens in the right state instead of only reacting to a later change.

## Data flow

```
Customize Export UI (groups: filtered/reordered/multi-run per questionnaire)
  -> POST /api/survey-customizer/export {exportFormat: "pavlovia", groups, survey, ...}
  -> handle_survey_customizer_export
  -> generate_pavlovia_from_customization(groups, ...)
       -> per group: extract_questions_from_customized_group
       -> build_psyexp_xml_grouped(task_name, [(routine_name, questions), ...], {})
       -> conditions.csv (combined, routine column) + README.md
  -> zip output dir -> send_file(...)
```

Exactly parallel to the existing LimeSurvey path; only the last two steps
differ.

## Error handling

Shared validation (survey name required, `groups` non-empty) already runs
before the format branch (`tools_survey_customizer_handlers.py:225-230`)
and needs no change. Pavlovia-specific: an all-groups-empty-after-filtering
condition (every question in every group disabled) surfaces as a checked
exception from `generate_pavlovia_from_customization`, caught by the
existing broad `except Exception as error: return jsonify({"error": ...}), 500`
in the handler — consistent with how the LimeSurvey branch already
surfaces converter errors.

## Testing

- `tests/test_pavlovia_exporter.py`:
  - `build_psyexp_xml_grouped` produces one `Routine` per group, in
    order, in both `Routines` and `Flow`, bracketed by `welcome`/`thanks`
    (extends the existing `test_build_psyexp_xml_single_routine_for_all_questions`
    style of assertion).
  - `build_psyexp_xml` (unchanged signature) still produces exactly the
    same output as before for a flat question list — regression guard for
    the wrapper refactor.
  - `extract_questions_from_customized_group`: respects `enabled=False`
    filtering, `displayOrder` sort, and a UI-overridden `mandatory` value
    that disagrees with `originalData["Mandatory"]`.
  - `generate_pavlovia_from_customization` end-to-end with two groups:
    two routines in the `.psyexp`, `conditions.csv` has a `routine` column
    with both group names represented, README present.
- `tests/test_tools_survey_customizer_handlers.py`: `handle_survey_customizer_export`
  with `exportFormat: "pavlovia"` returns a `.zip` (correct mimetype,
  filename pattern), and an unknown format still 400s.

No frontend test framework exists for this file today (checked: no
`survey-customizer.test.js`), so the JS change gets manual verification
via `run` (Customize Export screen, switch Target Tool to Pavlovia, confirm
the LimeSurvey-only panel hides and the export downloads a working `.zip`)
rather than a new test harness invented for one listener.

## Dual-tree drift check (per CLAUDE.md)

`find src -name pavlovia.py` / `find app/src -name pavlovia.py`: only
`src/converters/pavlovia.py` exists — no `app/src/converters/pavlovia.py`
counterpart, so no drift risk for the converter itself.
`tools_survey_customizer_handlers.py` and `survey_customizer.html`/`.js`
are Flask-route/template/adapter code living solely under `app/src`/`app/`
with no `src/`-side counterpart — not implicit-namespace-package territory,
no check needed.
