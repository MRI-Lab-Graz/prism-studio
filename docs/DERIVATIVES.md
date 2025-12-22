# PRISM Derivatives Specification

PRISM can automatically compute scores, subscales, and intermediate variables from your raw survey and biometric data. This is controlled by **Recipe** files located in the repository under `derivatives/surveys/` and `derivatives/biometrics/`.

## Recipe Structure

A recipe is a JSON file that defines how to transform raw items into scores.

```json
{
  "RecipeVersion": "1.0",
  "Kind": "biometrics",
  "Biometrics": {
    "Name": "Y Balance Test",
    "BiometricName": "y"
  },
  "Transforms": {
    "Invert": {
      "Items": ["item1", "item2"],
      "Scale": { "min": 0, "max": 4 }
    },
    "Derived": [
      {
        "Name": "best_trial",
        "Method": "max",
        "Items": ["trial1", "trial2", "trial3"]
      }
    ]
  },
  "Scores": [
    {
      "Name": "total_score",
      "Method": "sum",
      "Items": ["item1", "item2", "best_trial"]
    }
  ]
}
```

---

## Available Methods

### 1. `Transforms.Derived` (Intermediate Variables)
Used to compute values that are then used as inputs for final scores (e.g., taking the best of three trials).

| Method | Description |
| :--- | :--- |
| `max` | Returns the maximum value among the items. (Default) |
| `min` | Returns the minimum value among the items. |
| `mean` | Returns the arithmetic mean (average) of the items. (Alias: `avg`) |
| `sum` | Returns the sum of the items. |

### 2. `Scores` (Final Output Columns)
Used to compute the final variables that will appear in the derivative TSV/Excel/SPSS files.

| Method | Description |
| :--- | :--- |
| `sum` | Returns the sum of the items. (Default) |
| `mean` | Returns the arithmetic mean (average) of the items. |
| `formula` | Evaluates a mathematical expression. Requires a `Formula` field. |

#### The `formula` Method
When using `Method: "formula"`, you must provide a `Formula` string. Use curly braces `{}` to reference item IDs or derived variable names.

**Example:**
```json
{
  "Name": "normalized_score",
  "Method": "formula",
  "Items": ["A", "PM", "PL", "LegLength"],
  "Formula": "(({A} + {PM} + {PL}) / (3 * {LegLength})) * 100"
}
```

---

## Handling Missing Data

For `Scores`, you can control how missing values (`n/a` or empty cells) are handled using the `Missing` field:

| Option | Description |
| :--- | :--- |
| `ignore` | Skips missing values in calculations (e.g., `sum` of `[5, n/a, 5]` is `10`). (Default) |
| `require_all` | If any item in the list is missing, the entire score becomes `n/a`. (Aliases: `all`, `strict`) |

---

## Item Inversion (Reverse Coding)

The `Transforms.Invert` block allows you to automatically reverse-code items before any other calculations take place.

*   `Items`: List of item IDs to invert.
*   `Scale`: Must provide `min` and `max`.
*   **Formula**: `new_value = (max + min) - old_value`

---

## Validation (When and How)

- Recipes are validated **before execution** (fail-fast). If a recipe is malformed (unknown `Method`, missing `Formula`, etc.), derivative generation stops with a clear error message.
- The validator checks, among other things:
  - `Kind` is `survey` or `biometrics`
  - `Survey.TaskName` / `Biometrics.BiometricName` is present
  - `Method` values are from the supported sets documented above
  - `formula` scores contain a `Formula` and every `{placeholder}` is also listed in `Items`

---

## Output Structure

When you run derivatives, PRISM creates a BIDS-compliant derivatives folder:

- `derivatives/surveys/` or `derivatives/biometrics/`
- `dataset_description.json`: Automatically generated metadata file. It inherits `Name`, `Authors`, `License`, and `Funding` from your root dataset description to ensure transparency and reproducibility.
- `<recipe_id>/`: Folders containing the computed scores.

The `dataset_description.json` includes a `GeneratedBy` section identifying `prism-tools` and the specific version used, along with a timestamp.
