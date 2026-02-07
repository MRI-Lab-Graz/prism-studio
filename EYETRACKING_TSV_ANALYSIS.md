# Eyetracking TSV Support Analysis for PRISM Converter

**Date:** February 7, 2026  
**Status:** Analysis of current implementation & requirements for TSV support

---

## Executive Summary

Your college's demo TSV file (`sampleReport_s17_nr_1.tsv`) is an **SR Research EyeLink report export** - a pre-processed, trial-level summary of eyetracking data. The current converter only handles **raw binary EDF files**. To support TSV input, you need to add:

1. **Input recognition** for `.tsv` files in the eyetracking modality
2. **Column mapping** from raw TSV columns to PRISM schema
3. **JSON sidecar generation** with metadata extracted from TSV headers
4. **Naming convention** documentation for users

---

## 1. INPUT SPECIFICATION: How Users Should Name/Structure Files

### Current Implementation (EDF only)
Currently, the converter expects flat folder structure with **BIDS-like filenames**:

```
sourcedata/
├── sub-001_ses-1_task-antisaccade.edf
├── sub-001_ses-2_task-reading.edf
└── sub-002_ses-1_task-visualsearch.edf
```

### For TSV Support (Proposed)
**User should place files the SAME way** - flat folder under `sourcedata/`:

```
sourcedata/
├── sub-001_ses-1_task-antisaccade.tsv     # ✅ New: TSV support
├── sub-001_ses-1_task-antisaccade.edf     # ✅ Existing: EDF support
└── sub-002_ses-1_task-reading.tsv         # ✅ New
```

**Naming Convention (BIDS-compliant):**
```
sub-<label>[_ses-<label>]_task-<label>[_trackedEye-<left|right|both>][_run-<index>]_eyetrack.tsv
```

**Examples:**
- `sub-001_task-gaze_eyetrack.tsv` (single session, no trackedEye specified)
- `sub-001_ses-1_task-reading_eyetrack.tsv` (with session)
- `sub-001_task-search_trackedEye-both_eyetrack.tsv` (with eye specification)
- `sub-001_task-search_trackedEye-left_run-1_eyetrack.tsv` (with run index)

---

## 2. FILE NAMING: BIDS-Aligned Requirements

### What the schema says:
From [PRISM eyetracking.schema.json](file:///Users/karl/work/github/prism-studio/app/schemas/stable/eyetracking.schema.json#L6):
> Files should be named: `sub-<label>[_ses-<label>]_task-<label>[_trackedEye-<left|right|both>][_run-<index>]_eyetrack.<edf|asc|tsv.gz>`

### Status in current code:
**Pattern is defined but NOT fully enforced** in [batch_convert.py](file:///Users/karl/work/github/prism-studio/app/src/batch_convert.py#L26-L37):
```python
BIDS_FILENAME_PATTERN = re.compile(
    r"^(?P<sub>sub-[a-zA-Z0-9]+)"
    r"(?:_(?P<ses>ses-[a-zA-Z0-9]+))?"
    r"_(?P<task>task-[a-zA-Z0-9]+)"
    r"(?P<extra>(?:_[a-zA-Z0-9]+(?:-[a-zA-Z0-9]+)?)*)"
    r"\.(?P<ext>[a-zA-Z0-9]+(?:\.gz)?)$",
    re.IGNORECASE,
)
```

**Current support:** ✅ Handles `sub-XXX`, optional `ses-YYY`, `task-ZZZ`, `.edf`, `.tsv`, `.tsv.gz`  
**Missing:** `trackedEye-left|right|both` and `run-X` are not explicitly extracted (treated as "extra")

---

## 3. OUTPUT LOCATION & STRUCTURE

### Current Implementation
Converted files go to:
```
rawdata/
└── sub-001/
    └── [ses-1/]
        └── eyetracking/
            ├── sub-001_[ses-1_]task-gaze_eyetrack.edf
            └── sub-001_[ses-1_]task-gaze_eyetrack.json
```

### For TSV: Should Follow Same Structure
```
rawdata/
└── sub-001/
    └── ses-1/
        └── eyetracking/
            ├── sub-001_ses-1_task-reading_eyetrack.tsv      # ✅ Copied input
            └── sub-001_ses-1_task-reading_eyetrack.json     # ✅ JSON sidecar
```

### Root-Level JSON (Optional)
Currently created at dataset root if multiple tasks:
```
rawdata/
├── task-reading_eyetrack.json          # Root task-level metadata (optional)
└── sub-001/
    └── ses-1/
        └── eyetracking/
            ├── sub-001_ses-1_task-reading_eyetrack.tsv
            └── sub-001_ses-1_task-reading_eyetrack.json
```

---

## 4. JSON SIDECAR SPECIFICATION

### Schema Requirements
From [eyetracking.schema.json](file:///Users/karl/work/github/prism-studio/app/schemas/stable/eyetracking.schema.json):

**Required fields:**
- `Technical.SamplingFrequency` (number, Hz)
- `Technical.Manufacturer` (string, e.g., "SR Research")
- `Technical.RecordedEye` (enum: "left", "right", "both")
- `Screen.ScreenResolution` (array: [width, height])
- `Screen.ScreenDistance` (number, cm)
- `Study.TaskName` (string, a-z0-9+)
- `Metadata.SchemaVersion` (semver)
- `Metadata.CreationDate` (ISO date)

**Optional but recommended:**
- `Technical.StartTime` (seconds relative to first event)
- `Technical.ManufacturerModelName` (e.g., "EyeLink 1000 Plus")
- `Technical.SoftwareVersion` (e.g., "2.5")
- `Technical.FileFormat` ("tsv" or "tsv.gz")
- `Technical.TrackingMode` (e.g., "pupil-cr")
- `Technical.RecordedEye` 
- `Technical.CalibrationPositions` (number of points)
- `Technical.CalibrationAccuracy` (degrees of visual angle)
- `Screen.ScreenSize` ([width, height] in cm)
- `Screen.ScreenRefreshRate` (Hz)
- `Columns` (descriptions of TSV columns)
- `EventDetection` (fixation/saccade detection parameters)
- `Processing.ProcessingLevel` ("raw", "filtered", "parsed", "analyzed")

---

## 5. YOUR SAMPLE FILE ANALYSIS

### File: `sampleReport_s17_nr_1.tsv` (467,704 lines)

**Column Structure (14 columns):**
```
1. RECORDING_SESSION_LABEL     → Session identifier (s17_nr_1)
2. TRIAL_INDEX                 → Trial number (1, 2, ...)
3. AVERAGE_ACCELERATION_X      → Gaze acceleration X (pixels/s²)
4. AVERAGE_ACCELERATION_Y      → Gaze acceleration Y (pixels/s²)
5. AVERAGE_GAZE_X              → Average gaze X (pixels, ≈963.20)
6. AVERAGE_GAZE_Y              → Average gaze Y (pixels, ≈534.30)
7. AVERAGE_IN_BLINK            → Proportion in blink (0-1)
8. AVERAGE_IN_SACCADE          → Proportion in saccade (0-1)
9. AVERAGE_PUPIL_SIZE          → Pupil diameter (arbitrary units, ≈39.52)
10. AVERAGE_VELOCITY_X         → Gaze velocity X (pixels/s)
11. AVERAGE_VELOCITY_Y         → Gaze velocity Y (pixels/s)
12. IP_START_TIME              → Sample/interval start time (5529512 = timestamp)
13. SAMPLE_MESSAGE             → EyeLink recorder messages (CONFIG, blink detection, etc.)
14. TIMESTAMP                  → Explicit timestamp (5529512.00, 5529513.00, ...)

**Format:** TAB-separated (`.tsv`), ~467K rows
**Data Type:** Trial-level AGGREGATES (not raw samples - this is processed/binned data)
**Source Device:** SR Research EyeLink (identified by RECCFG message format)
```

### Key Observations:

1. **Data is PROCESSED (not raw)**
   - This is trial-level summary data from EyeLink Data Viewer export
   - Each row = 1 trial with average metrics
   - NOT the typical raw samples (100s Hz stream)

2. **Missing critical calibration info**
   - No explicit calibration accuracy in TSV
   - No screen resolution coordinates (GazeDim shows 1919.00 x 1079.00 in SAMPLE_MESSAGE)
   - No sampling frequency in header (inferred from RECCFG: "CR 1000 2" = 1000 Hz)

3. **Missing values indicated by "."**
   - Some acceleration columns contain "." (missing data)
   - Suggests optional/conditional columns

4. **Metadata embedded in SAMPLE_MESSAGE**
   - `RECCFG CR 1000 2 1 2 1 R` → 1000 Hz CR (corneal reflection)
   - `GAZE_COORDS 0.00 0.00 1919.00 1079.00` → Screen 1920×1080 (almost)
   - `CAMERA_LENS_FOCAL_LENGTH 38.00` → Optical spec
   - `PUPIL_DATA_TYPE RAW_AUTOSLIP` → Pupil type
   - `ELCL_PROC CENTROID (3)` → Pupil fit method

---

## 6. CURRENT CONVERTER IMPLEMENTATION STATUS

### What Already Works:
✅ **Batch conversion loop** - scans flat folder for files  
✅ **BIDS filename parsing** - extracts sub/ses/task  
✅ **Extension detection** - recognizes `.edf`, `.tsv`, `.csv`  
✅ **Directory creation** - creates `sub-XXX/ses-Y/eyetracking/`  
✅ **JSON sidecar template** - basic template generation  
✅ **EDF metadata extraction** - uses `pyedflib` for EDF files  

### What's Missing for TSV:
❌ **TSV column mapping** - no code to parse/validate TSV columns  
❌ **Metadata extraction from TSV** - no parser for SAMPLE_MESSAGE or headers  
❌ **TSV-specific validation** - no checks for required columns  
❌ **Incomplete JSON population** - missing fields from sample (e.g., `FileFormat: "tsv"`)  
❌ **UI form for TSV input** - converter has EDF single/batch but no TSV option  
❌ **Documentation** - no user guide for TSV input format

---

## 7. IMPLEMENTATION ROADMAP

### Phase 1: Core TSV Support
1. **Update extension detection** → Add `.tsv`, `.tsv.gz` to `EYETRACKING_EXTENSIONS`
2. **Add TSV parser function** → Extract columns, detect metadata from SAMPLE_MESSAGE
3. **Update `convert_eyetracking_file()`** → Handle both `.edf` and `.tsv`
4. **Improve JSON template** → Auto-populate fields like `FileFormat: "tsv"`, `ProcessingLevel: "parsed"`

### Phase 2: Enhanced Metadata
1. **Parse EyeLink SAMPLE_MESSAGE** → Extract calibration, screen, sampling info
2. **TSV header detection** → Support comment lines (`#`) with metadata
3. **User form inputs** → Add fields for screen specs, manufacturer model, etc.

### Phase 3: Validation & UI
1. **Add TSV validator** → Check for required columns
2. **Update web interface** → Add TSV upload tab (or toggle option)
3. **Generate sample templates** → Help users create properly-formatted TSV files

---

## 8. MINIMAL EXAMPLE: What the JSON Should Look Like

### For Your Sample TSV:

```json
{
  "Technical": {
    "SamplingFrequency": 1000,
    "Manufacturer": "SR Research",
    "ManufacturerModelName": "EyeLink 1000 Plus",
    "SoftwareVersion": "2.5",
    "FileFormat": "tsv",
    "RecordedEye": "both",
    "TrackingMode": "pupil-cr",
    "PupilFitMethod": "centroid",
    "CalibrationPositions": 9,
    "CalibrationAccuracy": 0.5
  },
  "Screen": {
    "ScreenResolution": [1920, 1080],
    "ScreenSize": [47.5, 26.8],
    "ScreenDistance": 60,
    "ScreenRefreshRate": 60
  },
  "Columns": {
    "TRIAL_INDEX": {
      "Description": "Trial number within the session",
      "Units": "index"
    },
    "AVERAGE_GAZE_X": {
      "Description": "Average gaze X position",
      "Units": "pixels"
    },
    "AVERAGE_GAZE_Y": {
      "Description": "Average gaze Y position",
      "Units": "pixels"
    },
    "AVERAGE_PUPIL_SIZE": {
      "Description": "Average pupil diameter",
      "Units": "arbitrary"
    },
    "AVERAGE_IN_BLINK": {
      "Description": "Proportion of trial time in blink",
      "Units": "0-1"
    },
    "AVERAGE_IN_SACCADE": {
      "Description": "Proportion of trial time in saccade",
      "Units": "0-1"
    },
    "AVERAGE_VELOCITY_X": {
      "Description": "Average gaze velocity X",
      "Units": "pixels/s"
    },
    "AVERAGE_VELOCITY_Y": {
      "Description": "Average gaze velocity Y",
      "Units": "pixels/s"
    },
    "AVERAGE_ACCELERATION_X": {
      "Description": "Average gaze acceleration X",
      "Units": "pixels/s²"
    },
    "AVERAGE_ACCELERATION_Y": {
      "Description": "Average gaze acceleration Y",
      "Units": "pixels/s²"
    }
  },
  "Study": {
    "TaskName": "reading",
    "TaskDescription": "Natural reading task with SR Research EyeLink 1000 Plus"
  },
  "Processing": {
    "ProcessingLevel": "parsed",
    "InterpolationMethod": "none",
    "DataLossPercentage": 5.0
  },
  "Participant": {
    "VisionCorrection": "corrected-to-normal",
    "HeadStabilization": "chinrest"
  },
  "Metadata": {
    "SchemaVersion": "1.1.0",
    "CreationDate": "2026-02-07",
    "Creator": "PRISM converter (TSV auto-conversion)",
    "SourceFile": "sampleReport_s17_nr_1.tsv"
  }
}
```

---

## 9. RECOMMENDATIONS & NEXT STEPS

### For Users (Now):
1. **Place TSV files in `sourcedata/`** with BIDS-compliant names:
   ```
   sub-001_ses-1_task-reading_eyetrack.tsv
   ```
   
2. **(Optional) Include metadata file** alongside TSV:
   ```
   sub-001_ses-1_task-reading_eyetrack.json  (or .yaml)
   ```
   with fields like:
   ```json
   {
     "SamplingFrequency": 1000,
     "Manufacturer": "SR Research",
     "ScreenResolution": [1920, 1080],
     "ScreenDistance": 60
   }
   ```

### For Implementation:
1. **High Priority** ✅
   - Add `.tsv`, `.tsv.gz` to `EYETRACKING_EXTENSIONS`
   - Update `convert_eyetracking_file()` to copy TSV + create JSON
   - Auto-populate `FileFormat: "tsv"` in sidecar

2. **Medium Priority** 🟡
   - Parse SAMPLE_MESSAGE for metadata extraction
   - Add simple TSV column validator (check for TIMESTAMP and TRIAL_INDEX)
   - UI form for eyetracking TSV input

3. **Lower Priority** 🔵
   - Advanced metadata parsing from TSV headers
   - Support for `.asc` (ASCII) format
   - Template generator for users

---

## References

- **BEP 020 Specification**: https://bids.neuroimaging.io/extensions/beps/bep_020.html
- **PRISM Schema**: [eyetracking.schema.json](file:///Users/karl/work/github/prism-studio/app/schemas/stable/eyetracking.schema.json)
- **Current Converter**: [batch_convert.py](file:///Users/karl/work/github/prism-studio/app/src/batch_convert.py)
- **Web Interface**: [converter_eyetracking.html](file:///Users/karl/work/github/prism-studio/app/templates/converter_eyetracking.html)

---

**Status:** Ready for implementation planning. Next step: Update the converter to handle `.tsv` files.
