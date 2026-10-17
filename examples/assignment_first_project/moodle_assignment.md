# Assignment: Your first PRISM project

**Goal:** Create a PRISM project, fill in its metadata, and import a sociodemographics table with proper annotation.

**Prerequisite:** PRISM Studio is installed and starts (http://localhost:5001). If not, see the installation chapter of the Getting Started tutorial first.

## Choose one

- **Option A (own project):** Use a study of your own, or one you are planning. You need a title, at least 3 keywords, authors, and a table with sociodemographic data (at least age, sex, handedness).
- **Option B (fictive project):** Use the FitCog study. Download the folder `assignment_first_project` (attached) with these files:
  - `project_metadata.html`: the metadata to enter
  - `sociodemographics.tsv`: 300 participants
  - `codebook.tsv`: what each column and code means

## Task a) Create the project and fill in the metadata

1. Open **Create or Open a Project**, then **Create New Project**.
2. Enter project name and location (DataLad off).
3. Fill in the **Study Metadata** card: at least Dataset Name, Authors (one corresponding, with email). Option B: you are the corresponding author, and Karl Koschutnig is co-author. Use the ORCID lookup button to search for his name and 3 or more Keywords. Also answer Ethics and Funding. (Option B: copy everything from `project_metadata.html`.)
4. Click **Create Project** (not Preliminary Save).
5. Open the created folder and check that `dataset_description.json` contains your title and authors.

## Task b) Import the sociodemographics

1. Go to **Prepare Data > Converter > Sociodemographics** and upload your table (Option B: `sociodemographics.tsv`).
2. Click **Review Participant Fields**.
3. The table contains columns that do not belong into the dataset (Option B: `data_entry_clerk` and `spreadsheet_row_check`). **Do not include them.** Only age, sex and handedness are detected automatically; add the other wanted columns (Option B: `iq`, `vo2max`) with **Add More Columns (Optional)**, and leave the unwanted ones out.
4. In the **Participant Annotation** panel, link the columns to NeuroBagel terms where one exists (age, sex, handedness) and harmonize the coded values to NeuroBagel labels (Option B: use `codebook.tsv`, e.g. sex 1 = Female, 2 = Male, 3 = Other). Give the unit for age (years). For columns without a NeuroBagel term, write a short description instead.
5. (Option B) In the same panel, select the **Eligibility criterion** *Age* for the `age` column. It is pre-selected once `age` is mapped to the NeuroBagel term Age; check it. Your own project: first add a *Checked Criteria* row in the Study Metadata (Eligibility section).
6. Click **Create Participant Files**.
7. Run the validator on your project. Change one age in `participants.tsv` to 17, run it again, and note the warning (`PRISM602`). Then change it back.

## What to hand in

Upload as one ZIP, or as separate files:

1. `dataset_description.json` from your project
2. `participants.tsv`
3. `participants.json`
4. A screenshot of the Participant Annotation panel after mapping
5. The validator warning text for the age you changed to 17

## How it is checked

- `dataset_description.json`: name, 2 or more authors (Option B), one corresponding author with email, 3 or more keywords
- `participants.tsv`: one row per participant (Option B: 300 rows) and **no** dummy columns
- `participants.json`: every column has a description; age has unit years; sex and handedness have labelled levels and NeuroBagel terms
- `participants.json`: age carries `EligibilityCriterion` (a link only; the limits stay in the project metadata)
- Codes are not changed in the table: `1` stays `1`, its meaning lives in the JSON

## Tips

- Project names: letters, numbers, `_` and `-` only.
- Imported IDs get the prefix `sub-` (P001 becomes sub-P001). This is expected.
- Hint on the Participants page about identical rows: only appears if too few columns are selected. Check that iq and vo2max are included.
- Stuck? Chapters 1 and 2 of the Getting Started tutorial walk through exactly these steps.
