# Schema Versioning

PRISM supports schema versioning so datasets can be validated against a specific schema release.

## Available Versions

Schema versions are stored under `schemas/`.

Common examples:

- `stable` - current recommended version
- `v0.1` - tagged legacy version

## CLI Usage

Use the default (`stable`):

```bash
python prism.py /path/to/dataset
```

Use a specific version:

```bash
python prism.py /path/to/dataset --schema-version 0.1
python prism.py /path/to/dataset --schema-version v0.1
python prism.py /path/to/dataset --schema-version stable
```

List available versions:

```bash
python prism.py --list-versions
```

## Web Interface

In PRISM Studio, select the schema version in the validator controls before running validation.

Validation outputs include the schema version used, so reports remain traceable.

## Version Naming

- `stable` points to the recommended release.
- Version tags follow `v<major>.<minor>` style (for example `v0.1`).
- The CLI accepts both `0.1` and `v0.1`.

## Best Practices

1. Use `stable` for routine/project validation.
2. Use explicit legacy versions only for reproducibility checks.
3. Record the schema version in methods/report text when sharing results.
4. Re-validate datasets after switching schema versions.

## Troubleshooting

If a schema version is not found:

- Check that the corresponding folder exists in `schemas/`.
- Verify spelling (`stable`, `v0.1`, etc.).
- Run `python prism.py --list-versions` to confirm available options.
