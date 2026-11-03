# Projects

The Projects page is the entry point for creating, opening, and re-opening PRISM
Studio projects.

![PRISM Studio Projects screen](../_static/screenshots/prism-studio-projects.png)

## Goal

Get a project created or loaded so the rest of Studio (Converter, Validator,
Template Editor, Recipe Builder, Share/Export) has something to work against.

## Entry points

The page shows three cards:

- **Create New Project** — start a brand-new project from scratch.
- **Init PRISM on BIDS Dataset** — add PRISM's project files to a BIDS dataset that
  already exists, without overwriting anything already there.
- **Open Existing Project** — load a project you (or a collaborator) already created.

## Creating a new project

Fields on the **Create New Project** form:

- **Project Name** — required, letters/numbers/`_`/`-` only, no spaces. The field
  validates live as you type and explains specifically what's wrong (e.g. flags
  spaces or German umlauts/`ß` by name) rather than just turning red.
- **Project Location** — the parent folder the new project directory is created in.
- **Use DataLad version control for this new project** — optional checkbox. If
  DataLad/git-annex aren't installed, project creation silently falls back to a
  non-DataLad project rather than failing. The switch starts on when the setting
  *DataLad for new projects* (Settings page) is on; it is off by default. Only the question
  is shown until you switch it on; then the explanation, the availability status and
  *Check DataLad setup* open below it.

Choosing **Create New Project** opens **Study Metadata**. **Create Project** stays grey
until the required fields are filled in: dataset name, an author (with email), three
keywords and the timepoints. The score row at the top (Required / Core / FAIR) shows
how far you are, and the button's hint names what is still missing.

There is no modality or session picker at creation time — modalities and sessions are
no longer chosen up front; they're populated as you actually import data.

### Importing from a study application

If **MRI-Lab Graz study application import** is enabled on the **Settings** page (gear icon in the navbar), the
Study Metadata card (shown for both **Create New Project** and **Init PRISM on
BIDS Dataset**) gets an **Import from study application (survey.json)** file
button that prefills PI/author/ethics/funding/study fields from a Pavlovia
study-application export. This format is specific to MRI-Lab Graz's intake
survey, so the toggle is off by default; external users can leave it off and
fill in Study Metadata by hand.

A hint beside the button says why it is grey and names the required fields still missing.

There is no preliminary save: **Create Project** (and **Save** for a loaded project)
waits for the required fields and names the ones still missing.

### Checked eligibility criteria

In **Study Metadata > Eligibility**, *Checked Criteria* holds limits the validator
tests against `participants.tsv`. Choose from the **Add variable** list: a standard term (Age, Sex, Handedness,
Group, Diagnosis, Education level) or **Other measure** (IQ, VO2max, ...), choose
**include** or **exclude**, then give a range (numeric, inclusive, either end may
stay empty) or the category labels. Enter the limits here only once: in the
[Sociodemographics converter](converter_participants.md) you just link a column
to the criterion. Participants outside a limit get a warning (`PRISM602`), never
an error, so you can validate while data collection is still running.

Rows follow the rule described under [Adding rows](#adding-rows-the-green-check-and-the-red-cross).
Accepted criteria count towards the Core fields: an *include* criterion satisfies
**Inclusion Criteria**, an *exclude* criterion **Exclusion Criteria**.

### Adding rows: the green check and the red cross

Everywhere on the Study Metadata form that you add a row (authors, funding, the
criteria and list fields, known issues, missing files, DOIs, checked criteria) the
same rule applies, so you always know whether a click is needed:

- A **new row is a draft** with a check mark and a gray **Cancel**. The check is gray
  and disabled while the row is empty or incomplete (for example without both author
  names), and a short hint says what is missing. It turns green as soon as the row
  can be accepted.
- **Click the green check to accept the row.** Only now does it count: it is saved,
  it feeds the badges and the readiness score, and it shows the **red cross**, which
  deletes it. A red cross always means "delete something that is already part of the form".
- A row with a check mark needs a click; a row without one never does.
- **Plain list fields** (independent, dependent and control variables, quality assessment,
  inclusion and exclusion criteria, quality control) have one input instead of rows: type
  an entry, press Enter or click the check, and it becomes a **green chip** below the
  input, like the CRediT roles. Click a chip to remove it; duplicates are ignored. Text
  that is typed but not accepted blocks saving.
- **Funding, known issues, missing files, recruitment locations and checked criteria**
  work the same way: one entry row (the agency and grant, the file and the issue, subject
  to detail, the location search, or the criterion), and every accepted entry becomes a
  green chip with a short summary, for example `FWF, P12345`, `sub-002_bold.nii – Shorter
  scan` or `Age · include 18–35 years`. To change an entry, remove its chip and add it
  again. A checked criterion that you remove and add again in the same editing session (same
  variable and name) gets its old id back, so a column linked to it in the Sociodemographics
  converter stays linked. Only authors stay as cards, because each author carries many details.
- **Errors link to their field.** In the *Dataset description issues* box, a message that
  names a field you can fill in (Name, Authors, Keywords, Funding, Ethics) is a link: click
  it and the page opens that section and focuses the field.
- Rows that are already in the project when you open it are accepted.
- The recruitment-location search works the same way: its green **Add Selected Location**
  button accepts the place you searched for.
- **You cannot save while a draft with content is pending.** Create Project and
  Save are blocked, the pending rows get a yellow outline, and a message says to
  click the green check or Cancel. A completely empty draft is simply dropped.

### What gets created

```text
my_first_study/
├── dataset_description.json
├── .bidsignore
├── .prismrc.json
├── README.md
├── project.json
├── CITATION.cff
├── CHANGES
├── .gitattributes        (only if the DataLad text-tracking policy write succeeds)
├── sourcedata/
├── derivatives/
└── code/
    ├── library/
    └── recipes/
```

`participants.tsv` and `participants.json` are **not** created here — they're written
later, once you run the participants/sociodemographics import step (see
[Converter — Participants](converter_participants.md)).

The generated `README.md` describes this same layout and points you at `sourcedata/`,
`code/library/`, and `code/recipes/` for the next steps.

## Init PRISM on BIDS Dataset

Same file set as project creation, but only for files that don't already exist —
nothing your existing BIDS dataset already has gets overwritten. If the dataset has a
legacy `phenotype/` directory, it's auto-imported as part of this step.

The project is named after the dataset (`Name` in `dataset_description.json`); there is
no separate name field. If the dataset brings its own `CITATION.cff`, its authors,
keywords, DOI, license and abstract are taken into the still-empty project fields, so a
later *Regenerate citation* does not replace them with placeholders. The file is
rewritten in PRISM's format only when nothing in it is lost; otherwise it stays as it
came and the log says why. The dataset's own `README.md` text is kept below the
generated README.

## Recent projects

The last 20 projects you opened are remembered. The page shows the 5 most recent;
older ones are in a pull-down.

## Settings

Global settings (libraries, monitoring, terminal, study-application import, beginner
help mode, DataLad for new projects, and the DataLad card of the loaded project) live on
their own **Settings** page (gear icon in the navbar). On the command line:
`prism_tools.py settings show|set`.

![PRISM Studio Settings page](../_static/screenshots/prism-studio-settings.png)

## Time or content sessions

A project declares whether its sessions follow time or content (`SessionLabels`). In a
content project each participant has a session order file, and date-numbered sessions
are named from it. Edit the order on the project page's Sessions section or with the
`session-order` commands (see the [CLI reference](../CLI_REFERENCE.md)).

## Deleting a project

A **Delete Project** button appears once a project is created or loaded (in the
project-created panel and in the loaded-project panel). Deletion is permanent and
irreversible — it removes the entire project folder from disk, including DataLad/git
history and derivatives.

To prevent accidental deletion, the confirmation dialog requires you to type the
project's exact name before the delete button enables. On confirmation, Studio clears
the project from your current-project and recent-projects state and returns you to the
Projects page.

There is still no "trash"/undo — deletion goes straight to the filesystem. If you want
a safety net, make sure the project is backed up (e.g. pushed to a DataLad sibling)
before deleting it here.

## Generate Methods Section

The **Generate Methods Section** card writes a paper-ready Methods text from
`project.json`, `dataset_description.json`, the linked templates **and the data in the
project**: sessions and instrument counts per session, survey language, version and
completion time, session timing (from `SurveyStartDate` or `acq_time`), scoring
recipes and sidecar acquisition parameters. Only participants that have data count
as the sample; screening-only participants are reported separately. Gaps (no sample
size, an instrument without a citation) are flagged, never invented.

Pick a **Detail Level** (Brief / Standard / Detailed), press **Generate**, then
download `.md`, `.html`, Word (`.docx`), TeX (`.tex`, citing the instruments via
natbib) or the references as BibTeX (`.bib`). CLI: `prism_tools.py methods generate`
([CLI Reference](../CLI_REFERENCE.md#methods-section-and-preregistration-draft)).

## Preregistration (optional)

The **Preregistration** block in the study metadata holds what a preregistration needs
beyond design and sample: data status, hypotheses, primary and secondary outcomes and
the analysis plan. **Download draft** produces a Markdown draft in AsPredicted question
order (also Word and TeX). It is a draft only, not a registration: register it at OSF
or AsPredicted to get a time-stamped, frozen version. Save the metadata first so
recent edits are included. CLI: `prism_tools.py preregistration draft`.

## Opening an existing project

The **Open Existing Project** form takes a single path, and accepts either:

- the project's root folder, or
- the path to its `project.json` file directly.

Submitting validates the project's structure, sets it as your active project for the
rest of Studio, and remembers it as your last-opened project.

A **Recent Projects** list (with a **Clear** button) tracks projects you've opened
before, de-duplicated by their resolved absolute path.

Each project gets a small emoji icon (e.g. 🧬) assigned the first time it's created
or loaded. It's chosen at random from a fixed set and then persisted into that
project's `project.json`, so it stays the same on every later load; it's shown next
to the project's name in Recent Projects and in the header once loaded, purely as a
visual identifier with no other meaning.

## What's next

- [Studio Guide overview](index.md)
- [Survey Import](converter_survey.md) or [Participants Import](converter_participants.md) to bring in your first data
- [Share / Export](export.md) once you have something to export
