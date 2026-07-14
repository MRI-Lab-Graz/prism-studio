# Validator

Use the Validator to check whether a project or dataset is structurally sound,
schema-complete, and optionally BIDS-compatible.

Validation is the step that turns a set of imported files into something you can
trust, share, or build analysis workflows on.

For the broader workflow map, see [STUDIO_OVERVIEW.md](STUDIO_OVERVIEW.md).

## What the Validator checks

Depending on the data you provide and the options you choose, validation can
check:

- required dataset files
- filename structure and entities
- sidecar presence
- JSON syntax and schema requirements
- modality-specific metadata
- optional BIDS expectations alongside PRISM expectations

## When to validate

Run validation after any meaningful structural step, especially after:

- creating a new project
- importing participants data
- importing survey or biometrics data
- editing templates or sidecars
- preparing an export-ready dataset

Validation should be a loop, not a final one-time button press.

## Run validation in Studio

1. Open **Validator**.
2. Choose the current project or an alternative folder.
3. Start the validation run.
4. Review findings by severity and file.

Full validation (PRISM + BIDS) runs by default — you don't need to opt in to BIDS
checks. Open **Advanced Options** if you want to narrow the scope: validation-mode
radios let you switch to PRISM Only or BIDS Only, there's a `bids_warnings` checkbox
to surface BIDS warnings (hidden by default), and a schema-version selector and
library-path field for less common setups.

If a project is already active, the correct path is often pre-filled, but you
should still verify it before starting. After a run, the results page also offers a
re-validate mode selector, a download-report option, and cleanup — not just the
severity list.

## Run validation from the CLI

Basic examples:

```bash
prism-validator /path/to/project
prism-validator /path/to/project --bids
prism-validator /path/to/project --fix
prism-validator /path/to/project --fix --dry-run
prism-validator /path/to/project --json-pretty
```

Machine-readable output formats are also available, for example:

```bash
prism-validator /path/to/project --format sarif > results.sarif
prism-validator /path/to/project --format markdown > results.md
```

Use [CLI_REFERENCE.md](CLI_REFERENCE.md) for the fuller command surface.

## PRISM validation vs BIDS validation

These are complementary, not competing, checks.

| Question | PRISM | BIDS |
|---|---|---|
| Are the psychology-specific files and metadata valid? | Yes | Usually no |
| Are standard BIDS-compatible structures still acceptable? | Yes | Yes |
| Should I use both when possible? | Usually yes | Usually yes |

Useful mental model:

- use **PRISM** to validate the psychology-specific structure and metadata
- use **BIDS** to confirm compatibility with the broader BIDS ecosystem

## How to read the results

### Severity levels

| Level | Meaning | Typical response |
|---|---|---|
| Error | Blocking problem | Fix before calling the dataset valid |
| Warning | Important issue | Fix before publication or handoff when possible |
| Suggestion | Improvement | Use when polishing or standardizing the dataset |

### Good first-pass reading order

1. Fix path-wide or naming problems first.
2. Fix missing required files or sidecars.
3. Fix schema-required metadata.
4. Review warnings and suggestions after the blocking issues are gone.

This order usually prevents you from spending time polishing a file that will be
renamed or restructured anyway.

## Example validation loop

Example project state:

- participant files were just imported
- survey files were just written from `wellbeing.xlsx`

Suggested loop:

1. Run validation with BIDS enabled.
2. Open the first blocking errors.
3. Fix missing or malformed sidecars.
4. Re-run validation.
5. Move on to warnings only after the dataset is structurally correct.

This is the normal workflow. A first validation run that reports several issues
is not a failure; it is the feedback step that tells you what to clean next.

## Common result types

| Example code | Meaning | Typical next action |
|---|---|---|
| `PRISM101` | Missing sidecar JSON | Add the matching sidecar or a valid inherited one |
| `PRISM102` | Invalid JSON syntax | Fix the JSON structure first |
| `PRISM201` | Invalid filename | Rename to the expected PRISM or BIDS pattern |
| `PRISM301` | Missing required metadata field | Complete the required schema field |

For the full catalog, use [ERROR_CODES.md](ERROR_CODES.md).

## Auto-fix: use it carefully

Auto-fix is a helper for supported issues, not a substitute for understanding the
problem.

Use auto-fix when:

- the issue is clearly mechanical
- the proposed change matches your intent
- you are comfortable re-running validation immediately after

Do not assume every issue is fixable. Many findings still require a deliberate
metadata or structural decision.

CLI examples:

```bash
prism-validator /path/to/project --fix
prism-validator /path/to/project --fix --dry-run
```

The `--dry-run` form is the safer first check when you want to see what would
change.

## Output modes for reports and CI

Use machine-readable or report-style outputs when you need validation artifacts.

Examples:

```bash
prism-validator /path/to/project --json-pretty > results.json
prism-validator /path/to/project --format sarif > results.sarif
prism-validator /path/to/project --format junit > results.xml
prism-validator /path/to/project --format markdown > results.md
prism-validator /path/to/project --format csv > results.csv
```

## Common mistakes

### Validating the wrong path

If the wrong project or folder is selected, the findings may be meaningless for
the work you just completed. Confirm the active path before every run.

### Treating warnings as unimportant forever

Warnings are often what turns a technically passable dataset into a reusable one.

### Using validation only once at the end

Frequent validation is usually faster than one huge cleanup at the end of the
workflow.

## Related pages

- [ERROR_CODES.md](ERROR_CODES.md)
- [PROJECTS.md](PROJECTS.md)
- [CONVERTER.md](CONVERTER.md)
- [STUDIO_OVERVIEW.md](STUDIO_OVERVIEW.md)
- [CLI_REFERENCE.md](CLI_REFERENCE.md)
