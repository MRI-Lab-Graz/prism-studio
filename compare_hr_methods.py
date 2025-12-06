import os
import glob
import random
import subprocess
import pandas as pd
import sys
import json

# Add helpers to path
sys.path.append(os.path.join(os.getcwd(), 'helpers', 'physio'))

def get_vpd_files(root_dir):
    return glob.glob(os.path.join(root_dir, '**', '*.vpd'), recursive=True)

def get_hr_stats(tsv_path, fs):
    """Run the estimate_sampling_rate script to get HR stats."""
    cmd_est = [
        "python", "helpers/physio/estimate_sampling_rate.py",
        tsv_path, str(fs)
    ]
    try:
        est_proc = subprocess.run(cmd_est, check=True, capture_output=True, text=True)
        output = est_proc.stdout
        
        mean_hr = "N/A"
        qrs_width = "N/A"
        
        for line in output.splitlines():
            if "Mean HR:" in line and mean_hr == "N/A":
                mean_hr = line.split(":")[1].strip().split()[0]
            if "Median QRS width:" in line and qrs_width == "N/A":
                qrs_width = line.split(":")[1].strip().split()[0]
                
        return mean_hr, qrs_width
    except subprocess.CalledProcessError:
        return "Error", "Error"

def run_comparison(vpd_files, num_samples=5):
    if len(vpd_files) < num_samples:
        selected_files = vpd_files
    else:
        selected_files = random.sample(vpd_files, num_samples)
    
    results = []
    
    print(f"Selected {len(selected_files)} files for comparison...")
    
    for i, vpd_path in enumerate(selected_files):
        filename = os.path.basename(vpd_path)
        print(f"\n[{i+1}/{len(selected_files)}] Processing {filename}...")
        
        # --- Method 1: Auto-detect (Python style) ---
        out_auto_tsv = "temp_auto.tsv.gz"
        out_auto_json = "temp_auto.json"
        
        try:
            subprocess.run([
                "python", "helpers/physio/convert_varioport.py",
                vpd_path, out_auto_tsv, out_auto_json
            ], check=True, capture_output=True)
            
            # Get detected fs
            with open(out_auto_json, 'r') as f:
                fs_auto = json.load(f).get("SamplingFrequency", 75.0)
            
            hr_auto, qrs_auto = get_hr_stats(out_auto_tsv, fs_auto)
            
        except Exception as e:
            print(f"  Auto-detect failed: {e}")
            fs_auto, hr_auto, qrs_auto = "Fail", "Fail", "Fail"

        # --- Method 2: Forced 512 Hz (R style) ---
        out_forced_tsv = "temp_forced.tsv.gz"
        out_forced_json = "temp_forced.json"
        
        try:
            subprocess.run([
                "python", "helpers/physio/convert_varioport.py",
                vpd_path, out_forced_tsv, out_forced_json,
                "--base-freq", "1024"
            ], check=True, capture_output=True)
            
            hr_forced, qrs_forced = get_hr_stats(out_forced_tsv, 512)
            
        except Exception as e:
            print(f"  Forced 512Hz failed: {e}")
            hr_forced, qrs_forced = "Fail", "Fail"

        results.append({
            "File": filename,
            "Auto FS": fs_auto,
            "Auto HR": hr_auto,
            "Auto QRS (samples)": qrs_auto,
            "Forced FS": 512,
            "Forced HR": hr_forced,
            "Forced QRS (samples)": qrs_forced
        })
        
        # Cleanup
        for f in [out_auto_tsv, out_auto_json, out_forced_tsv, out_forced_json]:
            if os.path.exists(f):
                os.remove(f)

    return pd.DataFrame(results)

if __name__ == "__main__":
    data_dir = "/Volumes/Evo/data/VPDATA"
    all_vpds = get_vpd_files(data_dir)
    
    if not all_vpds:
        print("No files found.")
        sys.exit(1)
        
    df = run_comparison(all_vpds, 5)
    
    print("\n" + "="*80)
    print("COMPARISON: Auto-Detect (Python) vs Forced 512 Hz (R-Script)")
    print("="*80)
    print(df.to_string(index=False))
    print("="*80)
