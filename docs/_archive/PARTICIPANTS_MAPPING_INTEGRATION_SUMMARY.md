# Participants Mapping System - Integration Summary

## ✅ Complete Implementation

Everything is ready to use! Here's what has been implemented:

---

## 📦 Components

### 1. Core Converter Module
**File:** `src/participants_converter.py`

- `ParticipantsConverter` class
- Methods:
  - `load_mapping_from_file(path)` - Load mapping from any location
  - `validate_mapping(spec)` - Validate JSON schema
  - `convert_participant_data(source, mapping)` - Transform raw data
  - `create_mapping_template(source)` - Auto-generate template

### 2. Web Integration
**File:** `app/src/web/validation.py`

- `_apply_participants_mapping()` function
- Auto-detects mapping in `code/library/` or `sourcedata/`
- Applied during dataset validation
- Progress logging to web terminal
- Non-blocking (graceful fallback)

### 3. Web Converter UI Enhancement
**File:** `app/src/web/blueprints/tools.py`

- Converter route now includes `participants_mapping_info`
- Shows if mapping file exists in project
- Displays helpful status messages

### 4. Documentation
**Files:**
- `docs/PARTICIPANTS_MAPPING.md` - User guide (complete)
- `docs/PARTICIPANTS_MAPPING_IMPLEMENTATION.md` - Technical details
- `docs/CONVERTER_PARTICIPANTS_MAPPING_INFO.md` - UI information panel

### 5. Workshop Exercise 2
**Folder:** `examples/workshop/exercise_2_participant_mapping/`

**Contents:**
- `README.md` - Exercise overview
- `INSTRUCTIONS.md` - Step-by-step guide (45 minutes)
- `template_participants_mapping.json` - Starting template
- `solution_participants_mapping.json` - Reference solution
- `raw_data/` - Sample datasets (wellbeing.tsv, fitness_data.tsv, wellbeing.xlsx)

**Learning Outcomes:**
- ✓ Create mapping specifications
- ✓ Document custom encodings
- ✓ Define value transformations
- ✓ Place in correct project location
- ✓ Verify output

---

## 📁 File Locations

```
my_dataset/
├── code/
│   └── library/
│       └── participants_mapping.json    ← Mapping specification
├── sourcedata/
│   └── raw_data/
│       └── wellbeing.tsv               ← Raw data (any encoding)
├── rawdata/                            ← Final BIDS/PRISM dataset
│   ├── dataset_description.json
│   ├── participants.tsv                ← Auto-generated (standardized)
│   └── ...
└── ...
```

---

## 🔄 Workflow

### User Perspective

1. **Create mapping**
   - Place `participants_mapping.json` in `code/library/`
   - Specify demographic variable mappings
   - Define value transformations (numeric → standard)

2. **Validate dataset**
   - Run PRISM validation
   - Mapping auto-detects
   - Data auto-transforms
   - Progress logged to web terminal

3. **Verify output**
   - Check `rawdata/participants.tsv`
   - Verify standardized values
   - Done! Data is now PRISM-compliant

### System Perspective

1. **Detection**
   - During validation, system searches for mapping file
   - Checks: `code/library/` → `sourcedata/`

2. **Validation**
   - Checks JSON syntax
   - Validates against specification schema
   - Reports errors

3. **Transformation**
   - Finds source data file
   - Loads raw values
   - Applies value mappings
   - Writes standardized output

4. **Logging**
   - Each step logged
   - Progress updates to web terminal
   - Messages show what was mapped

---

## 🎓 Workshop Integration

### Exercise 2: Participant Demographic Mapping

**Time:** 45 minutes

**Structure:**
1. **Background** (5 min) - Why mapping matters
2. **Examine raw data** (5 min) - Look at numeric codes
3. **Create mapping** (20 min) - Fill in specification
4. **Test mapping** (10 min) - Run validation
5. **Verify output** (5 min) - Check results

**Learning Path:**
- Exercise 1: Learn data conversion
- **Exercise 2: Learn demographic mapping** ← NEW
- Exercise 3: Learn scoring/validation
- Exercise 4: Learn export/reporting

**Materials Included:**
- Complete instructions
- Template file (students fill in)
- Solution file (for reference/cheating)
- Sample raw data
- Troubleshooting guide

---

## 📊 Example Transformation

**Input** (raw_data/wellbeing.tsv):
```
participant_id   age   sex   education   handedness
DEMO001          28    2     4           1
DEMO002          34    1     5           1
DEMO003          22    2     3           1
```

**Mapping** (code/library/participants_mapping.json):
```json
{
  "mappings": {
    "sex": {
      "source_column": "sex",
      "standard_variable": "sex",
      "value_mapping": {"1":"M", "2":"F", "4":"O"}
    },
    "handedness": {
      "source_column": "handedness",
      "standard_variable": "handedness",
      "value_mapping": {"1":"R", "2":"L"}
    },
    "education": {
      "source_column": "education",
      "standard_variable": "education_level"
    }
  }
}
```

**Output** (rawdata/participants.tsv):
```
participant_id   age   sex   education_level   handedness
DEMO001          28    F     4                 R
DEMO002          34    M     5                 R
DEMO003          22    F     3                 R
```

✓ Numeric codes transformed to standard codes automatically!

---

## 🧪 Testing

**Test Script:** `tests/test_participants_mapping.py`

Run:
```bash
source .venv/bin/activate
python tests/test_participants_mapping.py
```

**Verifies:**
- ✓ Mapping file loading
- ✓ Specification validation
- ✓ Value transformation accuracy
- ✓ Output file generation
- ✓ Template generation

**Status:** All tests passing ✓

---

## 📚 Documentation

### For Users
- **Quick Start:** `docs/PARTICIPANTS_MAPPING.md` (5 min read)
- **Complete Guide:** `docs/PARTICIPANTS_MAPPING.md` (20 min read)
- **Workshop:** `examples/workshop/exercise_2_participant_mapping/INSTRUCTIONS.md`

### For Developers
- **Implementation:** `docs/PARTICIPANTS_MAPPING_IMPLEMENTATION.md`
- **Code:** `src/participants_converter.py`
- **Web Integration:** `app/src/web/validation.py`

### For Instructors
- **Exercise Guide:** `examples/workshop/exercise_2_participant_mapping/INSTRUCTIONS.md`
- **Template/Solution:** Files in same folder
- **Timing:** 45 minutes
- **Prerequisites:** Complete Exercise 1

---

## ✨ Key Features

✅ **Automatic Detection** - Finds mapping file automatically  
✅ **Value Mapping** - Numeric codes → standard codes  
✅ **Column Renaming** - Can rename during transformation  
✅ **Validation** - Checks specification syntax  
✅ **Logging** - Shows progress to user  
✅ **Non-Breaking** - Optional (works without it)  
✅ **BIDS-Compatible** - Mapping in `code/`, not `rawdata/`  
✅ **Well-Documented** - Guide + examples + exercise  
✅ **Tested** - Full test suite passing  

---

## 🚀 Ready for Use

The system is **production-ready** and can be:

1. **Deployed** to production PRISM installations
2. **Taught** in workshops and training sessions
3. **Extended** with additional features as needed
4. **Documented** for users and developers

---

## 📋 Checklist

- ✅ Core converter module implemented and tested
- ✅ Web integration complete
- ✅ Web UI enhanced (converter route)
- ✅ Comprehensive user documentation
- ✅ Technical documentation
- ✅ Workshop exercise (Exercise 2) complete
- ✅ Example mappings provided
- ✅ Test script validates functionality
- ✅ All tests passing
- ✅ BIDS-compatible design

---

## 🎯 Next Steps for Users

1. Read `docs/PARTICIPANTS_MAPPING.md` (quick reference)
2. Work through `examples/workshop/exercise_2_participant_mapping/`
3. Create mapping for your study data
4. Place in `code/library/` of your project
5. Run validation - mapping auto-applies

Done! Your participant data is now standardized.

---

## 💡 Design Highlights

### Why `code/library/`?
- It's a **conversion spec**, not final data
- Standard BIDS/PRISM YODA location
- Automatically excluded from BIDS validation
- Clear: this is methodology/code, not data

### Why JSON?
- Human-readable and editable
- Self-documenting format
- Standard for data specifications
- Easy to version control

### Why Auto-Apply?
- User doesn't need to manually run converter
- Part of standard validation workflow
- Consistent application across all datasets
- No extra steps needed

### Why Non-Breaking?
- If no mapping file exists, validation continues normally
- Doesn't affect existing workflows
- Users can adopt gradually
- Backward compatible

---

## 📞 Support

For issues, see:
- **Troubleshooting:** `docs/PARTICIPANTS_MAPPING.md#troubleshooting`
- **Examples:** `examples/workshop/exercise_2_participant_mapping/`
- **Solution:** `solution_participants_mapping.json` in same folder
- **Testing:** `tests/test_participants_mapping.py`

