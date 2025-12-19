# ⚠️ Flat Structure Example - What NOT to Do

This folder demonstrates how research data often arrives from labs: **unorganized, inconsistently named, and difficult to manage**.

## Problems with This Structure

### 1. **Inconsistent Naming**
- `eyetracking_sub01_exp1.csv` vs `ET_Subject2_Experiment1.csv`
- `physio_sub01_ecg_rest.csv` vs `ECG_P01_resting.csv`
- No standardized naming convention

### 2. **No Metadata**
- What was the sampling rate?
- Which eye was tracked?
- What equipment was used?
- **No way to know without asking the experimenter!**

### 3. **Scalability Issues**
- With 100+ participants, finding files becomes a nightmare
- No clear organization by participant or modality
- Easy to accidentally mix up files

### 4. **No Provenance**
- When was data collected?
- Who collected it?
- What version of the protocol?

### 5. **Not Machine-Readable**
- Analysis scripts must be custom-written for each project
- Cannot use standard tools like fMRIPrep, BIDS-Apps
- Difficult to share or collaborate

## Compare With...

Look at `../prism_structure_example/` to see how the SAME data can be organized properly with:
- Consistent BIDS-style naming
- JSON sidecar files with full metadata
- Clear folder hierarchy
- Machine-readable format

## The Files Here

All files contain **synthetic dummy data** showing typical messy structures:

```
eyetracking_sub01_exp1.csv          # Inconsistent naming
ET_Subject2_Experiment1.csv         # Different convention
eyetrack_003_task1.csv              # Yet another format
physio_sub01_ecg_rest.csv           # Physio files mixed in
ECG_P01_resting.csv                 # Completely different naming
HR_subject1_baseline.csv            # No clear modality
ecg_data_participant_4.csv          # Verbose naming
raw_eyetrack_05.csv                 # Missing task info
physio_resp_sub06.csv               # Missing session info
EDA_data_P007.csv                   # Inconsistent prefixes
```

**This chaos is unfortunately very common in real research!**
