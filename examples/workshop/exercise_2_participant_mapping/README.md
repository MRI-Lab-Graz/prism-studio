# Exercise 2: Participant Demographic Mapping

This exercise teaches you how to create and use `participants_mapping.json` files to transform raw demographic data with custom encodings into standardized PRISM format.

## What's in this folder

- **INSTRUCTIONS.md** - Step-by-step guide (45 minutes)
- **INSTRUCTIONS.pdf** - Printable version
- **template_participants_mapping.json** - Starting template for the exercise
- **solution_participants_mapping.json** - Complete solution (spoiler!)
- **raw_data/** - Sample datasets to practice with
  - wellbeing.tsv - Survey with demographic data (numeric codes)
  - fitness_data.tsv - Biometric data

## Quick Start

1. Read INSTRUCTIONS.md
2. Copy template_participants_mapping.json to code/library/participants_mapping.json
3. Edit it to map your demographic variables
4. Run validation - mapping auto-applies
5. Verify output in rawdata/participants.tsv
6. Compare with solution_participants_mapping.json

## Key Concepts

- **Source data**: Raw TSV/XLSX with custom variable names and encodings
- **Mapping specification**: JSON file documenting the transformations
- **Standard variables**: PRISM/BIDS-compatible demographic variable names
- **Value mapping**: Numeric codes → standard codes (1→M, 2→F, 4→O)
- **Auto-transformation**: PRISM applies mapping automatically during validation

## File Structure

```
exercise_2_participant_mapping/
├── INSTRUCTIONS.md                     # This guide
├── INSTRUCTIONS.pdf                    # Printable version
├── README.md                           # This file
├── template_participants_mapping.json  # Starting point
├── solution_participants_mapping.json  # Reference solution
└── raw_data/
    ├── wellbeing.tsv                   # Survey with numeric codes
    └── fitness_data.tsv                # Biometric data
```

## Time Estimate

- Reading instructions: 10 minutes
- Creating mapping: 20 minutes
- Testing and troubleshooting: 15 minutes
- **Total**: 45 minutes

## Learning Outcomes

After this exercise, you will understand:
- ✓ How to document custom demographic encodings
- ✓ The `participants_mapping.json` specification format
- ✓ How to map columns to PRISM standard variables
- ✓ Value transformation patterns (numeric → standard codes)
- ✓ Where to place the mapping file (`code/library/`)
- ✓ How PRISM auto-applies mappings during validation
- ✓ How to verify the output

## For Help

If you get stuck:
1. Check **INSTRUCTIONS.md** for troubleshooting section
2. Compare with **solution_participants_mapping.json**
3. See **docs/PARTICIPANTS_MAPPING.md** for detailed reference
4. Run test: `python tests/test_participants_mapping.py`

