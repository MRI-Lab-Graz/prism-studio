#!/usr/bin/env python3

import pandas as pd
from pathlib import Path

test_file = Path("examples/workshop/exercise_2_hunting_errors/bad_examples/mystery_example_06.tsv")

# Load the TSV
df = pd.read_csv(test_file, sep='\t', dtype=str)
print(f"Loaded {len(df)} rows")
print(f"Columns: {list(df.columns)}")

# Test session detection
session_col_candidates = {"session", "ses", "visit", "timepoint"}
lower_map = {str(c).strip().lower(): str(c).strip() for c in df.columns}
session_col = None
for cand in session_col_candidates:
    if cand in lower_map:
        session_col = lower_map[cand]
        break

print(f"\nDetected session column: {session_col}")

if session_col:
    # Get unique sessions
    sessions = sorted([
        str(v).strip()
        for v in df[session_col].dropna().unique()
        if str(v).strip()
    ])
    print(f"Sessions found: {sessions}")
    print(f"Session value counts:\n{df[session_col].value_counts().sort_index()}")
else:
    print("No session column found")
