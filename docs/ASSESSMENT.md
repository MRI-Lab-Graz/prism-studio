# PRISM Studio — Repository Assessment

**Date:** 2026-05-27  
**Version assessed:** 1.15.3  
**Depth:** Quick sweep — top findings per area with file references and severity ratings.  
**Scope:** Architecture & layering, code quality, tests & CI, security & dependencies, frontend, performance & runtime, packaging & release, documentation.

---

## TL;DR

The repo has an 86.2% measured line rate on `src/`, a defined CI/build/release workflow set, and one confirmed medium-severity security code smell (`exec(..., globals())` in `app/src/derivatives/apps_runner_compat.py`). The main structural debt is concentrated in a small number of large modules (12,725 LOC across three files) and an incomplete migration of `app/src/` from hybrid copies to thin adapters over `src/`. The highest-value cleanup targets remain the `batch_convert` duplication, `PrismValidator.spec` drift, and the lack of `app/src/` coverage visibility.

---

## 1 — Architecture & Layering

### RULE #1 scorecard: thin web layer

| Module | Pattern | LOC | Status |
|---|---|---|---|
| `app/src/participants_backend.py` | pure proxy via `load_canonical_module` | 51 | ✅ |
| `app/src/project_structure.py` | pure proxy | 30 | ✅ |
| `app/src/anonymizer.py` | pure proxy | 36 | ✅ |
| `app/src/recipes_surveys.py` | pure proxy | 28 | ✅ |
| `app/src/runtime_dependencies.py` | pure proxy | 18 | ✅ |
| `app/src/project_session_logging.py` | pure proxy | 31 | ✅ |
| `app/src/batch_convert.py` | **full reimplementation + late proxy** | **2035** | ❌ |
| `app/src/participants_converter.py` | hybrid (own logic + late delegation) | 661 | ⚠️ |
| `app/src/formatters.py` | hybrid (own logic + late delegation) | 476 | ⚠️ |
| `app/src/project_manager.py` | no proxy — standalone god module | **6994** | ❌ |

Within the 10-module scorecard above, 6 modules are pure proxies, 3 are hybrid modules with substantial local logic plus late delegation, and 1 (`app/src/project_manager.py`) is a standalone app-layer god module rather than a thin adapter. This is a sampled classification of prominent modules, not a full census of every file under `app/src/`.

Evidence: the pure-proxy modules load canonical backends immediately near the top of the file in `app/src/participants_backend.py:9-11`, `app/src/project_structure.py:9-11`, `app/src/anonymizer.py:9-11`, `app/src/recipes_surveys.py:15-17`, `app/src/runtime_dependencies.py:5-7`, and `app/src/project_session_logging.py:9-11`. By contrast, `app/src/batch_convert.py:1952-1964`, `app/src/participants_converter.py:649-661`, and `app/src/formatters.py:464-476` load the canonical module only after hundreds or thousands of lines of local implementation.

### God modules

| File | LOC | Contents |
|---|---|---|
| `app/src/project_manager.py` | **6994** | Project CRUD, DataLad ops, git, citation sync, export, datalad repair |
| `src/recipes_surveys.py` | **3696** | Survey aggregation, formula evaluation engine, SPSS export, demographics join |
| `app/src/batch_convert.py` | **2035** | Full reimplementation of `src/batch_convert.py` plus Flask glue |

### OOP consolidation hotspots

1. **BIDS entity parsing** — The same BIDS filename regex patterns (`_ENTITY_TOKEN_PATTERN`, `_SUBJECT_DIR_PATTERN`) are duplicated independently in `src/bids_entity_rewriter.py`, `src/bids_file_deleter.py`, `src/repo_rewrite_datalad_runner.py`, and `src/subject_code_rewriter.py`. Consolidating into a single `BidsEntityParser` class in `src/` would remove four parallel definitions.
    Evidence: `src/bids_entity_rewriter.py:29-31`, `src/bids_file_deleter.py:39-41`, `src/repo_rewrite_datalad_runner.py:17`, and `src/subject_code_rewriter.py:12`.

2. **Participant value normalization** — `_normalized_participant_text()`, `_normalize_session_value()`, and similar helpers appear in both `src/participants_backend.py` and `app/src/participants_converter.py`. One canonical backend implementation should own this.
    Evidence: normalization helpers are defined in `src/participants_backend.py:666` and `src/participants_backend.py:711`, while `app/src/participants_converter.py:82` defines a separate `ParticipantsConverter` implementation before the late canonical import at `app/src/participants_converter.py:649-661`.

3. **File conflict & overwrite logic** — duplicated across `src/batch_convert.py` (canonical) and `app/src/batch_convert.py` (reimplementation). The `app/` file should become a pure proxy delegating to `src/`.
    Evidence: `app/src/batch_convert.py:1-1951` contains local conversion logic, and only then delegates at `app/src/batch_convert.py:1952-1964`. The canonical backend lives in `src/batch_convert.py`.

### Entrypoints

| File | Role | Status |
|---|---|---|
| `prism.py` (root) | venv-check wrapper | legacy |
| `prism-studio.py` (root) | Flask launcher stub | legacy |
| `prism_tools.py` (root) | tools entry stub | legacy |
| `app/prism.py` | canonical CLI entrypoint | ✅ active |
| `app/prism-studio.py` | canonical Flask launcher | ✅ active |
| `app/prism_tools.py` | canonical tools CLI | ✅ active |

Both root-level and `app/`-level entrypoints coexist. Root files are wrappers but the migration to `app/` as the canonical location is incomplete — users/docs referencing the root files still work but the duplication is confusing.

Evidence: the root launchers hand off into `app/` via `os.execv` in `prism.py:53-59`, `prism-studio.py:71-77`, and `prism_tools.py:7-14`. The `app/` entrypoints contain the actual CLI/web startup logic in `app/prism.py:1-40` and `app/prism_tools.py:1-31`.

### Refactor momentum

`app/src/web/blueprints/` has 57 extracted Python route-handler modules. Repository memory also contains numerous focused notes on controller/adapter extraction work across the survey converter, participants, file management, template editor, and related flows. The main outstanding architecture debt remains concentrated in the three god-module violations above.

---

## 2 — Tests & CI

### Coverage

- **Overall line rate: 86.2%** on `src/` (7766 / 9009 lines covered), per `coverage.xml` generated 2026-05-27.
- **Coverage scope is `src` only.** This is enforced both by the `pytest --cov=src` invocation in `ci.yml` and by `[tool.coverage.run].source = ["src"]` in `pyproject.toml`, so `app/src/` is invisible to the coverage report.
- 171 test files in `tests/`, versus 45 Python files in `src/` and 185 in `app/src/`.
- Only 11 `@pytest.mark.skipif` decorators exist, all conditional on optional package availability (numpy, biometrics converter). No `xfail` or `slow` markers in use.

Evidence: `.github/workflows/ci.yml:90` runs `pytest tests/ --cov=src`, and `pyproject.toml:8` sets `source = ["src"]`. Python 3.10 is pinned at `.github/workflows/ci.yml:32`, `.github/workflows/ci.yml:56`, and `.github/workflows/ci.yml:80`; fast and nightly verification run `verify_repo.py` at `.github/workflows/ci.yml:42` and `.github/workflows/ci.yml:66`; scheduled and manual deep checks are defined at `.github/workflows/ci.yml:11-13` and `.github/workflows/ci.yml:46`.

### CI workflows

| Workflow | Trigger | What it does |
|---|---|---|
| `ci.yml` — Coverage | push / PR to main, develop | pytest with coverage on Ubuntu + Python 3.10, uploads to Codecov |
| `ci.yml` — Fast checks | `workflow_dispatch` | `verify_repo.py` linting / mypy / import-boundary checks |
| `ci.yml` — Nightly deep | schedule (02:00) + dispatch | Full `verify_repo.py` suite: security, pip-audit, bids-compat-smoke, docs, todos |
| `build.yml` | tag push / manual | Cross-platform build matrix for macOS (Apple Silicon + Intel), Windows, and Linux |
| `readthedocs-release.yml` | release tag | Docs build trigger |

### CI gaps

| Gap | Severity | Notes |
|---|---|---|
| No OS matrix for automated tests in `ci.yml` | MED | Windows/macOS test files exist (`test_windows_*.py`) but the main test workflow runs only on Ubuntu |
| Python 3.10 only | LOW | No 3.11 / 3.12 matrix despite `utcnow` deprecation notes targeting 3.14 |
| No frontend tests | MED | ES module structure is testable; no JS test runner configured |
| Coverage excludes `app/src/` | MED | Adapter layer debt is invisible in reports |
| Docs build not in main CI | LOW | ReadTheDocs handles it but a PR can silently break Sphinx |

---

## 3 — Security & Dependencies

### OWASP check table

| Check | Result | Notes |
|---|---|---|
| `subprocess(shell=True)` | ✅ CLEAN | No matches |
| `eval()` / `exec()` | ⚠️ MEDIUM | `app/src/derivatives/apps_runner_compat.py:16` — see below |
| `pickle.load` | ✅ CLEAN | No matches |
| `yaml.load` without SafeLoader | ✅ CLEAN | No matches |
| `render_template_string` with user input | ✅ CLEAN | No matches |
| Hardcoded secrets / API keys | ✅ CLEAN | All via `os.environ.get()` |
| SQL string concatenation | ✅ CLEAN | No SQL usage |
| `send_file` path traversal | ✅ MITIGATED | `.resolve()` + bounds check in `projects_sourcedata_handlers.py:169` |
| CORS wide-open | ✅ CLEAN | No `origins="*"` |
| `debug=True` in production | ✅ SAFE | Explicit `debug=False`; Waitress used in prod |
| XXE in XML parsing | ✅ CLEAN | `defusedxml` used consistently for untrusted XML |
| Recipe formula `eval()` sandbox bypass | ✅ FIXED | Replaced with AST-based restricted evaluator (2026-04-23) |

### MEDIUM finding: `exec()` globals pollution

**File:** `app/src/derivatives/apps_runner_compat.py:16`  
**Risk:** MEDIUM (code smell, not an injection vector)

```python
exec(
    compile(
        _ROOT_MODULE_PATH.read_text(encoding="utf-8"), str(_ROOT_MODULE_PATH), "exec"
    ),
    globals(),
)
```

The path is fixed at module load time — not user-controlled. However, executing a file's source with `globals()` pollutes the module namespace in unpredictable ways and is difficult to audit. Replacing this with a proper `importlib` import would eliminate the risk class entirely.

Evidence: the wrapper computes a fixed `_ROOT_MODULE_PATH` in `app/src/derivatives/apps_runner_compat.py:5-13` and executes it at `app/src/derivatives/apps_runner_compat.py:16-20`.

### Dependencies

- All critical security packages specify explicit minimum versions: Flask ≥3.1.3, Werkzeug ≥3.1.8, requests ≥2.33.0, cryptography ≥46.0.7, authlib ≥1.7.0, urllib3 ≥2.6.3.
- `defusedxml` present and used for all untrusted XML input.
- No loose (unpinned) entries detected in `requirements-runtime.txt` or `requirements-optional.txt`.
- DeepL and LibreTranslate keys are sourced from environment variables. ORCID lookup uses the public HTTPS ORCID API and does not use an API key.
- Flask `secret_key` has a dev default fallback but is overridable via `PRISM_SECRET_KEY` env var. The dev default is documented; production deployments should override it.
- `MAX_CONTENT_LENGTH` and `MAX_FORM_PARTS = 20000` are set, limiting multipart abuse.

Evidence: `app/src/web/blueprints/projects_sourcedata_handlers.py:164-171` resolves the candidate path, checks that it stays under `sourcedata`, and only then calls `send_file`. `app/prism-studio.py:448-455` sets `PRISM_SECRET_KEY`, `MAX_CONTENT_LENGTH`, and `MAX_FORM_PARTS`, while `app/prism-studio.py:1487-1492` starts Waitress. External translation keys are read from environment variables in `app/src/library_autotranslate.py:133` and `app/src/library_autotranslate.py:201`. Restricted AST-based recipe formula evaluation is implemented in `src/recipes_surveys.py:85-188`.

---

## 4 — Frontend

### Module structure

- **ES modules throughout** — no IIFE monoliths. `app/static/js/shared/` contains reusable helpers: API fallback, project-state, storage, validation, path-picker, session-register, download, job-polling, DOM utilities.
- `converter-bootstrap.js` orchestrates per-page initialization using explicit imports from feature controller modules.
- 22 top-level JS files and 115 total JS files under `app/static/js/` for distinct pages, shared helpers, and feature modules.

Evidence: `app/static/js/converter-bootstrap.js:1-15` imports page modules plus shared helpers, and `app/static/js/converter-bootstrap.js:17` installs the shared API fallback up front.

### Inline `<script>` in templates

Inline scripts are limited to config injection:
- `app/templates/base.html` — injects `PRISM_API_ORIGIN` and beginner-help mode flag.
- `app/templates/recipe_builder.html` — injects `window.currentProjectPath`.
- `app/templates/library_editor.html` — injects JSON config.

No business logic in inline scripts. All module logic lives in `.js` files.

Evidence: template-side injections are limited to configuration surfaces at `app/templates/base.html:25`, `app/templates/recipe_builder.html:267`, and `app/templates/library_editor.html:95`.

### Refactor state

The controller/adapter extraction refactor is documented throughout repository memory. Survey converter, participants merge, file management, template editor, survey customizer, and offset editor all show evidence of that modularization pattern. The work is incremental and generally isolated by feature area.

### Gap

No JS test framework is configured: there is no `package.json`, and no Vitest/Jest/Playwright/Cypress config file in the repo. With the existing ES module structure, adding Vitest or Jest with module mocking would be straightforward and would give coverage over the shared helpers and complex controllers.

---

## 5 — Performance & Runtime

- **Production server:** Waitress (not Flask dev server) — `app/prism-studio.py` imports `waitress.serve` and starts it with `threads=8`.
- **Async job handling:** The repo contains targeted tests such as `tests/test_conversion_job_store.py` and `tests/test_web_validation_progress.py`, and repository memory records recent fixes around job retention, polling, and lock release semantics.
- **Background execution policy:** the repository instructions explicitly require long-running actions to be non-blocking.
- **No dedicated profiling-tool references were found** for `cProfile`, `pyinstrument`, or `line_profiler`. Given the size of `src/recipes_surveys.py` (3696 LOC, handles survey aggregation + formula eval + SPSS export) and `app/src/project_manager.py` (6994 LOC), a smoke performance test over a medium-sized dataset (e.g., 30 subjects, 5 surveys) would catch regressions early and help size the god-module split effort.

Evidence: Waitress startup is in `app/prism-studio.py:1487-1492`. The two large runtime hotspots measured in this assessment are `src/recipes_surveys.py` (3696 LOC) and `app/src/project_manager.py` (6994 LOC).

---

## 6 — Packaging & Release

### Version sync

All four version sources are in agreement as of 2026-05-27:

| Source | Version |
|---|---|
| `src/__init__.py` | 1.15.3 |
| `CITATION.cff` | 1.15.3 |
| `codemeta.json` | 1.15.3 |
| `CHANGELOG.md` latest entry | 1.15.3 (2026-05-27) |

Evidence: `src/__init__.py:10`, `CITATION.cff:7`, `codemeta.json:6`, and `CHANGELOG.md:10`.

### PyInstaller specs

| Spec | Heavy-package excludes | Status |
|---|---|---|
| `PrismStudio.spec` | 14 packages excluded (pyarrow, nibabel, pydicom, authlib, nltk, beautifulsoup4, bs4, pyedflib, sphinx, sphinx_rtd_theme, myst_parser, babel, docutils, pygments) | ✅ |
| `PrismValidator.spec` | **None**, and it omits the `('src', 'backend_bundle/src')` data bundle present in `PrismStudio.spec` | ⚠️ Clear spec drift |

`PrismValidator.spec` should be reviewed against `PrismStudio.spec` as a whole, not just for excludes. The missing backend bundle entry and zero exclude list indicate the two specs have drifted materially.

Evidence: `PrismStudio.spec:8` includes `('src', 'backend_bundle/src')` and `PrismStudio.spec:13` defines 14 excludes, while `PrismValidator.spec:8` omits that backend bundle entry and `PrismValidator.spec:13` sets `excludes=[]`.

### Setup scripts

- `setup.sh` and `setup.ps1` are functionally mirrored around uv/venv setup and optional build/dev dependencies. The PowerShell script adds Windows-specific checks for `tkinter` and `deno`, but the core setup flow is aligned.
- `build_local.ps1` is a Windows-only wrapper around `scripts/build/build_app.py`. No overlap with the setup scripts.
- The release build workflow contains explicit macOS-specific handling for Intel Rosetta/runtime dependencies and post-build code-signature verification, which indicates active maintenance of macOS packaging.

Evidence: `setup.sh:21-31` exposes `--build` and `--dev`, and its uv/deno/tkinter checks live at `setup.sh:181-206`; the Windows equivalents are at `setup.ps1:70-145`. `build_local.ps1:57` calls `scripts/build/build_app.py`, while the release build workflow creates `survey_library` at `.github/workflows/build.yml:87-89` and defines the cross-platform build matrix at `.github/workflows/build.yml:14-43`.

---

## 7 — Documentation

- **109 markdown files** and **2 rst files** in `docs/`.
- `docs/index.rst` references 37 documents. The remaining docs footprint is dominated by archived material and operational notes, including **50 markdown files under `docs/_archive/`**, **6 release-note files**, and **6 Windows-focused docs** at the top level of `docs/`. The new assessment is now linked from `docs/index.rst` under **Project Health**.
- **README, CHANGELOG, and ROADMAP** are all current as of 2026-05-27.
- **DeepL translation helper commands** now live in `docs/DEEPL_TRANSLATION_COMMANDS.txt`, which removes that operational note from the repo root.
- **`coverage.json` and `coverage.xml`** are present at the repo root but are not tracked by git. They are still generated artifacts and are better kept out of the working tree when not needed.

Evidence: the assessment is linked from `docs/index.rst:110-112` under the `Project Health` toctree.

---

## 8 — Top 10 Prioritized Recommendations

Ordered by impact × implementation ease. All are incremental changes; none require rewrites.

Current remediation-branch status: recommendations 1, 2, 3, 4, 5, 7, 9, and 10 are now completed; recommendation 8 was already satisfied by `.gitignore`; recommendation 6 has now extracted three sub-modules from `src/recipes_surveys.py` — `src/recipes_formula_engine.py` (formula AST + scoring), `src/recipes_path_utils.py` (filename / participant-ID helpers), and `src/recipes_export_helpers.py` (SPSS / SAV / codebook export helpers) — trimming the monolith from 3696 LOC to ~2680 LOC while preserving the original import surface via re-exports. Remaining inside `recipes_surveys.py`: aggregation/orchestration (`compute_survey_recipes`, `_export_recipe_*`, `_load_*`) and dataset-description/boilerplate generation; further splits can be done incrementally.

| # | Recommendation | Area | Severity | Effort |
|---|---|---|---|---|
| 1 | **Delete `app/src/batch_convert.py` reimplementation.** Make it a pure proxy delegating to `src/batch_convert.py`. Removes 2035 LOC of duplication and closes the single largest RULE #1 violation. | Architecture | HIGH | Low |
| 2 | **Extend CI coverage to `app/src/`.** Add `--cov=app/src` to the pytest invocation in `ci.yml`. This immediately surfaces the real coverage picture for the adapter layer without changing any test code. | CI | HIGH | Low |
| 3 | **Fix `exec(compile(...), globals())` in `apps_runner_compat.py`.** Replace with a proper `importlib`-based import. Eliminates the only OWASP-class code smell. | Security | MED | Low |
| 4 | **Bring `PrismValidator.spec` back in sync with `PrismStudio.spec`.** At minimum, mirror the 14 excludes and review the missing backend bundle entry. This addresses both binary size and packaging drift. | Packaging | MED | Low |
| 5 | **Extract `BidsEntityParser` class.** Consolidate the BIDS entity/subject regex patterns from four `src/` files into one canonical class. Reduces four parallel definitions to one. | Architecture / OOP | MED | Medium |
| 6 | **Split `src/recipes_surveys.py` (3696 LOC) into three modules.** Suggested split: `src/recipes_survey_aggregation.py`, `src/recipes_formula_engine.py`, `src/recipes_export.py`. No behavior change needed — move functions and update internal imports. | Code quality | MED | Medium |
| 7 | **Expand CI to at least Python 3.11.** Add a matrix entry. Catches stdlib deprecations (e.g., `utcnow`) before they reach production users. | CI | LOW | Low |
| 8 | **Gitignore `coverage.json` and `coverage.xml`.** These generated coverage artifacts are currently present in the repo root and should stay out of normal working-tree state. | Hygiene | LOW | Trivial |
| 9 | **Move `DEEPL_TRANSLATION_COMMANDS.txt` to `docs/` or `scripts/`.** Keep the root directory clean. | Hygiene | LOW | Trivial |
| 10 | **Configure a JS test runner (Vitest or Jest).** The repo currently has no JS test toolchain configured, and the ES module structure is ready for one. Start with the `app/static/js/shared/` helpers — these are the most critical and most reused. | Frontend | LOW | Medium |

---

## Appendix — Methodology

This assessment was produced by automated workspace exploration (file tree listing, targeted grep, LOC counts, CI/config file reads) combined with static analysis of `coverage.xml`, `.github/workflows/ci.yml`, `pytest.ini`, `pyproject.toml`, and PyInstaller spec files. No application code or tests were modified during assessment; only this report and its `docs/index.rst` entry were added.

**Files inspected directly (non-exhaustive):**

- `coverage.xml` — coverage numbers
- `.github/workflows/ci.yml` and `.github/workflows/build.yml` — CI/build pipeline structure and gaps
- `pytest.ini` — test configuration
- `pyproject.toml` — coverage scoping
- `requirements-runtime.txt`, `requirements-optional.txt` — dependency hygiene
- `PrismStudio.spec`, `PrismValidator.spec` — packaging
- `app/src/derivatives/apps_runner_compat.py` — security finding
- `app/src/web/blueprints/projects_sourcedata_handlers.py` — path traversal mitigation
- `app/prism-studio.py` — Flask security config
- `app/static/js/converter-bootstrap.js`, `app/templates/base.html`, `app/templates/recipe_builder.html`, `app/templates/library_editor.html` — frontend module/injection checks
- `src/__init__.py`, `CITATION.cff`, `codemeta.json`, `CHANGELOG.md` — version sync
- `docs/index.rst` — toctree coverage
- Sample of `app/src/` modules for RULE #1 compliance

**Limitations:** God-module internal complexity was assessed by LOC and structural observation only — no call graph or cyclomatic complexity analysis was performed. `app/src/` coverage gaps are estimated from scope exclusion in CI, not measured directly.
