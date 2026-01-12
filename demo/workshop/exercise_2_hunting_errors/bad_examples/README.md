# Mystery Error Challenges

These files all have something wrong with them. Your task is to upload them to PRISM and figure out exactly why they are failing validation.

## The Challenges

| File | Status | Your Diagnosis |
|------|--------|----------------|
| `mystery_example_01.tsv` | ❌ Fails | |
| `mystery_example_02.tsv` | ❌ Fails | |
| `mystery_example_03.tsv` | ❌ Fails | |
| `mystery_example_04.tsv` | ❌ Fails | |
| `mystery_example_05.tsv` | ❌ Fails | |
| `mystery_example_06.tsv` | ❌ Fails | |
| `mystery_example_07.tsv` | ❌ Fails | |
| `mystery_example_08.tsv` | ❌ Fails | |
| `mystery_example_09.tsv` | ❌ Fails | |
| `mystery_example_10.tsv` | ❌ Fails | |
| `mystery_example_11.tsv` | ❌ Fails | |
| `mystery_example_12.tsv` | ❌ Fails | |
| `mystery_example_13.tsv` | ❌ Fails | |

## Instructions

1. Go to the Data Conversion page in the PRISM web interface.
2. Select the wellbeing template library: `demo/templates/survey/`.
3. Try uploading each mystery file one by one.
4. Read the validation error messages carefully.
5. Can you identify the specific row or column causing the problem?

## Solution Key (Don't look until you've tried!)

<details>
<summary>Click to see common issues found in these files</summary>

1.  **mystery_example_01**: Missing `participant_id` column
2.  **mystery_example_02**: Wrong delimiter (uses `;` instead of TAB)
3.  **mystery_example_03**: String values where numbers were expected
4.  **mystery_example_04**: Values out of range (e.g., 99 in a 1-5 scale)
5.  **mystery_example_05**: Missing values in required fields
6.  **mystery_example_06**: Unknown columns not defined in the template
7.  **mystery_example_07**: Duplicate IDs (same participant/session twice)
8.  **mystery_example_08**: Inconsistent number of columns across rows
9.  **mystery_example_09**: Mixed data types and broken values (NaN, Inf, #REF!)
10. **mystery_example_10**: Empty file
11. **mystery_example_11**: Headers present but no data rows
12. **mystery_example_12**: Special characters, HTML tags, or quotes causing issues
13. **mystery_example_13**: Incorrectly formatted participant IDs (missing `sub-` prefix)

</details>
