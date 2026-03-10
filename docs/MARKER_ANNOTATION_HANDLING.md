# EDF+ Marker and Annotation Handling in PRISM

## Overview

This document describes how PRISM handles marker/annotation information when converting Varioport (.vpd, .raw) and EDF data. The implementation follows the **EDF+ specification (section 2.2)** for Time-stamped Annotations Lists (TALs), which allows storing time-keeping, events, and stimuli information directly in EDF files.

## EDF+ Annotations Specification

### Key Concepts

- **EDF Annotations Signal**: A special signal with label "EDF Annotations" that stores text annotations at arbitrary time points instead of physiological samples.

- **Time-stamped Annotations Lists (TAL)**: Text-encoded annotations with precise timing information.

- **TAL Format**: 
  ```
  +Onset[20Duration]20annotation1[20annotation2...]200
  ```
  Where:
  - `+Onset`: Time in seconds (e.g., "+123.45")
  - `20`: Separator (ASCII 20 = space character in TAL encoding)
  - `Duration`: Optional duration (e.g., "5.0")
  - `annotation1, annotation2`: Text labels separated by `20`
  - `00`: Terminates the TAL

### Example

```
+18020Lights off20Close door200       (Two events at 180s)
+1800.22125.520Apnea200               (25.5s apnea event at 30m 0.2s)
+5672020                               (Time-keeping: datarecord starts at 567.2s)
```

## PRISM Implementation

### 1. Marker Channel Detection

During Varioport conversion, channels with names containing "marker" or "trigger" are identified and separated from physiological signals:

```python
marker_channels = [c for c in channels if "marker" in c["name"].lower()]
physio_channels = [c for c in channels if "marker" not in c["name"].lower()]
```

### 2. Marker Event Extraction

Marker events are extracted by detecting edges (state changes) in the marker signal:

```python
def _extract_trigger_annotations_from_signal(marker_signal, sampling_rate, channel_label):
    """Extract rising edges in marker data as annotations."""
    diffs = np.diff(marker_signal, prepend=0)
    changes = np.where(diffs != 0)[0]  # Edge detection
    
    for idx in changes:
        if marker_signal[idx] > 0:
            onset = float(idx) / sampling_rate
            description = f"{channel_label}:{int(marker_signal[idx])}"
            # Returns (onset, duration=0, description) for EDF+ TAL format
```

### 3. EDF+ Annotation Writing

Marker events are written to EDF files using the `pyedflib` library:

```python
for onset, duration, description in marker_events:
    f_edf.writeAnnotation(onset, duration, description)
```

This automatically formats events according to EDF+ TAL specification.

### 4. PRISM Sidecar Documentation

The JSON sidecar now includes complete marker and channel metadata:

```json
{
  "Technical": {
    "SamplingFrequency": 256.0,
    "Columns": ["ekg", "Marker"]
  },
  "Channels": {
    "ekg": {
      "Type": "ECG",
      "Role": "cardiac",
      "SamplingFrequencyStored": 256.0,
      "SamplingFrequencyNative": 256.0
    },
    "Marker": {
      "Type": "TRIGGER",
      "Role": "trigger",
      "Description": "EDF+ annotations (TAL). Event markers stored per EDF+ spec 2.2.2"
    }
  },
  "Annotations": {
    "Description": "EDF+ Time-stamped Annotations Lists (TALs).",
    "Format": "TAL format: +Onset[20Duration]20annotation1[20annotation2...]200",
    "MarkerEvents": [
      {"onset": 10.5, "duration": 0.0, "annotation": "event:1"},
      {"onset": 25.3, "duration": 0.0, "annotation": "event:2"}
    ]
  }
}
```

## Channel Roles and Types

### Supported Channel Types

| Type | Description | PRISM Role |
|------|-------------|-----------|
| ECG/EKG | Electrocardiogram | `cardiac` |
| RESP | Respiration | `respiration` |
| EDA/GSR | Electrodermal activity | `electrodermal` |
| PPG/PULS | Photoplethysmogram | `plethysmograph` |
| TRIGGER/MARKER | Event markers/triggers | `trigger` |
| OTHER | Unidentified signals | `other` |

### Role Inference

Channel types and roles are automatically inferred from channel names (case-insensitive):

- `"ekg"` or `"ecg"` → Type: ECG, Role: cardiac
- `"resp"` → Type: RESP, Role: respiration
- `"marker"` or `"trigger"` → Type: TRIGGER, Role: trigger
- `"eda"` or `"gsr"` → Type: EDA, Role: electrodermal
- `"ppg"` or `"puls"` → Type: PPG, Role: plethysmograph

## Recording Type Classification

The `RecordingType` field in the Technical section indicates the content mix:

- `"ecg"`: ECG-only recording
- `"resp"`: Respiration-only
- `"mixed"`: Multiple physiological modalities
- `"unknown"`: Unable to classify

Example:
```python
recording_type = _infer_recording_type(channels)  # Returns "mixed" for ECG+Resp+Markers
```

## Integration with Data Analysis Pipelines

### ANTs (Annotation-aware Time Series) Processing

When marker information is present in compliance with EDF+ TAL format:

1. **Segmentation**: Analyses can segment data by marker events
2. **Alignment**: Multiple subjects' data can be aligned to common events
3. **Statistics**: Event-triggered averaging is possible
4. **Validation**: Tools can verify marker timing against expected experimental protocols

### NeuroBagel Compatibility

The channel metadata with explicit roles enables:
- Proper annotation in the NeuroBagel format
- Contribution tracking for signal processing
- Tool compatibility estimation

## Files Modified

| File | Purpose |
|------|---------|
| `src/batch_convert.py` | Enhanced `_create_physio_sidecar()` to include Annotations and Channels blocks |
| `app/helpers/physio/convert_varioport.py` | Added marker extraction and channel description functions |
| Tests | New test suite for marker annotation handling |

## Helper Functions

### `_extract_trigger_annotations_from_signal()`
Extracts marker events (rising edges) from marker signal data and returns EDF+ TAL-compatible tuples.

### `_build_channel_descriptions()`
Creates channel metadata dict with type, role, sampling rate, and description information.

### `_infer_recording_type()`
Classifies recording type based on channel composition.

## Backwards Compatibility

The sidecar JSON structure is backwards compatible:
- Old scripts reading only `Technical` and `Study` sections will continue to work
- New applications can access rich `Channels` and `Annotations` metadata
- Default values ensure no required data is missing

## Future Enhancements

1. **Marker Duration Detection**: Enhance edge detection to compute falling edges for marker duration
2. **Stimulus Information**: Link annotations to stimulus parameters from experimental logs
3. **Multi-lingual Annotations**: Support UTF-8 encoded annotations in multiple languages (per EDF+ spec 2.2.3)
4. **TAL Validation Analysis**: Report marker event statistics and timing regularity

## References

- **EDF+ Specification**: Section 2.2 - Annotations for text, time-keeping, events and stimuli
- **pyedflib Documentation**: Signal and annotation methods
- **PRISM Schema**: Channel roles and technical metadata requirements
