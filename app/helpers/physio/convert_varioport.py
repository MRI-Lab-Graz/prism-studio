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

            siz_code = hex_values[1] if len(hex_values) > 1 else None
            scn = hex_values[2] if len(hex_values) > 2 else None
            sto = hex_values[4] if len(hex_values) > 4 else None
            mux = hex_values[5] if len(hex_values) > 5 else None
            dslcf = hex_values[6] if len(hex_values) > 6 else None
            doffs_def = hex_values[7] if len(hex_values) > 7 else None
            scale = hex_values[8] if len(hex_values) > 8 else None

            channel_map[zero_based_index] = {
                "index": zero_based_index,
                "name": name,
                "unit": unit,
                "is_placeholder": name_lower in {"ntused", "999", "unused"},
                "is_marker": "marker" in name_lower,
                "is_ecg": ("ekg" in name_lower or "ecg" in name_lower),
                "siz_code": siz_code,
                "scn": scn,
                "sto": sto,
                "mux": mux,
                "dslcf": dslcf,
                "doffs_def": doffs_def,
                "scale": scale,
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

    if ecg_candidates:
        def _ecg_anchor_score(channel: dict) -> tuple[int, int, int]:
            info = definition_channels.get(channel["index"], {})
            scale = int(info.get("scale") or 0)
            siz_code = int(info.get("siz_code") or 0)
            # Prefer channels with meaningful analog scaling and extended size coding.
            return (scale, siz_code, -channel["index"])

        anchor = max(ecg_candidates, key=_ecg_anchor_score)
    else:
        anchor = candidates[0]
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


def _choose_best_type7_group_by_ecg_quality(
    channels: list[dict],
    definition_info: dict | None,
    raw_bytes: bytes,
    base_sampling_rate: float,
    task_name: str,
) -> tuple[list[dict], dict]:
    if not definition_info:
        return channels, {"status": "no_definition"}

    definition_channels = definition_info.get("channels_by_index", {})
    channel_by_key: dict[tuple[int | None, int | None], list[dict]] = {}
    group_has_ecg: set[tuple[int | None, int | None]] = set()

    for channel in channels:
        info = definition_channels.get(channel["index"], {})
        key = (info.get("mux"), info.get("scn"))
        channel_by_key.setdefault(key, []).append(channel)
        if info.get("is_ecg", False):
            group_has_ecg.add(key)

    candidate_keys = [key for key in channel_by_key if key in group_has_ecg]
    if not candidate_keys:
        return channels, {"status": "no_ecg_group_candidates"}

    scored_candidates: list[dict] = []
    best_score = -1e12
    best_group = channels
    best_key = None

    for key in candidate_keys:
        group_channels = channel_by_key[key]
        native_data, demux_info = _decode_type7_multiplexed_periodic(
            raw_bytes,
            group_channels,
            base_sampling_rate,
        )

        ecg_channel = next(
            (c for c in group_channels if "ekg" in c["name"].lower() or "ecg" in c["name"].lower()),
            None,
        )
        score = -1e6
        status = "no_ecg_channel"
        reason = "no_ecg_channel"
        samples = 0

        if ecg_channel is not None:
            ecg_signal = native_data.get(ecg_channel["name"], np.array([], dtype=float))
            ecg_fs = float(ecg_channel.get("fs") or base_sampling_rate)
            samples = int(ecg_signal.size)

            if ecg_signal.size > 0 and ecg_fs > 0:
                bpm, details = _estimate_average_heart_rate_bpm(
                    ecg_signal,
                    ecg_fs,
                    task_name=task_name,
                    return_details=True,
                )
                status = details.get("status", "unknown")
                reason = details.get("reason", "unknown")

                signal_std = float(np.std(ecg_signal))
                length_component = min(float(samples) / max(ecg_fs * 10.0, 1.0), 50.0)
                variability_component = min(signal_std, 1000.0) / 10.0

                score = length_component + variability_component
                if status == "estimated":
                    score += 100.0
                if bpm is not None:
                    score += 5.0

        scored_candidates.append(
            {
                "mux": key[0],
                "scn": key[1],
                "channels": [c["name"] for c in group_channels],
                "ecg_samples": samples,
                "status": status,
                "reason": reason,
                "score": round(float(score), 3),
                "demux": {
                    "consumed_bytes": demux_info.get("consumed_bytes"),
                    "total_bytes": demux_info.get("total_bytes"),
                    "ticks": demux_info.get("ticks"),
                },
            }
        )

        if score > best_score:
            best_score = score
            best_group = group_channels
            best_key = key

    selected_names = {c["name"] for c in best_group}
    dropped = [c["name"] for c in channels if c["name"] not in selected_names]

    return best_group, {
        "status": "data_driven_selected",
        "selected_mux": best_key[0] if best_key else None,
        "selected_scn": best_key[1] if best_key else None,
        "selected_channels": [c["name"] for c in best_group],
        "dropped_channels": dropped,
        "candidate_scores": scored_candidates,
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

    return hdrlen, hdrtype, scnrate, channels


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


def _decode_type7_multiplexed_periodic(
    raw_bytes: bytes,
    active_channels: list[dict],
    base_sampling_rate: float,
) -> tuple[dict[str, np.ndarray], dict]:
    """Decode Type-7 RAW multiplexed stream with mixed-rate channel scheduling.

    Assumption (matching Varioport developer guidance): data are ordered as channel samples
    as they become due in scan time. Faster channels occur more often than slower channels.
    """
    if base_sampling_rate <= 0:
        return {}, {"status": "invalid_base_sampling_rate"}

    periods: dict[str, int] = {}
    decode_info_channels: list[dict] = []

    for channel in active_channels:
        fs = float(channel.get("fs", 0) or 0)
        if fs <= 0:
            fs = float(base_sampling_rate)
        ratio = float(base_sampling_rate) / float(fs)
        period = max(int(round(ratio)), 1)
        periods[channel["name"]] = period
        decode_info_channels.append(
            {
                "name": channel["name"],
                "fs": fs,
                "period": period,
            }
        )

    values_by_channel: dict[str, list[float]] = {c["name"]: [] for c in active_channels}
    cursor = 0
    tick = 0
    total_len = len(raw_bytes)

    while cursor < total_len:
        any_due_channel = False
        for channel in active_channels:
            period = periods[channel["name"]]
            if tick % period != 0:
                continue

            any_due_channel = True

            dsize = int(channel["dsize"])
            if cursor + dsize > total_len:
                cursor = total_len
                break

            sample_bytes = raw_bytes[cursor : cursor + dsize]
            cursor += dsize

            if dsize == 2:
                raw_val = struct.unpack(">H", sample_bytes)[0]
            elif dsize == 1:
                raw_val = sample_bytes[0]
            else:
                continue

            doffs = channel["doffs"]
            mul = channel["mul"]
            div = channel["div"]
            if mul == 0 or div == 0:
                defaults = get_default_scaling(channel["name"])
                if defaults:
                    doffs = defaults["doffs"]
                    mul = defaults["mul"]
                    div = defaults["div"]
                else:
                    doffs, mul, div = 0, 1, 1
            if div == 0:
                div = 1

            value = (float(raw_val) - float(doffs)) * float(mul) / float(div)
            values_by_channel[channel["name"]].append(value)

        if not any_due_channel:
            tick += 1
            continue
        tick += 1

    channel_arrays = {
        name: np.asarray(values, dtype=float) for name, values in values_by_channel.items()
    }

    return channel_arrays, {
        "status": "decoded",
        "ticks": tick,
        "consumed_bytes": cursor,
        "total_bytes": total_len,
        "channels": decode_info_channels,
    }


def _upsample_channel_to_target_length(
    signal: np.ndarray,
    period: int,
    target_length: int,
) -> np.ndarray:
    if target_length <= 0:
        return np.array([], dtype=float)
    if signal.size == 0:
        return np.zeros(target_length, dtype=float)

    period = max(int(period), 1)
    if period == 1:
        out = signal
    else:
        out = np.repeat(signal, period)

    if out.size >= target_length:
        return out[:target_length]

    pad_value = float(out[-1]) if out.size > 0 else 0.0
    return np.pad(out, (0, target_length - out.size), mode="constant", constant_values=pad_value)


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
        hdrlen, hdrtype, scnrate, channels = read_varioport_header(
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
        type7_raw_bytes = None
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
            definition_channels = definition_info.get("channels_by_index", {})
            active_channels = [
                c
                for c in channels
                if (
                    c["index"] in definition_channels
                    and not definition_channels[c["index"]].get("is_placeholder", False)
                )
            ]
            type7_selection_meta = {
                "status": "candidates_from_definition",
                "candidate_count": len(active_channels),
            }
            if active_channels:
                print(
                    "Using Type-7 candidate channels from definition file: "
                    f"{[c['name'] for c in active_channels]}"
                )

        if not active_channels:
            if hdrtype != 6:
                # RAW/Type-7 often has chlen=0 for slower channels that are still
                # present in the multiplexed stream. Include all non-placeholder
                # channels to avoid byte desynchronization.
                for c in channels:
                    name_lower = c["name"].lower()
                    if name_lower in {"ntused", "999", "unused", ""}:
                        continue
                    active_channels.append(c)
            else:
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

        if hdrtype != 6:
            data_start = hdrlen
            f.seek(data_start)
            type7_raw_bytes = f.read()
            if len(type7_raw_bytes) > 500_000_000:
                print(
                    "WARNING: Large RAW file loaded in memory for Type-7 demultiplexing; "
                    "consider splitting recording if memory is limited."
                )

            if definition_info and active_channels:
                selected_group, group_meta = _choose_best_type7_group_by_ecg_quality(
                    active_channels,
                    definition_info,
                    type7_raw_bytes,
                    scnrate,
                    task_name,
                )
                if selected_group:
                    active_channels = selected_group
                type7_selection_meta = {
                    **type7_selection_meta,
                    **group_meta,
                }
                print(
                    "Selected Type-7 group by ECG quality: "
                    f"{[c['name'] for c in active_channels]}"
                )
                if type7_selection_meta.get("dropped_channels"):
                    print(
                        "Dropped channels outside selected Type-7 group: "
                        f"{type7_selection_meta.get('dropped_channels')}"
                    )

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

        # Separate marker channels from physiological signals
        # Markers should be written as EDF+ annotations, not as signal channels
        marker_channels = []
        physio_channels = []
        
        for c in active_channels:
            if "marker" in c["name"].lower():
                marker_channels.append(c)
            else:
                physio_channels.append(c)
        
        # Prepare EDF headers only for physiological signals (exclude markers)
        signal_headers = []
        for c in physio_channels:
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
            elif "batt" in c["name"].lower():
                header["physical_min"] = 0
                header["physical_max"] = 20
            else:
                header["physical_min"] = -32768
                header["physical_max"] = 32767

            signal_headers.append(header)

        # Initialize EDF Writer with physiological signals only
        try:
            f_edf = pyedflib.EdfWriter(
                output_path, len(physio_channels), file_type=pyedflib.FILETYPE_EDFPLUS
            )
            f_edf.setSignalHeaders(signal_headers)
        except Exception as e:
            print(f"Error initializing EDF writer: {e}")
            return

        channel_data = {}  # Only used for Type 6
        marker_data = {}  # Storage for marker channel data

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

                # Store marker data separately for annotation processing
                if "marker" in name.lower():
                    marker_data[name] = data_array
                else:
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
            max_len = max(lengths) if lengths else 0

            signals = []
            for h in signal_headers:
                name = h["label"]
                data = channel_data.get(name, np.array([]))
                if len(data) < max_len:
                    padding = np.zeros(max_len - len(data))
                    data = np.concatenate([data, padding])
                signals.append(data)

            if signals:
                f_edf.writeSamples(signals)
            
            # Extract and write marker events as EDF+ annotations
            for marker_name, marker_values in marker_data.items():
                if marker_values.size == 0:
                    continue
                    
                print(f"Processing marker channel: {marker_name}")
                
                # Find marker events (state changes with rising edges)
                # Pad with 0 at start to catch initial events
                diffs = np.diff(marker_values, prepend=0)
                # Find indices where value changed (rising edge: diff > 0)
                changes = np.where(diffs != 0)[0]
                
                marker_fs = effective_fs
                # Get the actual sampling rate of the marker channel if available
                for mc in marker_channels:
                    if mc["name"] == marker_name:
                        marker_fs = float(mc.get("fs") or effective_fs)
                        break
                
                for idx in changes:
                    if idx >= marker_values.size:
                        continue
                    val = marker_values[idx]
                    if val > 0:  # Only mark positive values as events
                        onset = float(idx) / marker_fs
                        duration = 0  # Point event
                        description = str(int(val))
                        try:
                            f_edf.writeAnnotation(onset, duration, description)
                        except Exception as e:
                            print(f"Warning: Could not write annotation for marker {marker_name} at {onset}s: {e}")
                
                print(f"Added {len(changes)} marker annotations from {marker_name}")
            
            f_edf.close()

        else:
            # Type 7: Raw / Multiplexed (or other)
            # The data starts after the header and is multiplexed by channel schedule.
            print(
                f"Detected Type {hdrtype} (Raw/Multiplexed). Streaming data to EDF..."
            )

            raw_bytes = type7_raw_bytes if type7_raw_bytes is not None else b""

            native_channel_data, demux_info = _decode_type7_multiplexed_periodic(
                raw_bytes,
                active_channels,
                scnrate,
            )

            if demux_info.get("status") != "decoded":
                print(f"Type-7 demux failed: {demux_info}")
            else:
                print(
                    "Type-7 periodic demux summary: "
                    f"ticks={demux_info.get('ticks')}, "
                    f"consumed={demux_info.get('consumed_bytes')}/{demux_info.get('total_bytes')} bytes"
                )

            periods = {
                c["name"]: max(int(round(float(effective_fs) / max(float(c.get("fs", 1) or 1), 1e-9))), 1)
                for c in physio_channels
            }

            target_lengths = [
                int(native_channel_data.get(c["name"], np.array([], dtype=float)).size * periods[c["name"]])
                for c in physio_channels
            ]
            target_length = max(target_lengths) if target_lengths else 0

            write_signals = []
            for c in physio_channels:
                native = native_channel_data.get(c["name"], np.array([], dtype=float))
                upsampled = _upsample_channel_to_target_length(
                    native,
                    periods[c["name"]],
                    target_length,
                )
                write_signals.append(upsampled)

            if write_signals:
                f_edf.writeSamples(write_signals)
            
            # Extract and write marker events as EDF+ annotations (Type 7)
            for marker_channel in marker_channels:
                marker_name = marker_channel["name"]
                marker_native = native_channel_data.get(marker_name)
                
                if marker_native is None or marker_native.size == 0:
                    continue
                    
                print(f"Processing marker channel (Type 7): {marker_name}")
                
                # Upsample marker data to match the target length
                marker_period = max(int(round(float(effective_fs) / max(float(marker_channel.get("fs", 1) or 1), 1e-9))), 1)
                marker_upsampled = _upsample_channel_to_target_length(
                    marker_native,
                    marker_period,
                    target_length,
                )
                
                # Find marker events (state changes with rising edges)
                diffs = np.diff(marker_upsampled, prepend=0)
                # Find indices where value changed (rising edge: diff > 0)
                changes = np.where(diffs != 0)[0]
                
                for idx in changes:
                    if idx >= marker_upsampled.size:
                        continue
                    val = marker_upsampled[idx]
                    if val > 0:  # Only mark positive values as events
                        onset = float(idx) / effective_fs
                        duration = 0  # Point event
                        description = str(int(val))
                        try:
                            f_edf.writeAnnotation(onset, duration, description)
                        except Exception as e:
                            print(f"Warning: Could not write annotation for marker {marker_name} at {onset}s: {e}")
                
                print(f"Added {len(changes)} marker annotations from {marker_name}")
            
            f_edf.close()

            ecg_channel = next(
                (c for c in active_channels if "ekg" in c["name"].lower() or "ecg" in c["name"].lower()),
                None,
            )
            if ecg_channel is not None:
                ecg_native = native_channel_data.get(ecg_channel["name"])
                ecg_fs = float(ecg_channel.get("fs") or effective_fs)
                if ecg_native is not None and ecg_native.size > 0 and ecg_fs > 0:
                    avg_hr_bpm, hr_details = _estimate_average_heart_rate_bpm(
                        ecg_native,
                        ecg_fs,
                        task_name=task_name,
                        return_details=True,
                    )

            type7_selection_meta["demux"] = demux_info

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


def _extract_trigger_annotations_from_signal(marker_signal: np.ndarray, sampling_rate: float, channel_label: str) -> list[tuple[float, float, str]]:
    """Extract trigger/marker events from a marker signal.
    
    Detects rising and falling edges in marker data and returns list of (onset, duration, description)
    tuples compatible with EDF+ annotation format. Based on EDF+ spec section 2.2.2 (TAL format).
    
    Args:
        marker_signal: 1D array of marker values
        sampling_rate: Sampling frequency in Hz
        channel_label: Name of the marker channel
        
    Returns:
        List of (onset_seconds, duration_seconds, annotation_text) tuples
    """
    if marker_signal.size == 0:
        return []
    
    annotations = []
    # Detect state changes (edges) in the signal
    diffs = np.diff(marker_signal, prepend=0)
    changes = np.where(diffs != 0)[0]
    
    for idx in changes:
        if idx >= marker_signal.size:
            continue
        val = marker_signal[idx]
        if val > 0:  # Only positive values indicate events
            onset = float(idx) / sampling_rate
            duration = 0.0  # Point event (instantaneous marker)
            description = f"{channel_label}:{int(val)}"
            annotations.append((onset, duration, description))
    
    return annotations


def _build_channel_descriptions(channels: list[dict], effective_fs: float) -> dict:
    """Build EDF+ channel descriptions with role and metadata for PRISM sidecar.
    
    Args:
        channels: List of channel dicts with 'name', 'unit', 'fs', 'dsize'
        effective_fs: Effective sampling rate for upsampling reference
        
    Returns:
        Dict mapping channel name to EDF+ description dict
    """
    descriptions = {}
    
    for ch in channels:
        name = ch["name"].strip()
        unit = ch.get("unit", "unknown").strip()
        fs = float(ch.get("fs") or effective_fs)
        
        # Determine channel type and role
        lower = name.lower()
        if "ekg" in lower or "ecg" in lower:
            channel_type = "ECG"
            role = "cardiac"
        elif "resp" in lower:
            channel_type = "RESP"
            role = "respiration"
        elif "marker" in lower or "trigger" in lower:
            channel_type = "TRIGGER"
            role = "trigger"
        elif "eda" in lower or "gsr" in lower:
            channel_type = "EDA"
            role = "electrodermal"
        elif "ppg" in lower or "puls" in lower:
            channel_type = "PPG"
            role = "plethysmograph"
        else:
            channel_type = "OTHER"
            role = "other"
        
        desc = {
            "Type": channel_type,
            "Role": role,
            "Units": unit,
            "SamplingFrequencyStored": effective_fs,
            "SamplingFrequencyNative": fs,
        }
        
        if channel_type == "TRIGGER":
            desc["Description"] = "EDF+ annotations (TAL). Event markers stored per EDF+ spec 2.2.2"
        else:
            desc["Description"] = f"{channel_type} signal (acquired at {fs} Hz, stored at {effective_fs} Hz)"
        
        descriptions[name] = desc
    
    return descriptions


def _infer_recording_type(channels: list[dict]) -> str:
    """Infer recording type from channel composition.
    
    Args:
        channels: List of channel dicts
        
    Returns:
        Recording type: 'ecg', 'ecg+resp', 'mixed', etc.
    """
    types = set()
    for ch in channels:
        name = ch["name"].lower()
        if "ekg" in name or "ecg" in name:
            types.add("ecg")
        elif "resp" in name:
            types.add("resp")
        elif "eda" in name or "gsr" in name:
            types.add("eda")
        elif "ppg" in name or "puls" in name:
            types.add("ppg")
        elif "marker" not in name and "trigger" not in name:
            types.add("other")
    
    if not types:
        return "unknown"
    if len(types) == 1:
        return list(types)[0]
    return "mixed"


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
