# Generated CLI Reference — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Generate `docs/cli/*.md` — one page per `prism_tools` subcommand, every flag/default/choice/help string — directly from `app/src/cli/parser.py`'s argparse tree, so the CLI reference can never silently drift from the real commands the way a hand-maintained copy would.

**Architecture:** A single script, `scripts/gen_cli_reference.py`, introspects the argparse tree built by `build_prism_tools_parsers()` and writes one Markdown page per command/command-group under `docs/cli/`. A new check in `tests/verify_repo.py` (matching the existing `dual-tree-drift` / `docs-build` checks) fails CI if the committed `docs/cli/` tree doesn't match a fresh run. `docs/CLI_REFERENCE.md` and `docs/CLI_WORKFLOWS.md` stay hand-written as the narrative layer and link into the generated pages — they are never machine-written, and the generated pages are never hand-edited.

**Tech Stack:** Python stdlib `argparse` introspection only. No new dependency (see "Why not sphinx-argparse" below — it was evaluated and rejected with concrete evidence, not skipped on assumption).

**Spec:** `docs/superpowers/specs/2026-09-12-documentation-expansion-design.md`, Section D2.

## Why not sphinx-argparse

Sphinx already has a purpose-built extension for exactly this
(`sphinx-argparse`'s `.. argparse::` directive, rendering live at every doc
build so it can never go stale) — the more obviously "correct" design on
paper, so before writing a custom generator this plan tested it directly
against this repo's real parser tree rather than assuming it would work:

1. **Default RST mode fails this repo's real content.** `pip install
   sphinx-argparse` and a minimal Sphinx project pointed at
   `build_prism_tools_parsers()`'s `survey` subparser built with warnings
   (`-W`): `Inline emphasis start-string without end-string`, traced to the
   literal help string `"...single-language survey-*.json templates..."` —
   a lone `*` in a glob pattern, which RST parses as unterminated emphasis
   markup. `docs/.readthedocs.yaml` has `fail_on_warning: true`, so this is
   a real, repo-specific build failure, not a hypothetical.
2. **The escape hatch drags in an unmaintained dependency.** The
   `:markdownhelp:` option (meant to sidestep RST's strictness by parsing
   help text as Markdown instead) requires the `CommonMark` PyPI package
   (last released 2019, superseded by `commonmark`/`markdown-it-py`
   everywhere else) — confirmed by installing `sphinx-argparse` and hitting
   `ModuleNotFoundError: No module named 'CommonMark'` at build time.
3. **This docs tree's actual engine (MyST, not RST) doesn't have the
   problem sphinx-argparse works around.** A direct test — a `.md` file
   with the same unbalanced `survey-*.json` text, built with `myst_parser`
   and `-W` — built clean, zero warnings. MyST (CommonMark-based) is
   lenient about a stray `*`; docutils' RST parser is not. Writing plain
   Markdown pages directly (this plan's approach) uses the tolerant path
   this docs tree already runs on, rather than routing help text through
   RST's stricter one via an extra directive layer.

Net result: the custom generator is less code than it looks like it should
be (no dependency, no RST-escaping logic needed) and more reliable for this
specific repo's content than the standard tool built for the job.

## Global Constraints

- The RTD build must stay green: `cd docs && python3 -m sphinx -b html -W --keep-going . <outdir>` (matches `.readthedocs.yaml`'s `fail_on_warning: true`).
- Markdown cross-page links use `.md`, not `.html` (verified house convention; see the signing-and-chapter-zero plan's Global Constraints for the failure mode this causes).
- The canonical CLI import is `from src.cli.parser import build_prism_tools_parsers` (matching `app/src/cli/entrypoint.py:79`) — resolves through `src/__init__.py`'s namespace-package merge to the one physical file at `app/src/cli/parser.py`. Verified no `src/cli/` tree exists to compete with it (`find src -iname parser.py` returns nothing), so this is not a `CLAUDE.md` dual-tree-drift case — but if a future change ever adds a physical `src/cli/parser.py`, this script's import would silently start reading a different, possibly-stale file. The generator's own `--check` mode is a partial safety net (it would start rendering different content and fail `--check`'s diff), but that's a side effect, not a guarantee — CLAUDE.md's `python3 -c "import ...; print(m.__file__)"` check is the real one, worth re-running if this generator's output ever looks unexpectedly wrong.
- Generated content lives under `docs/cli/`. **Nothing in that directory is ever hand-edited** — a hand edit is silently overwritten by the next `python scripts/gen_cli_reference.py` run and is exactly the kind of drift this plan exists to eliminate. Fix wrong output by fixing the generator or the source help text in `app/src/cli/parser.py`, never the generated file.
- Git commit messages end with: `Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>`

---

### Task 1: Create the generator and generate `docs/cli/`

**Files:**
- Create: `scripts/gen_cli_reference.py`
- Create: `docs/cli/*.md` (62 files, generated — do not hand-edit; exact
  count may shift if `app/src/cli/parser.py` changes before this task runs,
  since the generator always reflects the parser tree as it exists at
  generation time)
- Modify: `docs/index.rst` (CLI toctree)

**Interfaces:**
- Produces: `docs/cli/index.md` as the entry point other tasks link to.
  `scripts/gen_cli_reference.py`'s `generate() -> dict[str, str]` and
  `main() -> int` (supporting a `--check` flag) are consumed by Task 2's CI
  check, which shells out to this script rather than reimplementing its
  diff logic.

This script was written and tested against this repo's real 61-subparser,
15-top-level-command tree during this plan's own research (not left to be
figured out at execution time) — verified: deterministic across repeated
runs (byte-identical output), no leaked machine-specific absolute paths, no
duplicate pages from argparse command aliases (`recipes surveys` has
aliases `survey`/`surves`, `recipes biometrics` has alias `biometric` —
confirmed at `app/src/cli/parser.py:730,844`), and a full `sphinx -b html -W
--keep-going` build against this repo's actual `docs/` tree with these
pages included produces zero warnings.

- [ ] **Step 1: Write `scripts/gen_cli_reference.py`**

```python
#!/usr/bin/env python3
"""Generate docs/cli/*.md from the prism_tools argparse tree.

Every subcommand's flags, defaults, and help text live in
app/src/cli/parser.py. Hand-maintaining a matching Markdown reference is how
it goes stale (see docs/superpowers/specs/2026-09-12-documentation-expansion-
design.md, Section D2). This script regenerates the whole docs/cli/ tree
from that single source of truth.

Usage:
    python scripts/gen_cli_reference.py          # write docs/cli/*.md
    python scripts/gen_cli_reference.py --check  # exit 1 if regenerating
                                                  # would change any file
                                                  # (for CI)
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

# Canonical import path, matching the real CLI (app/src/cli/entrypoint.py) --
# resolves through src/__init__.py's namespace-package merge to the one
# physical file at app/src/cli/parser.py (verified: no src/cli/ tree exists
# to compete with it, so this is not a dual-tree-drift risk).
from src.cli.parser import build_prism_tools_parsers  # noqa: E402

OUT_DIR = REPO_ROOT / "docs" / "cli"


def _subparsers_action(parser: argparse.ArgumentParser):
    """Return the parser's _SubParsersAction, if it has one."""
    for action in parser._actions:
        if isinstance(action, argparse._SubParsersAction):
            return action
    return None


def _positionals(parser: argparse.ArgumentParser) -> list[argparse.Action]:
    sub = _subparsers_action(parser)
    return [
        a
        for a in parser._actions
        if not a.option_strings and a is not sub and a.dest != "help"
    ]


def _optionals(parser: argparse.ArgumentParser) -> list[argparse.Action]:
    return [a for a in parser._actions if a.option_strings and a.dest != "help"]


def _default_str(action: argparse.Action) -> str | None:
    if action.default is None or action.default is argparse.SUPPRESS:
        return None
    if isinstance(action.default, bool) and action.default is False:
        return None  # store_true flags defaulting False: not worth stating
    return str(action.default)


def _render_action_row(action: argparse.Action) -> str:
    name = ", ".join(action.option_strings) if action.option_strings else action.dest
    bits = [f"`{name}`"]
    if action.choices:
        bits.append(f"choices: {', '.join(str(c) for c in action.choices)}")
    default = _default_str(action)
    if default is not None:
        bits.append(f"default: `{default}`")
    if getattr(action, "required", False) and action.option_strings:
        bits.append("**required**")
    help_text = (action.help or "").replace("\n", " ").strip()
    left = " — ".join(bits)
    return f"- {left}" + (f" — {help_text}" if help_text else "")


def _canonical_subcommands(sub_action: argparse._SubParsersAction) -> list[tuple[str, list[str], argparse.ArgumentParser]]:
    """Collapse argparse command aliases (add_parser(..., aliases=[...]))
    into one (canonical_name, alias_list, parser) entry per unique parser,
    in first-seen order. Without this, each alias would get its own
    duplicate page -- verified against this repo's real tree, where
    `recipes surveys` has aliases `survey`/`surves` and `recipes biometrics`
    has alias `biometric` (app/src/cli/parser.py:730,844).
    """
    seen: dict[int, tuple[str, list[str], argparse.ArgumentParser]] = {}
    order: list[int] = []
    for name, sub in sub_action.choices.items():
        key = id(sub)
        if key not in seen:
            seen[key] = (name, [], sub)
            order.append(key)
        else:
            canonical_name, aliases, canonical_sub = seen[key]
            aliases.append(name)
            seen[key] = (canonical_name, aliases, canonical_sub)
    return [seen[key] for key in order]


def render_command_page(prog_path: list[str], parser: argparse.ArgumentParser, aliases: list[str] | None = None) -> str:
    title = " ".join(prog_path)
    lines = [f"# `{title}`", ""]
    if aliases:
        lines += [f"Aliases: {', '.join(f'`{a}`' for a in aliases)}", ""]
    if parser.description:
        lines += [parser.description.strip(), ""]

    positionals = _positionals(parser)
    if positionals:
        lines.append("## Positional arguments")
        lines.append("")
        for a in positionals:
            help_text = (a.help or "").replace("\n", " ").strip()
            lines.append(f"- `{a.dest}`" + (f" — {help_text}" if help_text else ""))
        lines.append("")

    optionals = _optionals(parser)
    if optionals:
        lines.append("## Options")
        lines.append("")
        for a in optionals:
            lines.append(_render_action_row(a))
        lines.append("")

    lines.append("```text")
    lines.append(parser.format_usage().strip())
    lines.append("```")
    lines.append("")
    return "\n".join(lines)


def render_group_page(prog_path: list[str], parser: argparse.ArgumentParser, entries: list[tuple[str, list[str], argparse.ArgumentParser]]) -> str:
    title = " ".join(prog_path) if prog_path else "prism_tools.py"
    lines = [f"# `{title}`", ""]
    if parser.description:
        lines += [parser.description.strip(), ""]
    lines.append("## Subcommands")
    lines.append("")
    sub_action = _subparsers_action(parser)
    help_by_dest = {ca.dest: (ca.help or "") for ca in sub_action._choices_actions}
    for name, aliases, _sub in entries:
        summary = help_by_dest.get(name, "")
        link = "-".join(prog_path + [name]) + ".md"
        alias_note = f" (aliases: {', '.join(aliases)})" if aliases else ""
        lines.append(f"- [`{name}`]({link}){alias_note}" + (f" — {summary}" if summary else ""))
    lines.append("")

    # A hidden toctree of direct children, so every generated page is
    # reachable from docs/cli/index.md's chain and Sphinx never reports it
    # as an orphan -- markdown links in the bulleted list above are not
    # enough on their own (verified: Sphinx's toctree-membership check does
    # not treat a plain inline link as inclusion).
    lines.append("```{toctree}")
    lines.append(":maxdepth: 1")
    lines.append(":hidden:")
    lines.append("")
    for name, _aliases, _sub in entries:
        lines.append("-".join(prog_path + [name]))
    lines.append("```")
    lines.append("")
    return "\n".join(lines)


def walk(prog_path: list[str], parser: argparse.ArgumentParser, pages: dict[str, str], aliases: list[str] | None = None):
    sub_action = _subparsers_action(parser)
    slug = "-".join(prog_path) if prog_path else "index"
    if sub_action and sub_action.choices:
        entries = _canonical_subcommands(sub_action)
        pages[f"{slug}.md"] = render_group_page(prog_path, parser, entries)
        for name, sub_aliases, sub in entries:
            walk(prog_path + [name], sub, pages, aliases=sub_aliases)
    else:
        pages[f"{slug}.md"] = render_command_page(prog_path, parser, aliases=aliases)


def generate() -> dict[str, str]:
    # argparse derives each subparser's default `prog` from sys.argv[0] at
    # the moment the top-level parser is constructed, so without this the
    # generated usage lines would say "gen_cli_reference.py ..." instead of
    # the real entry point users actually type.
    # A few flags (e.g. `recipes surveys --repo`) default to a path derived
    # from the project_root argument. Passing the real REPO_ROOT would bake
    # this machine's absolute filesystem path into the generated docs --
    # non-portable, and a source of pure-noise diffs every time the CI
    # staleness check runs on a different runner. A clearly-symbolic
    # placeholder (still named "app" so the parser's own
    # `.name == "app"` branch behaves the same way) keeps the output
    # identical across machines.
    placeholder_root = Path("/path/to/prism-studio/app")
    real_argv0 = sys.argv[0]
    sys.argv[0] = "prism_tools.py"
    try:
        parser, _ = build_prism_tools_parsers(placeholder_root)
    finally:
        sys.argv[0] = real_argv0
    pages: dict[str, str] = {}
    walk([], parser, pages)
    return pages


def main() -> int:
    check = "--check" in sys.argv
    pages = generate()

    if check:
        stale = []
        for name, content in pages.items():
            path = OUT_DIR / name
            if not path.exists() or path.read_text() != content:
                stale.append(name)
        existing = {p.name for p in OUT_DIR.glob("*.md")} if OUT_DIR.exists() else set()
        removed = existing - set(pages.keys())
        if stale or removed:
            print("docs/cli/ is stale. Run: python scripts/gen_cli_reference.py")
            for name in stale:
                print(f"  changed: {name}")
            for name in removed:
                print(f"  should be removed: {name}")
            return 1
        print("docs/cli/ is up to date.")
        return 0

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    existing = {p.name for p in OUT_DIR.glob("*.md")}
    for name, content in pages.items():
        (OUT_DIR / name).write_text(content)
    for stale_name in existing - set(pages.keys()):
        (OUT_DIR / stale_name).unlink()
    print(f"Wrote {len(pages)} pages to {OUT_DIR}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 2: Run it**

```bash
python3 scripts/gen_cli_reference.py
```
Expected: `Wrote 62 pages to .../docs/cli` (the exact count reflects
whatever `app/src/cli/parser.py` looks like when you run this — if it
differs from 62, that's fine, it means the parser tree changed since this
plan was written, not that something is wrong).

- [ ] **Step 3: Wire the top-level toctree**

Find (in `docs/index.rst`):
```
.. toctree::
   :maxdepth: 2
   :hidden:
   :caption: CLI

   CLI_REFERENCE
   CLI_WORKFLOWS
```

Replace with:
```
.. toctree::
   :maxdepth: 2
   :hidden:
   :caption: CLI

   CLI_REFERENCE
   CLI_WORKFLOWS
   cli/index
```

- [ ] **Step 4: Verify**

Run:
```bash
python3 scripts/gen_cli_reference.py --check
cd docs && python3 -m sphinx -b html -W --keep-going . /tmp/prism_docs_build_check && echo BUILD_OK
grep -rl "/private/tmp\|/Users/" docs/cli/ 2>/dev/null; echo "(nothing above this line is expected)"
```
Expected: `docs/cli/ is up to date.`, `build succeeded.`, `BUILD_OK`, and the
last grep prints nothing. (It deliberately does not search for
`/path/to/prism-studio` — that's the intentional placeholder from
`generate()`'s `placeholder_root`, and `recipes-surveys.md` /
`recipes-biometrics.md` are expected to contain it; searching for it here
would just confirm the placeholder is present, not catch a real leak. The
real check is for an actual machine path like `/Users/<name>` or
`/private/tmp`.)

- [ ] **Step 5: Commit**

```bash
git add scripts/gen_cli_reference.py docs/cli/ docs/index.rst
git commit -m "docs: generate docs/cli/ from the prism_tools argparse tree

One page per subcommand (62 pages across 15 top-level command groups),
generated by scripts/gen_cli_reference.py directly from
app/src/cli/parser.py rather than hand-maintained -- every flag, default,
choice, and help string comes from the one place the real CLI already
defines them. Evaluated and rejected sphinx-argparse first: it fails this
repo's real help text (a lone '*' in a glob-pattern example breaks RST's
strict emphasis parsing under -W) and its markdown-mode escape hatch pulls
in the unmaintained CommonMark package -- documented in this script's
sibling plan file.

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>"
```

---

### Task 2: Add a CI staleness check

**Files:**
- Modify: `tests/verify_repo.py` (new `check_cli_reference_sync` function,
  registered in `CHECKS` and the `"fast"` profile)

**Interfaces:**
- Consumes: `scripts/gen_cli_reference.py`'s `--check` exit code from Task 1
  (shelled out to via `run_command`, matching how `check_docs_build`
  already shells out to `sphinx-build`, rather than re-implementing the
  diff logic inline).

This follows the exact pattern of the existing `check_dual_tree_drift`
function (`tests/verify_repo.py:2389`) — a same-file, no-CLAUDE.md-required
precedent for "generated/derived content must match its source, checked in
CI" — and `check_docs_build` (`tests/verify_repo.py:2088`) for the
subprocess-and-report pattern specifically.

- [ ] **Step 1: Add `check_cli_reference_sync`**

Find (immediately before the `CHECKS = {` dictionary definition, i.e. right
after the last `check_*` function in the file — this plan's step 2 below
locates that exact spot by the `CHECKS = {` line itself, so this step just
adds the new function anywhere above it; the convention in this file is one
function per check, defined before the registry):

```python
def check_cli_reference_sync(repo_path, fix=False):
    """Ensure docs/cli/*.md matches a fresh run of
    scripts/gen_cli_reference.py -- the generated CLI reference
    (docs/superpowers/specs/2026-09-12-documentation-expansion-design.md,
    Section D2) has one job: never drift from app/src/cli/parser.py."""
    print_header("Checking Generated CLI Reference (docs/cli/)")

    script = Path(repo_path) / "scripts" / "gen_cli_reference.py"
    if not script.exists():
        print_success("No scripts/gen_cli_reference.py found. Skipping.")
        return

    if fix:
        result = run_command(f'python3 "{script}"', cwd=repo_path)
        if result and result.returncode == 0:
            print_success("Regenerated docs/cli/ from app/src/cli/parser.py.")
        else:
            print_error("Failed to regenerate docs/cli/.")
        return

    result = run_command(f'python3 "{script}" --check', cwd=repo_path)
    if result and result.returncode == 0:
        print_success("docs/cli/ matches app/src/cli/parser.py.")
    else:
        print_error(
            "docs/cli/ is stale -- run: python scripts/gen_cli_reference.py "
            "and commit the result."
        )
        if result and result.stdout:
            for line in result.stdout.splitlines():
                print_info(f"  {line}")
```

Add it to the file now (paste it just above the `CHECKS = {` line).

- [ ] **Step 2: Register it**

Find:
```python
CHECKS = {
    "git-status": check_git_status,
```

Replace with:
```python
CHECKS = {
    "git-status": check_git_status,
    "cli-reference-sync": check_cli_reference_sync,
```

- [ ] **Step 3: Add it to the fast profile and the fix-support set**

Find:
```python
        "dual-tree-drift",
        "library-uniqueness",
        "unsafe-patterns",
```

Replace with:
```python
        "dual-tree-drift",
        "cli-reference-sync",
        "library-uniqueness",
        "unsafe-patterns",
```

Find:
```python
CHECKS_SUPPORT_FIX = {
    "secrets",
```

Replace with:
```python
CHECKS_SUPPORT_FIX = {
    "cli-reference-sync",
    "secrets",
```

- [ ] **Step 4: Verify the check passes on the just-generated tree, and correctly fails when stale**

Run:
```bash
python3 tests/verify_repo.py --check cli-reference-sync --no-fix
```
Expected: passes (Task 1 already generated a fresh, matching `docs/cli/`).

Then deliberately stage a staleness to confirm the check actually catches
it:
```bash
echo "stale test" >> docs/cli/index.md
python3 tests/verify_repo.py --check cli-reference-sync --no-fix
git checkout -- docs/cli/index.md
```
Expected: the first run fails with "docs/cli/ is stale", naming
`index.md`; the checkout restores the generated file so the working tree
is clean again afterward — confirm with `git status --short docs/cli/`
(nothing printed).

- [ ] **Step 5: Commit**

```bash
git add tests/verify_repo.py
git commit -m "test: add cli-reference-sync check for docs/cli/ staleness

Matches the dual-tree-drift / docs-build check pattern already in this
file: shells out to scripts/gen_cli_reference.py --check and fails if the
committed docs/cli/ tree doesn't match a fresh run. Added to the fast
profile since it's cheap (pure argparse introspection, no I/O beyond
reading the committed files) and to CHECKS_SUPPORT_FIX so --fix
regenerates it automatically.

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>"
```

---

### Task 3: Link the hand-written CLI docs into the generated reference

**Files:**
- Modify: `docs/CLI_REFERENCE.md` (add a pointer near the top)
- Modify: `docs/CLI_WORKFLOWS.md` (add a pointer near the top)

**Interfaces:**
- Consumes: `docs/cli/index.md` from Task 1.

Per the spec: "`CLI_REFERENCE.md` and `CLI_WORKFLOWS.md` stay hand-written
as the narrative layer above the generated pages, and link into them." This
task is the linking half of that — small and self-contained.

Checked both files' actual current openings first (verified 2026-09-12, not
assumed): `CLI_REFERENCE.md` already positions itself as "the detailed
command reference" and already points to `CLI_WORKFLOWS.md` as the guided
narrative — so the generated pages are a third, more mechanical layer
*beneath* `CLI_REFERENCE.md`'s curated tables, not a replacement for the
"reference vs. narrative" split that already exists between these two
files. Word the pointer accordingly: "exhaustive and always-current, but
unexplained" under "curated and explained."

- [ ] **Step 1: Add a pointer to `docs/CLI_REFERENCE.md`**

Find:
```
# CLI & Script Reference

The detailed command reference for PRISM's terminal surfaces. Reference-first — for
a guided narrative use [CLI Workflows](CLI_WORKFLOWS.md), for a guided first success
[Getting Started](TUTORIAL_BEGINNER.md), for schema context [Specifications](SPECIFICATIONS.md),
for scoring-definition details [Recipes](RECIPES.md).
```

Replace with:
```
# CLI & Script Reference

The detailed command reference for PRISM's terminal surfaces. Reference-first — for
a guided narrative use [CLI Workflows](CLI_WORKFLOWS.md), for a guided first success
[Getting Started](TUTORIAL_BEGINNER.md), for schema context [Specifications](SPECIFICATIONS.md),
for scoring-definition details [Recipes](RECIPES.md).

For every flag, default, and choice on every subcommand — generated
directly from the code, so it can't drift the way this page's curated
tables could — see the [generated CLI reference](cli/index.md). This page
stays the curated, explained version; that one is the exhaustive one.
```

- [ ] **Step 2: Add the same pointer to `docs/CLI_WORKFLOWS.md`**

Find:
```
For working from the terminal rather than the Studio web interface — best for
automation, CI/batch validation, reproducible scripted workflows, and terminal-first
users. PRISM remains an add-on to BIDS in the CLI path just as it does in Studio.

If you're new to this: activate the environment → validate a dataset → inspect or
generate templates/recipes only as needed → automate once the manual commands are
understood.
```

Replace with:
```
For working from the terminal rather than the Studio web interface — best for
automation, CI/batch validation, reproducible scripted workflows, and terminal-first
users. PRISM remains an add-on to BIDS in the CLI path just as it does in Studio.

For the full, always-current list of every flag, default, and choice per
command, see the [generated CLI reference](cli/index.md).

If you're new to this: activate the environment → validate a dataset → inspect or
generate templates/recipes only as needed → automate once the manual commands are
understood.
```
(leave the matched text itself unchanged; add the following as a new
paragraph immediately after the opening paragraph ends)
```
For the full, always-current list of every flag, default, and choice per
command, see the [generated CLI reference](cli/index.md).
```

- [ ] **Step 3: Verify**

Run:
```bash
cd docs && python3 -m sphinx -b html -W --keep-going . /tmp/prism_docs_build_check && echo BUILD_OK
grep -c "cli/index" /tmp/prism_docs_build_check/CLI_REFERENCE.html /tmp/prism_docs_build_check/CLI_WORKFLOWS.html
```
Expected: `build succeeded.`, `BUILD_OK`, nonzero counts in both files.

- [ ] **Step 4: Commit**

```bash
git add docs/CLI_REFERENCE.md docs/CLI_WORKFLOWS.md
git commit -m "docs: link CLI_REFERENCE and CLI_WORKFLOWS to the generated reference

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>"
```

---

## Plan-level verification

```bash
python3 scripts/gen_cli_reference.py --check
python3 tests/verify_repo.py --check cli-reference-sync --no-fix
cd docs && python3 -m sphinx -b html -W --keep-going . /tmp/prism_docs_build_check && echo BUILD_OK
```

Expected: all three pass. As a final sanity check, open three or four
generated pages at random (`docs/cli/*.md`) and compare them against
running the real commands with `--help` (e.g.
`python prism_tools.py survey export-pavlovia --help`) — the generated
page's flags, defaults, and choices should match exactly, since they come
from the same argparse objects.
