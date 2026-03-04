import struct
import json
import argparse
import re
from pathlib import Path
import numpy as np
import pyedflib


def _find_companion_definition_file(raw_path: str | Path) -> Path | None:
    path = Path(raw_path)
    exact_match = path.with_suffix(".def")
    if exact_match.exists():
        return exact_match

    defs_in_folder = sorted(path.parent.glob("*.def"))
    if len(defs_in_folder) == 1:
        return defs_in_folder[0]

    return None


def _parse_varioport_definition_file(def_path: str | Path) -> dict:
    """Parse VitaGraf/Varioport .def channel table.

    Returns a dict with keys:
      - file: definition file path
      - channels_by_index: mapping of zero-based channel index -> metadata
    """
    path = Path(def_path)
    channel_map: dict[int, dict] = {}

    # Example line:
    # C01 ekg    uV   $05 $01 $01 ...
    line_pattern = re.compile(
        r"^C(?P<index>\d{2})\s+"
        r"(?P<name>\S+)\s+"
        r"(?P<unit>\S+)\s+"
    )

    with open(path, "r", encoding="latin-1", errors="ignore") as handle:
        for raw_line in handle:
            line = raw_line.strip()
            if not line or line.startswith("*"):
                continue

            match = line_pattern.match(line)
            if not match:
                continue

            one_based_index = int(match.group("index"))
            zero_based_index = one_based_index - 1
            name = match.group("name").strip()
            unit = match.group("unit").strip()
            name_lower = name.lower()
            parts = line.split()
            hex_values: list[int | None] = []
            for token in parts[3:]:
                if not token.startswith("$"):
                    continue
                try:
                    hex_values.append(int(token[1:], 16))
                except ValueError:
                    hex_values.append(None)

            scn = hex_values[2] if len(hex_values) > 2 else None
            mux = hex_values[5] if len(hex_values) > 5 else None

            channel_map[zero_based_index] = {
                "index": zero_based_index,
                "name": name,
                "unit": unit,
                "is_placeholder": name_lower in {"ntused", "999", "unused"},
                "is_marker": "marker" in name_lower,
                "is_ecg": ("ekg" in name_lower or "ecg" in name_lower),
                "scn": scn,
                "mux": mux,
            }

    return {
        "file": str(path),
        "channels_by_index": channel_map,
    }


def _select_type7_channels_from_definition(
    channels: list[dict],
    definition_info: dict | None,
) -> tuple[list[dict], dict]:
    if not definition_info:
        return channels, {"status": "no_definition"}

    definition_channels = definition_info.get("channels_by_index", {})
    candidates = [
        c
        for c in channels
        if (
            c["index"] in definition_channels
            and not definition_channels[c["index"]].get("is_placeholder", False)
        )
    ]

    if not candidates:
        return channels, {"status": "no_non_placeholder_candidates"}

    ecg_candidates = [
        c for c in candidates if definition_channels[c["index"]].get("is_ecg", False)
    ]
    anchor = ecg_candidates[0] if ecg_candidates else candidates[0]
    anchor_meta = definition_channels.get(anchor["index"], {})
    anchor_mux = anchor_meta.get("mux")
    anchor_scn = anchor_meta.get("scn")

    def _matches_anchor(channel: dict) -> bool:
        info = definition_channels.get(channel["index"], {})
        if anchor_mux is not None and info.get("mux") != anchor_mux:
            return False
        if anchor_scn is not None and info.get("scn") != anchor_scn:
            return False
        return True

    grouped = [c for c in candidates if _matches_anchor(c)]
    if not grouped:
        grouped = candidates

    selected_indices = {c["index"] for c in grouped}
    dropped = [
        definition_channels[c["index"]].get("name", c["name"])
        for c in candidates
        if c["index"] not in selected_indices
    ]

    return grouped, {
        "status": "selected",
        "anchor_channel": anchor_meta.get("name", anchor.get("name", "unknown")),
        "anchor_mux": anchor_mux,
        "anchor_scn": anchor_scn,
        "selected_count": len(grouped),
        "candidate_count": len(candidates),
        "dropped_channels": dropped,
    }


def read_varioport_header(f, override_base_freq=None):
    """
    Reads the Varioport file header and channel definitions.
    Based on the R code 'read_vpd.R' and inspection of VPDATA.RAW.
    """
    f.seek(0)

    # 1. File Header
    # Byte 2: Header Length
    f.seek(2)
    hdrlen = struct.unpack(">H", f.read(2))[0]

    # Byte 4: Channel Offset
    f.seek(4)
    choffs = struct.unpack(">H", f.read(2))[0]

    # Byte 6: Header Type
    f.seek(6)
    hdrtype = struct.unpack(">B", f.read(1))[0]

    # Byte 7: Channel Count
    f.seek(7)
    chcnt = struct.unpack(">B", f.read(1))[0]

    # Byte 20: Global Scan Rate (Not in R code, but found in file)
    f.seek(20)
    file_scnrate = struct.unpack(">H", f.read(2))[0]

    if override_base_freq:
        scnrate = override_base_freq
        print(
            f"Using overridden base frequency: {scnrate} Hz (File says: {file_scnrate})"
        )
    else:
        scnrate = 512
        print(
            f"Using default base frequency 512 Hz (File says: {file_scnrate})."
        )

    print(
        f"Header Info: Length={hdrlen}, Type={hdrtype}, Channels={chcnt}, BaseRate={scnrate}"
    )

    # 2. Channel Definitions
    channels = []
    for i in range(chcnt):
        offset = choffs + i * 40
        f.seek(offset)
        ch_def = f.read(40)

        name = ch_def[0:6].decode("ascii", errors="ignore").strip()
        unit = ch_def[6:10].decode("ascii", errors="ignore").strip()
        # data_size: 0=uint8, 1=uint16. Actual bytes = val + 1
        dsize_code = ch_def[11]
        dsize = dsize_code + 1

        scnfac = ch_def[12]
        strfac = ch_def[14]

        mul = struct.unpack(">H", ch_def[16:18])[0]
        doffs = struct.unpack(">H", ch_def[18:20])[0]
        div = struct.unpack(">H", ch_def[20:22])[0]

        # Offset to data (relative to some base, R code adds hdrlen)
        offs_val = struct.unpack(">I", ch_def[24:28])[0]
        abs_offs = offs_val + hdrlen

        chlen = struct.unpack(">I", ch_def[28:32])[0]

        # Calculate effective sampling rate
        # chscnrate = scnrate / scnfac
        # chstrrate = chscnrate / strfac
        if scnfac == 0:
            scnfac = 1
        if strfac == 0:
            strfac = 1
        fs = scnrate / (scnfac * strfac)

        chan_info = {
            "index": i,
            "name": name,
            "unit": unit,
            "dsize": dsize,
            "scnfac": scnfac,
            "strfac": strfac,
            "mul": mul,
            "doffs": doffs,
            "div": div,
            "abs_offs": abs_offs,
            "chlen": chlen,
            "fs": fs,
        }
        channels.append(chan_info)
        print(
            f"Channel {i}: {name} ({unit}), fs={fs:.2f}Hz, len={chlen}, dsize={dsize}"
        )

    return hdrlen, hdrtype, channels


def get_default_scaling(name):
    """
    Returns default scaling parameters based on Varioport Toolbox (MATLAB).
    Used if file header contains invalid values (e.g. mul=0).
    """
    # Defaults from Varioport_Toolbox load_channel_data.m
    # offset = 32767
    defaults = {
        "EDA": {"doffs": 32767, "mul": 10, "div": 6400},
        "EMG1": {"doffs": 32767, "mul": 1297, "div": 10000},
        "EMG2": {"doffs": 32767, "mul": 1297, "div": 10000},
        "AUX": {
            "doffs": 32767,
            "mul": 1,
            "div": 1,
        },  # Toolbox says "no factors given... possible to omit offset", but code uses offset.
        "UBATT": {
            "doffs": 0,
            "mul": 127,
            "div": 10000,
        },  # Toolbox doesn't subtract offset for UBATT
        "BATT": {"doffs": 0, "mul": 127, "div": 10000},  # Alias
    }

    # Check for partial matches (e.g. "EDA " or "EDA1")
    for key in defaults:
        if name.upper().startswith(key):
            return defaults[key]
    return None


def _moving_average(signal: np.ndarray, window: int) -> np.ndarray:
    if window <= 1:
        return signal
    kernel = np.ones(window, dtype=float) / float(window)
    return np.convolve(signal, kernel, mode="same")


def _estimate_average_heart_rate_bpm(
    signal: np.ndarray,
    sampling_rate: float,
    task_name: str | None = None,
    return_details: bool = False,
) -> float | None | tuple[float | None, dict]:
    if sampling_rate <= 0 or signal.size < max(int(sampling_rate * 8), 10):
        details = {
            "status": "rejected",
            "reason": "too_short_or_invalid_sampling",
            "quality_gate": "signal_driven",
            "task_label": (task_name or ""),
        }
        return (None, details) if return_details else None

    task = (task_name or "").strip().lower()
    is_rest_task = "rest" in task

    # Quality gate is signal-driven and independent from task naming.
    min_bpm = 40.0
    max_bpm = 180.0
    expected_rest_min_bpm = 50.0
    expected_rest_max_bpm = 90.0

    data = np.asarray(signal, dtype=float)
    if not np.isfinite(data).any():
        details = {
            "status": "rejected",
            "reason": "non_finite_signal",
            "quality_gate": "signal_driven",
            "task_label": (task_name or ""),
        }
        return (None, details) if return_details else None

    data = np.nan_to_num(data, nan=0.0, posinf=0.0, neginf=0.0)
    data = data - np.median(data)

    std = float(np.std(data))
    if std == 0:
        details = {
            "status": "rejected",
            "reason": "flat_signal",
            "quality_gate": "signal_driven",
            "task_label": (task_name or ""),
        }
        return (None, details) if return_details else None
    data = data / std

    highpass_window = max(int(0.75 * sampling_rate), 3)
    data_hp = data - _moving_average(data, highpass_window)

    diff = np.diff(data_hp, prepend=data_hp[0])
    energy = diff * diff
    envelope_window = max(int(0.12 * sampling_rate), 3)
    envelope = _moving_average(energy, envelope_window)

    env_std = float(np.std(envelope))
    if env_std == 0:
        details = {
            "status": "rejected",
            "reason": "no_envelope_variation",
            "quality_gate": "signal_driven",
            "task_label": (task_name or ""),
        }
        return (None, details) if return_details else None
    envelope = (envelope - np.mean(envelope)) / env_std

    min_lag = max(int(sampling_rate * 60.0 / max_bpm), 1)
    max_lag = max(int(sampling_rate * 60.0 / min_bpm), min_lag + 1)
    if max_lag >= envelope.size:
        details = {
            "status": "rejected",
            "reason": "insufficient_samples_for_lag_range",
            "quality_gate": "signal_driven",
            "task_label": (task_name or ""),
        }
        return (None, details) if return_details else None

    autocorr = np.correlate(envelope, envelope, mode="full")
    autocorr = autocorr[autocorr.size // 2 :]
    if autocorr.size <= max_lag:
        details = {
            "status": "rejected",
            "reason": "autocorr_too_short",
            "quality_gate": "signal_driven",
            "task_label": (task_name or ""),
        }
        return (None, details) if return_details else None

    lag_slice = autocorr[min_lag : max_lag + 1]
    if lag_slice.size == 0:
        details = {
            "status": "rejected",
            "reason": "invalid_lag_slice",
            "quality_gate": "signal_driven",
            "task_label": (task_name or ""),
        }
        return (None, details) if return_details else None

    lag_at_max = int(np.argmax(lag_slice)) + min_lag
    bpm_autocorr = 60.0 * float(sampling_rate) / float(lag_at_max)

    threshold = float(np.percentile(envelope, 95))
    candidate_peaks = []
    for idx in range(1, envelope.size - 1):
        if (
            envelope[idx] > threshold
            and envelope[idx] > envelope[idx - 1]
            and envelope[idx] >= envelope[idx + 1]
        ):
            candidate_peaks.append(idx)

    peaks = []
    for idx in candidate_peaks:
        if not peaks or (idx - peaks[-1]) >= min_lag:
            peaks.append(idx)
        elif envelope[idx] > envelope[peaks[-1]]:
            peaks[-1] = idx

    bpm_peaks = None
    rr_cv_value = None
    if len(peaks) >= 4:
        rr_intervals = np.diff(np.array(peaks, dtype=float)) / float(sampling_rate)
        rr_min = 60.0 / max_bpm
        rr_max = 60.0 / min_bpm
        rr_valid = rr_intervals[(rr_intervals >= rr_min) & (rr_intervals <= rr_max)]
        if rr_valid.size >= 3:
            rr_median = float(np.median(rr_valid))
            rr_mean = float(np.mean(rr_valid))
            rr_std = float(np.std(rr_valid))
            rr_cv = rr_std / rr_mean if rr_mean > 0 else 1.0
            rr_cv_value = rr_cv
            if rr_median > 0 and 0.01 <= rr_cv < 0.35:
                bpm_peaks = 60.0 / rr_median

    if bpm_peaks is None:
        if is_rest_task and expected_rest_min_bpm <= bpm_autocorr <= expected_rest_max_bpm:
            bpm_out = round(float(bpm_autocorr), 2)
            details = {
                "status": "estimated",
                "reason": "autocorr_fallback_rest_window",
                "quality_gate": "signal_driven",
                "task_label": (task_name or ""),
                "bpm": bpm_out,
                "bpm_autocorr": round(float(bpm_autocorr), 2),
                "method_agreement": "autocorr_only_fallback",
            }
            return (bpm_out, details) if return_details else bpm_out

        details = {
            "status": "rejected",
            "reason": "insufficient_peak_confidence",
            "quality_gate": "signal_driven",
            "task_label": (task_name or ""),
            "bpm_autocorr": round(float(bpm_autocorr), 2),
        }
        return (None, details) if return_details else None

    if abs(bpm_peaks - bpm_autocorr) > 15.0:
        # Harmonic mismatch can happen in autocorrelation; allow peak-based fallback
        # only when RR variability indicates stable physiological rhythm.
        if rr_cv_value is not None and rr_cv_value < 0.2:
            bpm = bpm_peaks
            disagreement_fallback = True
        else:
            details = {
                "status": "rejected",
                "reason": "method_disagreement",
                "quality_gate": "signal_driven",
                "task_label": (task_name or ""),
                "bpm_autocorr": round(float(bpm_autocorr), 2),
                "bpm_peaks": round(float(bpm_peaks), 2),
            }
            return (None, details) if return_details else None
    else:
        bpm = 0.5 * (bpm_peaks + bpm_autocorr)
        disagreement_fallback = False

    if bpm < min_bpm or bpm > max_bpm:
        details = {
            "status": "rejected",
            "reason": "outside_global_physiological_range",
            "quality_gate": "signal_driven",
            "task_label": (task_name or ""),
            "bpm": round(float(bpm), 2),
        }
        return (None, details) if return_details else None

    bpm_out = round(float(bpm), 2)
    details = {
        "status": "estimated",
        "reason": "ok",
        "quality_gate": "signal_driven",
        "task_label": (task_name or ""),
        "bpm": bpm_out,
        "bpm_autocorr": round(float(bpm_autocorr), 2),
        "bpm_peaks": round(float(bpm_peaks), 2),
    }

    if disagreement_fallback:
        details["method_agreement"] = "peaks_fallback_from_autocorr_harmonic"

    # Task label is used as soft plausibility check only (never hard reject).
    if is_rest_task and not (expected_rest_min_bpm <= bpm_out <= expected_rest_max_bpm):
        details["task_plausibility_warning"] = (
            f"rest_task_bpm_outside_expected_range_{int(expected_rest_min_bpm)}_{int(expected_rest_max_bpm)}"
        )

    return (bpm_out, details) if return_details else bpm_out


def convert_varioport(
    raw_path,
    output_path,
    sidecar_path,
    task_name="rest",
    base_freq=None,
    allow_raw_multiplexed: bool = False,
):
    """
    Converts a Varioport .RAW file to BIDS .edf and .json.

    Returns:
        dict: Written sidecar metadata (includes AverageHeartRateBPM when estimable)
    """

    definition_info = None
    definition_file = _find_companion_definition_file(raw_path)
    if definition_file:
        try:
            definition_info = _parse_varioport_definition_file(definition_file)
            print(f"Using companion definition file: {definition_file}")
        except Exception as exc:
            print(
                f"Warning: Could not parse companion definition file {definition_file}: {exc}"
            )

    with open(raw_path, "rb") as f:
        hdrlen, hdrtype, channels = read_varioport_header(
            f, override_base_freq=base_freq
        )

        if definition_info:
            definition_channels = definition_info.get("channels_by_index", {})
            for channel in channels:
                info = definition_channels.get(channel["index"])
                if not info:
                    continue
                if info.get("name"):
                    channel["name"] = info["name"]
                if info.get("unit"):
                    channel["unit"] = info["unit"]

        decoding_mode = (
            "type6_demultiplexed" if hdrtype == 6 else "type7_multiplexed_experimental"
        )

        if hdrtype != 6 and not allow_raw_multiplexed:
            raise ValueError(
                "Unsupported Varioport header type for reliable conversion: "
                f"{hdrtype}. Please reconfigure/export the file to Type 6 (demultiplexed) "
                "in VitaGraf before conversion."
            )

        if hdrtype != 6 and allow_raw_multiplexed:
            print(
                "WARNING: Converting raw multiplexed Type-7 data in experimental mode. "
                "Signal morphology and timing must be quality-checked."
            )

        avg_hr_bpm = None
        type7_selection_meta = {}
        hr_details = {
            "status": "not_estimated",
            "reason": "ecg_channel_not_found_or_not_processed",
            "quality_gate": "signal_driven",
            "task_label": (task_name or ""),
        }

        # Identify active channels
        # In the test file, EKG has len=-1 (0xFFFFFFFF), others have 0.
        # We assume only channels with len != 0 are active.
        # BUT: Marker channel often has len=0 but is present in Type 7 streams (checking file size divisibility).
        active_channels = []
        if hdrtype != 6 and definition_info:
            active_channels, type7_selection_meta = _select_type7_channels_from_definition(
                channels,
                definition_info,
            )
            if active_channels:
                print(
                    "Using active channels from definition file (ECG-anchored): "
                    f"{[c['name'] for c in active_channels]}"
                )
            if type7_selection_meta.get("dropped_channels"):
                print(
                    "Dropped channels outside ECG SCN/MUX group: "
                    f"{type7_selection_meta.get('dropped_channels')}"
                )

        if not active_channels:
            for c in channels:
                if c["chlen"] != 0:
                    active_channels.append(c)
                elif "marker" in c["name"].lower():
                    # Force include marker if it looks like it might be in the stream
                    # We'll verify block alignment later
                    print(f"Force-including channel {c['name']} despite len=0")
                    active_channels.append(c)

        if not active_channels:
            print(
                "No active channels found (all have length 0). Assuming all are active?"
            )
            active_channels = channels

        # Filter out unsupported dsize
        supported_channels = []
        for c in active_channels:
            if c["dsize"] in [1, 2]:
                supported_channels.append(c)
            else:
                print(
                    f"Warning: Skipping channel {c['name']} with unsupported dsize {c['dsize']}"
                )

        active_channels = supported_channels

        print(
            f"Found {len(active_channels)} active supported channels: {[c['name'] for c in active_channels]}"
        )

        # Check if all active channels have the same sampling rate
        if not active_channels:
            print("Error: No channels to process.")
            return

        # Determine effective sampling rate
        # We assume the stream is uniform with the highest rate found (usually EKG).
        # This handles the case where Marker is 1Hz in header but interleaved 1-to-1 with 256Hz EKG.
        ecg_channels = [
            c
            for c in active_channels
            if ("ekg" in c["name"].lower() or "ecg" in c["name"].lower())
        ]
        effective_fs = (
            ecg_channels[0]["fs"] if ecg_channels else max(c["fs"] for c in active_channels)
        )
        print(f"Effective sampling rate for all channels: {effective_fs} Hz")

        # Prepare EDF headers
        signal_headers = []
        for c in active_channels:
            header = {
                "label": c["name"],
                "dimension": c["unit"],
                "sample_frequency": effective_fs,
                "physical_max": 32767,
                "physical_min": -32768,
                "digital_max": 32767,
                "digital_min": -32768,
                "transducer": "Varioport",
                "prefilter": "",
            }

            # Set reasonable physical ranges to avoid clipping
            if "ekg" in c["name"].lower():
                header["physical_min"] = -50000
                header["physical_max"] = 50000
            elif "marker" in c["name"].lower():
                header["physical_min"] = 0
                header["physical_max"] = 255
            elif "batt" in c["name"].lower():
                header["physical_min"] = 0
                header["physical_max"] = 20
            else:
                header["physical_min"] = -32768
                header["physical_max"] = 32767

            signal_headers.append(header)

        # Initialize EDF Writer
        try:
            f_edf = pyedflib.EdfWriter(
                output_path, len(active_channels), file_type=pyedflib.FILETYPE_EDFPLUS
            )
            f_edf.setSignalHeaders(signal_headers)
        except Exception as e:
            print(f"Error initializing EDF writer: {e}")
            return

        channel_data = {}  # Only used for Type 6

        if hdrtype == 6:
            # Type 6: Reconfigured / Demultiplexed
            # Data for each channel is at specific offsets
            print(
                "Detected Type 6 (Reconfigured) file. Reading channels independently."
            )

            for ch in active_channels:
                name = ch["name"]
                print(f"Processing channel: {name}")

                data_start = ch["abs_offs"]
                data_len_bytes = ch["chlen"]

                f.seek(data_start)
                raw_bytes = f.read(data_len_bytes)

                dsize = ch["dsize"]
                num_samples = len(raw_bytes) // dsize

                if dsize == 2:
                    # Big Endian uint16
                    fmt = f">{num_samples}H"
                    raw_values = struct.unpack(fmt, raw_bytes[: num_samples * dsize])
                elif dsize == 1:
                    fmt = f">{num_samples}B"
                    raw_values = struct.unpack(fmt, raw_bytes[: num_samples * dsize])
                else:
                    print(f"Skipping channel {name}: Unsupported data size {dsize}")
                    continue

                # Apply scaling
                doffs = ch["doffs"]
                mul = ch["mul"]
                div = ch["div"]

                # Check for invalid scaling parameters and apply defaults if needed
                if mul == 0 or div == 0:
                    print(
                        f"  Warning: Invalid scaling (mul={mul}, div={div}). Checking defaults..."
                    )
                    defaults = get_default_scaling(name)
                    if defaults:
                        doffs = defaults["doffs"]
                        mul = defaults["mul"]
                        div = defaults["div"]
                        print(
                            f"  Applied defaults for {name}: doffs={doffs}, mul={mul}, div={div}"
                        )
                    else:
                        print(
                            f"  No defaults found for {name}. Using raw values (mul=1, div=1, doffs=0)."
                        )
                        doffs = 0
                        mul = 1
                        div = 1

                if div == 0:
                    div = 1  # Safety

                data_array = np.array(raw_values, dtype=float)
                data_array = (data_array - doffs) * mul / div

                channel_data[name] = data_array

            for ch in active_channels:
                name_lower = ch["name"].lower()
                if "ekg" in name_lower or "ecg" in name_lower:
                    ecg_signal = channel_data.get(ch["name"])
                    if ecg_signal is not None and len(ecg_signal) > 0:
                        avg_hr_bpm, hr_details = _estimate_average_heart_rate_bpm(
                            ecg_signal,
                            effective_fs,
                            task_name=task_name,
                            return_details=True,
                        )
                    break

            # Write Type 6 data to EDF
            # We need to pad to match lengths if they differ
            lengths = [len(d) for d in channel_data.values()]
            max_len = max(lengths)

            signals = []
            for h in signal_headers:
                name = h["label"]
                data = channel_data.get(name, np.array([]))
                if len(data) < max_len:
                    padding = np.zeros(max_len - len(data))
                    data = np.concatenate([data, padding])
                signals.append(data)

            f_edf.writeSamples(signals)
            f_edf.close()

        else:
            # Type 7: Raw / Multiplexed (or other)
            # The data starts after the header and is interleaved.
            print(
                f"Detected Type {hdrtype} (Raw/Multiplexed). Streaming data to EDF..."
            )

            data_start = hdrlen
            f.seek(data_start)

            block_size = sum(c["dsize"] for c in active_channels)

            # Define chunk size (e.g. 60 seconds)
            # Must be multiple of effective_fs to align with 1s records
            chunk_duration = 60  # seconds
            samples_per_chunk = int(chunk_duration * effective_fs)
            bytes_per_chunk = samples_per_chunk * block_size

            # Prepare dtype for numpy
            dtype_list = []
            for c in active_channels:
                fmt = ">u2" if c["dsize"] == 2 else ">u1"
                safe_name = (
                    c["name"].replace(" ", "_").replace("(", "").replace(")", "")
                )
                dtype_list.append((safe_name, fmt))
            dt = np.dtype(dtype_list)

            total_samples = 0
            ecg_chunks = []
            ecg_channel_index = None
            for idx, channel in enumerate(active_channels):
                name_lower = channel["name"].lower()
                if "ekg" in name_lower or "ecg" in name_lower:
                    ecg_channel_index = idx
                    break
            while True:
                raw_bytes = f.read(bytes_per_chunk)
                if not raw_bytes:
                    break

                read_len = len(raw_bytes)
                num_blocks = read_len // block_size

                if num_blocks == 0:
                    break

                valid_bytes = num_blocks * block_size

                try:
                    raw_data = np.frombuffer(raw_bytes[:valid_bytes], dtype=dt)
                except Exception as e:
                    print(f"Error parsing buffer: {e}")
                    break

                chunk_signals = []
                for i, c in enumerate(active_channels):
                    safe_name = dtype_list[i][0]
                    raw_vals = raw_data[safe_name]

                    # Scaling
                    doffs = c["doffs"]
                    mul = c["mul"]
                    div = c["div"]

                    if mul == 0 or div == 0:
                        defaults = get_default_scaling(c["name"])
                        if defaults:
                            doffs = defaults["doffs"]
                            mul = defaults["mul"]
                            div = defaults["div"]
                        else:
                            doffs, mul, div = 0, 1, 1
                    if div == 0:
                        div = 1

                    data_array = raw_vals.astype(float)
                    data_array = (data_array - doffs) * mul / div
                    chunk_signals.append(data_array)

                    if ecg_channel_index is not None and i == ecg_channel_index:
                        ecg_chunks.append(data_array)

                # Write chunk
                try:
                    f_edf.writeSamples(chunk_signals)
                except Exception as e:
                    print(f"Error writing chunk to EDF: {e}")
                    break

                total_samples += num_blocks
                print(f"Processed {total_samples} samples...", end="\r")

            print(f"\nFinished streaming. Total samples: {total_samples}")
            f_edf.close()

            if ecg_chunks:
                try:
                    ecg_signal = np.concatenate(ecg_chunks)
                    avg_hr_bpm, hr_details = _estimate_average_heart_rate_bpm(
                        ecg_signal,
                        effective_fs,
                        task_name=task_name,
                        return_details=True,
                    )
                except Exception:
                    avg_hr_bpm = None
                    hr_details = {
                        "status": "not_estimated",
                        "reason": "ecg_signal_concatenation_failed",
                        "quality_gate": "signal_driven",
                        "task_label": (task_name or ""),
                    }

        # Create Sidecar JSON
        note = "Converted from VPDATA.RAW. Base rate set to default 512 Hz."
        if base_freq is not None:
            note = f"Converted from VPDATA.RAW. Base rate overridden to {base_freq} Hz."

        sidecar = {
            "TaskName": task_name,
            "SamplingFrequency": effective_fs,
            "StartTime": 0,
            "Columns": [h["label"] for h in signal_headers],
            "Manufacturer": "Becker Meditec",
            "ManufacturersModelName": "Varioport",
            "Note": note,
            "DecodingMode": decoding_mode,
        }

        if definition_file:
            sidecar["CompanionDefinitionFile"] = str(definition_file)

        if type7_selection_meta:
            sidecar["DefinitionChannelSelection"] = type7_selection_meta

        if avg_hr_bpm is not None:
            sidecar["AverageHeartRateBPM"] = avg_hr_bpm

        sidecar["HeartRateEstimation"] = {
            "Status": hr_details.get("status", "not_estimated"),
            "Reason": hr_details.get("reason", "unknown"),
            "QualityGate": hr_details.get("quality_gate", "signal_driven"),
            "TaskLabel": hr_details.get("task_label", task_name),
        }

        if "task_plausibility_warning" in hr_details:
            sidecar["HeartRateEstimation"]["TaskPlausibilityWarning"] = hr_details[
                "task_plausibility_warning"
            ]

        with open(sidecar_path, "w") as jf:
            json.dump(sidecar, jf, indent=4)

        print("Conversion complete.")
        return sidecar


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Convert Varioport RAW to BIDS")
    parser.add_argument("input_file", help="Path to VPDATA.RAW")
    parser.add_argument("output_edf", help="Path to output .edf")
    parser.add_argument("output_json", help="Path to output .json")
    parser.add_argument(
        "--base-freq", type=float, help="Override base frequency (e.g. 1000)"
    )

    args = parser.parse_args()

    convert_varioport(
        args.input_file, args.output_edf, args.output_json, base_freq=args.base_freq
    )
