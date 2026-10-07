# prism-validator: the BIDS check is part of the package and on by default

Status: approved, implemented on branch `validator-bids-default`

Date: 2026-10-07 · Branch: `validator-bids-default` · Release: 1.20.0 (proposed)

## Problem

`prism-validator` (the validator-only PyPI package, also used by DataLad Desktop and
the Austrian neurocloud) has two ways of treating BIDS that do not fit a package whose
datasets are all BIDS-based:

- **The BIDS check is off unless asked for** (`--bids`, or `runBids` in `.prismrc.json`).
  A plain run reports `valid: true` without ever having run the BIDS validator.
- **Running it needs a Deno installation that the package does not provide.**
  `app/src/bids_validator.py` runs `deno run -ERWN --allow-sys jsr:@bids/validator@2.4.1`,
  which needs a system `deno` on `PATH`, downloads the validator from jsr at run time
  and grants the validator environment, read, write, network and subprocess access;
  it falls back to an old Node `bids-validator` command that none of our dependencies
  provide. Consumers such as DataLad Desktop bundle Deno themselves, keep a lock
  file and a cache folder, and put Deno on `PATH` for the validator.

What the BIDS validator adds is real. Run on `examples/wellbeing_multi_demo` it reports
`PARTICIPANT_ID_MISMATCH`, which the PRISM-only run does not flag. And a correct BIDS
check of a PRISM dataset only exists inside `prism-validator`: the stock BIDS validator
reports 15 false `NOT_INCLUDED` errors for the PRISM folders (even with the dataset's
`.bidsignore`), which our wrapper filters out.

## What was found out (measured, not assumed)

- The official BIDS site lists a "python library" (PyPI `bids-validator`, 1.14.x). That is a
  file-name helper (`BIDSValidator().is_bids(path)`), not a validator. The repository
  `bids-standard/python-validator` is an alpha rewrite (tag `2.0.0.dev0`, not on PyPI):
  its command line only prints "is not a valid bids filename"; the rule engine, the issues
  model, derivatives, HED and NWB are open issues. It cannot replace Deno today.
- The official BIDS validator README itself publishes a **pre-compiled validator to PyPI**:
  `pip install bids-validator-deno` (3.0.2, MIT, Python >= 3.10). It depends on the PyPI
  package `deno` (2.9.7), which ships the Deno program as a wheel for macOS (Intel and
  Apple Silicon), Linux (x86-64 and ARM64, glibc >= 2.27) and Windows x64. The validator
  is one bundled file (13 MB); the launcher finds the Deno from the `deno` wheel itself
  and starts it with `--allow-read --allow-env --allow-net --allow-write --allow-run=git`.
  It ran without anything named Deno on `PATH` and without a network download.
- Its JSON report has the same structure our parser reads (`issues.issues[]` plus a
  `summary`).
- Speed is not a cost: on the 36-file demo dataset a PRISM-only run takes 0.13 s and the
  BIDS validator 0.16 s. The cost is install size: the core install is about 21 MB, the
  Deno program adds about 80 MB installed (40 MB download).

## Decisions (made with the project owner)

1. **The BIDS check is integral, installed with the package and on by default.**
   (An optional extra and an opt-in run were considered and rejected: PRISM promises
   BIDS-compatible datasets, so a verdict that skipped BIDS would promise less than users
   assume, and callers cannot run the stock validator themselves without the false errors.)
2. **One engine: `bids-validator-deno`.** System Deno, the jsr download and the Node
   fallback are removed completely; no escape hatch.
3. **No Python-package file-name check for now** (not needed once the full engine is
   always there; it would also force renaming our own module `bids_validator.py`).
4. Release as **1.20.0**: results change for existing users.

## Out of scope

- A pure-Python BIDS rule engine, and the `bids-standard/python-validator` package.
- Changing Studio's own validation modes, save gate, export gate or share-publish
  settings (they call the library function with explicit flags and keep doing so).
- Reading NIfTI headers by default (stays opt-in with `--check-nifti-headers`).
- Platforms without a `deno` wheel (Windows on ARM, Alpine/musl, glibc older than 2.27):
  covered by a clear error, not by a workaround.

## Behaviour

### Command line (`app/prism.py`, `prism-validator`)

- Every run checks PRISM **and** BIDS. New flag `--no-bids` skips the BIDS part, like
  `--no-prism` skips PRISM (both together: usage error, exit 2).
- `--bids` stays accepted (callers such as DataLad Desktop pass it); it is now the default and
  only matters to override `runBids: false` in a config file.
- `.prismrc.json` `runBids` defaults to `true` (`PrismConfig.run_bids`); `false` behaves like
  `--no-bids`. Precedence: command line over config file over default.
- The **library function** `validate_dataset(..., run_bids=False)` keeps its default; Studio
  (`web/validation.py`, `projects_export_blueprint.py`, `project_manager.py`), `src/api.py`
  and `src/share_publish.py` pass explicit values and are unchanged. Only the standalone
  command line changes its default.
- One verdict: `valid: true` means no ERROR from PRISM and no ERROR from BIDS. The machine
  output tells which checks ran and which BIDS engine/version produced the result (a new top-level `bids_validator` key in `--json` and `--format json`, absent with `--no-bids`):
  `{"engine": "bids-validator-deno", "version": "3.0.2"}` (version from package metadata,
  no subprocess). With `--no-bids` the key is absent.
- **Fail closed, unchanged in spirit:** if the BIDS check is on and cannot run (engine not
  found, crash, unreadable output), the result is an ERROR `PRISM902`, never a pass. The
  message names the cause; the hint says to reinstall `prism-validator` or use `--no-bids`.
- Exit codes and the JSON contract (documented in 1.19.2) are unchanged: 0 valid, 1 errors,
  2 could not run.

### The BIDS engine (`app/src/bids_validator.py`)

- Runs only `bids-validator-deno <dataset> --json` (plus `--ignoreNiftiHeaders` unless
  `--check-nifti-headers`). The program is looked up next to the running Python
  (`Path(sys.executable).parent`, also `Scripts/` on Windows), then on `PATH`.
- Removed: the `deno run jsr:@bids/validator@2.4.1` path (and `DENO_BIDS_VALIDATOR_SPEC`),
  the Node `bids-validator` fallback, their messages and the legacy-report parsing.
- Kept and re-checked against the real 3.0.2 output: the filtering of PRISM-only folders
  (`prism_ignore_folders`, `.bidsignore` handling), the citation-precedence suppression,
  the placeholder / structure-only handling, the `PARTICIPANT_ID_MISMATCH` handling in
  `runner.py`. Any rule code that 3.x renamed is mapped or documented.
- Output discipline from 1.19.2 stays: in `--json` / `--format` modes progress goes to stderr.

### Packaging

- `requirements-validator.txt` (the wheel's dependency list, read by
  `scripts/build_validator_wheel.py`) gains `bids-validator-deno>=3.0.2,<4` and drops
  `bids-validator` (PyPI), which nothing in the validator imports and which provides no
  command line. Check `bidsschematools` (a transitive dependency of the dropped package):
  keep it in `requirements-runtime.txt` only if Studio code imports it.
- The dependency carries environment markers for the platforms that have a `deno` wheel
  (`platform_system` / `platform_machine`, Linux glibc cannot be expressed in a marker,
  so pip simply finds no wheel on musl). On a platform without it the install of
  `prism-validator` still succeeds and the first run reports `PRISM902` with the hint to use
  `--no-bids`.
- `requirements-runtime.txt` (Studio) gets the same dependency. `install.sh` and
  `scripts/setup/windows.ps1` stop downloading and running the `deno.land` installer script;
  they no longer check for a system Deno.
- The Docker validator image (`python:3.13-slim`) installs the same list; the image run
  is covered by the integration test below.
- `tests/test_validator_runs_without_pandas.py` and the wheel tests keep guarding "no Studio
  dependencies" (Deno is allowed, pandas/Flask/DataLad are not).

## Compatibility and release

- **1.20.0**, release notes `docs/RELEASE_NOTES_v1.20.0.md` and a changelog entry:
  *Changed:* the BIDS check runs by default in `prism-validator` / `prism.py`; BIDS
  validator 2.4.1 -> 3.0.2 (check codes may differ); the validator package now includes the
  Deno runtime (about 80 MB more installed). *Removed:* use of a system Deno and the Node
  `bids-validator` fallback. *How to keep the old behaviour:* `--no-bids` (or
  `"runBids": false` in `.prismrc.json`).
- DataLad Desktop and the neurocloud: pin `prism-validator`; their own Deno download script,
  lock file, `DENO_DIR`, neutral working folder and `PATH` change are no longer needed.
  (Their repository is theirs to change; the release notes say what became unnecessary.)
- `SECURITY.md`: the validator starts the bundled Deno with read, env, net, write and
  `run=git` only (no `--allow-run` for everything, no `--allow-sys`); network access is
  still allowed.

## Testing (TDD, tests first)

- **Real integration tests** (run in normal CI; the dependency is an ordinary one): the
  installed `bids-validator-deno` on (a) a tiny valid BIDS dataset (no ERROR), (b) one with a
  real BIDS error, (c) `examples/wellbeing_multi_demo` (no false `NOT_INCLUDED` for the PRISM
  folders; the engine version is in the JSON). Report fixtures of the real 3.0.2 output are
  saved for the unit tests.
- **Unit tests** with a fake `bids-validator-deno` script on a temp `PATH` / next to a fake
  `sys.executable` directory: engine missing -> `PRISM902`; non-zero exit and unreadable
  output -> `PRISM902`; a failing exit code with a parseable report keeps the real issues;
  Windows script name handling by monkeypatching `sys.platform`; `--ignoreNiftiHeaders`
  toggle; lookup order (next to Python before `PATH`).
- **Flag tests:** default run includes BIDS; `--no-bids` does not; `--no-bids --no-prism` is
  exit 2; `runBids` false in config; `--bids` still works; the JSON `bids_validator` key
  present/absent; `valid` is false for a BIDS-only error.
- **Wheel tests:** the wheel metadata declares `bids-validator-deno` (with its markers) and
  not `bids-validator`; a clean-venv install of the built wheel runs the demo dataset with BIDS
  on and exits cleanly (this needs network for dependencies, like the existing wheel test).
- The existing `tests/test_bids_validator.py` (44 Deno references) is rewritten around the
  new engine; `tests/test_bids_validator_fail_closed.py`,
  `tests/test_validator_cli_json_contract.py` and the `PRISM902` tests are updated.
- Studio is checked for unchanged behaviour: its validation modes and the export gate tests
  stay green without edits to their expectations.

## Docs

`docs/CLI_REFERENCE.md` (flags, default, exit codes unchanged), `docs/INSTALLATION.md`,
`docs/SECURITY.md`, `docs/ERROR_CODES.md` and `app/src/issues.py` (`PRISM902` text),
`docs/studio/validator.md`, `src/share_publish.py` (its note about Deno), `.gitignore`
(the `deno.lock` line), `README.md` if it mentions Deno, release notes and changelog.

## Risks

- **Results change** for datasets that passed only because BIDS was off. Mitigated by the
  release note, `--no-bids`, and the version jump to 1.20.0.
- **BIDS validator 3.x** may report issues 2.4.1 did not; our filtering must be re-verified
  (hence the integration test on the PRISM demo dataset).
- **Install size** grows by about 80 MB. Accepted: BIDS is integral.
- **Unsupported platforms** get a working install and a clear `PRISM902`, not a crash.
- The `deno` PyPI package is third-party-maintained (it ships the official Deno binary);
  consumers that lock hashes pin it through `prism-validator`.
