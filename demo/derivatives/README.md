# Demo Derivatives Recipes

This folder contains derivative scoring recipes that can be used with `prism_tools.py` to generate computed scores from raw PRISM data.

## Structure

```
derivatives/
├── surveys/
│   └── wellbeing.json      # Scoring recipe for wellbeing survey
└── biometrics/
    └── fitness.json        # Scoring recipe for fitness assessment
```

## Survey Derivatives (wellbeing.json)

Demonstrates:
- **Scale inversion**: WB03 (stress) is reverse-coded so higher scores = better well-being
- **Subscales**:
  - `WB_total`: Sum of all items (5-25)
  - `WB_positive`: Mean of happiness + energy items
  - `WB_satisfaction`: Mean of life satisfaction + sleep items
  - `WB_stress_inv`: Inverted stress score

### Usage

```bash
# Generate derivatives from PRISM-structured survey data
python prism_tools.py derivatives-surveys /path/to/dataset \
    --recipe demo/derivatives/surveys/wellbeing.json
```

## Biometrics Derivatives (fitness.json)

Demonstrates:
- **Derived measures**:
  - `grip_strength_avg`: Mean of left/right grip strength
  - `hr_recovery`: Difference between post-exercise and recovery heart rate
- **Composite scores**:
  - `cardio_score`: Weighted combination of resting HR and recovery
  - `strength_score`: Weighted combination of grip strength and plank
  - `flexibility_score`: Normalized sit-and-reach score
  - `fitness_total`: Overall weighted fitness score

### Interpretation Guidelines

| Score | Interpretation |
|-------|----------------|
| 0-40  | Below average |
| 41-60 | Average |
| 61-80 | Above average |
| 81-100| Excellent |

## Recipe Format

### Transforms

```json
{
  "Transforms": {
    "Invert": {
      "Scale": {"min": 1, "max": 5},
      "Items": ["WB03"]
    }
  }
}
```

### Scores

```json
{
  "Scores": [
    {
      "Name": "score_name",
      "Method": "sum|mean|composite",
      "Items": ["item1", "item2"],
      "Missing": "ignore|require_all"
    }
  ]
}
```

## Note

These recipes are for demonstration purposes. Adapt them to match your actual instruments and scoring procedures.
