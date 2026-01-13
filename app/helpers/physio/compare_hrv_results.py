import json
import pandas as pd
import argparse


def compare_results(computed_json_path, ref_tsv_path, ref_json_path=None):
    # Load Computed Results
    with open(computed_json_path, "r") as f:
        computed = json.load(f)

    # Load Reference Data
    ref_df = pd.read_csv(ref_tsv_path, sep="\t")
    if ref_json_path:
        with open(ref_json_path, "r") as f:
            ref_meta = json.load(f)
    else:
        ref_meta = {}

    # Flatten computed results for easier lookup
    flat_computed = {}
    flat_computed.update(computed.get("TimeDomain", {}))
    flat_computed.update(computed.get("FrequencyDomain", {}))

    # Define Mapping: Computed Key -> Reference Column ID
    # Based on descriptions in ref_json
    mapping = {
        "mean_nni": "ECG05",  # Mean RR (ms)
        "sdnn": "ECG06",  # SDNN (ms)
        "mean_hr": "ECG07",  # Mean HR (bpm)
        "std_hr": "ECG08",  # SD HR (bpm)
        "min_hr": "ECG09",  # Min HR (bpm)
        "max_hr": "ECG10",  # Max HR (bpm)
        "rmssd": "ECG11",  # RMSSD (ms)
        "nni_50": "ECG12",  # NNxx (beats) - Assuming xx=50
        "pnni_50": "ECG13",  # pNNxx (%)
        # 'triangular_index': 'ECG14', # Not computed by hrv-analysis?
        # 'tinn': 'ECG15',
        # 'sdann': 'ECG16',
        # 'sdnni': 'ECG17',
        "vlf": "ECG21",  # VLFpow FFT (ms2) - Check units! hrv-analysis returns ms2
        "lf": "ECG22",  # LFpow FFT (ms2)
        "hf": "ECG23",  # HFpow FFT (ms2)
        "lf_hf_ratio": "ECG33",  # LF HF ratio FFT
        "total_power": "ECG32",  # TOTpow FFT (ms2)
        "sd1": "ECG51",  # SD1 (ms)
        "sd2": "ECG52",  # SD2 (ms)
        "sd2_sd1_ratio": "ECG53",  # SD2 SD1 ratio - hrv-analysis computes ratio_sd2_sd1
        "sampen": "ECG55",  # SampEn
    }

    # Add some computed keys that might have different names
    if "ratio_sd2_sd1" in flat_computed:
        flat_computed["sd2_sd1_ratio"] = flat_computed["ratio_sd2_sd1"]

    print(
        f"{'Metric':<25} | {'Computed':<15} | {'Reference':<15} | {'Diff':<15} | {'% Diff':<10}"
    )
    print("-" * 90)

    for comp_key, ref_col in mapping.items():
        if comp_key not in flat_computed:
            continue

        comp_val = flat_computed[comp_key]

        if ref_col not in ref_df.columns:
            continue

        ref_val = ref_df[ref_col].iloc[0]

        # Handle NaN
        if pd.isna(ref_val):
            ref_val_str = "NaN"
            diff = "N/A"
            pct_diff = "N/A"
        else:
            ref_val_str = f"{ref_val:.4f}"
            diff = comp_val - ref_val
            if ref_val != 0:
                pct_diff = (diff / ref_val) * 100
                pct_diff_str = f"{pct_diff:.2f}%"
            else:
                pct_diff_str = "Inf"
            diff_str = f"{diff:.4f}"

        desc = ref_meta.get(ref_col, {}).get("Description", comp_key)

        print(
            f"{desc:<25} | {comp_val:<15.4f} | {ref_val_str:<15} | {diff_str:<15} | {pct_diff_str:<10}"
        )


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("computed_json")
    parser.add_argument("ref_tsv")
    parser.add_argument("--ref_json", default=None)
    args = parser.parse_args()

    compare_results(args.computed_json, args.ref_tsv, args.ref_json)
