# Registering the `biosample` modality (maintainer steps)

PRISM does not register modalities automatically. Do these steps by hand in the
pull request, then let CI validate the fixture in this folder.

1. Copy `biosample.schema.json` to `app/schemas/stable/biosample.schema.json`.
2. In `app/schemas/stable/entities.schema.json`, add this entry under
   `"modalities"`:

```json
{
  "biosample": {
    "kind": "prism",
    "suffixes": [
      "bloodchem"
    ],
    "extensions": [
      "tsv",
      "json"
    ]
  }
}
```

3. Add `"biosample"` to `COMMUNITY_MODALITY_SCHEMAS` in `tests/verify_repo.py`.
4. Check the registration:
   `python tests/verify_repo.py --check schema-sync` and
   `python tests/verify_repo.py --check modality-schema-conventions`.
5. Validate the generated dataset: from the repository root, run
   `python prism.py <this folder>/fixture`. It must pass without errors.

Review by hand what no check can judge: units, a modality that duplicates an
existing one under another name, and whether the sample holds any real
participant data.
