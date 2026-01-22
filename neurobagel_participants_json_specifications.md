# NeuroBagel participants.json Specifications

**Document Created:** January 22, 2026  
**Source:** neurobagel/documentation GitHub repository

---

## 1. Official Schema & Format

### Structure
NeuroBagel data dictionaries are JSON files that describe phenotypic data columns. They are **compatible with and expand upon BIDS `participants.json` data dictionaries**.

**JSON Schema Standard:**  
NeuroBagel uses the [`jsonschema` schema language](https://json-schema.org/) to specify the structure of data dictionaries.

**Reference Documentation:**
- Main Specification: https://github.com/neurobagel/documentation/blob/main/docs/data_models/dictionaries.md
- Comprehensive Example: https://raw.githubusercontent.com/neurobagel/neurobagel_examples/main/data-upload/example_synthetic.json

---

## 2. Required Fields & Data Types

### Basic Structure for Each Column Entry

```json
{
  "column_name": {
    "Description": "string",
    "Levels": { ... },  // For categorical variables only
    "Units": "string",  // Optional
    "Annotations": { ... }
  }
}
```

### Field Definitions

| Field | Type | Required? | Description |
|-------|------|-----------|-------------|
| **Description** | string | YES | Human-readable description of what the column contains |
| **Levels** | object | Categorical only | Key-value pairs mapping raw values to human-readable labels |
| **Units** | string | Optional | Units of measurement (e.g., "years", "mm/Hg") |
| **Annotations** | object | YES (NeuroBagel specific) | Semantic annotations for machine-readable interpretation |

### Annotations Structure

All NeuroBagel annotations require:

```json
"Annotations": {
  "IsAbout": {
    "TermURL": "string",  // URL to controlled vocabulary term
    "Label": "string"     // Human-readable label
  },
  "VariableType": "string",  // "Identifier", "Continuous", "Categorical", "Collection"
  "Format": { ... },  // For continuous variables
  "MissingValues": [],  // Array of values representing missing data
  "IsPartOf": { ... }  // For assessment tools
}
```

---

## 3. Standardized Variable Names & Coding Schemes

### A. Participant Identifier

**Field Name:** `participant_id`  
**Data Type:** String  
**Required:** YES

```json
{
  "participant_id": {
    "Description": "A participant ID",
    "Annotations": {
      "IsAbout": {
        "TermURL": "nb:ParticipantID",
        "Label": "Subject Unique Identifier"
      },
      "VariableType": "Identifier"
    }
  }
}
```

**Coding Rules:**
- Must be unique per row
- For BIDS datasets: Must match BIDS format `sub-<label>` (e.g., `sub-01`, `sub-MNI001`)
- **Case-sensitive** - `sub-MNI001` ≠ `sub-mni001`
- Cannot contain missing values

---

### B. Session Identifier

**Field Name:** `session_id`  
**Data Type:** String  
**Required:** Conditional (if longitudinal data)

```json
{
  "session_id": {
    "Description": "A session ID",
    "Annotations": {
      "IsAbout": {
        "TermURL": "nb:SessionID",
        "Label": "Unique session identifier"
      },
      "VariableType": "Identifier"
    }
  }
}
```

**Coding Rules:**
- For BIDS datasets: Follow format `ses-<label>` (e.g., `ses-01`, `ses-baseline`)
- Combination of `participant_id` + `session_id` must be unique per row
- NeuroBagel supports session_id in participants files (unlike strict BIDS)

---

### C. Age

**Field Name:** `age` or custom name (e.g., `pheno_age`)  
**Data Type:** Continuous (numeric)  
**Variable Type:** `Continuous`

```json
{
  "pheno_age": {
    "Description": "Age of the participant",
    "Units": "years",
    "Annotations": {
      "IsAbout": {
        "TermURL": "nb:Age",
        "Label": "Chronological age"
      },
      "Format": {
        "TermURL": "nb:FromFloat",  // See formats below
        "Label": "Float value"
      },
      "MissingValues": ["NA"],
      "VariableType": "Continuous"
    }
  }
}
```

**Allowed Formats for Age Values:**

| TermURL | Label | Examples |
|---------|-------|----------|
| `nb:FromFloat` | Float value | `31.5`, `31` |
| `nb:FromEuro` | European decimal value | `31,5` |
| `nb:FromBounded` | Bounded value | `30+` |
| `nb:FromRange` | Range between min/max | `30-35` |
| `nb:FromISO8061` | ISO 8601 period format | `31Y6M` |

**REQUIRED:** Format annotation must be specified for continuous variables.

---

### D. Sex / Gender

**Field Name:** `sex` or custom name (e.g., `pheno_sex`)  
**Data Type:** Categorical  
**Variable Type:** `Categorical`

```json
{
  "pheno_sex": {
    "Description": "Sex variable",
    "Levels": {
      "M": "Male",
      "F": "Female",
      "O": "Other"
    },
    "Annotations": {
      "IsAbout": {
        "TermURL": "nb:Sex",
        "Label": "Sex"
      },
      "Levels": {
        "M": {
          "TermURL": "snomed:248153007",
          "Label": "Male"
        },
        "F": {
          "TermURL": "snomed:248152002",
          "Label": "Female"
        },
        "O": {
          "TermURL": "snomed:32570681000036106",
          "Label": "Other"
        }
      },
      "MissingValues": ["missing", "NA"],
      "VariableType": "Categorical"
    }
  }
}
```

**BIDS Aligned SNOMED-CT Terms:**

| Value | Label | SNOMED-CT URL |
|-------|-------|---------------|
| M | Male | http://purl.bioontology.org/ontology/SNOMEDCT/248153007 |
| F | Female | http://purl.bioontology.org/ontology/SNOMEDCT/248152002 |
| O | Other | http://purl.bioontology.org/ontology/SNOMEDCT/32570681000036106 |

---

### E. Diagnosis / Group

**Field Name:** `group`, `diagnosis`, or custom name (e.g., `pheno_group`)  
**Data Type:** Categorical  
**Variable Type:** `Categorical`

```json
{
  "pheno_group": {
    "Description": "Group variable",
    "Levels": {
      "PAT": "Patient",
      "CTRL": "Control subject"
    },
    "Annotations": {
      "IsAbout": {
        "TermURL": "nb:Diagnosis",
        "Label": "Diagnosis"
      },
      "Levels": {
        "PAT": {
          "TermURL": "snomed:406506008",
          "Label": "Attention deficit hyperactivity disorder"
        },
        "CTRL": {
          "TermURL": "ncit:C94342",
          "Label": "Healthy Control"
        }
      },
      "MissingValues": ["NA"],
      "VariableType": "Categorical"
    }
  }
}
```

**Coding Standards:**
- **Clinical diagnoses:** Use SNOMED-CT ontology terms (https://browser.ihtsdotools.org/)
  - Example: `snomed:49049000` for Parkinson's disease
  - Example: `snomed:406506008` for ADHD
- **Healthy control status:** Use National Cancer Institute Thesaurus
  - Example: `ncit:C94342` for Healthy Control

---

### F. Assessment Tools / Cognitive Tests

**Field Names:** Multiple columns, each representing items or subscales of a single assessment  
**Data Type:** Varies (typically numeric)  
**Variable Type:** `Collection`

```json
{
  "tool1_item1": {
    "Description": "item 1 scores for Montreal Cognitive Assessment",
    "Annotations": {
      "IsAbout": {
        "TermURL": "nb:Assessment",
        "Label": "Assessment tool"
      },
      "IsPartOf": {
        "TermURL": "snomed:859351000000102",
        "Label": "Montreal cognitive assessment"
      },
      "MissingValues": ["missing", "NA"],
      "VariableType": "Collection"
    }
  },
  "tool1_item2": {
    "Description": "item 2 scores for Montreal Cognitive Assessment",
    "Annotations": {
      "IsAbout": {
        "TermURL": "nb:Assessment",
        "Label": "Assessment tool"
      },
      "IsPartOf": {
        "TermURL": "snomed:859351000000102",
        "Label": "Montreal cognitive assessment"
      },
      "MissingValues": ["missing"],
      "VariableType": "Collection"
    }
  }
}
```

**Coding Rules for Assessment Tools:**
- **Minimum two annotations required:**
  1. `IsAbout` the generic category `nb:Assessment`
  2. `IsPartOf` the specific assessment tool (SNOMED-CT term)
- **MissingValues:** Optional but recommended
- **VariableType:** Always `"Collection"` for assessment items
- **Assessment Tool Terms:** Use SNOMED-CT ontology
  - Montreal Cognitive Assessment: `snomed:859351000000102`
  - UPDRS (Unified Parkinson's Disease Rating Scale): `snomed:342061000000106`

---

## 4. Context (Prefixes) for Controlled Vocabularies

All NeuroBagel data dictionaries should include an `@context` section:

```json
{
  "@context": {
    "nb": "http://neurobagel.org/vocab/",
    "ncit": "http://ncicb.nci.nih.gov/xml/owl/EVS/Thesaurus.owl#",
    "nidm": "http://purl.org/nidash/nidm#",
    "snomed": "http://purl.bioontology.org/ontology/SNOMEDCT/"
  }
}
```

---

## 5. Missing Values Convention

Missing values are specified as an array under the `MissingValues` annotation.

```json
"MissingValues": [
  "",
  " ",
  "NA",
  "missing",
  "not completed"
]
```

**Rules:**
- Missing values NOT allowed for:
  - `participant_id` (identifier)
  - `session_id` (identifier)
- Missing values ARE allowed for:
  - All other phenotypic variables
  - Assessment tool items

---

## 6. Example of Complete participants.json File

```json
{
  "@context": {
    "nb": "http://neurobagel.org/vocab/",
    "ncit": "http://ncicb.nci.nih.gov/xml/owl/EVS/Thesaurus.owl#",
    "nidm": "http://purl.org/nidash/nidm#",
    "snomed": "http://purl.bioontology.org/ontology/SNOMEDCT/"
  },
  "participant_id": {
    "Description": "A participant ID",
    "Annotations": {
      "IsAbout": {
        "TermURL": "nb:ParticipantID",
        "Label": "Subject Unique Identifier"
      },
      "VariableType": "Identifier"
    }
  },
  "session_id": {
    "Description": "A session ID",
    "Annotations": {
      "IsAbout": {
        "TermURL": "nb:SessionID",
        "Label": "Unique session identifier"
      },
      "VariableType": "Identifier"
    }
  },
  "age": {
    "Description": "Age of the participant",
    "Units": "years",
    "Annotations": {
      "IsAbout": {
        "TermURL": "nb:Age",
        "Label": "Age"
      },
      "Format": {
        "TermURL": "nb:FromFloat",
        "Label": "Float value"
      },
      "MissingValues": ["NA"],
      "VariableType": "Continuous"
    }
  },
  "sex": {
    "Description": "Sex variable",
    "Levels": {
      "M": "Male",
      "F": "Female"
    },
    "Annotations": {
      "IsAbout": {
        "TermURL": "nb:Sex",
        "Label": "Sex"
      },
      "Levels": {
        "M": {
          "TermURL": "snomed:248153007",
          "Label": "Male"
        },
        "F": {
          "TermURL": "snomed:248152002",
          "Label": "Female"
        }
      },
      "MissingValues": ["missing"],
      "VariableType": "Categorical"
    }
  },
  "group": {
    "Description": "Group variable",
    "Levels": {
      "PAT": "Patient",
      "CTRL": "Control subject"
    },
    "Annotations": {
      "IsAbout": {
        "TermURL": "nb:Diagnosis",
        "Label": "Diagnosis"
      },
      "Levels": {
        "PAT": {
          "TermURL": "snomed:406506008",
          "Label": "Attention deficit hyperactivity disorder"
        },
        "CTRL": {
          "TermURL": "ncit:C94342",
          "Label": "Healthy Control"
        }
      },
      "MissingValues": ["NA"],
      "VariableType": "Categorical"
    }
  }
}
```

---

## 7. Example Data Row Format (participants.tsv)

Corresponding `participants.tsv` file:

```
participant_id	session_id	age	sex	group
sub-01	ses-01	25	M	PAT
sub-01	ses-02	26	M	PAT
sub-02	ses-01	28	F	CTRL
sub-02	ses-02	29	F	CTRL
```

---

## 8. NeuroBagel Harmonization Guidelines

### Key Principles:

1. **Semantic Tagging:** Every column should be tagged with a term from controlled vocabularies
2. **Backward Compatible:** NeuroBagel dictionaries extend BIDS format, not replace it
3. **JSON-LD:** Uses JSON-LD syntax for semantic web standards
4. **Ontology Usage:** Leverages SNOMED-CT, NCIT, and NeuroBagel-specific ontologies
5. **Human + Machine Readable:** Includes both readable descriptions and machine-interpretable semantic tags

### Data Harmonization Process:

1. Prepare TSV with phenotypic data
2. Create/annotate `participants.json` using NeuroBagel Annotation Tool (https://annotate.neurobagel.org)
3. Tool generates semantic tags automatically
4. Resulting dictionary is BIDS-compatible AND enables NeuroBagel querying

---

## 9. Validation & Tools

### Official NeuroBagel Tools:
- **Annotation Tool:** https://annotate.neurobagel.org
  - Web-based interface for annotating TSV files
  - Generates compliant `participants.json` automatically
  - Supports uploading existing BIDS `participants.json` for reference

### Validation:
- NeuroBagel CLI validates dictionaries against schema
- Compatible with BIDS validator (extra fields ignored)
- JSON schema validation using standard `jsonschema` tools

---

## 10. Important Notes & Compatibility

### BIDS Compatibility:
- NeuroBagel dictionaries are **supersets** of BIDS `participants.json`
- Extra fields added by NeuroBagel are safely ignored by BIDS validator
- Existing BIDS `participants.json` files can be directly used with NeuroBagel (with enhancements)

### Variable Naming:
- Column names are case-sensitive
- Recommended to use snake_case (e.g., `participant_id`, `pheno_age`, `tool1_item1`)
- `participant_id` and `session_id` are reserved names

### Format Support:
- File format: **JSON** (`.json` extension)
- Data format: Tab-separated values (`.tsv`) for the actual participant data
- Compatible with both BIDS and NeuroBagel CLI

---

## References & URLs

| Item | URL |
|------|-----|
| **Main Documentation** | https://github.com/neurobagel/documentation/blob/main/docs/data_models/dictionaries.md |
| **Data Prep Guide** | https://github.com/neurobagel/documentation/blob/main/docs/user_guide/data_prep.md |
| **Complete Example** | https://raw.githubusercontent.com/neurobagel/neurobagel_examples/main/data-upload/example_synthetic.json |
| **Example TSV** | https://raw.githubusercontent.com/neurobagel/neurobagel_examples/main/data-upload/example_synthetic.tsv |
| **Annotation Tool** | https://annotate.neurobagel.org |
| **Variables Guide** | https://github.com/neurobagel/documentation/blob/main/docs/data_models/variables.md |
| **SNOMED-CT Browser** | https://browser.ihtsdotools.org/ |
| **JSON-LD Spec** | https://w3c.github.io/json-ld-syntax/ |
| **JSON Schema** | https://json-schema.org/ |

---

**Last Updated:** January 22, 2026  
**NeuroBagel Version:** Latest (as of documentation repository main branch)
