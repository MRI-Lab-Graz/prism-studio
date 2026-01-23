# Workshop

Learn PRISM through hands-on exercises with real example data.

## Overview

The PRISM workshop takes you from raw survey data to a fully validated, scored, and exportable dataset. Each exercise builds on the previous one.

| Exercise | Topic | Duration | What You'll Learn |
|----------|-------|----------|-------------------|
| **0** | Project Setup | 15 min | YODA principles, folder structure |
| **1** | Data Conversion | 30 min | Excel → PRISM format |
| **2** | Participant Mapping | 45 min | Demographic transformations |
| **3** | Recipes & Scoring | 20 min | Calculate questionnaire scores |
| **4** | Templates | 20 min | Create item descriptions |

**Total time: ~2 hours**

## Getting Started

### 1. Launch PRISM Studio

```bash
cd prism-studio
python prism-studio.py
```

### 2. Open the Workshop Materials

The workshop files are in:
```
examples/workshop/
├── exercise_0_project_setup/
├── exercise_1_raw_data/
├── exercise_2_participant_mapping/
├── exercise_3_using_recipes/
└── exercise_4_templates/
```

### 3. Follow the Handout

Open the complete guide: [WORKSHOP_HANDOUT_WELLBEING.md](https://github.com/MRI-Lab-Graz/prism-studio/blob/main/examples/workshop/WORKSHOP_HANDOUT_WELLBEING.md)

---

## Exercise Summaries

### Exercise 0: Project Setup (YODA)

**Goal**: Create an organized research project following YODA principles.

**Key Concepts**:
- Separation of raw data, code, and results
- `rawdata/` contains the validated PRISM dataset
- `code/` contains analysis scripts
- `analysis/` contains derived results

**Steps**:
1. Go to **Projects → Create New Project**
2. Name your project `wellbeing_study`
3. Observe the created folder structure

### Exercise 1: Data Conversion

**Goal**: Convert `wellbeing.xlsx` to PRISM format.

**Source Data**: `exercise_1_raw_data/raw_data/wellbeing.xlsx`

| participant_id | WB01 | WB02 | WB03 | WB04 | WB05 |
|---------------|------|------|------|------|------|
| sub-001 | 3 | 4 | 3 | 4 | 3 |
| sub-002 | 2 | 2 | 3 | 2 | 2 |

**Steps**:
1. Go to **Converter**
2. Load `wellbeing.xlsx`
3. Map the `participant_id` column
4. Select all `WB*` columns as survey items
5. Convert and save to your project

**Output**: BIDS-structured files in `rawdata/sub-XXX/survey/`

### Exercise 2: Participant Mapping

**Goal**: Transform demographic data with custom encodings.

**Challenge**: Your source data uses custom codes:
- Sex: `1=Male, 2=Female, 4=Other`
- Age: Stored as text `"25 years"`

**Solution**: Create a `participants_mapping.json` that transforms:
```json
{
  "sex": {
    "source_column": "gender_code",
    "mapping": {"1": "M", "2": "F", "4": "O"}
  },
  "age": {
    "source_column": "age_text",
    "transform": "extract_number"
  }
}
```

**Steps**:
1. Go to **Projects → Participants**
2. Create mapping rules
3. Generate standardized `participants.tsv`

### Exercise 3: Recipes & Scoring

**Goal**: Calculate WHO-5 Well-Being scores and export to SPSS.

**Recipe**: The WHO-5 total score is the sum of items, multiplied by 4 (range: 0-100).

```json
{
  "RecipeName": "WHO-5 Well-Being Index",
  "Scoring": {
    "WHO5_total": {
      "operation": "sum",
      "items": ["WB01", "WB02", "WB03", "WB04", "WB05"]
    },
    "WHO5_percent": {
      "operation": "custom",
      "formula": "WHO5_total * 4"
    }
  }
}
```

**Steps**:
1. Go to **Tools → Recipes & Scoring**
2. Select your dataset
3. Load `recipe-who5.json`
4. Run and export as SPSS (.sav)

### Exercise 4: Templates

**Goal**: Create survey metadata with item descriptions.

**Why?**: Templates make your data self-documenting. Anyone who opens your `.json` sidecar can understand what each item measures.

**Steps**:
1. Go to **Tools → Template Editor**
2. Create a new survey template
3. Add items with questions in English and German
4. Add response options with labels
5. Save to your project

---

## Sample Data

The workshop uses the **WHO-5 Well-Being Index**:

| Item | Question |
|------|----------|
| WB01 | I have felt cheerful and in good spirits |
| WB02 | I have felt calm and relaxed |
| WB03 | I have felt active and vigorous |
| WB04 | I woke up feeling fresh and rested |
| WB05 | My daily life has been filled with things that interest me |

**Scale**: 0 (At no time) to 5 (All of the time)

**Scoring**: Sum × 4 = Percentage score (0-100)

---

## Tips for Instructors

1. **Allow buffer time** – Participants work at different speeds
2. **Show the raw data first** – Context helps understanding
3. **Validate after Exercise 1** – See what's missing before adding metadata
4. **Demo SPSS export** – This is often the "wow" moment
5. **Have solutions ready** – Each exercise folder includes a solution

---

## Additional Resources

- [CLI Reference](CLI_REFERENCE.md) – Command-line options
- [Recipes Guide](RECIPES.md) – Creating custom scoring recipes
- [Survey Library](SURVEY_LIBRARY.md) – Pre-built survey templates
- [Error Codes](ERROR_CODES.md) – Understanding validation messages
