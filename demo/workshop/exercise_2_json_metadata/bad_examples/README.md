# Bad Example Files for Testing

These files are intentionally malformed to test error handling in the PRISM converter.

## Test Cases

| File | Issue | Expected Behavior |
|------|-------|-------------------|
| `01_missing_id_column.tsv` | No `participant_id` column | Error: Cannot identify participants |
| `02_wrong_delimiter.tsv` | Uses semicolons instead of tabs | May fail to parse columns correctly |
| `03_string_values.tsv` | Text instead of numeric Likert values | Warning or error about non-numeric data |
| `04_out_of_range_values.tsv` | Values outside 1-5 scale (99, -5, 300) | Should warn about invalid scale values |
| `05_empty_values.tsv` | Missing values in cells | Should handle gracefully, possibly warn |
| `06_unknown_columns.tsv` | Extra columns not in template | Depends on `unknown` setting (warn/ignore/error) |
| `07_duplicate_ids.tsv` | Same participant+session twice | Should warn about duplicates |
| `08_inconsistent_columns.tsv` | Rows have different column counts | Parsing error expected |
| `09_mixed_types.tsv` | Mix of numbers, floats, N/A, NULL, #REF! | Should handle or warn about bad values |
| `10_empty_file.tsv` | Completely empty file | Error: No data to process |
| `11_headers_only.tsv` | Headers but no data rows | Warning: No participant data |
| `12_special_characters.tsv` | Quotes, HTML tags, special chars | Should escape/sanitize properly |
| `13_wrong_id_format.tsv` | IDs not in `sub-XXX` format | May auto-fix or warn |

## Usage

1. Go to the Data Conversion page in the web interface
2. Select the wellbeing template library: `demo/templates/survey/`
3. Try uploading each file to see how errors are handled
4. Check the terminal log and validation results

## Expected Results

A well-designed converter should:
- ✅ Provide clear error messages explaining what's wrong
- ✅ Point to the specific row/column with issues
- ✅ Fail gracefully without crashing
- ✅ Validate data types and ranges where possible
- ✅ Handle edge cases like empty files
