import sys
import os
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import subprocess
import json

def verify_raw_signal(vpd_path):
    print(f"Verifying raw signal for {vpd_path}...")
    
    # Convert using Auto (75Hz)
    out_tsv = "temp_verify.tsv.gz"
    out_json = "temp_verify.json"
    
    subprocess.run([
        "python", "helpers/physio/convert_varioport.py",
        vpd_path, out_tsv, out_json
    ], check=True)
    
    # Load data
    df = pd.read_csv(out_tsv, sep='\t', compression='gzip')
    
    # Find ECG column
    ecg_col = [c for c in df.columns if 'ekg' in c.lower() or 'ecg' in c.lower()][0]
    ecg = df[ecg_col].values
    
    print(f"Total samples: {len(ecg)}")
    
    # Find a peak in the raw data
    # Simple threshold detection
    thresh = np.percentile(ecg, 99)
    peaks = np.where(ecg > thresh)[0]
    
    if len(peaks) == 0:
        print("No peaks found.")
        return

    # Take the first clear peak
    # Group consecutive indices
    peak_groups = np.split(peaks, np.where(np.diff(peaks) > 10)[0] + 1)
    
    print(f"Found {len(peak_groups)} potential peak regions.")
    
    for i in range(min(3, len(peak_groups))):
        group = peak_groups[i]
        center = group[len(group)//2]
        
        # Extract window
        win = 50
        start = max(0, center - win)
        end = min(len(ecg), center + win)
        snippet = ecg[start:end]
        
        # Measure width at half max (relative to local baseline)
        baseline = np.median(snippet)
        peak_val = np.max(snippet)
        half_max = baseline + (peak_val - baseline) / 2
        
        above_half = np.where(snippet > half_max)[0]
        if len(above_half) > 0:
            width_samples = above_half[-1] - above_half[0] + 1
            print(f"Peak {i+1} (at sample {center}): Width ~ {width_samples} samples")
            
            # Interpret
            width_ms_75 = width_samples / 75.0 * 1000
            width_ms_512 = width_samples / 512.0 * 1000
            print(f"  If 75 Hz:  {width_ms_75:.1f} ms")
            print(f"  If 512 Hz: {width_ms_512:.1f} ms")
            
            # Print values for visual inspection
            # print(snippet)

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python verify_raw_signal.py <vpd_file>")
        sys.exit(1)
    
    verify_raw_signal(sys.argv[1])
