import argparse
import pandas as pd
import numpy as np
import json
import os
from hrvanalysis import remove_outliers, interpolate_nan_values
from hrvanalysis import get_time_domain_features, get_frequency_domain_features


class NumpyEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, np.integer):
            return int(obj)
        if isinstance(obj, np.floating):
            return float(obj)
        if isinstance(obj, np.ndarray):
            return obj.tolist()
        return super(NumpyEncoder, self).default(obj)


def compute_hrv(rpeaks_file, output_json=None):
    print(f"Loading R-peaks from {rpeaks_file}...")
    df = pd.read_csv(rpeaks_file, sep="\t")

    if "timestamp_sec" not in df.columns:
        print("Error: 'timestamp_sec' column not found in input file.")
        return

    # Calculate RR intervals in milliseconds
    timestamps = df["timestamp_sec"].values
    rr_intervals = np.diff(timestamps) * 1000  # Convert to ms

    print(f"Initial RR intervals: {len(rr_intervals)}")

    # Pre-processing: Remove outliers and ectopic beats
    # This is crucial for HRV analysis
    rr_intervals_cleaned = remove_outliers(rr_intervals, low_rri=300, high_rri=2000)
    rr_intervals_cleaned = interpolate_nan_values(rr_intervals_cleaned)

    # Remove ectopic beats (optional, but good practice)
    # rr_intervals_cleaned = remove_ectopic_beats(rr_intervals_cleaned, method="malik")
    # rr_intervals_cleaned = interpolate_nan_values(rr_intervals_cleaned)

    print(f"Cleaned RR intervals: {len(rr_intervals_cleaned)}")

    # Time Domain Features
    print("\n--- Time Domain Metrics ---")
    time_domain_features = get_time_domain_features(rr_intervals_cleaned)
    for k, v in time_domain_features.items():
        print(f"{k}: {v:.4f}")

    # Frequency Domain Features
    print("\n--- Frequency Domain Metrics ---")
    try:
        freq_domain_features = get_frequency_domain_features(rr_intervals_cleaned)
        for k, v in freq_domain_features.items():
            print(f"{k}: {v:.4f}")
    except Exception as e:
        print(f"Could not compute frequency domain features: {e}")
        freq_domain_features = {}

    # Combine results
    results = {
        "TimeDomain": time_domain_features,
        "FrequencyDomain": freq_domain_features,
        "Stats": {
            "n_intervals_original": len(rr_intervals),
            "n_intervals_cleaned": len(rr_intervals_cleaned),
        },
    }

    if output_json:
        with open(output_json, "w") as f:
            json.dump(results, f, indent=2, cls=NumpyEncoder)
        print(f"\nSaved HRV metrics to {output_json}")
    else:
        # Default output name
        base_name = os.path.splitext(rpeaks_file)[0]
        output_json = base_name + "_hrv.json"
        with open(output_json, "w") as f:
            json.dump(results, f, indent=2, cls=NumpyEncoder)
        print(f"\nSaved HRV metrics to {output_json}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Compute HRV metrics from R-peaks.")
    parser.add_argument("rpeaks_file", help="Path to R-peaks TSV file")
    parser.add_argument("--out-json", help="Path to output JSON file (optional)")

    args = parser.parse_args()

    compute_hrv(args.rpeaks_file, args.out_json)
