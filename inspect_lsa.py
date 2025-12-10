
import sys
import os
import pandas as pd

# Add the current directory to sys.path so we can import from scripts
sys.path.append(os.getcwd())

from scripts.limesurvey_to_prism import parse_lsa_responses

lsa_path = "/Volumes/Evo/data/AF134/sourcedata/Dance & Brain_T2.lsa"

if not os.path.exists(lsa_path):
    print(f"File not found: {lsa_path}")
    sys.exit(1)

print(f"Inspecting {lsa_path}...")
try:
    df, questions_map, groups_map = parse_lsa_responses(lsa_path)
    print("Columns found in LSA response:")
    for col in df.columns:
        print(f"  - {col}")
        
    print("\nFirst row sample:")
    print(df.iloc[0].to_dict())

except Exception as e:
    print(f"Error parsing LSA: {e}")
