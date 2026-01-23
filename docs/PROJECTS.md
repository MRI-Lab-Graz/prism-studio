# Projects

Detailed documentation for project management in PRISM Studio.

```{note}
This page is under construction. For now, see [Studio Overview](STUDIO_OVERVIEW.md) for project basics.
```

## Creating Projects

→ See [Studio Overview - Projects Page](STUDIO_OVERVIEW.md#projects-page)

## Project Structure (YODA)

PRISM projects follow the [YODA principles](https://handbook.datalad.org/en/latest/basics/101-127-yoda.html):

```
my_study/
├── rawdata/                    # ← PRISM validates here
│   ├── dataset_description.json
│   ├── participants.tsv
│   ├── participants.json
│   └── sub-001/
│       └── survey/
│           └── sub-001_task-*_survey.tsv
├── code/                       # Analysis scripts
├── analysis/                   # Results and derivatives
├── project.json               # Project metadata
├── contributors.json          # Team information
└── CITATION.cff               # Citation file
```

## Dataset Description

The `rawdata/dataset_description.json` file is required and contains:

```json
{
  "Name": "My Study Title",
  "BIDSVersion": "1.9.0",
  "DatasetType": "raw",
  "Authors": ["FirstName LastName"],
  "License": "CC-BY-4.0"
}
```

## Participants Files

### participants.tsv

Tab-separated file with one row per participant:

```
participant_id	age	sex	handedness
sub-001	25	F	R
sub-002	30	M	L
```

### participants.json

Describes the columns in participants.tsv:

```json
{
  "age": {
    "Description": "Age at time of assessment",
    "Units": "years"
  },
  "sex": {
    "Description": "Biological sex",
    "Levels": {
      "F": "Female",
      "M": "Male",
      "O": "Other"
    }
  }
}
```

## NeuroBagel Compliance

PRISM supports [NeuroBagel](https://neurobagel.org/) annotations for harmonized participant data across studies.

→ See [Participants Mapping](PARTICIPANTS_MAPPING.md) for details on transforming demographic data.
