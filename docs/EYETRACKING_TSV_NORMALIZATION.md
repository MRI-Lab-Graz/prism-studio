# Eye-Tracking TSV Normalization: Dots vs Empty Strings

## Decision: Use Empty Strings (Not NaNs or Dots)

### Why Not NaNs?
- **NaN** is a Python-specific numeric concept (`float('nan')`)
- In TSV/CSV files (plain text), NaN cannot be represented directly
- When data is written to text, it becomes the string `"nan"` (4 characters)
- This violates BIDS/TSV standards for missing data

### Why Not Dots?
- While SR Research EyeLink exports use **`.`** to indicate missing values
- BIDS standard prefers **empty cells** (no value between tabs) for missing data
- Dots could be ambiguous - are they missing values or the string "."?
- Empty strings are more portable and universally understood

### What We Do Instead: Empty Strings

```
BEFORE (EyeLink format):
AVERAGE_ACCELERATION_X  AVERAGE_GAZE_X
.                       963.20
-497.78                 965.30

AFTER (PRISM/BIDS format):
AVERAGE_ACCELERATION_X  x
                        963.20
-497.78                 965.30
```

The column between the tabs is **completely empty** - no dot, no "nan", no "NA".

---

## BIDS/TSV Standard for Missing Values

According to [BIDS specification on TSV files](https://bids.neuroimaging.io/getting_started/folders_and_files/metadata/tsv.html):

> **Missing values**: Missing values SHOULD be left empty and not represented as a string.

### Valid representations for missing values in TSV:
- ✅ Empty cell (nothing between tabs)
- ✅ Column not present (column dropped entirely)

### Invalid representations:
- ❌ `"."` (dot)
- ❌ `"NA"` (string)
- ❌ `"NaN"` (string representation of NaN)
- ❌ `"null"` (JSON-style)

---

## How to Handle Missing Values When Reading

When your analysis code **reads** these TSV files:

### Python (pandas)
```python
import pandas as pd

df = pd.read_csv('sub-17_ses-1_task-gaze_eyetrack.tsv', sep='\t')

# Empty strings are automatically treated as missing:
# To explicitly convert to NaN:
df = df.replace('', pd.NA)

# To work with them:
print(df['x'].isna())  # Shows True for empty cells
print(df['x'].dropna())  # Removes rows with missing x
```

### R
```r
df <- read.delim('sub-17_ses-1_task-gaze_eyetrack.tsv')

# Empty strings are automatically NA in R
df$x[is.na(df$x)]  # Find missing values
```

### NumPy/SciPy
```python
import numpy as np

data = np.genfromtxt('sub-17_ses-1_task-gaze_eyetrack.tsv', 
                     delimiter='\t', 
                     dtype=None, 
                     encoding='utf-8',
                     missing_values='',  # Treat empty as missing
                     filling_values=np.nan)  # Replace with NaN
```

---

## Summary of Changes

The updated `_process_eyetracking_tsv()` function now:

1. **Drops** `RECORDING_SESSION_LABEL` column
   - Redundant: filename already encodes `sub-17_ses-1`
   - Saves ~30 bytes per row × millions of rows

2. **Converts dots to empty strings**
   - Complies with BIDS/TSV standard
   - Makes data more portable
   - Keeps analysis tools happy

3. **Renames columns to BIDS-style**
   - `AVERAGE_GAZE_X` → `x`
   - `AVERAGE_GAZE_Y` → `y`
   - `AVERAGE_PUPIL_SIZE` → `pupil_size`
   - `TIMESTAMP` → `timestamp`

4. **Preserves all other columns**
   - Kinematic data (accelerations, velocities)
   - Blink/saccade flags
   - Trial indices
   - Metadata (SAMPLE_MESSAGE)

---

## Example: Before and After

### BEFORE (Raw EyeLink Export)
```tsv
RECORDING_SESSION_LABEL	TRIAL_INDEX	AVERAGE_ACCELERATION_X	AVERAGE_GAZE_X	TIMESTAMP
s17_nr_1	1	.	963.20	5529512.00
s17_nr_1	1	-497.78	965.30	5529521.00
```

### AFTER (PRISM Normalized)
```tsv
TRIAL_INDEX	AVERAGE_ACCELERATION_X	x	timestamp
1		963.20	5529512.00
1	-497.78	965.30	5529521.00
```

---

## Configuration in JSON Sidecar

The JSON sidecar documents this normalization:

```json
{
  "Technical": {
    "FileFormat": "tsv",
    "ProcessingLevel": "parsed",
    "NormalizationApplied": {
      "DroppedColumns": ["RECORDING_SESSION_LABEL"],
      "RenamedColumns": {
        "AVERAGE_GAZE_X": "x",
        "AVERAGE_GAZE_Y": "y",
        "AVERAGE_PUPIL_SIZE": "pupil_size",
        "TIMESTAMP": "timestamp"
      },
      "MissingValueNormalization": {
        "From": "dots (.)",
        "To": "empty strings",
        "Standard": "BIDS-compatible"
      }
    }
  }
}
```

---

## References

- [BIDS Specification - TSV Format](https://bids.neuroimaging.io/getting_started/folders_and_files/metadata/tsv.html)
- [BEP 020 - Eye Tracking](https://bids.neuroimaging.io/extensions/beps/bep_020.html)
- [Python/pandas handling of missing values](https://pandas.pydata.org/docs/user_guide/missing_data.html)
