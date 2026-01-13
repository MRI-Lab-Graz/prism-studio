import argparse
import pandas as pd
import json
import os
import numpy as np
from scipy.signal import butter, filtfilt
from ecgdetectors import Detectors


def butter_bandpass(lowcut, highcut, fs, order=5):
    nyq = 0.5 * fs
    low = lowcut / nyq
    high = highcut / nyq
    b, a = butter(order, [low, high], btype="band")
    return b, a


def butter_bandpass_filter(data, lowcut, highcut, fs, order=5):
    b, a = butter_bandpass(lowcut, highcut, fs, order=order)
    y = filtfilt(b, a, data)
    return y


def detect_rpeaks(
    tsv_file,
    json_file=None,
    detector_type="hamilton",
    fs_override=None,
    do_filter=False,
    min_dist_sec=None,
):
    if json_file is None:
        # Try to infer json file from tsv file
        base_path = os.path.splitext(tsv_file)[0]
        json_file = base_path + ".json"

    if fs_override:
        fs = float(fs_override)
        print(f"Using overridden Sampling Frequency: {fs} Hz")
    elif os.path.exists(json_file):
        # Load Sampling Rate
        with open(json_file, "r") as f:
            metadata = json.load(f)
            fs = metadata.get("SamplingFrequency")
            print(f"Loaded Sampling Frequency from JSON: {fs} Hz")
    else:
        print("Error: SamplingFrequency not found.")
        return

    # Load Data
    print(f"Loading data from {tsv_file}...")
    df = pd.read_csv(tsv_file, sep="\t")

    if "ekg" not in df.columns:
        # Try case insensitive
        cols = [c.lower() for c in df.columns]
        if "ekg" in cols:
            ekg_col = df.columns[cols.index("ekg")]
        elif "ecg" in cols:
            ekg_col = df.columns[cols.index("ecg")]
        else:
            print(
                f"Error: Could not find 'ekg' or 'ecg' column. Available columns: {list(df.columns)}"
            )
            return
    else:
        ekg_col = "ekg"

    ecg_data = df[ekg_col].values

    if do_filter:
        print("Applying bandpass filter (0.5 - 45 Hz)...")
        nyquist = 0.5 * fs
        high_cut = 45.0
        if high_cut >= nyquist:
            print(
                f"Warning: High cut frequency {high_cut} is >= Nyquist {nyquist}. Clamping to {nyquist - 1}."
            )
            high_cut = nyquist - 1.0

        ecg_data = butter_bandpass_filter(ecg_data, 0.5, high_cut, fs, order=2)

    # Initialize Detectors
    detectors = Detectors(fs)

    print(f"Running {detector_type} detector on {len(ecg_data)} samples...")

    r_peaks = []
    if detector_type == "hamilton":
        r_peaks = detectors.hamilton_detector(ecg_data)
    elif detector_type == "christov":
        r_peaks = detectors.christov_detector(ecg_data)
    elif detector_type == "engzee":
        r_peaks = detectors.engzee_detector(ecg_data)
    elif detector_type == "pan_tompkins":
        r_peaks = detectors.pan_tompkins_detector(ecg_data)
    elif detector_type == "swt":
        r_peaks = detectors.swt_detector(ecg_data)
    elif detector_type == "two_average":
        r_peaks = detectors.two_average_detector(ecg_data)
    else:
        print(f"Unknown detector: {detector_type}")
        return

    print(f"Detected {len(r_peaks)} R-peaks (raw).")

    # Apply minimum distance filter
    if min_dist_sec:
        min_dist_samples = int(min_dist_sec * fs)
        print(
            f"Applying minimum distance filter: {min_dist_sec}s ({min_dist_samples} samples)"
        )

        filtered_peaks = []
        if len(r_peaks) > 0:
            filtered_peaks.append(r_peaks[0])
            for peak in r_peaks[1:]:
                if peak - filtered_peaks[-1] > min_dist_samples:
                    filtered_peaks.append(peak)

        print(
            f"Filtered {len(r_peaks) - len(filtered_peaks)} peaks. Remaining: {len(filtered_peaks)}"
        )
        r_peaks = filtered_peaks

    # Calculate Heart Rate
    if len(r_peaks) > 1:
        r_peaks_np = np.array(r_peaks)
        rr_intervals = np.diff(r_peaks_np) / fs  # in seconds
        hr = 60 / rr_intervals
        print(f"Mean Heart Rate: {np.mean(hr):.2f} bpm")
        print(f"Min/Max HR: {np.min(hr):.2f} / {np.max(hr):.2f} bpm")

    # Save results
    output_file = os.path.splitext(tsv_file)[0] + "_rpeaks.tsv"

    # Create a DataFrame for output
    # We can save indices and timestamps
    timestamps = np.array(r_peaks) / fs
    results_df = pd.DataFrame({"sample_index": r_peaks, "timestamp_sec": timestamps})

    results_df.to_csv(output_file, sep="\t", index=False)
    print(f"Saved R-peaks to {output_file}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Detect R-peaks in ECG data.")
    parser.add_argument("tsv_file", help="Path to BIDS physio TSV file")
    parser.add_argument("--json", help="Path to BIDS physio JSON sidecar (optional)")
    parser.add_argument(
        "--detector",
        default="hamilton",
        choices=[
            "hamilton",
            "christov",
            "engzee",
            "pan_tompkins",
            "swt",
            "two_average",
        ],
        help="Detector algorithm to use",
    )
    parser.add_argument("--fs", help="Override sampling frequency (Hz)")
    parser.add_argument(
        "--filter", action="store_true", help="Apply bandpass filter (0.5-45Hz)"
    )
    parser.add_argument(
        "--min-dist",
        type=float,
        help="Minimum distance between peaks in seconds (refractory period)",
    )

    args = parser.parse_args()

    detect_rpeaks(
        args.tsv_file, args.json, args.detector, args.fs, args.filter, args.min_dist
    )
