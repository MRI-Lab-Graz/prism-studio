#!/usr/bin/env python3
import os
import json
import csv
import argparse
from pathlib import Path

def generate_boilerplate(json_path, output_dir):
    """
    Generates a boilerplate TSV file from a PRISM library JSON template.
    Extracts all non-reserved keys as columns and adds a dummy data row.
    """
    try:
        with open(json_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
    except Exception as e:
        print(f"Error reading {json_path}: {e}")
        return
    
    # Reserved keys in PRISM library files that are metadata, not columns
    reserved = {"Technical", "I18n", "Study", "Metadata", "Instructions", "Levels"}
    
    # Extract variable names (keys that are not in the reserved list)
    variables = [k for k in data.keys() if k not in reserved]
    
    if not variables:
        print(f"  - No variables found in {json_path}, skipping.")
        return

    # Determine output filename
    # e.g., survey-ads.json -> survey-ads_boilerplate.tsv
    stem = Path(json_path).stem
    output_path = os.path.join(output_dir, f"{stem}_boilerplate.tsv")
    
    try:
        with open(output_path, 'w', encoding='utf-8', newline='') as f:
            writer = csv.writer(f, delimiter='\t')
            writer.writerow(variables)
            
            # Generate a dummy row with example values based on the schema
            dummy_row = []
            for var in variables:
                var_def = data.get(var, {})
                if isinstance(var_def, dict):
                    # Try to find an example value from Levels
                    levels = var_def.get("Levels")
                    if isinstance(levels, dict) and levels:
                        # Use the first key as an example
                        dummy_row.append(list(levels.keys())[0])
                    else:
                        # Fallback based on DataType if available
                        dtype = var_def.get("DataType", "string").lower()
                        if dtype in ("int", "integer"):
                            dummy_row.append("1")
                        elif dtype in ("float", "number"):
                            dummy_row.append("1.0")
                        else:
                            dummy_row.append("n/a")
                else:
                    dummy_row.append("n/a")
            
            writer.writerow(dummy_row)
        
        print(f"  ✅ Created {output_path}")
    except Exception as e:
        print(f"  ❌ Error writing {output_path}: {e}")

def main():
    parser = argparse.ArgumentParser(
        description="Generate boilerplate TSV files from PRISM library JSON files."
    )
    parser.add_argument(
        "input", 
        help="Path to a JSON file or a directory containing JSON files (e.g., library/survey)."
    )
    parser.add_argument(
        "--output", 
        default="boilerplates", 
        help="Output directory for TSV files (default: 'boilerplates')."
    )
    
    args = parser.parse_args()
    
    input_path = Path(args.input)
    output_dir = Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)
    
    print(f"Scanning {input_path} for PRISM templates...")
    
    if input_path.is_file():
        generate_boilerplate(input_path, output_dir)
    elif input_path.is_dir():
        json_files = sorted(list(input_path.glob("*.json")))
        if not json_files:
            print(f"No .json files found in {input_path}")
            return
        for f in json_files:
            generate_boilerplate(f, output_dir)
    else:
        print(f"Error: {input_path} not found.")
    
    print(f"\nDone! Boilerplates are in: {output_dir.absolute()}")

if __name__ == "__main__":
    main()
