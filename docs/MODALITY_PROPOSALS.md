# Proposing a New Modality

PRISM describes data belonging to a subject as a data file plus a JSON sidecar.
Surveys, biometrics, physiology and the other modalities all follow this
principle, and so can yours (for example blood samples drawn alongside MRI).

New modalities are added to PRISM itself: you propose one, a maintainer
registers it, and it ships with the next release.

## What you need

1. The workbook `official/create_new_modality/modality_proposal_template.xlsx`
   (it opens in Excel, LibreOffice and Numbers).
   - Sheet `Modality`: `Name`, `Suffix`, `Extensions`, `Description`, `Rationale`.
   - Sheet `Types` (optional): a short vocabulary of the measurements your
     modality knows (for example CRP, glucose, cortisol), each with a
     description. A column can then carry a `Type` from this list or `other`, so
     the same measurement gets the same name across studies even when column
     names differ. New types are added later through an upstream pull request.
   - Sheet `Columns`: the columns of your **sample file**, as an example (two or
     three are enough; every study defines its own columns in its own sidecar),
     with `ID`, `Description`, `Units`, `DataType` (string, integer or float;
     guessed if empty), `Scale` (optional drop-down: categorical, continuous or
     boolean; leave empty for identifiers, times and free text), `Type`
     (optional, from the `Types` sheet or `other`), `Min`, `Max`,
     `AllowedValues` (separated by `;`). A continuous column must be a number
     without `AllowedValues`, a categorical column needs its categories in
     `AllowedValues`, a boolean column needs exactly two (for example `yes; no`).
2. A small **synthetic** sample data file in the same format as your real data:
   at most 50 rows and 1 MB. Its header must match the `Columns` sheet. Never
   use real participant data.

## Choosing a name and suffix

Both must be lowercase letters and digits, starting with a letter, and must
not already be used by PRISM or BIDS. `blood` for example is a BIDS suffix
(blood radioactivity in PET). The check tells you what a taken name means.

## Submit it

**On GitHub:** open a *Propose a New Modality* issue, drag in the workbook and
the sample file, tick the privacy box. A bot is meant to check both and open a
draft pull request (automatically only when the issue author is an owner,
member or collaborator of the repository; otherwise a maintainer takes it from
here), or comment what to fix (then open a new issue with the corrected files). Note: this bot has not yet run on a real issue.

**From the command line:**

    python prism_tools.py modality propose my_proposal.xlsx --sample my_sample.tsv --check
    python prism_tools.py modality propose my_proposal.xlsx --sample my_sample.tsv --out my_modality

`--check` only validates. The second command writes the schema, an example
sidecar, a small dataset to test with, and `REGISTRATION.md`. YAML or JSON can
be used instead of the workbook (see `examples/modality_proposal/`).

## What happens next

A maintainer follows `REGISTRATION.md` (copy the schema, add the modality to
`entities.schema.json`, run the checks) and reviews units, ranges and the
sample. After the merge the modality is available in the next PRISM release.
GitHub does not start CI from the bot's own push; a maintainer starts it by
approving the run or pushing. While the pull request only adds files under
`proposals/`, CI runs a reduced set (repo checks plus
`tests/test_modality_proposal_fixtures.py`) and skips the docs build and the
cross-platform tests. The fixture test stays red until the modality is
registered; the maintainer's registration push touches other files and runs the
full CI.

## For maintainers

- The label `type: new-modality` must exist in the repository (the issue form
  applies it; if it is missing the bot never starts).
- The repository setting "Allow GitHub Actions to create and approve pull
  requests" must be on for the bot to open PRs; otherwise open the PR by hand
  from the pushed branch.
- PRs are opened automatically only for OWNER, MEMBER and COLLABORATOR authors.
- Do not open a contributor's original `.xlsx` in desktop Excel (formulas or
  external links); review the generated JSON instead.
- The bot has not run on a real issue yet. On the first real run check that
  GitHub accepts `.tsv`/`.yml` attachments, that the artifact handoff between
  the two jobs works and that the PR is created.
- Registration also means adding the name to `COMMUNITY_MODALITY_SCHEMAS` in
  `tests/verify_repo.py` (the generated `REGISTRATION.md` lists this step).
