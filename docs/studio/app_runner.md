# PRISM App Runner

At `/prism-app-runner`. Intended to let you run BIDS Apps (containerized pipelines
like fMRIPrep) directly against a PRISM project. **It is currently disabled** — this
is a real, deliberate feature flag in the code
(`PRISM_APP_RUNNER_ENABLED = False` in
`tools_prism_app_runner_handlers.py`), not a bug or a partial rollout you're seeing by
accident. Every API call this screen would make returns HTTP 503 while the flag is
off.

## What you'll see today

The full form renders, but everything interactive is wrapped in a disabled
`<fieldset>` with a banner: *"PRISM App Runner is temporarily unavailable... PRISM
App Runner is temporarily disabled while under construction."* You can look at the
layout, but you can't run anything.

## What it's designed to do (once enabled)

- **Integration Scope** panel — checks for a Docker runtime, runner config shape
  (`common`/`app`, optional `hpc`), and flags BIDS-compatibility concerns in output
  paths.
- **1. Data Locations** — BIDS Dataset Folder, Output Folder, Work/Temp Folder,
  Templateflow path, FreeSurfer License.
- **2. Container Settings** — Docker repo/tag (with fetch/pull), BIDS App Name,
  Analysis Level, Log Level, Subjects, Jobs, Timeout, Dry Run.
- **3. App-Specific Arguments** — a JSON options field, container help output,
  detected flags.
- Hidden panels for HPC / DataLad / Remote SSH execution.
- Primary action: **Prepare + Run with Active PRISM Project**.

There's no per-user or per-project toggle for this — enabling it requires a code
change, not a settings change.

## What's next

- [Recipe Builder](recipe_builder.md) and [Export](export.md) for derivatives that
  don't require this screen
