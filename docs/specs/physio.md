# Physio

Physiological recordings such as ECG, EDA, respiration, PPG and EMG, with a JSON sidecar describing the recording.

## File Name Structure

`sub-<label>[_ses-<label>]_task-<label>[_recording-<label>]_physio.<tsv.gz|tsv|json|edf>`

| Entity | Description |
| --- | --- |
| `sub` | **Required**. The subject identifier. |
| `ses` | Optional. The session identifier. |
| `task` | **Required**. The task during which the signal was recorded. |
| `recording` | Optional. The signal type: `ecg`, `cardiac`, `puls`, `resp`, `eda`, `ppg`, `emg`, `temp`, `bp`, `spo2`, `trigger`, or any other alphanumeric label. |
| `physio` | **Required**. The suffix indicating the modality. |

## Sidecar JSON (`*_physio.json`)

The sidecar requires the `Technical` and `Metadata` blocks, a `Study` block with `TaskName`, and may describe `Recording`, `Channels`, `TriggerAnnotations`, `Acquisition` and `Processing`. The authoritative definition is [`physio.schema.json`](../../app/schemas/stable/physio.schema.json).
