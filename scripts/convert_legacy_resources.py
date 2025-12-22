import pandas as pd
import json
import os
import re
from pathlib import Path
from datetime import datetime

def sanitize_task_name(name):
    """Convert to alphanumeric lowercase."""
    if not name or not isinstance(name, str):
        return "unknown"
    # Remove anything not alphanumeric
    s = re.sub(r'[^a-zA-Z0-9]', '', name)
    return s.lower()

def convert_resources():
    resources_dir = Path("/Volumes/Evo/software/prism-studio/tmp/resources")
    output_dir = Path("/Volumes/Evo/software/prism-studio/library/survey")
    output_dir.mkdir(parents=True, exist_ok=True)

    files = [f for f in resources_dir.glob("*.xlsx") if not f.name.startswith("~$")]
    
    print(f"Found {len(files)} Excel files to convert.")

    for excel_path in files:
        print(f"Processing {excel_path.name}...")
        try:
            df = pd.read_excel(excel_path)
            if df.empty:
                print(f"  Skipping empty file: {excel_path.name}")
                continue

            # Skip row 0 (instructions)
            data_df = df.iloc[1:].copy()
            
            # Extract Survey Metadata from first data row
            first_row = data_df.iloc[0]
            raw_name = str(first_row.get('construct', excel_path.stem))
            task_name = sanitize_task_name(excel_path.stem)
            description = str(first_row.get('description', ''))
            instruction = str(first_row.get('instruction', ''))
            
            # Extract Scales
            scales = {}
            # Scale 1
            s1_levels = df['levels'].iloc[1:].dropna().tolist()
            s1_descs = df['leveldescription'].iloc[1:].dropna().tolist()
            if s1_levels and s1_descs:
                scales[1] = {str(l): {"de": str(d), "en": ""} for l, d in zip(s1_levels, s1_descs)}
            
            # Alternative Scales (2, 3, 4)
            for i in range(2, 5):
                lvl_col = f'levels{i}'
                desc_col = f'leveldescription{i}'
                if lvl_col in df.columns and desc_col in df.columns:
                    si_levels = df[lvl_col].iloc[1:].dropna().tolist()
                    si_descs = df[desc_col].iloc[1:].dropna().tolist()
                    if si_levels and si_descs:
                        scales[i] = {str(l): {"de": str(d), "en": ""} for l, d in zip(si_levels, si_descs)}

            # Build JSON structure
            result = {
                "Technical": {
                    "StimulusType": "Questionnaire",
                    "FileFormat": "tsv",
                    "SoftwarePlatform": "Legacy/Imported",
                    "Language": "de",
                    "Respondent": "self",
                    "ResponseType": ["paper-pencil"]
                },
                "Study": {
                    "TaskName": task_name,
                    "OriginalName": {"de": raw_name, "en": ""},
                    "Version": {"de": "1.0", "en": ""},
                    "Description": {"de": description, "en": ""},
                    "Instruction": {"de": instruction, "en": ""},
                    "Citation": ""
                },
                "Metadata": {
                    "SchemaVersion": "1.1.0",
                    "CreationDate": datetime.now().strftime("%Y-%m-%d"),
                    "Creator": "convert_legacy_resources.py"
                }
            }

            # Add Items
            for _, row in data_df.iterrows():
                item_id = str(row.get('Itemname', '')).strip()
                if not item_id or item_id.lower() == 'nan':
                    continue
                
                item_desc = str(row.get('Itemdescription', ''))
                alt_scale_val = row.get('alternativescale')
                try:
                    scale_idx = int(float(alt_scale_val)) if pd.notna(alt_scale_val) else 1
                except:
                    scale_idx = 1
                
                item_json = {
                    "Description": {"de": item_desc, "en": ""},
                    "Levels": scales.get(scale_idx, scales.get(1, {}))
                }
                
                # Add extra metadata if present
                if pd.notna(row.get('inverted')) and str(row.get('inverted')).lower() == 'yes':
                    item_json["Inverted"] = True
                
                subscale = row.get('subscale')
                if pd.notna(subscale) and str(subscale).strip():
                    item_json["Subscale"] = str(subscale).strip()

                result[item_id] = item_json

            # Save to library
            output_path = output_dir / f"survey-{task_name}.json"
            with open(output_path, "w", encoding="utf-8") as f:
                json.dump(result, f, indent=2, ensure_ascii=False)
            
            print(f"  Successfully converted to {output_path.name}")

        except Exception as e:
            print(f"  Error processing {excel_path.name}: {e}")

if __name__ == "__main__":
    convert_resources()
