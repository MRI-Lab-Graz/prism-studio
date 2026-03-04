"""Batch conversion utilities for physiological and eyetracking data.

This module provides utilities for batch converting raw data files from a flat folder
structure into PRISM/BIDS-style datasets. The input files must follow the naming convention:

    sub-<id>_ses-<id>_task-<id>.<ext>

Example:
    sub-003_ses-1_task-rest.raw     → physio data
    sub-003_ses-1_task-find.edf     → eyetracking data

Supported formats:
- Physio: .raw, .vpd (Varioport devices) → converted to .edf + .json
- Eyetracking: .edf (SR Research EyeLink) → copied + .json sidecar generated
"""

from __future__ import annotations

import json
import io
import re
import shutil
from contextlib import redirect_stdout
from datetime import datetime
from dataclasses import dataclass, field
from html import escape
from pathlib import Path
from typing import Callable

import numpy as np

# Pattern for BIDS-like filenames: sub-XXX_ses-YYY_task-ZZZ[_extra].<ext>
BIDS_FILENAME_PATTERN = re.compile(
    r"^(?P<sub>sub-[a-zA-Z0-9]+)"
    r"(?:_(?P<ses>ses-[a-zA-Z0-9]+))?"
    r"_(?P<task>task-[a-zA-Z0-9]+)"
    r"(?P<extra>(?:_[a-zA-Z0-9]+(?:-[a-zA-Z0-9]+)?)*)"
    r"\.(?P<ext>[a-zA-Z0-9]+(?:\.gz)?)$",
    re.IGNORECASE,
)

# Modality detection by extension
PHYSIO_EXTENSIONS = {".raw", ".vpd", ".edf"}
EYETRACKING_EXTENSIONS = {".edf"}
GENERIC_EXTENSIONS = {
    ".tsv",
    ".tsv.gz",
    ".csv",
    ".txt",
    ".json",
    ".nii",
    ".nii.gz",
    ".pdf",
    ".png",
    ".jpg",
    ".jpeg",
}


@dataclass
class ConvertedFile:
    """Result of converting a single file."""

    source_path: Path
    output_files: list[Path]
    modality: str
    subject: str
    session: str | None
    task: str
    success: bool
    error: str | None = None


@dataclass
class FileConflict:
    """A file conflict when output already exists."""

    output_path: Path
    source_path: Path | None = None
    reason: str = "File already exists"  # "identical" or "different"


@dataclass
class BatchConvertResult:
    """Result of batch conversion."""

    source_folder: Path
    output_folder: Path
    converted: list[ConvertedFile] = field(default_factory=list)
    skipped: list[tuple[Path, str]] = field(default_factory=list)  # (path, reason)
    conflicts: list[FileConflict] = field(default_factory=list)  # File conflicts
    existing_files: int = 0  # Count of files that already exist (for dry-run reporting)
    new_files: int = 0  # Count of files that would be created (for dry-run reporting)

    @property
    def success_count(self) -> int:
        return sum(1 for f in self.converted if f.success)

    @property
    def error_count(self) -> int:
        return sum(1 for f in self.converted if not f.success)


def parse_bids_filename(filename: str) -> dict | None:
    """Parse a BIDS-like filename into its components.

    Args:
        filename: The filename to parse (e.g., "sub-003_ses-1_task-rest.raw")

    Returns:
        Dictionary with keys: sub, ses, task, extra, ext, or None if invalid
    """
    match = BIDS_FILENAME_PATTERN.match(filename)
    if not match:
        return None

    return {
        "sub": match.group("sub"),
        "ses": match.group("ses"),
        "task": match.group("task"),
        "extra": match.group("extra") or "",
        "ext": match.group("ext").lower(),
    }


def detect_modality(ext: str) -> str | None:
    """Detect the modality based on file extension."""
    ext_lower = ext.lower() if not ext.startswith(".") else ext.lower()
    if not ext_lower.startswith("."):
        ext_lower = f".{ext_lower}"

    if ext_lower in PHYSIO_EXTENSIONS:
        return "physio"
    elif ext_lower in EYETRACKING_EXTENSIONS:
        return "eyetracking"
    elif ext_lower in GENERIC_EXTENSIONS:
        return "generic"
    return None


def _files_identical(path1: Path, path2: Path) -> bool:
    """Check if two files have identical content (for binary and text files)."""
    try:
        if not path1.exists() or not path2.exists():
            return False
        # For large files, compare size first
        if path1.stat().st_size != path2.stat().st_size:
            return False
        # For small files, compare content
        if path1.stat().st_size < 1_000_000:  # < 1 MB
            return path1.read_bytes() == path2.read_bytes()
        # For larger files, just trust size comparison
        return True
    except Exception:
        return False


def safe_write_file(
    source_path: Path,
    dest_path: Path,
    *,
    allow_overwrite: bool = True,
) -> tuple[bool, str | None]:
    """Safely write a file, checking for conflicts.

    Args:
        source_path: Path to source file to copy
        dest_path: Path to destination
        allow_overwrite: If False, skip if file exists

    Returns:
        (success: bool, conflict_reason: str | None)
        - (True, None): File written successfully
        - (False, None): Source file not found
        - (False, "identical"): File exists with same content (skipped)
        - (False, "different"): File exists with different content (conflict)
    """
    if not source_path.exists():
        return False, None

    if dest_path.exists():
        # Check if content is identical
        if _files_identical(source_path, dest_path):
            return False, "identical"
        # Content differs
        if not allow_overwrite:
            return False, "different"

    try:
        dest_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source_path, dest_path)
        return True, None
    except Exception as e:
        return False, f"error: {e}"


def _create_physio_sidecar(
    source_path: Path,
    output_json: Path,
    *,
    task_name: str,
    sampling_rate: float | None = None,
    recording_label: str = "ecg",
    extra_meta: dict | None = None,
) -> None:
    """Create a PRISM-compliant JSON sidecar for physio data."""
    extra_meta = extra_meta or {}
    sidecar = {
        "Technical": {
            "SamplingRate": sampling_rate
            or extra_meta.get("SamplingFrequency")
            or "unknown",
            "RecordingDuration": extra_meta.get("RecordingDuration") or "unknown",
            "SourceFormat": source_path.suffix.lower().lstrip("."),
        },
        "Study": {
            "TaskName": task_name.replace("task-", ""),
        },
        "Metadata": {
            "SourceFile": source_path.name,
            "ConvertedFrom": (
                "Varioport" if source_path.suffix.lower() in (".raw", ".vpd") else "EDF"
            ),
        },
        "Columns": {
            "time": {"Description": "Time in seconds", "Units": "s"},
        },
    }

    if "Channels" in extra_meta:
        for ch in extra_meta["Channels"]:
            sidecar["Columns"][ch] = {"Description": f"Channel {ch}"}

    with open(output_json, "w", encoding="utf-8") as f:
        json.dump(sidecar, f, indent=2, ensure_ascii=False)


def _create_eyetracking_sidecar(
    source_path: Path,
    output_json: Path,
    *,
    task_name: str,
    extra_meta: dict | None = None,
) -> None:
    """Create a PRISM-compliant JSON sidecar for eyetracking data."""
    extra_meta = extra_meta or {}
    sidecar = {
        "Technical": {
            "SamplingRate": extra_meta.get("SamplingFrequency") or "unknown",
            "Manufacturer": "SR Research",
            "DeviceSerialNumber": "unknown",
            "EyeTrackingMethod": "video-based",
            "RecordedEye": "unknown",
        },
        "Study": {
            "TaskName": task_name.replace("task-", ""),
        },
        "Metadata": {
            "SourceFile": source_path.name,
        },
        "ScreenDistance": "unknown",
        "ScreenSize": "unknown",
    }

    with open(output_json, "w", encoding="utf-8") as f:
        json.dump(sidecar, f, indent=2, ensure_ascii=False)


def _extract_edf_metadata(edf_path: Path) -> dict:
    """Extract metadata from an EDF file using pyedflib."""
    try:
        import pyedflib
        from collections import Counter

        f = pyedflib.EdfReader(str(edf_path))

        # Get basic info
        n_channels = f.signals_in_file
        duration = f.file_duration
        start_datetime = f.getStartdatetime()

        # Get channel info
        channels = []
        sampling_rates = []
        for i in range(n_channels):
            channels.append(f.getLabel(i))
            sampling_rates.append(f.getSampleFrequency(i))

        f.close()

        # Use the most common sampling rate as the default
        common_sr = (
            Counter(sampling_rates).most_common(1)[0][0] if sampling_rates else 0
        )

        return {
            "SamplingFrequency": common_sr,
            "RecordingDuration": duration,
            "StartTime": (
                start_datetime.strftime("%H:%M:%S") if start_datetime else None
            ),
            "Channels": channels,
            "AllSamplingRates": sampling_rates,
        }
    except Exception as e:
        print(f"Warning: Could not extract EDF metadata from {edf_path}: {e}")
        return {}


def _find_physio_sidecar(output_folder: Path, task: str, edf_path: Path) -> Path | None:
    local_sidecar = edf_path.with_suffix(".json")
    if local_sidecar.exists():
        return local_sidecar

    task_clean = task.replace("task-", "")
    root_sidecar = output_folder / f"task-{task_clean}_physio.json"
    if root_sidecar.exists():
        return root_sidecar
    return None


def _detect_r_peaks(ecg_signal: np.ndarray, sampling_rate: float) -> np.ndarray:
    if ecg_signal.size < max(int(sampling_rate * 8), 10) or sampling_rate <= 0:
        return np.array([], dtype=int)

    data = np.asarray(ecg_signal, dtype=float)
    data = np.nan_to_num(data, nan=0.0, posinf=0.0, neginf=0.0)
    data = data - np.median(data)

    std = np.std(data)
    if std <= 0:
        return np.array([], dtype=int)
    normalized = data / std

    diff = np.diff(normalized, prepend=normalized[0])
    energy = diff * diff
    window = max(int(0.12 * sampling_rate), 3)
    kernel = np.ones(window, dtype=float) / float(window)
    envelope = np.convolve(energy, kernel, mode="same")

    threshold = float(np.percentile(envelope, 95))
    refractory = max(int(0.3 * sampling_rate), 1)

    peaks: list[int] = []
    for idx in range(1, envelope.size - 1):
        if (
            envelope[idx] > threshold
            and envelope[idx] > envelope[idx - 1]
            and envelope[idx] >= envelope[idx + 1]
        ):
            if not peaks or (idx - peaks[-1]) >= refractory:
                peaks.append(idx)
            elif envelope[idx] > envelope[peaks[-1]]:
                peaks[-1] = idx

    return np.array(peaks, dtype=int)


def _downsample_xy(x: np.ndarray, y: np.ndarray, max_points: int = 1400) -> tuple[np.ndarray, np.ndarray]:
    if x.size <= max_points:
        return x, y
    stride = max(int(np.ceil(x.size / max_points)), 1)
    return x[::stride], y[::stride]


def _line_svg(
    x: np.ndarray,
    y: np.ndarray,
    *,
    width: int = 900,
    height: int = 240,
    stroke: str = "#0d6efd",
    title: str = "",
    x_label: str = "Time (s)",
    y_label: str = "Amplitude",
    marker_x: np.ndarray | None = None,
    marker_y: np.ndarray | None = None,
) -> str:
    if x.size < 2 or y.size < 2:
        return '<div class="plot-empty">Not enough data to render plot.</div>'

    x_ds, y_ds = _downsample_xy(x, y)
    x_min, x_max = float(np.min(x_ds)), float(np.max(x_ds))
    y_min, y_max = float(np.min(y_ds)), float(np.max(y_ds))

    if x_max <= x_min:
        x_max = x_min + 1.0
    if y_max <= y_min:
        y_max = y_min + 1.0

    pad_x = 55
    pad_y = 20
    axis_label_margin_bottom = 22
    axis_label_margin_left = 28
    inner_w = width - 2 * pad_x
    inner_h = height - 2 * pad_y - axis_label_margin_bottom

    def sx(val: float) -> float:
        return pad_x + ((val - x_min) / (x_max - x_min)) * inner_w

    def sy(val: float) -> float:
        return height - pad_y - ((val - y_min) / (y_max - y_min)) * inner_h

    points = " ".join(f"{sx(float(xv)):.2f},{sy(float(yv)):.2f}" for xv, yv in zip(x_ds, y_ds))

    circles = ""
    if marker_x is not None and marker_y is not None and marker_x.size and marker_y.size:
        max_markers = 300
        mx, my = marker_x, marker_y
        if marker_x.size > max_markers:
            mx, my = _downsample_xy(marker_x, marker_y, max_points=max_markers)
        circles = "".join(
            f'<circle cx="{sx(float(xm)):.2f}" cy="{sy(float(ym)):.2f}" r="2" fill="#dc3545" />'
            for xm, ym in zip(mx, my)
        )

    title_svg = f'<text x="{pad_x}" y="14" font-size="12" fill="#495057">{escape(title)}</text>'
    x_label_svg = (
        f'<text x="{pad_x + inner_w/2:.2f}" y="{height - 4}" '
        'font-size="11" fill="#6c757d" text-anchor="middle">'
        f"{escape(x_label)}</text>"
    )
    y_label_svg = (
        f'<text x="{axis_label_margin_left}" y="{pad_y + inner_h/2:.2f}" '
        'font-size="11" fill="#6c757d" text-anchor="middle" '
        f'transform="rotate(-90 {axis_label_margin_left} {pad_y + inner_h/2:.2f})">'
        f"{escape(y_label)}</text>"
    )

    return (
        f'<svg viewBox="0 0 {width} {height}" class="plot-svg" role="img" aria-label="{escape(title)}">'
        f"{title_svg}"
        f"{x_label_svg}"
        f"{y_label_svg}"
        f'<rect x="{pad_x}" y="{pad_y}" width="{inner_w}" height="{inner_h}" fill="#ffffff" stroke="#dee2e6" />'
        f'<polyline fill="none" stroke="{stroke}" stroke-width="1" points="{points}" />'
        f"{circles}"
        "</svg>"
    )


def _hist_svg(values: np.ndarray, *, bins: int = 20, width: int = 900, height: int = 240, title: str = "") -> str:
    if values.size == 0:
        return '<div class="plot-empty">Not enough data to render histogram.</div>'

    counts, edges = np.histogram(values, bins=bins)
    max_count = int(np.max(counts)) if counts.size else 1
    if max_count <= 0:
        max_count = 1

    pad_x = 40
    pad_y = 20
    inner_w = width - 2 * pad_x
    inner_h = height - 2 * pad_y

    bar_w = inner_w / max(len(counts), 1)
    rects = []
    for i, count in enumerate(counts):
        h = (count / max_count) * inner_h
        x = pad_x + i * bar_w
        y = height - pad_y - h
        rects.append(
            f'<rect x="{x:.2f}" y="{y:.2f}" width="{max(bar_w - 1, 1):.2f}" height="{h:.2f}" fill="#17a2b8" />'
        )

    title_svg = f'<text x="{pad_x}" y="14" font-size="12" fill="#495057">{escape(title)}</text>'
    return (
        f'<svg viewBox="0 0 {width} {height}" class="plot-svg" role="img" aria-label="{escape(title)}">'
        f"{title_svg}"
        f'<rect x="{pad_x}" y="{pad_y}" width="{inner_w}" height="{inner_h}" fill="#ffffff" stroke="#dee2e6" />'
        f"{''.join(rects)}"
        "</svg>"
    )


def _generate_physio_html_report(
    *,
    converted: ConvertedFile,
    output_folder: Path,
) -> Path | None:
    edf_files = [p for p in converted.output_files if p.suffix.lower() == ".edf"]
    if not edf_files:
        return None

    edf_path = edf_files[0]

    try:
        import pyedflib
    except Exception:
        report_dir = output_folder / "derivatives" / "physio" / converted.subject
        if converted.session:
            report_dir = report_dir / converted.session
        report_dir.mkdir(parents=True, exist_ok=True)
        report_path = report_dir / f"{converted.subject}_{converted.task}_physio_report.html"
        report_path.write_text(
            "<html><body><h1>Physio report unavailable</h1><p>pyedflib is required to generate reports.</p></body></html>",
            encoding="utf-8",
        )
        return report_path

    with pyedflib.EdfReader(str(edf_path)) as reader:
        labels = [reader.getLabel(i).strip() for i in range(reader.signals_in_file)]
        if not labels:
            return None

        channel_specs = []
        for idx, label in enumerate(labels):
            fs = float(reader.getSampleFrequency(idx))
            try:
                unit = reader.getPhysicalDimension(idx)
            except Exception:
                unit = ""
            signal = np.asarray(reader.readSignal(idx), dtype=float)
            channel_specs.append(
                {
                    "index": idx,
                    "label": label or f"channel-{idx}",
                    "fs": fs,
                    "unit": unit or "n/a",
                    "signal": signal,
                }
            )

        ecg_idx = None
        for idx, label in enumerate(labels):
            lower = label.lower()
            if "ecg" in lower or "ekg" in lower:
                ecg_idx = idx
                break
        if ecg_idx is None:
            ecg_idx = 0

        ecg_label = labels[ecg_idx]
        ecg_unit = channel_specs[ecg_idx]["unit"] if ecg_idx < len(channel_specs) else "uV"
        sampling_rate = float(reader.getSampleFrequency(ecg_idx))
        ecg = np.asarray(reader.readSignal(ecg_idx), dtype=float)
        if ecg.size == 0:
            return None

    sidecar_path = _find_physio_sidecar(output_folder, converted.task, edf_path)
    sidecar_info = {}
    if sidecar_path and sidecar_path.exists():
        try:
            sidecar_info = json.loads(sidecar_path.read_text(encoding="utf-8"))
        except Exception:
            sidecar_info = {}

    demux_channels = (
        sidecar_info.get("DefinitionChannelSelection", {})
        .get("demux", {})
        .get("channels", [])
        if isinstance(sidecar_info, dict)
        else []
    )
    native_fs_by_label = {
        str(c.get("name", "")): float(c.get("fs", 0) or 0)
        for c in demux_channels
        if c.get("name")
    }

    time_axis = np.arange(ecg.size, dtype=float) / sampling_rate
    peaks = _detect_r_peaks(ecg, sampling_rate)

    hr_values = np.array([], dtype=float)
    hr_time = np.array([], dtype=float)
    rr_intervals = np.array([], dtype=float)
    if peaks.size >= 2:
        rr_intervals = np.diff(peaks.astype(float)) / sampling_rate
        valid_rr = rr_intervals[(rr_intervals > 0.3) & (rr_intervals < 1.5)]
        if valid_rr.size:
            hr_values = 60.0 / valid_rr
            hr_time = time_axis[peaks[1 : 1 + valid_rr.size]]

    ecg_svg = _line_svg(
        time_axis,
        ecg,
        stroke="#0d6efd",
        title="Raw ECG with detected peaks",
        x_label="Time (s)",
        y_label=f"Amplitude ({ecg_unit})",
        marker_x=time_axis[peaks] if peaks.size else np.array([]),
        marker_y=ecg[peaks] if peaks.size else np.array([]),
    )

    # Close-up window (about 4 seconds) centered on typical detected R-peaks.
    # Falls back to recording midpoint if no peaks are available.
    closeup_window_sec = 4.0
    if peaks.size > 0:
        center_idx = int(np.median(peaks))
        closeup_anchor = "median R-peak"
    else:
        center_idx = ecg.size // 2
        closeup_anchor = "recording midpoint"
    half_window = int((closeup_window_sec * sampling_rate) / 2)
    start_idx = max(center_idx - half_window, 0)
    end_idx = min(center_idx + half_window, ecg.size)
    closeup_time = time_axis[start_idx:end_idx]
    closeup_ecg = ecg[start_idx:end_idx]

    closeup_peak_mask = (peaks >= start_idx) & (peaks < end_idx)
    closeup_peaks = peaks[closeup_peak_mask] if peaks.size else np.array([], dtype=int)
    closeup_marker_x = time_axis[closeup_peaks] if closeup_peaks.size else np.array([])
    closeup_marker_y = ecg[closeup_peaks] if closeup_peaks.size else np.array([])

    ecg_closeup_svg = _line_svg(
        closeup_time,
        closeup_ecg,
        stroke="#0d6efd",
        title=f"ECG close-up (~{closeup_window_sec:.0f}s around {closeup_anchor})",
        x_label="Time (s)",
        y_label=f"Amplitude ({ecg_unit})",
        marker_x=closeup_marker_x,
        marker_y=closeup_marker_y,
    )
    hr_svg = _line_svg(
        hr_time,
        hr_values,
        stroke="#198754",
        title="Heart rate over time (BPM)",
        x_label="Time (s)",
        y_label="BPM",
    )
    rr_hist_svg = _hist_svg(rr_intervals, bins=20, title="RR-interval histogram (seconds)")

    channel_colors = [
        "#0d6efd",
        "#198754",
        "#fd7e14",
        "#6f42c1",
        "#dc3545",
        "#20c997",
        "#0dcaf0",
        "#6c757d",
    ]
    channel_plot_cards = []
    native_rate_note_needed = False
    for spec in channel_specs:
        signal = spec["signal"]
        fs = spec["fs"]
        if fs <= 0 or signal.size == 0:
            continue
        native_fs = native_fs_by_label.get(str(spec["label"]), fs)
        plotted_signal = signal
        plotted_fs = fs
        if native_fs > 0 and native_fs < fs:
            stride = max(int(round(fs / native_fs)), 1)
            plotted_signal = signal[::stride]
            plotted_fs = fs / stride
            native_rate_note_needed = True

        t = np.arange(plotted_signal.size, dtype=float) / plotted_fs
        color = channel_colors[spec["index"] % len(channel_colors)]
        svg = _line_svg(
            t,
            plotted_signal,
            stroke=color,
            title=(
                f"Channel {spec['index']}: {spec['label']} "
                f"({spec['unit']}), fs={plotted_fs:.2f} Hz"
            ),
            x_label="Time (s)",
            y_label=f"Amplitude ({spec['unit']})",
        )
        fs_note = (
            f"Sampling rate: {plotted_fs:.2f} Hz"
            if abs(plotted_fs - fs) < 1e-9
            else f"Sampling rate: {plotted_fs:.2f} Hz (native view; EDF stored at {fs:.2f} Hz)"
        )
        channel_plot_cards.append(
            "<div class=\"card\">"
            f"<h2>Channel {spec['index']} · {escape(str(spec['label']))}</h2>"
            f"<div class=\"muted\">Unit: {escape(str(spec['unit']))} · "
            f"{fs_note} · Samples: {plotted_signal.size}</div>"
            f"{svg}</div>"
        )

    all_channel_plots_html = "".join(channel_plot_cards)

    hr_meta = sidecar_info.get("HeartRateEstimation") if isinstance(sidecar_info, dict) else {}

    duration_sec = ecg.size / sampling_rate
    quality_status = hr_meta.get("Status", "unknown") if isinstance(hr_meta, dict) else "unknown"
    quality_reason = hr_meta.get("Reason", "unknown") if isinstance(hr_meta, dict) else "unknown"
    avg_hr = sidecar_info.get("AverageHeartRateBPM") if isinstance(sidecar_info, dict) else None

    report_dir = output_folder / "derivatives" / "physio" / converted.subject
    if converted.session:
        report_dir = report_dir / converted.session
    report_dir.mkdir(parents=True, exist_ok=True)

    session_label = converted.session or "nosession"
    report_name = f"{converted.subject}_{session_label}_{converted.task}_physio_report.html"
    report_path = report_dir / report_name

    generated_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    html = f"""
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>PRISM Physio Report - {escape(converted.subject)} {escape(converted.task)}</title>
  <style>
    body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; margin: 20px; color: #212529; background: #f8f9fa; }}
    .card {{ background: #fff; border: 1px solid #dee2e6; border-radius: 10px; padding: 14px 16px; margin-bottom: 14px; }}
    .grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 10px; }}
    .k {{ font-size: 12px; color: #6c757d; }}
    .v {{ font-size: 18px; font-weight: 600; }}
    .plot-svg {{ width: 100%; height: auto; display: block; }}
    .plot-empty {{ padding: 14px; border: 1px dashed #adb5bd; color: #6c757d; background: #fff; border-radius: 8px; }}
    h1 {{ margin: 0 0 8px 0; font-size: 22px; }}
    h2 {{ margin: 0 0 8px 0; font-size: 16px; }}
    .muted {{ color: #6c757d; }}
  </style>
</head>
<body>
  <div class="card">
    <h1>PRISM Physiological Report</h1>
    <div class="muted">Generated: {escape(generated_at)} · Source: {escape(edf_path.name)}</div>
    <div class="muted">PRISM extends BIDS with additional schemas while preserving BIDS compatibility.</div>
  </div>

  <div class="card grid">
    <div><div class="k">Subject</div><div class="v">{escape(converted.subject)}</div></div>
    <div><div class="k">Session</div><div class="v">{escape(converted.session or 'n/a')}</div></div>
    <div><div class="k">Task</div><div class="v">{escape(converted.task)}</div></div>
    <div><div class="k">ECG Channel</div><div class="v">{escape(ecg_label)}</div></div>
    <div><div class="k">Sampling Rate</div><div class="v">{sampling_rate:.2f} Hz</div></div>
    <div><div class="k">Duration</div><div class="v">{duration_sec:.1f} s</div></div>
    <div><div class="k">Detected Peaks</div><div class="v">{int(peaks.size)}</div></div>
    <div><div class="k">Average HR</div><div class="v">{escape(str(avg_hr)) if avg_hr is not None else 'not estimated'}</div></div>
    <div><div class="k">HR Quality Status</div><div class="v">{escape(str(quality_status))}</div></div>
    <div><div class="k">HR Quality Reason</div><div class="v">{escape(str(quality_reason))}</div></div>
  </div>

  <div class="card"><h2>Raw ECG + R-Peaks</h2>{ecg_svg}</div>
    <div class="card"><h2>ECG Close-up + R-Peaks</h2>{ecg_closeup_svg}</div>
  <div class="card"><h2>Heart Rate Over Time</h2>{hr_svg}</div>
  <div class="card"><h2>RR-Interval Histogram</h2>{rr_hist_svg}</div>
        <div class="card"><h2>All Found Channels</h2><div class="muted">Per-channel overview from the converted EDF.{" Slower channels are shown in native-rate view when demux metadata is available." if native_rate_note_needed else ""}</div></div>
    {all_channel_plots_html}
</body>
</html>
"""
    report_path.write_text(html, encoding="utf-8")
    return report_path


def convert_physio_file(
    source_path: Path,
    output_dir: Path,
    *,
    parsed: dict,
    base_freq: float | None = None,
    log_callback: Callable[[str, str], None] | None = None,
) -> ConvertedFile:
    """Convert a single physio file (Varioport .raw/.vpd) to PRISM format.

    This uses the existing convert_varioport function if available, otherwise
    just copies the file and creates a sidecar.
    """
    sub = parsed["sub"]
    ses = parsed["ses"]
    task = parsed["task"]
    ext = parsed["ext"]

    # Build output path: output_dir/sub-XXX/[ses-YYY/]physio/
    if ses:
        out_folder = output_dir / sub / ses / "physio"
    else:
        out_folder = output_dir / sub / "physio"
    out_folder.mkdir(parents=True, exist_ok=True)

    # Recording label based on source format
    rec_label = "vpd" if ext == "vpd" else "raw"

    # Build BIDS filename
    parts = [sub]
    if ses:
        parts.append(ses)
    parts.append(task)
    parts.append(f"recording-{rec_label}")
    parts.append("physio")
    base_name = "_".join(parts)

    output_files = []

    try:
        # Try to use the Varioport converter for .raw/.vpd
        # Note: parse_bids_filename stores extension without leading dot
        if ext in ("raw", "vpd"):
            try:
                try:
                    from helpers.physio.convert_varioport import convert_varioport
                except ImportError:
                    from app.helpers.physio.convert_varioport import convert_varioport

                out_edf = out_folder / f"{base_name}.edf"
                out_json = out_folder / f"{base_name}.json"

                conversion_stdout = io.StringIO()
                with redirect_stdout(conversion_stdout):
                    try:
                        conversion_meta = convert_varioport(
                            str(source_path),
                            str(out_edf),
                            str(out_json),
                            task_name=task.replace("task-", ""),
                            base_freq=base_freq,
                        )
                    except ValueError as e:
                        if "Unsupported Varioport header type" in str(e):
                            if log_callback:
                                log_callback(
                                    "  ⚠️ Type-7 RAW detected. Retrying with experimental multiplexed decoder (QC required).",
                                    "warning",
                                )
                            conversion_meta = convert_varioport(
                                str(source_path),
                                str(out_edf),
                                str(out_json),
                                task_name=task.replace("task-", ""),
                                base_freq=base_freq,
                                allow_raw_multiplexed=True,
                            )
                        else:
                            raise

                if log_callback:
                    for raw_line in conversion_stdout.getvalue().splitlines():
                        line = raw_line.strip()
                        if line:
                            log_callback(f"    {line}", "info")

                avg_hr = None
                hr_est = {}
                if isinstance(conversion_meta, dict):
                    avg_hr = conversion_meta.get("AverageHeartRateBPM")
                    hr_est = conversion_meta.get("HeartRateEstimation") or {}

                if out_edf.exists():
                    output_files.append(out_edf)
                if out_json.exists():
                    output_files.append(out_json)

                if avg_hr is not None:
                    if log_callback:
                        log_callback(f"  ❤️ Average heart rate: {avg_hr} bpm", "info")
                        task_warning = hr_est.get("TaskPlausibilityWarning")
                        if task_warning:
                            log_callback(
                                "  ⚠️ Task label plausibility warning: HR is signal-valid but outside expected range for this task label.",
                                "warning",
                            )
                else:
                    if log_callback:
                        reason = hr_est.get("Reason", "insufficient ECG confidence")
                        log_callback(
                            f"  ℹ️ Average heart rate not estimated ({reason}).",
                            "warning",
                        )

            except ImportError as ie:
                # Fallback: just copy file and create minimal sidecar
                if log_callback:
                    log_callback(
                        f"  ⚠️ Cannot convert RAW to EDF: {ie}. Missing pyedflib? Install with: pip install pyedflib",
                        "warning",
                    )
                    log_callback(
                        f"  ℹ️ Copying {ext.upper()} file without conversion.",
                        "info",
                    )
                out_data = out_folder / f"{base_name}.{ext}"
                out_json = out_folder / f"{base_name}.json"

                shutil.copy2(source_path, out_data)
                _create_physio_sidecar(
                    source_path,
                    out_json,
                    task_name=task,
                    sampling_rate=base_freq,
                )

                output_files.extend([out_data, out_json])
        else:
            # For .edf or other formats already in physio-compatible format
            out_data = out_folder / f"{base_name}.{ext}"
            out_json = out_folder / f"{base_name}.json"

            shutil.copy2(source_path, out_data)

            # Extract metadata if it's an EDF file
            edf_meta = {}
            if ext == "edf":
                edf_meta = _extract_edf_metadata(source_path)

            _create_physio_sidecar(
                source_path,
                out_json,
                task_name=task,
                sampling_rate=base_freq,
                extra_meta=edf_meta,
            )
            output_files.extend([out_data, out_json])

        return ConvertedFile(
            source_path=source_path,
            output_files=output_files,
            modality="physio",
            subject=sub,
            session=ses,
            task=task,
            success=True,
        )

    except Exception as e:
        return ConvertedFile(
            source_path=source_path,
            output_files=[],
            modality="physio",
            subject=sub,
            session=ses,
            task=task,
            success=False,
            error=str(e),
        )


def convert_eyetracking_file(
    source_path: Path,
    output_dir: Path,
    *,
    parsed: dict,
) -> ConvertedFile:
    """Convert a single eyetracking file (.edf) to PRISM format.

    For EyeLink .edf files, we copy the file (it's already a standard format)
    and create a JSON sidecar with metadata.
    """
    sub = parsed["sub"]
    ses = parsed["ses"]
    task = parsed["task"]

    # Build output path: output_dir/sub-XXX/[ses-YYY/]eyetracking/
    if ses:
        out_folder = output_dir / sub / ses / "eyetracking"
    else:
        out_folder = output_dir / sub / "eyetracking"
    out_folder.mkdir(parents=True, exist_ok=True)

    # Build BIDS filename
    parts = [sub]
    if ses:
        parts.append(ses)
    parts.append(task)
    parts.append("eyetrack")
    base_name = "_".join(parts)

    out_edf = out_folder / f"{base_name}.edf"
    out_json = out_folder / f"{base_name}.json"

    output_files = []

    try:
        # Copy the EDF file
        shutil.copy2(source_path, out_edf)
        output_files.append(out_edf)

        # Create sidecar
        edf_meta = _extract_edf_metadata(source_path)
        _create_eyetracking_sidecar(
            source_path, out_json, task_name=task, extra_meta=edf_meta
        )
        output_files.append(out_json)

        # Try to enrich sidecar with EDF header info if pyedflib is available
        try:
            import pyedflib

            with pyedflib.EdfReader(str(source_path)) as f:
                with open(out_json, "r", encoding="utf-8") as jf:
                    sidecar = json.load(jf)

                if "Technical" not in sidecar:
                    sidecar["Technical"] = {}

                # Extract sampling rate (from first signal)
                if f.signals_in_file > 0:
                    sidecar["Technical"]["SamplingFrequency"] = f.getSampleFrequency(0)

                # Extract duration
                sidecar["Technical"]["Duration"] = f.getFileDuration()

                with open(out_json, "w", encoding="utf-8") as jf:
                    json.dump(sidecar, jf, indent=2)
        except (ImportError, Exception):
            pass

        return ConvertedFile(
            source_path=source_path,
            output_files=output_files,
            modality="eyetracking",
            subject=sub,
            session=ses,
            task=task,
            success=True,
        )

    except Exception as e:
        return ConvertedFile(
            source_path=source_path,
            output_files=[],
            modality="eyetracking",
            subject=sub,
            session=ses,
            task=task,
            success=False,
            error=str(e),
        )


def convert_generic_file(
    source_path: Path,
    output_dir: Path,
    *,
    parsed: dict,
    target_modality: str = "extra",
) -> ConvertedFile:
    """Organize a generic file into PRISM structure by copying it.

    Args:
        source_path: Path to source file
        output_dir: Path to output dataset root
        parsed: Parsed BIDS components
        target_modality: Modality folder name (e.g., 'survey', 'anat', 'func')
    """
    sub = parsed["sub"]
    ses = parsed["ses"]
    task = parsed["task"]
    ext = parsed["ext"]
    extra = parsed["extra"]

    # Build output path: output_dir/sub-XXX/[ses-YYY/]modality/
    if ses:
        out_folder = output_dir / sub / ses / target_modality
    else:
        out_folder = output_dir / sub / target_modality
    out_folder.mkdir(parents=True, exist_ok=True)

    # Build BIDS filename
    parts = [sub]
    if ses:
        parts.append(ses)
    parts.append(task)
    if extra:
        parts.append(extra.lstrip("_"))

    # Add suffix based on modality if not already in extra
    suffix_map = {
        "survey": "survey",
        "biometrics": "biometrics",
        "physio": "physio",
        "eyetracking": "eyetrack",
        "anat": "T1w",
        "func": "bold",
    }

    suffix = suffix_map.get(target_modality, target_modality)

    # Check if suffix is already present in the parts
    suffix_already_present = False
    for p in parts:
        if p == suffix or p.endswith(f"_{suffix}") or p.endswith(f"-{suffix}"):
            suffix_already_present = True
            break

    if not suffix_already_present:
        parts.append(suffix)

    base_name = "_".join(parts)
    out_data = out_folder / f"{base_name}.{ext}"

    try:
        shutil.copy2(source_path, out_data)

        # Create a minimal sidecar if it's a data file (not already a json)
        output_files = [out_data]
        if ext != "json":
            out_json = out_folder / f"{base_name}.json"
            sidecar = {
                "Metadata": {
                    "SourceFile": source_path.name,
                    "OrganizedBy": "prism batch organizer",
                }
            }
            with open(out_json, "w", encoding="utf-8") as f:
                json.dump(sidecar, f, indent=2)
            output_files.append(out_json)

        return ConvertedFile(
            source_path=source_path,
            output_files=output_files,
            modality=target_modality,
            subject=sub,
            session=ses,
            task=task,
            success=True,
        )
    except Exception as e:
        return ConvertedFile(
            source_path=source_path,
            output_files=[],
            modality=target_modality,
            subject=sub,
            session=ses,
            task=task,
            success=False,
            error=str(e),
        )


def batch_convert_folder(
    source_folder: Path | str,
    output_folder: Path | str,
    *,
    physio_sampling_rate: float | None = None,
    generate_physio_reports: bool = False,
    modality_filter: str = "all",
    log_callback: Callable | None = None,
    dry_run: bool = False,
) -> BatchConvertResult:
    """Batch convert all supported files from a flat folder structure.

    Args:
        source_folder: Path to folder containing raw data files
        output_folder: Path to output PRISM dataset folder
        physio_sampling_rate: Optional sampling rate override for physio files
        generate_physio_reports: Generate per subject/session HTML physio reports
        modality_filter: Which modalities to process ("all", "physio", or "eyetracking")
        log_callback: Optional callback for logging messages: log_callback(message, level)
                      where level is "info", "success", "warning", or "error"

    Returns:
        BatchConvertResult with details of all conversions
    """

    def log(msg: str, level: str = "info"):
        if log_callback:
            log_callback(msg, level)

    source_folder = Path(source_folder)
    output_folder = Path(output_folder)

    result = BatchConvertResult(
        source_folder=source_folder,
        output_folder=output_folder,
    )

    log(f"📂 Scanning source folder: {source_folder.name}", "info")
    if dry_run:
        log("🧪 DRY RUN MODE - No files will be written", "info")

    # Find all supported files
    all_extensions = set()
    if modality_filter in ("all", "physio"):
        all_extensions.update(PHYSIO_EXTENSIONS)
    if modality_filter in ("all", "eyetracking"):
        all_extensions.update(EYETRACKING_EXTENSIONS)
    if modality_filter not in ("all", "physio", "eyetracking"):
        # If a specific modality is requested that isn't physio/eyetracking,
        # we assume it's a generic copy operation
        all_extensions.update(GENERIC_EXTENSIONS)
        all_extensions.update(PHYSIO_EXTENSIONS)
        all_extensions.update(EYETRACKING_EXTENSIONS)

    # Collect files first to get total count
    files_to_process = []
    for file_path in sorted(source_folder.iterdir()):
        if not file_path.is_file():
            continue
        ext = file_path.suffix.lower()
        # Handle .nii.gz
        if file_path.name.lower().endswith(".nii.gz"):
            ext = ".nii.gz"

        if modality_filter == "all":
            if (
                ext in PHYSIO_EXTENSIONS
                or ext in EYETRACKING_EXTENSIONS
                or ext in GENERIC_EXTENSIONS
            ):
                files_to_process.append(file_path)
        elif ext in all_extensions:
            files_to_process.append(file_path)

    log(f"📋 Found {len(files_to_process)} files to process", "info")

    for idx, file_path in enumerate(files_to_process, 1):
        ext = file_path.suffix.lower()
        if file_path.name.lower().endswith(".nii.gz"):
            ext = ".nii.gz"

        # Parse filename
        parsed = parse_bids_filename(file_path.name)
        if not parsed:
            msg = f"Invalid filename pattern. Expected: sub-XXX_ses-YYY_task-ZZZ.{ext}"
            result.skipped.append((file_path, msg))
            log(
                f"⏭️  [{idx}/{len(files_to_process)}] Skipped: {file_path.name} - {msg}",
                "warning",
            )
            continue

        subject_label = parsed.get("sub", "unknown")
        session_label = parsed.get("ses") or "nosession"
        task_label = parsed.get("task", "unknown")
        log(
            f"👤 Working on {subject_label} / {session_label} / {task_label}",
            "info",
        )

        # Detect modality and convert
        modality = detect_modality(ext)

        # Override modality if filter is specific and not 'all'
        if modality_filter not in ("all", "physio", "eyetracking"):
            modality = "generic"
            target_modality = modality_filter
        else:
            target_modality = modality

        log(
            f"🔄 [{idx}/{len(files_to_process)}] Processing: {file_path.name} ({target_modality})",
            "info",
        )

        if target_modality == "physio":
            converted = convert_physio_file(
                file_path,
                output_folder,
                parsed=parsed,
                base_freq=physio_sampling_rate,
                log_callback=log_callback,
            )
        elif target_modality == "eyetracking":
            converted = convert_eyetracking_file(
                file_path,
                output_folder,
                parsed=parsed,
            )
        elif modality == "generic" or modality_filter not in (
            "all",
            "physio",
            "eyetracking",
        ):
            converted = convert_generic_file(
                file_path,
                output_folder,
                parsed=parsed,
                target_modality=(
                    target_modality if target_modality != "generic" else "extra"
                ),
            )
        else:
            msg = f"Unknown modality for extension: {ext}"
            result.skipped.append((file_path, msg))
            log(
                f"⏭️  [{idx}/{len(files_to_process)}] Skipped: {file_path.name} - {msg}",
                "warning",
            )
            continue

        result.converted.append(converted)

        if converted.success:
            # Track file existence for dry-run reporting
            if dry_run and converted.output_files:
                files_exist = sum(1 for f in converted.output_files if f.exists())
                result.existing_files += files_exist
                result.new_files += len(converted.output_files) - files_exist

            if dry_run:
                # In dry run, show what would be created
                if converted.output_files:
                    output_paths = ", ".join([f.name for f in converted.output_files])
                    log(
                        f"✅ [{idx}/{len(files_to_process)}] Would create: {file_path.name} → {converted.modality}/ ({output_paths})",
                        "success",
                    )
                else:
                    log(
                        f"✅ [{idx}/{len(files_to_process)}] Would process: {file_path.name} → {converted.modality}/",
                        "success",
                    )
            else:
                log(
                    f"✅ [{idx}/{len(files_to_process)}] Success: {file_path.name} → {converted.modality}/",
                    "success",
                )

            if (
                not dry_run
                and generate_physio_reports
                and target_modality == "physio"
                and converted.output_files
            ):
                try:
                    report_path = _generate_physio_html_report(
                        converted=converted,
                        output_folder=output_folder,
                    )
                    if report_path is not None:
                        log(
                            f"   🧾 Physio report: {report_path.relative_to(output_folder)}",
                            "info",
                        )
                except Exception as report_error:
                    log(
                        f"   ⚠️ Physio report generation failed: {report_error}",
                        "warning",
                    )
        else:
            log(
                f"❌ [{idx}/{len(files_to_process)}] Error: {file_path.name} - {converted.error}",
                "error",
            )

    # Summary
    log("", "info")
    if dry_run:
        log("🧪 DRY RUN SUMMARY:", "info")
        log(f"   ✅ Would organize: {result.success_count} files", "success")
        log(f"   📄 New files: {result.new_files}", "info")
        log(
            f"   📋 Existing files (will be overwritten): {result.existing_files}",
            "warning",
        )
    else:
        log("📊 Conversion complete:", "info")
        log(f"   ✅ Successful: {result.success_count}", "success")
    if result.error_count > 0:
        log(f"   ❌ Errors: {result.error_count}", "error")
    if result.skipped:
        log(f"   ⏭️  Skipped: {len(result.skipped)}", "warning")
    if result.conflicts:
        log(f"   ⚠️  Conflicts: {len(result.conflicts)}", "warning")
    if dry_run:
        log("💡 Run 'Copy to Project' when you're ready to execute.", "info")

    # Update participants.tsv with all participant IDs found in converted files
    if not dry_run and result.success_count > 0:
        participant_ids = {
            conv.subject for conv in result.converted if conv.success and conv.subject
        }

        if participant_ids:
            try:
                # Import the utility function
                try:
                    from src.utils.io import update_participants_tsv
                except ImportError:
                    # Fallback if running from different location
                    try:
                        from utils.io import update_participants_tsv
                    except ImportError:
                        update_participants_tsv = None

                if update_participants_tsv:
                    update_participants_tsv(
                        output_folder,
                        participant_ids,
                        log_fn=lambda msg: log(msg, "info"),
                    )
            except Exception as e:
                log(f"⚠️  Could not update participants.tsv: {e}", "warning")

    return result


def create_dataset_description(
    output_folder: Path,
    *,
    name: str = "Converted Dataset",
    description: str = "Dataset converted from raw physio/eyetracking files",
) -> Path:
    """Create a dataset_description.json file for the output dataset following BIDS v1.10.1."""
    desc = {
        "Name": name,
        "BIDSVersion": "1.10.1",
        "DatasetType": "raw",
        "Description": description,
        "Authors": [],
        "GeneratedBy": [
            {
                "Name": "PRISM Batch Converter",
                "Version": "1.1.1",
                "Description": "Automated conversion from raw physiological/eyetracking files to BIDS/PRISM structure.",
            }
        ],
        "HEDVersion": "8.2.0",
    }

    output_path = output_folder / "dataset_description.json"
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(desc, f, indent=2, ensure_ascii=False)

    return output_path


# CLI interface
if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="Batch convert physio/eyetracking data from flat folder to PRISM format"
    )
    parser.add_argument(
        "source",
        type=Path,
        help="Source folder containing raw files (flat structure)",
    )
    parser.add_argument(
        "output",
        type=Path,
        help="Output folder for PRISM dataset",
    )
    parser.add_argument(
        "--sampling-rate",
        type=float,
        help="Override sampling rate for physio files",
    )
    parser.add_argument(
        "--modality",
        choices=["all", "physio", "eyetracking"],
        default="all",
        help="Which modalities to convert (default: all)",
    )
    parser.add_argument(
        "--physio-reports",
        action="store_true",
        help="Generate per subject/session HTML physio reports under derivatives/physio",
    )
    parser.add_argument(
        "--dataset-name",
        default="Converted Dataset",
        help="Name for dataset_description.json",
    )

    args = parser.parse_args()

    print(f"Converting files from: {args.source}")
    print(f"Output folder: {args.output}")
    print()

    # Create output folder
    args.output.mkdir(parents=True, exist_ok=True)

    # Run conversion
    result = batch_convert_folder(
        args.source,
        args.output,
        physio_sampling_rate=args.sampling_rate,
        generate_physio_reports=args.physio_reports,
        modality_filter=args.modality,
    )

    # Create dataset description
    create_dataset_description(args.output, name=args.dataset_name)

    # Print summary
    print(f"✅ Successfully converted: {result.success_count} files")
    if result.error_count > 0:
        print(f"❌ Errors: {result.error_count} files")
    if result.skipped:
        print(f"⏭️  Skipped: {len(result.skipped)} files")
        for path, reason in result.skipped:
            print(f"   - {path.name}: {reason}")

    print()
    for conv in result.converted:
        status = "✅" if conv.success else "❌"
        print(f"{status} {conv.source_path.name} → {conv.modality}/")
        if conv.error:
            print(f"   Error: {conv.error}")
