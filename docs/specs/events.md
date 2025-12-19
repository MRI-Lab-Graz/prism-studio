# Events (Super-BIDS)

The `events` modality in PRISM enforces a "Super-BIDS" standard. While standard BIDS allows for minimal event files, PRISM requires detailed provenance about the stimulus presentation software to ensure reproducibility.

## File Name Structure

Event files MUST follow the standard BIDS naming convention:

`sub-<label>[_ses-<label>]_task-<label>[_run-<index>]_events.tsv`

## Sidecar JSON (`*_events.json`)

PRISM enforces strict requirements on the JSON sidecar associated with the events file.

### `StimulusPresentation` Object

This object is **MANDATORY** in PRISM (though optional in standard BIDS). It describes the software and hardware used to present stimuli.

| Key | Requirement | Type | Description |
| --- | --- | --- | --- |
| `OperatingSystem` | **REQUIRED** | `string` | The operating system used (e.g., `"Windows 10"`, `"macOS 12.4"`). |
| `SoftwareName` | **REQUIRED** | `string` | The name of the presentation software (e.g., `"PsychoPy"`, `"Presentation"`). |
| `SoftwareVersion` | RECOMMENDED | `string` | The specific version used (e.g., `"2023.1.0"`). |
| `SoftwareRRID` | RECOMMENDED | `string` | Research Resource Identifier (e.g., `"SCR_006571"`). |
| `Code` | OPTIONAL | `string` | URL to the experiment code repository. |

### Column Definitions

Standard BIDS column definitions are supported and validated.

| Key | Description |
| --- | --- |
| `onset` | Description of the onset column. |
| `duration` | Description of the duration column. |
| `trial_type` | Description of the trial_type column. |

## Example Sidecar

```json
{
  "StimulusPresentation": {
    "OperatingSystem": "macOS 14.0",
    "SoftwareName": "PsychoPy",
    "SoftwareVersion": "2023.2.3",
    "SoftwareRRID": "SCR_006571",
    "Code": "https://github.com/lab/experiment-repo"
  },
  "trial_type": {
    "LongName": "Event category",
    "Description": "Category of the presented stimulus",
    "Levels": {
      "face": "Face image",
      "house": "House image"
    }
  }
}
```
