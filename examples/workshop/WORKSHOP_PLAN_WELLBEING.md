# PRISM Hands-on Workshop Plan: Wellbeing Survey Analysis

**Duration:** 2 hours  
**Theme:** WHO-5 Well-Being Index Survey Data  
**Method:** Graphical Interface (PRISM Studio) - No Command Line Required

---

## Workshop Objectives

Participants will learn to:
1. **Organize** research projects following YODA principles
2. **Convert** raw Excel survey data to BIDS/PRISM format
3. **Document** data with comprehensive JSON metadata
4. **Calculate** scores using recipes
5. **Export** analysis-ready data to SPSS

---

## Target Audience

Researchers who:
- Collect survey, behavioral, or biometric data
- Want to standardize data for sharing and analysis
- Prefer graphical interfaces over command-line tools
- Need to export to statistical software (SPSS, R, Jamovi)
- Value reproducibility and open science

---

## Schedule (120 Minutes)

| Time | Duration | Activity | Description |
|------|----------|----------|-------------|
| **00:00** | 10 min | **Introduction** | Why data structure matters. BIDS + PRISM + YODA overview |
| **00:10** | 15 min | **Exercise 0** | Create YODA-structured project |
| **00:25** | 30 min | **Exercise 1** | Convert wellbeing.xlsx to PRISM |
| **00:55** | 10 min | **Break** | Coffee + Q&A |
| **01:05** | 25 min | **Exercise 2** | Add metadata and validate |
| **01:30** | 20 min | **Exercise 3** | Calculate scores and export to SPSS |
| **01:50** | 10 min | **Wrap-up** | Review + resources + own data |

---

## Exercise 0: Project Setup with YODA (15 min)

### Learning Goals
- Understand YODA project organization
- Create proper folder structure
- Know where different files belong

### YODA Principles
**YODA** (Yet anOther Data Analysis) provides:
- **sourcedata/** → Original files (never modified)
- **rawdata/** → BIDS/PRISM formatted data
- **code/** → Analysis scripts
- **derivatives/** → Results and exports

### Steps
1. Open Projects page in PRISM Studio
2. Create new project: `Wellbeing_Study_Workshop`
3. Select location (Desktop, Documents, etc.)
4. Choose "YODA Structure" template
5. Verify folder structure created
6. Check "Active Project" indicator

### Expected Outcome
```
Wellbeing_Study_Workshop/
├── sourcedata/
├── rawdata/
│   ├── dataset_description.json
│   └── participants.tsv
├── code/
├── derivatives/
└── README.md
```

### Key Takeaways
- Separation keeps workflow clean
- Original data preserved in sourcedata/
- PRISM format goes in rawdata/
- Results saved to derivatives/

---

## Exercise 1: Convert Raw Data (30 min)

### Learning Goals
- Transform Excel to BIDS/PRISM format
- Understand BIDS folder hierarchy
- Learn proper file naming conventions

### Starting Material
**File:** `examples/workshop/exercise_1_raw_data/raw_data/wellbeing.xlsx`

**Contents:**
| Column | Description |
|--------|-------------|
| `participant_id` | DEMO001, DEMO002, ... |
| `session` | baseline, followup, ... |
| `age`, `sex`, `education`, `handedness` | Demographics |
| `WB01-WB05` | WHO-5 survey items (0-5 scale) |
| `completion_date` | Survey completion date |

**WHO-5 Items:**
- WB01: "I have felt cheerful and in good spirits"
- WB02: "I have felt calm and relaxed"
- WB03: "I have felt active and vigorous"
- WB04: "I woke up feeling fresh and rested"
- WB05: "My daily life has been filled with things that interest me"

### Steps

1. **Open Converter**
   - Click "Converter" in navigation
   - Select "Survey Data Converter"

2. **Upload File**
   - Browse to `wellbeing.xlsx`
   - Preview displays data

3. **Map Columns**
   - Participant ID → `participant_id`
   - Session → `session`
   - Task name → `wellbeing`
   - Modality → `survey`
   - Survey items automatically included

4. **Configure Output**
   - Directory: `Wellbeing_Study_Workshop/rawdata/`
   - Enable:
     - ✅ Generate JSON sidecars
     - ✅ Create participants.tsv
     - ✅ Create dataset_description.json

5. **Convert**
   - Click "Convert to BIDS"
   - Wait for progress bar
   - Review success message

6. **Review Structure**
```
rawdata/
├── dataset_description.json
├── participants.tsv
└── sub-DEMO001/
    └── ses-baseline/
        └── survey/
            ├── sub-DEMO001_ses-baseline_task-wellbeing_survey.tsv
            └── sub-DEMO001_ses-baseline_task-wellbeing_survey.json
```

### Key Takeaways
- BIDS uses hierarchical folders (Dataset → Subject → Session → Modality)
- Filenames follow strict pattern: `sub-<ID>_ses-<SESSION>_task-<NAME>_<SUFFIX>.<EXT>`
- Every data file has a JSON sidecar
- Structure enables interoperability

### Common Issues & Solutions
**Issue:** Excel file won't upload  
**Solution:** Close Excel, or use `wellbeing.tsv` instead

**Issue:** Subject IDs include "sub-" prefix  
**Solution:** System auto-adds "sub-" prefix, so use raw IDs

---

## Exercise 2: Metadata & Validation (25 min)

### Learning Goals
- Understand importance of metadata
- Use template library efficiently
- Validate dataset completeness

### Why Metadata?
- Makes data **self-documenting**
- Enables **reuse** by others
- Provides **proper attribution**
- Required for **data repositories**

### Steps

1. **Run Validation**
   - Go to "Validator"
   - Select dataset: `Wellbeing_Study_Workshop/rawdata/`
   - Click "Validate Dataset"
   - Review errors (expected at this stage!)

**Expected Errors:**
- Missing survey metadata (name, authors, citation)
- Missing item descriptions
- Missing response level labels

2. **Access Template**
   - Location: `examples/workshop/exercise_4_templates/survey-wellbeing.json`
   - Or use Template Editor in PRISM Studio

3. **Edit Sidecar**
   - Open any survey JSON:
     `rawdata/sub-DEMO001/ses-baseline/survey/sub-DEMO001_ses-baseline_task-wellbeing_survey.json`
   - Can use PRISM Studio editor or text editor (VS Code, etc.)

4. **Add Metadata**

**Study Information:**
```json
{
  "Study": {
    "OriginalName": {
      "en": "Wellbeing Survey (WHO-5 adapted)"
    },
    "Abbreviation": "WB",
    "Authors": ["Topp", "C.W.", "Østergaard", "S.D.", "Søndergaard", "S.", "Bech", "P."],
    "Year": 2015,
    "DOI": "10.1159/000376585",
    "Citation": "Topp, C.W., et al. (2015). The WHO-5 Well-Being Index...",
    "NumberOfItems": 5,
    "Instructions": {
      "en": "Please indicate for each statement which is closest to how you have been feeling over the last two weeks."
    }
  }
}
```

**Item Descriptions (example for WB01):**
```json
{
  "WB01": {
    "Description": {
      "en": "I have felt cheerful and in good spirits"
    },
    "Reversed": false,
    "Levels": {
      "5": {"en": "All of the time"},
      "4": {"en": "Most of the time"},
      "3": {"en": "More than half the time"},
      "2": {"en": "Less than half the time"},
      "1": {"en": "Some of the time"},
      "0": {"en": "At no time"}
    }
  }
}
```

**Tip:** Copy entire template file - faster than typing!

5. **Re-validate**
   - Run validation again
   - Confirm errors resolved
   - Dataset now fully documented

### Key Takeaways
- JSON structure is hierarchical (Study → Items → Properties)
- Templates save time and ensure consistency
- Validation catches missing/incorrect metadata
- Complete metadata enables data sharing

---

## Exercise 3: Scoring & Export (20 min)

### Learning Goals
- Apply recipes to calculate scores
- Export to analysis-ready formats
- Preserve metadata through workflow

### Recipe Concept
A recipe is a JSON file specifying:
- Which items to include
- Calculation method (sum, mean, etc.)
- Score ranges
- Quality checks

### Steps

1. **Copy Recipe**
   - Source: `examples/workshop/exercise_3_using_recipes/recipe-wellbeing.json`
   - Or import via PRISM Studio

2. **Review Recipe**
```json
{
  "RecipeVersion": "1.0.0",
  "Kind": "survey",
  "Survey": {
    "Name": "Wellbeing"
  },
  "Scores": {
    "Total": {
      "Description": {
        "en": "Total score for Wellbeing (WHO-5)"
      },
      "Items": ["WB01", "WB02", "WB03", "WB04", "WB05"],
      "Method": "sum",
      "Range": {"min": 5, "max": 35}
    }
  }
}
```

**Interpretation:**
- Sum all 5 items
- Valid range: 5-35
- Higher score = better wellbeing
- Scores <13 suggest depression screening

3. **Run Recipe**
   - Go to "Recipes & Scoring"
   - Select dataset: `rawdata/`
   - Select recipe: `recipe-wellbeing`
   - Click "Run Recipe"

4. **Configure Export**
   - **Format:** SPSS (.sav) - *Recommended!*
   - **Layout:** Long format (one row per session)
   - **Output:** `Wellbeing_Study_Workshop/derivatives/wellbeing_scores.sav`

5. **Generate Export**
   - Click "Export"
   - Wait for processing
   - Download file

6. **Verify in SPSS/Excel**
Open `derivatives/wellbeing_scores.sav`:

**Expected Columns:**
- `participant_id`, `session`
- `WB01`, `WB02`, `WB03`, `WB04`, `WB05` (original responses)
- `Total` (calculated score: 5-35)
- Demographics (if included)

**In SPSS:**
- Variable labels preserved
- Value labels show text ("All of the time", etc.)
- Ready for statistical analysis!

### Key Takeaways
- Recipes automate scoring (reproducible!)
- SPSS format preserves labels
- Data flows: Raw → PRISM → Scores → Analysis
- Entire workflow is documented

---

## Wrap-up & Resources (10 min)

### What You Accomplished

✅ Created YODA-structured project  
✅ Converted Excel → PRISM format  
✅ Added comprehensive metadata  
✅ Calculated scores automatically  
✅ Exported analysis-ready SPSS file

### Complete Workflow

```
1. Raw Data (wellbeing.xlsx)
   ↓
2. PRISM Format (rawdata/)
   ↓
3. Add Metadata (survey-wellbeing.json)
   ↓
4. Calculate Scores (recipe-wellbeing.json)
   ↓
5. Analysis (wellbeing_scores.sav in SPSS/R/Python)
```

### Using PRISM with Your Own Data

**Check Official Library:**
- `official/library/survey/` - 100+ survey templates
- `official/recipe/survey/` - Scoring formulas
- Use existing templates when available!

**Create Custom Templates:**
- Follow examples in `exercise_4_templates/`
- Include all items and response scales
- Document properly for reuse

**Share with Community:**
- Submit templates via GitHub
- Help build open survey library
- Proper attribution to original authors

### Data Sharing & Repositories

PRISM datasets are BIDS-compatible:
- Upload to **OpenNeuro** (neuroimaging + behavioral)
- Share via **OSF** (Open Science Framework)
- Archive in **institutional repositories**
- Metadata ensures others can use your data

### Integration with Analysis Tools

**R:**
```r
library(haven)
data <- read_sav("wellbeing_scores.sav")
```

**Python:**
```python
import pyreadstat
data, meta = pyreadstat.read_sav("wellbeing_scores.sav")
```

**JASP / Jamovi:**
- Open `.sav` files directly
- Labels preserved

### Resources

📚 **Documentation:** https://psycho-validator.readthedocs.io/  
🐙 **GitHub:** https://github.com/[your-repo]/prism-validator  
💬 **Issues:** Report bugs, request features  
📖 **Survey Library:** Browse official templates  
🎓 **Tutorials:** More examples and walkthroughs

### Common Questions

**Q: Can PRISM handle imaging data too?**  
A: Yes! PRISM extends BIDS, so you can combine survey + fMRI/EEG. Standard BIDS apps still work.

**Q: What if my survey isn't in the library?**  
A: Create custom template following examples. Request additions via GitHub.

**Q: How to handle missing data?**  
A: Recipes can specify missing data rules. Document in recipe JSON.

**Q: Can I use languages other than English?**  
A: Yes! All metadata fields support multilingual (en, de, fr, etc.)

**Q: Is PRISM free?**  
A: Yes! Open source (MIT license). Use, modify, share freely.

---

## Instructor Notes

### Pre-Workshop Checklist

**Software:**
- [ ] PRISM Studio installed and tested
- [ ] Web browsers available (Chrome/Edge)
- [ ] SPSS/R/Python for viewing exports (optional)

**Materials:**
- [ ] `wellbeing.xlsx` accessible
- [ ] `survey-wellbeing.json` template available
- [ ] `recipe-wellbeing.json` recipe available
- [ ] Handout printed or shared digitally

**Network:**
- [ ] Internet access for downloads (if needed)
- [ ] Backup materials on USB drives
- [ ] Pre-converted datasets as fallback

### Timing Adjustments

**If Running Short:**
- Shorten Exercise 0 to 10 minutes (quick YODA explanation)
- Skip detailed validation review in Exercise 2
- Demo recipe export instead of having everyone do it

**If Extra Time:**
- Show advanced recipe features (subscales, reverse coding)
- Demonstrate integration with R/Python
- Discuss data sharing best practices
- Show more library examples

### Common Issues

**Converter doesn't load Excel:**
- Close Excel application
- Use TSV alternative: `wellbeing.tsv`
- Check file permissions

**Many validation errors:**
- Expected before Exercise 2!
- Use as teaching moment
- Show how metadata fixes everything

**Recipe doesn't run:**
- Verify recipe location
- Check column names match (WB01-WB05)
- Ensure dataset path correct

**SPSS export empty:**
- Confirm recipe ran successfully
- Check output directory path
- Verify data exists in rawdata/

### Demo Tips

- **Show, Don't Just Tell:** Screen share each step
- **Pause for Questions:** After each exercise
- **Use Real Example:** Wellbeing is relatable
- **Emphasize Benefits:** Time savings, reproducibility
- **Encourage Exploration:** It's OK to click around!

### Advanced Topics (if time)

- Reverse-scored items
- Subscale calculation
- Quality checks (completion time, patterns)
- NeuroBagel integration
- Multi-modal datasets (survey + imaging)

---

## Materials Inventory

### Essential Files
- `examples/workshop/exercise_1_raw_data/raw_data/wellbeing.xlsx`
- `examples/workshop/exercise_1_raw_data/raw_data/wellbeing.tsv`
- `examples/workshop/exercise_3_using_recipes/recipe-wellbeing.json`
- `examples/workshop/exercise_4_templates/survey-wellbeing.json`
- `examples/workshop/WORKSHOP_HANDOUT_WELLBEING.md`
- `examples/workshop/PREPARATION.md`

### Reference Files
- `official/library/survey/survey-who5.json` (original WHO-5)
- `official/recipe/survey/recipe-who5.json` (original recipe)

### Optional Materials
- Slides (BIDS/PRISM introduction)
- Pre-converted reference dataset
- Example SPSS output file

---

**Workshop Plan Complete** ✅

For detailed participant instructions, see: [WORKSHOP_HANDOUT_WELLBEING.md](../examples/workshop/WORKSHOP_HANDOUT_WELLBEING.md)
