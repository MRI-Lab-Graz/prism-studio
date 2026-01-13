# PRISM Schemas

This directory contains the JSON Schema definitions for PRISM modalities. These schemas are used by the validator to ensure that metadata sidecars are correctly structured.

## Modalities

- **[Survey](stable/survey.schema.json)**: Metadata for questionnaires and surveys.
- **[Biometrics](stable/biometrics.schema.json)**: Metadata for physical performance and biometric assessments.
- **[Events](stable/events.schema.json)**: Metadata for task events.
- **[Eyetracking](stable/eyetracking.schema.json)**: Metadata for eyetracking data.
- **[Physio](stable/physio.schema.json)**: Metadata for physiological recordings.

## Practical Templates

To help you create metadata that complies with these schemas, we provide Excel templates with built-in help and validation options:

- **[Survey Import Template](../docs/examples/survey_import_template.xlsx)**: Use this to define your survey variables and metadata.
- **[Biometrics Import Template](../docs/examples/biometrics_import_template.xlsx)**: Use this to define your biometric assessments.

Both templates include a **Help** sheet that explains every column name and provides examples of valid options backed by the schemas in this directory.
