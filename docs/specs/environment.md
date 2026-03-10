# Environment Specification

This page describes the PRISM environment modality at a high level.

## Scope

The `environment` modality captures contextual environmental information that can be linked to recordings or sessions (for example weather- or site-related context in a privacy-safe form).

## Position in PRISM

- **PRISM (model)** defines the structure and metadata expectations for environment sidecars and tables.
- **PRISM Studio (software)** executes environment workflows (generation, validation runs, and exports where applicable).

## Typical Artifacts

- Environment TSV tables with contextual variables.
- Matching JSON sidecars describing fields, units, and provenance.

## Validation

Environment files are validated by PRISM Studio/CLI against the environment schema used by your selected schema version.

## Notes

Use environment data as contextual metadata. Avoid storing direct identifying temporal/location details unless your governance and privacy policy explicitly allow it.
