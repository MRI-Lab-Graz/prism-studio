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
    
    # Find marker channel
    marker_col = [c for c in df.columns if 'marker' in c.lower() or 'trg' in c.lower()]
    if marker_col:
        marker_data = df[marker_col[0]].values
        # Find non-zero markers
        marker_indices = np.where(marker_data > 0)[0]
        if len(marker_indices) > 0:
            print(f"\nMarker Analysis:")
            print(f"  Found {len(marker_indices)} marker events.")
            print(f"  First marker at sample: {marker_indices[0]}")
            print(f"  Last marker at sample:  {marker_indices[-1]}")
            duration_samples = marker_indices[-1] - marker_indices[0]
            print(f"  Marker span: {duration_samples} samples")
            print(f"  Span at 75 Hz:  {duration_samples/75.0/60:.2f} minutes")
            print(f"  Span at 256 Hz: {duration_samples/256.0/60:.2f} minutes")
            print(f"  Span at 512 Hz: {duration_samples/512.0/60:.2f} minutes")
        else:
            print("\nMarker Analysis: No markers found.")

    # Find a peak in the raw data
    # Simple threshold detection
    thresh = np.percentile(ecg, 99.5)
    peaks = np.where(ecg > thresh)[0]
    
    if len(peaks) == 0:
        print("No peaks found.")
        return

    # Take the first clear peak
    # Group consecutive indices
    peak_groups = np.split(peaks, np.where(np.diff(peaks) > 10)[0] + 1)
    
    print(f"\nPeak Analysis (Found {len(peak_groups)} regions):")
    
    for i in range(min(3, len(peak_groups))):
        group = peak_groups[i]
        center = group[len(group)//2]
        
        # Extract window
        win = 20
        start = max(0, center - win)
        end = min(len(ecg), center + win)
        snippet = ecg[start:end]
        
        print(f"\nPeak {i+1} (Center: {center}):")
        print(f"Values: {snippet.tolist()}")
        
        # Measure width at half max (relative to local baseline)
        baseline = np.median(snippet)
        peak_val = np.max(snippet)
        half_max = baseline + (peak_val - baseline) / 2
        
        above_half = np.where(snippet > half_max)[0]
        if len(above_half) > 0:
            width_samples = above_half[-1] - above_half[0] + 1
            print(f"  FWHM Width: {width_samples} samples")
            print(f"  If 75 Hz:  {width_samples/75.0*1000:.1f} ms")
            print(f"  If 256 Hz: {width_samples/256.0*1000:.1f} ms")
            print(f"  If 512 Hz: {width_samples/512.0*1000:.1f} ms")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python verify_raw_signal.py <vpd_file>")
        sys.exit(1)
    
    verify_raw_signal(sys.argv[1])
