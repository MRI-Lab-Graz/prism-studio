# AND Export Templates

This folder contains templates used by the PRISM AND exporter.

## Files

### Templates (used by exporter)
- **`dataset_README_template.md`** - Template for ANC-formatted dataset README
- **`dataset_CITATION_template.cff`** - Template for dataset citation metadata

### Examples (for reference)
- **`example-gitlab-ci.yml`** - Example GitLab CI/CD pipeline for dataset validation
- **`example-github-actions.yml`** - Example GitHub Actions workflow for dataset validation

## Usage

These templates are automatically used by the AND export converter:

```bash
python -m src.converters.anc_export /path/to/dataset
```

The CI/CD examples should be copied to your exported dataset if you want automated validation:

**For GitLab:**
```bash
cp official/anc_templates/example-gitlab-ci.yml /path/to/dataset/.gitlab-ci.yml
```

**For GitHub:**
```bash
mkdir -p /path/to/dataset/.github/workflows
cp official/anc_templates/example-github-actions.yml /path/to/dataset/.github/workflows/validate.yml
```

## See Also

- [AND Export Documentation](../../docs/ANC_EXPORT.md)
- [AND Handbook](https://handbook.and.plus.ac.at/)
