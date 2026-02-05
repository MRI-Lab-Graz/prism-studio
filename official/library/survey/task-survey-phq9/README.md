# survey-phq9 - Pavlovia Experiment

This experiment was automatically generated from PRISM survey data.

## Files

- `survey-phq9.psyexp`: PsychoPy Builder experiment file
- `conditions.csv`: Trial/question parameters (if applicable)
- `README.md`: This file

## Usage

### Local Testing (PsychoPy)

1. Install PsychoPy: https://www.psychopy.org/download.html
2. Open `survey-phq9.psyexp` in PsychoPy Builder
3. Click the green "Run" button to test locally

### Upload to Pavlovia

1. Create account at https://pavlovia.org
2. In PsychoPy Builder:
   - Click "Pavlovia" button (globe icon)
   - Log in to Pavlovia
   - Create new project or sync to existing
3. Set experiment to "RUNNING" on Pavlovia.org

### Collecting Data

- Share your Pavlovia URL with participants
- Data saves automatically to Pavlovia or OSF
- Download data from your Pavlovia dashboard

## Customization

This is a basic conversion. You may want to customize:

- **Visual appearance**: Edit text sizes, colors, positions in Builder
- **Instructions**: Modify welcome/thanks messages
- **Timing**: Add response time recording
- **Logic**: Add conditional display in Code components
- **Randomization**: Enable in loop settings

## Converting Data Back to PRISM

After collecting data on Pavlovia:

```bash
python src/converters/pavlovia.py --import pavlovia_data.csv task-survey-phq9_beh.json
```

This will create PRISM-compatible TSV files.

## Support

- PRISM Documentation: docs/PAVLOVIA_EXPORT.md
- PsychoPy Forum: https://discourse.psychopy.org
- Pavlovia Help: https://pavlovia.org/docs
