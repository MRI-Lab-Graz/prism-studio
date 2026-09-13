# Documentation Corrections and Introduction — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix the two factual errors in the ReadTheDocs site that are live right now (the "data never leaves your computer" overclaim, and the undocumented `survey export-pavlovia` CLI command), then add a new `docs/INTRODUCTION.md` that makes the four points the paper stresses — open-endedness, the two-layer validator, the helper command groups, UX as a contribution.

**Architecture:** Pure documentation edits (`.md`/`.rst`), no code changes. Three small text corrections, one new page wired into the existing Sphinx toctree and the `CONCEPTS.md` card hub.

**Tech Stack:** Sphinx + MyST (existing `docs/` toolchain, `shibuya` theme).

**Spec:** `docs/superpowers/specs/2026-09-12-documentation-expansion-design.md` — this plan implements Section A (Corrections) and Section B (Introduction) only. Sections C/D/E are separate plans.

## Global Constraints

- The RTD build must stay green after every task: `sphinx-build -b html -W --keep-going` (matches `.readthedocs.yaml`'s `fail_on_warning: true`). Run it after every task, not just at the end.
- No Python autodoc anywhere (spec Non-goals).
- Every factual claim is verified against the code, never against the paper — the paper is known to have at least one wrong count (`paper/main.tex:374` says "fourteen" `prism_tools` command groups and lists fifteen; the real, verified count is fifteen top-level command groups in `app/src/cli/parser.py`).
- Git commit messages end with: `Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>`

---

### Task 1: Correct the "data never leaves your computer" overclaim

**Files:**
- Modify: `docs/index.rst` (hero tagline)
- Modify: `docs/studio/home.md:4`
- Modify: `README.md:25`

**Interfaces:** None — this task touches only prose, no code or cross-file references.

The claim is false: the optional environment-enrichment feature queries
Open-Meteo (`app/src/web/blueprints/conversion_environment_handlers.py:114-116`)
for weather/air-quality/geocoding. The paper already corrected the same
overclaim (`paper/main.tex:411-417`): "participant data is neither uploaded
nor sent to a remote service. The single exception is the optional
environment-enrichment feature... it is disabled by default, and no
participant-level data is transmitted." Match that framing without lifting
the sentence verbatim (docs voice vs. paper voice differ).

- [ ] **Step 1: Fix `docs/index.rst`**

Find:
```
       <p class="prism-tagline">
         Turn raw psychology and neuroscience study data into clean, BIDS-compatible
         datasets &mdash; without your data ever leaving your own computer.
       </p>
```

Replace with:
```
       <p class="prism-tagline">
         Turn raw psychology and neuroscience study data into clean, BIDS-compatible
         datasets &mdash; running locally on your machine, with participant data
         never uploaded or sent to a remote service.
       </p>
```

- [ ] **Step 2: Fix `docs/studio/home.md`**

Find (the second sentence of the opening paragraph, line 4):
```
PRISM Studio turns raw psychology and neuroscience study data into clean,
BIDS-compatible datasets — without your data ever leaving your own computer. The
Home screen is where every session starts: it makes the case for the tool in one
glance and gets you to your project in one click.
```

Replace with:
```
PRISM Studio turns raw psychology and neuroscience study data into clean,
BIDS-compatible datasets, running locally on your machine — participant data
is never uploaded or sent to a remote service. The one exception is the
optional, off-by-default environment-enrichment feature, which sends
coordinates and dates (never participant data) to a public weather service.
The Home screen is where every session starts: it makes the case for the
tool in one glance and gets you to your project in one click.
```

- [ ] **Step 3: Fix `README.md`**

Find (line 25, in the "Core Features" list):
```
- Local-first operation (data stays on your machine)
```

Replace with:
```
- Local-first operation (data stays on your machine; the only exception is
  optional, off-by-default environment enrichment, which sends coordinates
  and dates — never participant data — to a public weather service)
```

- [ ] **Step 4: Verify the old text is gone and the new text is present**

Run:
```bash
grep -rn "without your data ever leaving" docs/index.rst docs/studio/home.md README.md
grep -n "never uploaded or sent to a remote service" docs/index.rst docs/studio/home.md README.md
```
Expected: first command prints nothing (no matches); second command prints
one match per file (three lines total).

- [ ] **Step 5: Build the docs and confirm no new warnings**

Run:
```bash
cd docs && python3 -m sphinx -b html -W --keep-going . /tmp/prism_docs_build_check && echo BUILD_OK
```
Expected: ends with `build succeeded.` and `BUILD_OK`. (`.. raw:: html` blocks
and plain Markdown prose are not link-checked by Sphinx, so this build only
confirms nothing else broke — Step 4's grep is the real check for this task.)

- [ ] **Step 6: Commit**

```bash
git add docs/index.rst docs/studio/home.md README.md
git commit -m "docs: correct data-never-leaves-computer overclaim

The environment-enrichment converter queries Open-Meteo for weather/air-
quality/geocoding data; the docs' absolute claim was false. Matches the
correction already made in paper/main.tex.

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>"
```

---

### Task 2: Document `survey export-pavlovia` in the CLI reference

**Files:**
- Modify: `docs/CLI_REFERENCE.md` (insert after the `export-lss` /
  `export-lss-customized` / `export-questionnaire-docx` block, before the
  `import-limesurvey` block, currently around line 183)

**Interfaces:** None.

`survey export-pavlovia` was added in commit `a2643448` and is the only one
of 61 argparse subparsers with zero mentions in `docs/CLI_REFERENCE.md`.
Its flags, verified against `app/src/cli/parser.py:1362-1380`:
`json_path` (positional, required), `--output` (default: alongside input),
`--experiment-name` (default: none, uses template name), `--language`/`-l`
(default: template's own default language; help text says "Pavlovia export
is single-language scoped"). The Studio GUI equivalent is the "Target Tool"
dropdown in Survey Generator/Export with the `Pavlovia/PsychoPy` option
(`app/templates/survey_generator.html:45`), matching the phrasing already
used in this file for the neighboring `export-lss` bullet ("CLI equivalents
of Studio's Survey Generator...").

- [ ] **Step 1: Insert the new command block**

Find (the block immediately before `**`survey import-limesurvey`**`):
```
python prism_tools.py survey export-questionnaire-docx \
  --template library/survey/survey-gad7.json --output gad7.docx
```

**`survey import-limesurvey`** / **`survey import-limesurvey-batch`**:
```

Replace with:
```
python prism_tools.py survey export-questionnaire-docx \
  --template library/survey/survey-gad7.json --output gad7.docx
```

**`survey export-pavlovia`** — export a PRISM survey template to a
Pavlovia/PsychoPy experiment (`.psyexp` + `conditions.csv`). CLI equivalent
of the "Pavlovia/PsychoPy" option in Studio's Survey Generator "Target
Tool" selector:

```bash
python prism_tools.py survey export-pavlovia library/survey/survey-gad7.json \
  --output ./pavlovia_export --experiment-name gad7_study --language en
```

Pavlovia export is single-language scoped: `--language`/`-l` picks which
one (default: the template's own default language); `--experiment-name`
overrides the generated experiment/task name (default: derived from the
template); `--output` defaults to alongside the input file.

**`survey import-limesurvey`** / **`survey import-limesurvey-batch`**:
```

- [ ] **Step 2: Verify**

Run:
```bash
grep -n "export-pavlovia" docs/CLI_REFERENCE.md
```
Expected: at least 3 matches (the heading bullet and two command-line
examples).

- [ ] **Step 3: Build the docs**

Run:
```bash
cd docs && python3 -m sphinx -b html -W --keep-going . /tmp/prism_docs_build_check && echo BUILD_OK
```
Expected: `build succeeded.` and `BUILD_OK`.

- [ ] **Step 4: Commit**

```bash
git add docs/CLI_REFERENCE.md
git commit -m "docs: document survey export-pavlovia in CLI reference

The only one of 61 argparse subparsers with no mention in
CLI_REFERENCE.md, added in a2643448 and never backfilled.

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>"
```

---

### Task 3: Write `docs/INTRODUCTION.md` and wire it into the navigation

**Files:**
- Create: `docs/INTRODUCTION.md`
- Modify: `docs/index.rst` (Concepts toctree — insert `INTRODUCTION` above `WHAT_IS_PRISM`)
- Modify: `docs/CONCEPTS.md` (card grid — insert a new first card)

**Interfaces:**
- Consumes: nothing from Tasks 1-2.
- Produces: `docs/INTRODUCTION.md` as a page other plans may link to (Plan 2's
  signing page and Plan 3's GUI reference pages may reference it — link
  target is `INTRODUCTION.html` from `docs/*.md` at the top level, or
  `../INTRODUCTION.md` from `docs/studio/*.md`/`docs/cli/*.md`).

This is the docs' argument for the project. It states the four points the
paper stresses (`paper/main.tex`, commit `b4b1e3db`) as user-facing
consequences, each verified against the running code in this session — not
copied from the paper's prose, since the paper's own helper-group count is
off by one.

Verified facts this content relies on (all checked in this working session,
2026-09-12):
- `additionalProperties` appears in `app/schemas/stable/survey.schema.json`
  (and seven other stable schemas) — items are not enumerated by ID.
- `ApplicableVersions`, `VariantScales`, `Aliases` are handled across
  `src/survey_template_normalization.py`, `app/src/validator.py`,
  `app/src/questionnaire_renderer.py`, `app/src/schema_manager.py`, and
  others.
- `x-prism.officialOnlyRequired` / `x-prism.projectOnlyRequired` are two
  validation profiles implemented in
  `app/src/schema_manager.py:166-195` (`apply_schema_validation_profile`):
  the `project` profile relaxes fields the *official* library schema
  requires (so in-progress project data need not carry them yet); the
  `official` profile relaxes fields only *projects* require (so a shared
  library template need not carry them).
- Three schema versions coexist on disk: `app/schemas/stable/`,
  `app/schemas/v0.1/`, `app/schemas/v0.2/`.
- The validator's plugin system (`app/src/plugins.py`) loads user-supplied
  Python modules via `.prismrc.json`'s `plugins` array or a
  `<dataset>/validators/` directory; a plugin module defines
  `validate(dataset_path: str, context: dict) -> List[Issue]`. CLI flags:
  `--init-plugin`, `--list-plugins`, `--no-plugins` (`docs/CLI_REFERENCE.md`,
  confirmed present).
- The BIDS validator integration (`app/src/bids_validator.py:12`) invokes
  the real upstream tool via Deno (`DENO_BIDS_VALIDATOR_SPEC =
  "jsr:@bids/validator@2.4.1"`), not a reimplementation.
- Five report formats: `json`, `sarif`, `junit`, `markdown`, `csv`
  (`docs/CLI_REFERENCE.md:71`, matches `app/src/cli/parser.py`).
- `--fix` / `--dry-run` gives preview-before-write repair
  (`docs/CLI_REFERENCE.md:69`).
- Fifteen top-level `prism_tools` command groups, verified by parsing
  `app/src/cli/parser.py`'s top-level `subparsers.add_parser(...)` calls:
  `convert`, `wide-to-long`, `participants`, `environment`, `demo`,
  `survey`, `biometrics`, `physio`, `recipes`, `dataset`, `anonymize`,
  `template-export`, `library`, `file-management`, `json-editor`. (The
  paper's prose says "fourteen" and then lists all fifteen of these same
  names — the number in the paper is wrong, the list is right. Use fifteen.)
- 19 Studio Guide pages under `docs/studio/*.md` (excluding `index.md`),
  covering ~21 Flask templates in `app/templates/`.

- [ ] **Step 1: Write `docs/INTRODUCTION.md`**

```markdown
# Introduction

Psychological and neuroscience studies routinely combine two kinds of data:
imaging and physiological recordings that [BIDS](https://bids.neuroimaging.io/)
already standardizes well, and questionnaires, sociodemographic data,
biometrics, and scoring rules that BIDS deliberately leaves open. That
second category usually ends up in spreadsheets and lab-specific folder
conventions — workable until someone else has to reuse, validate, or
reproduce a derived score from it.

PRISM Studio's bet is that closing that gap needs more than a schema. It
needs a schema that does not need to know your instruments in advance, a
validator that is trustworthy enough to build a pipeline on, tooling for
the unglamorous conversion work in between, and an interface a
non-programmer will actually finish using. This page states that bet
directly, in four parts.

## Open-ended by construction

Most schemas for survey data work by enumerating what a valid item looks
like: a fixed list of instrument IDs, a fixed list of response scales.
PRISM's survey schema does not do this. It declares a *shape* a survey item
must satisfy — required keys, allowed types — via JSON Schema's
`additionalProperties`, rather than a closed list of the instruments
PRISM's authors have seen. A questionnaire PRISM has never shipped, in a
language it does not ship, validates fully on day one, with no schema
change and no PRISM update.

The mechanisms that make this practical, not just possible:

- **`ApplicableVersions` / `VariantScales` / `Aliases`** let one instrument
  definition cover multiple study versions and item variants without
  duplicating the whole instrument per version.
- **Two validation profiles** (`x-prism.officialOnlyRequired` and
  `x-prism.projectOnlyRequired`) mean the same schema validates a shared
  library template and a specific project's in-progress data with
  different, appropriate strictness — a template need not yet carry the
  fields only a live project has, and a live project need not carry the
  fields only the shared library standard requires.
- **Three schema versions coexist** (`stable`, `v0.1`, `v0.2`) so a
  project started under an older schema keeps validating without a forced
  migration.
- **Validator plugins**: a project can add its own checks — a Python
  module returning a list of issues — via `.prismrc.json` or a
  `validators/` folder, for lab-specific rules PRISM will never ship.

## A validator, not a linter

Validation is not a single pass of pattern-matching. PRISM runs two
independent layers: its own schema and cross-file checks, and the real
upstream [BIDS Validator](https://github.com/bids-standard/bids-validator)
— invoked, never reimplemented, so PRISM datasets are held to the same
standard every other BIDS tool checks against.

Around that core: five machine-readable report formats (JSON, SARIF,
JUnit, Markdown, CSV) so validation slots into CI the way any other check
does; a `--fix`/`--dry-run` pair that previews an auto-fix before writing
it, rather than mutating a dataset silently; template validation for the
library layer, independent of any specific dataset; and version pinning so
a validator run states which schema version it checked against.

## Fifteen helper commands for the unglamorous work

Between a raw export and a valid dataset is a long tail of mundane,
error-prone wrangling that no standard addresses and that researchers
otherwise solve with one-off scripts: detecting which spreadsheet column
holds the participant ID, reshaping a wide questionnaire export into long
format, stripping subject data from a validated project to seed the next
study, recomputing a derived score with its provenance attached instead of
trusting a methods-section description.

PRISM ships this as fifteen command groups under `prism_tools`, each
available both in Studio and as a scriptable CLI subcommand: `convert`,
`wide-to-long`, `participants`, `environment`, `survey`, `biometrics`,
`physio`, `recipes`, `dataset`, `anonymize`, `template-export`, `library`,
`file-management`, `json-editor`, `demo`. Individually these are small.
Collectively they are the difference between a data standard that is
theoretically satisfiable and one a lab actually satisfies on a deadline.
See [CLI Reference](CLI_REFERENCE.md) for the full command set.

## User experience as a design goal

BIDS defines a structure; it does not make that structure easy to reach.
The typical entry point is not a clean slate but a LimeSurvey archive, an
Excel codebook of uncertain provenance, and a folder of scanner output,
held by a researcher whose expertise is psychology rather than data
engineering. PRISM Studio treats the resulting last-mile problem as part
of the job, through three conventions that run across its screens:

- **Guidance where the domain knowledge is needed.** Converters ask
  domain questions — which column identifies the participant, which
  session a file belongs to — instead of requiring files pre-arranged into
  a BIDS layout the user must first learn. Correct BIDS names are derived
  from entity rules, not typed by hand.
- **Preview before commit.** Conversions, ID normalization, entity
  renames, validator fixes, and exports all show a preview of what will
  change before it changes. Operations that could collide or lose data
  report the conflict instead of resolving it silently.
- **Parity between the interface and the command line.** Every Studio
  action is reachable from the CLI, so interactive exploration and a
  scripted, reproducible pipeline are the same operation, not two
  implementations that can drift apart.

## What's next

- [What is PRISM?](WHAT_IS_PRISM.md) — the data and metadata model, and how
  it relates to BIDS
- [Project Overview](PROJECT_OVERVIEW.md) — the repo and feature map
- [Getting Started](TUTORIAL_BEGINNER.md) — the hands-on tutorial
- [Studio Guide](studio/index.md) — every screen, in depth
```

- [ ] **Step 2: Wire `INTRODUCTION` into the Concepts toctree**

In `docs/index.rst`, find:
```
.. toctree::
   :maxdepth: 2
   :hidden:
   :caption: Concepts

   CONCEPTS
   WHAT_IS_PRISM
   PROJECT_OVERVIEW
   SPECIFICATIONS
```

Replace with:
```
.. toctree::
   :maxdepth: 2
   :hidden:
   :caption: Concepts

   CONCEPTS
   INTRODUCTION
   WHAT_IS_PRISM
   PROJECT_OVERVIEW
   SPECIFICATIONS
```

- [ ] **Step 3: Add an Introduction card to `docs/CONCEPTS.md`**

Find (the opening of the card grid):
```
<div class="prism-chapter-grid prism-chapter-grid--slate">
  <a class="prism-chapter-card" href="WHAT_IS_PRISM.html">
```

Replace with:
```
<div class="prism-chapter-grid prism-chapter-grid--slate">
  <a class="prism-chapter-card" href="INTRODUCTION.html">
    <span class="prism-card-icon"><svg viewBox="0 0 24 24" fill="none" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M4 19.5V6a2 2 0 0 1 2-2h13v15H6a2 2 0 0 0 0 4h14"/></svg></span>
    <span class="prism-chapter-title">Introduction</span>
    <span class="prism-chapter-outcome">What PRISM Studio is staking a claim on, and why</span>
  </a>
  <a class="prism-chapter-card" href="WHAT_IS_PRISM.html">
```

- [ ] **Step 4: Verify the new page renders and is reachable**

Run:
```bash
cd docs && python3 -m sphinx -b html -W --keep-going . /tmp/prism_docs_build_check && echo BUILD_OK
grep -c "INTRODUCTION" /tmp/prism_docs_build_check/index.html
test -f /tmp/prism_docs_build_check/INTRODUCTION.html && echo PAGE_BUILT
```
Expected: `build succeeded.`, `BUILD_OK`, a nonzero count from the `grep -c`
(the toctree renders a link to it), and `PAGE_BUILT`. If the build instead
emits an "orphan" warning for `INTRODUCTION`, the toctree edit in Step 2 was
not saved correctly — re-check it before proceeding.

- [ ] **Step 5: Spot-check the four verified-fact blocks against source one more time**

Run:
```bash
grep -c "additionalProperties" app/schemas/stable/survey.schema.json
grep -n "officialOnlyRequired\|projectOnlyRequired" app/src/schema_manager.py
ls app/schemas | grep -E "^(stable|v0\.1|v0\.2)$"
grep -n "DENO_BIDS_VALIDATOR_SPEC" app/src/bids_validator.py
python3 <<'PYEOF'
import re
t = open('app/src/cli/parser.py').read()
lines = t.split('\n')
top = []
for i, l in enumerate(lines):
    m = re.match(r'\s*(\w+)\s*=\s*subparsers\.add_parser\(', l)
    if m:
        chunk = '\n'.join(lines[i:i + 3])
        nm = re.search(r'add_parser\(\s*\n?\s*[\'"]([^\'"]+)[\'"]', chunk)
        top.append(nm.group(1) if nm else '???')
print(len(top), sorted(top))
PYEOF
```
Expected: the schema has `additionalProperties`; both profile keys appear in
`schema_manager.py`; all three version directories exist; the Deno spec
constant is present; the parser script prints `15` and a list matching the
fifteen names used in the page. If any of these has drifted since this plan
was written, update the page text to match current reality before
committing — the constraint is "verified against the code," not "matches
this plan."

- [ ] **Step 6: Commit**

```bash
git add docs/INTRODUCTION.md docs/index.rst docs/CONCEPTS.md
git commit -m "docs: add Introduction page stressing the paper's four points

Open-endedness (additionalProperties + ApplicableVersions/VariantScales/
Aliases + validation profiles + plugin system), the two-layer validator
(PRISM checks + real upstream BIDS Validator, never reimplemented), the
fifteen prism_tools helper command groups, and UX as a design goal. Every
claim verified against current source in this session, not copied from the
paper (whose own helper-group count is off by one).

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>"
```

---

## Plan-level verification

After all three tasks:

```bash
cd docs && python3 -m sphinx -b html -W --keep-going . /tmp/prism_docs_build_check && echo BUILD_OK
grep -rn "without your data ever leaving\|leaving your own computer" docs/ README.md --include="*.md" --include="*.rst" | grep -v _build
```

Expected: `BUILD_OK`, and the grep prints nothing (the phrase is gone from
every doc source file, not just the three named in Task 1 — this is a
belt-and-suspenders check in case another copy exists that wasn't caught
during spec research).
