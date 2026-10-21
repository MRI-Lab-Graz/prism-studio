# Assignment: Your first PRISM project

**Goal:** Create a PRISM project, fill in its metadata as completely as you can, import a sociodemographics table with proper annotation, and validate the project.

**Prerequisite:** PRISM Studio should already be installed on your computer. Before you start, **install the latest version**:

1. Open the [PRISM Studio repository](https://github.com/MRI-Lab-Graz/prism-studio), click **Code > Download ZIP** (source code), and extract it into a new folder (do not reuse an old copy).
2. Run the installer in the extracted folder: macOS/Linux `./install.sh` (or `bash install.sh`), Windows double-click `install.cmd`. It sets everything up and starts PRISM Studio (http://localhost:5001). For later sessions use the **PRISM Studio** shortcut it creates.

Older versions can behave differently from this description. Problems: installation chapter of the Getting Started tutorial.

## Choose one

- **Option A (own project):** Use a real study of your own, or one you are planning (or invent one). You need a title, at least 3 keywords, authors, and a table with sociodemographic data (at least age, sex, handedness).
- **Option B (fictive project):** Use the FitCog study. Download the folder `assignment_first_project` (attached) with these files:
  - `project_metadata.html`: the metadata to enter
  - `sociodemographics.tsv`: 300 participants
  - `codebook.tsv`: what each column and code means

## Task a) Create the project and fill in the metadata

1. Open **Create or Open a Project**, then **Create New Project**.
2. Enter project name and location (DataLad off).
3. Fill in the **Study Metadata** card **completely**. Do not stop at the required fields: open every collapsed section and fill in everything you can, with as much detail as you have (Overview, Study design, Recruitment, Eligibility with inclusion/exclusion criteria, the age limits and a *Checked Criteria* row, Procedure, Sample size and power analysis, Preregistration, Ethics, Funding, Discovery & Citation, Missing data, Background literature, and any other field). An empty optional field counts as missing information.
   - Authors: one corresponding author with email. Use the ORCID lookup button where you can.
   - At least 3 keywords.
   - Option B: you are the corresponding author, and Karl Koschutnig is co-author (find his ORCID with the lookup button). Copy **everything**, including the "Optional" sections, from `project_metadata.html`.
   - Option A (own or invented project): write the texts yourself. Short sentences are fine, but every field should say something concrete.
4. Click **Create Project** (not Preliminary Save).
5. Open the created folder and check that `dataset_description.json` contains your title and authors.

## Task b) Convert and annotate the sociodemographics

1. Go to **Prepare Data > Converter > Sociodemographics** and upload your table (Option B: `sociodemographics.tsv`).
2. Click **Review Participant Fields**.
3. The table contains columns that do not belong into the dataset (Option B: `data_entry_clerk` and `spreadsheet_row_check`). **Do not include them.** Only age, sex and handedness are detected automatically; add the other wanted columns (Option B: `iq`, `vo2max`) with **Add More Columns (Optional)**, and leave the unwanted ones out.
4. In the **Participant Annotation** panel, **annotating for NeuroBagel is mandatory**: link the columns to NeuroBagel terms where one exists (age, sex, handedness) and harmonize the coded values to NeuroBagel labels (Option B: use `codebook.tsv`, e.g. sex 1 = Female, 2 = Male, 3 = Other). Give the unit for age (years). For columns without a NeuroBagel term, write a short description instead.
5. (Option B) In the same panel, select the **Eligibility criterion** *Age* for the `age` column. It is pre-selected once `age` is mapped to the NeuroBagel term Age; check it. Your own project: first add a *Checked Criteria* row in the Study Metadata (Eligibility section).
6. Click **Create Participant Files**.

## Task c) Validate the project

1. Run the validator on your project and read the result. Fix anything it reports as an error.
2. Change one age in `participants.tsv` to 17, run the validator again, and note the warning (`PRISM602`). Then change it back and validate once more: the warning must be gone.

## What to hand in

Upload as one ZIP, or as separate files:

1. `dataset_description.json` from your project
2. `participants.tsv`
3. `participants.json`
4. A screenshot of the Participant Annotation panel after mapping
5. The validator warning text for the age you changed to 17
6. A screenshot of the final validator result (after changing the age back)

## How it is checked

- `dataset_description.json`: name, 2 or more authors (Option B), one corresponding author with email, 3 or more keywords, and every section filled (overview, design, recruitment, eligibility with age limits, procedure, sample size, preregistration, ethics, funding, citation, literature)
- Final validator screenshot shows no errors
- `participants.tsv`: one row per participant (Option B: 300 rows) and **no** dummy columns
- `participants.json`: every column has a description; age has unit years; sex and handedness have labelled levels and NeuroBagel terms
- `participants.json`: age carries `EligibilityCriterion` (a link only; the limits stay in the project metadata)
- Codes are not changed in the table: `1` stays `1`, its meaning lives in the JSON

## Tips

- Project names: letters, numbers, `_` and `-` only.
- Imported IDs get the prefix `sub-` (P001 becomes sub-P001). This is expected.
- Hint on the Participants page about identical rows: only appears if too few columns are selected. Check that iq and vo2max are included.
- Stuck? Chapters 1 and 2 of the Getting Started tutorial walk through exactly these steps.
