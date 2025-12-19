# Raw Demo Data

This folder contains example source data in tabular format (TSV).

## Files

### `survey_wellbeing_data.tsv`
Synthetic survey responses for the Well-being questionnaire.
- 10 fictional participants (DEMO001-DEMO010)
- 5 questions (WB01-WB05)
- Random responses 1-5 on a Likert scale

### `biometrics_fitness_data.tsv`
Synthetic fitness assessment data.
- 10 fictional participants (DEMO001-DEMO010)
- 7 measures (resting_hr, plank_duration, sit_and_reach, etc.)
- Realistic random values

## Usage with Web Interface

These TSV files can be directly uploaded to the PRISM web interface:

1. Start the web interface: `python prism-studio.py`
2. Go to **Survey Generator** → **Survey Conversion**
3. Select a library path (use `demo/templates/survey`)
4. Upload `survey_wellbeing_data.tsv`
5. Click **Convert & Download** to get a PRISM-structured ZIP

For biometrics:
1. Go to **Biometrics** tab
2. Set library path to `demo/templates/biometrics`
3. Upload `biometrics_fitness_data.tsv`
4. Convert to PRISM format

## Supported Input Formats

The converter accepts:
- **TSV** (tab-separated values) - like these demo files
- **CSV** (comma-separated values)
- **XLSX** (Excel spreadsheets)
- **LSA** (LimeSurvey archives) - for survey data only

## Note

These files contain **completely synthetic data** - safe to share and use for testing.
