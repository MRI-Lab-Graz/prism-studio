#!/usr/bin/env python3
"""
Estimate true sampling rate from ECG signal morphology.
Uses QRS complex duration (typically 80-120ms) as a reference.
"""

import sys
import gzip
import numpy as np
import pandas as pd
from scipy import signal


def load_ecg_from_tsv_gz(path):
    """Load ECG column from gzipped TSV."""
    df = pd.read_csv(path, sep='\t', compression='gzip')
    
    # Find ECG column (case insensitive)
    ecg_col = None
    for col in df.columns:
        if 'ekg' in col.lower() or 'ecg' in col.lower():
            ecg_col = col
            break
    
    if ecg_col is None:
        raise ValueError(f"No ECG/EKG column found in {path}. Columns: {df.columns.tolist()}")
    
    return df[ecg_col].values


def estimate_fs_from_qrs_width(ecg_signal, assumed_fs, expected_qrs_ms=(80, 120)):
    """
    Estimate true sampling rate by measuring QRS complex width.
    
    Parameters:
    -----------
    ecg_signal : array
        ECG signal
    assumed_fs : float
        The sampling rate we think we have
    expected_qrs_ms : tuple
        Expected QRS duration in milliseconds (min, max)
    
    Returns:
    --------
    estimated_fs : float
        Estimated true sampling rate
    confidence : str
        Confidence level
    """
    
    # Bandpass filter for QRS detection (5-15 Hz)
    sos = signal.butter(4, [5, 15], btype='band', fs=assumed_fs, output='sos')
    ecg_filtered = signal.sosfilt(sos, ecg_signal)
    
    # Find R-peaks using scipy
    peaks, properties = signal.find_peaks(
        ecg_filtered,
        distance=int(0.3 * assumed_fs),  # min 300ms between peaks (200 bpm)
        prominence=np.std(ecg_filtered) * 0.5
    )
    
    if len(peaks) < 10:
        return None, "Insufficient R-peaks detected"
    
    print(f"Found {len(peaks)} R-peaks")

    # Calculate HR
    rr_intervals_samples = np.diff(peaks)
    rr_intervals_sec = rr_intervals_samples / assumed_fs
    hr_bpm = 60 / rr_intervals_sec
    
    mean_hr = np.mean(hr_bpm)
    std_hr = np.std(hr_bpm)
    min_hr = np.min(hr_bpm)
    max_hr = np.max(hr_bpm)
    
    print(f"\nHeart Rate Statistics (at {assumed_fs} Hz):")
    print(f"  Mean HR: {mean_hr:.1f} bpm")
    print(f"  Std HR:  {std_hr:.1f} bpm")
    print(f"  Range:   {min_hr:.1f} - {max_hr:.1f} bpm")
    
    # Measure QRS width using full-width at half-maximum (FWHM) approach
    qrs_widths = []
    
    for peak_idx in peaks[:50]:  # Use first 50 peaks
        # Get window around peak
        window_size = int(0.2 * assumed_fs)  # 200ms window
        start = max(0, peak_idx - window_size // 2)
        end = min(len(ecg_signal), peak_idx + window_size // 2)
        
        segment = ecg_signal[start:end]
        peak_in_segment = peak_idx - start
        
        if peak_in_segment <= 0 or peak_in_segment >= len(segment):
            continue
            
        peak_val = segment[peak_in_segment]
        
        # Find width at half maximum
        half_max = (peak_val + np.median(segment)) / 2
        
        # Search left
        left_idx = peak_in_segment
        while left_idx > 0 and segment[left_idx] > half_max:
            left_idx -= 1
        
        # Search right
        right_idx = peak_in_segment
        while right_idx < len(segment) - 1 and segment[right_idx] > half_max:
            right_idx += 1
        
        width_samples = right_idx - left_idx
        if 5 < width_samples < 100:  # Sanity check
            qrs_widths.append(width_samples)
    
    if not qrs_widths:
        return None, "Could not measure QRS widths"
    
    median_qrs_width_samples = np.median(qrs_widths)
    print(f"Median QRS width: {median_qrs_width_samples:.1f} samples")
    
    # Calculate what the true sampling rate would be for expected QRS durations
    expected_qrs_samples_min = expected_qrs_ms[0] / 1000 * assumed_fs
    expected_qrs_samples_max = expected_qrs_ms[1] / 1000 * assumed_fs
    
    # If measured width is within expected range, assumed_fs is likely correct
    if expected_qrs_samples_min <= median_qrs_width_samples <= expected_qrs_samples_max:
        return assumed_fs, "High confidence - QRS width matches expected range"
    
    # Otherwise, calculate correction factor
    # Use middle of expected range (100ms) as reference
    expected_qrs_mid_ms = np.mean(expected_qrs_ms)
    measured_qrs_ms = (median_qrs_width_samples / assumed_fs) * 1000
    
    scaling_factor = expected_qrs_mid_ms / measured_qrs_ms
    estimated_fs = assumed_fs * scaling_factor
    
    confidence = "Medium"
    if 0.8 <= scaling_factor <= 1.2:
        confidence = "High"
    elif 0.5 <= scaling_factor <= 2.0:
        confidence = "Medium"
    else:
        confidence = "Low"
    
    print(f"Measured QRS duration: {measured_qrs_ms:.1f} ms")
    print(f"Expected QRS duration: {expected_qrs_mid_ms:.1f} ms")
    print(f"Scaling factor: {scaling_factor:.3f}")
    
    return estimated_fs, confidence


def main():
    if len(sys.argv) < 2:
        print("Usage: python estimate_sampling_rate.py <ecg_file.tsv.gz> [assumed_fs]")
        sys.exit(1)
    
    ecg_path = sys.argv[1]
    assumed_fs = float(sys.argv[2]) if len(sys.argv) > 2 else 75.0
    
    print(f"Loading ECG from: {ecg_path}")
    print(f"Assumed sampling rate: {assumed_fs} Hz")
    print()
    
    ecg = load_ecg_from_tsv_gz(ecg_path)
    print(f"ECG signal length: {len(ecg)} samples")
    print(f"Duration at assumed fs: {len(ecg)/assumed_fs:.1f} seconds ({len(ecg)/assumed_fs/60:.1f} minutes)")
    print()
    
    # Try estimation
    estimated_fs, confidence = estimate_fs_from_qrs_width(ecg, assumed_fs)
    
    if estimated_fs is None:
        print(f"ERROR: {confidence}")
        sys.exit(1)
    
    print()
    print("="*60)
    print(f"ESTIMATED TRUE SAMPLING RATE: {estimated_fs:.1f} Hz")
    print(f"Confidence: {confidence}")
    print(f"Duration at estimated fs: {len(ecg)/estimated_fs:.1f} seconds ({len(ecg)/estimated_fs/60:.1f} minutes)")
    print("="*60)
    
    # Test common rates
    print("\nTesting common sampling rates:")
    for test_fs in [75, 128, 150, 200, 250, 256, 500, 512, 1000]:
        test_est, test_conf = estimate_fs_from_qrs_width(ecg, test_fs)
        if test_est:
            deviation = abs(test_est - test_fs) / test_fs * 100
            print(f"  {test_fs:4.0f} Hz -> estimated {test_est:6.1f} Hz (deviation: {deviation:5.1f}%, {test_conf})")


if __name__ == '__main__':
    main()
