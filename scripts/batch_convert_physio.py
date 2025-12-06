import os
import sys
import pandas as pd
from pathlib import Path

# Add project root to path to import helpers
project_root = Path(__file__).resolve().parent.parent
sys.path.append(str(project_root))

from helpers.physio.convert_varioport import convert_varioport

def main():
    # Configuration
    source_dir = Path("/Volumes/Evo/data/VPDATA")
    output_root = project_root / "PK01"
    participants_file = project_root / "participants.tsv"

    # 1. Load participants mapping
    print(f"Loading participants from {participants_file}...")
    try:
        df = pd.read_csv(participants_file, sep='\t')
    except Exception as e:
        print(f"Error reading participants file: {e}")
        return

    # Create mapping: last 3 digits -> full participant_id
    # e.g. "001" -> "sub-1292001"
    id_map = {}
    for pid in df['participant_id']:
        short_id = pid[-3:]
        id_map[short_id] = pid
    
    print(f"Loaded {len(id_map)} participants.")

    # 2. Walk through source directory
    print(f"Scanning {source_dir}...")
    
    processed_count = 0
    error_count = 0

    # Iterate over items in source_dir
    for subject_folder in source_dir.iterdir():
        if not subject_folder.is_dir():
            continue
        
        folder_name = subject_folder.name
        
        # Check if folder name matches a participant ID (last 3 digits)
        if folder_name in id_map:
            participant_id = id_map[folder_name]
            print(f"Found subject: {folder_name} -> {participant_id}")
            
            # Check for session folders (t1, t2, t3)
            for session_folder in subject_folder.iterdir():
                if not session_folder.is_dir():
                    continue
                
                session_name = session_folder.name
                if session_name not in ['t1', 't2', 't3']:
                    continue
                
                # Map session name: t1 -> 1, t2 -> 2, t3 -> 3
                session_num = session_name.replace('t', '')
                session_id = f"ses-{session_num}"
                
                # Check for VPDATA.RAW
                input_file = session_folder / "VPDATA.RAW"
                if not input_file.exists():
                    # Try case insensitive check if needed, but find output showed uppercase
                    continue
                
                # Define output paths
                # Structure: PK01/sub-<ID>/ses-<session>/physio/
                output_dir = output_root / participant_id / session_id / "physio"
                output_dir.mkdir(parents=True, exist_ok=True)
                
                # Filename: sub-<ID>_ses-<session>_task-rest_ecg.edf
                base_filename = f"{participant_id}_{session_id}_task-rest_ecg"
                output_edf = output_dir / f"{base_filename}.edf"
                output_json = output_dir / f"{base_filename}.json"
                
                print(f"  Converting {session_name} -> {session_id}...")
                print(f"    Input: {input_file}")
                print(f"    Output: {output_edf}")
                
                try:
                    convert_varioport(
                        str(input_file), 
                        str(output_edf), 
                        str(output_json)
                        # base_freq is forced to 512 inside the function now, so we don't pass it
                    )
                    processed_count += 1
                except Exception as e:
                    print(f"    ERROR converting {input_file}: {e}")
                    error_count += 1
                    
        else:
            # print(f"Skipping folder {folder_name} (not in participants list)")
            pass

    print("-" * 50)
    print(f"Batch conversion complete.")
    print(f"Processed: {processed_count}")
    print(f"Errors: {error_count}")

if __name__ == "__main__":
    main()
