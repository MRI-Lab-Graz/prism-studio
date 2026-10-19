"""Write BIDS physio files (`*_physio.tsv.gz` + `.json`) and read EDF without pyedflib."""

from __future__ import annotations

import gzip
import io
import json
import re
from pathlib import Path

import numpy as np


def write_bids_physio(
    channels: dict[str, np.ndarray],
    *,
    sampling_frequency: float,
    start_time: float,
    out_base: Path,
    extra_meta: dict | None = None,
) -> list[Path]:
    """Write `<out_base>.tsv.gz` (no header, one column per channel) and `<out_base>.json`."""
    out_base = Path(out_base)
    data = np.column_stack(list(channels.values()))
    tsv = out_base.with_name(out_base.name + ".tsv.gz")
    sidecar = out_base.with_name(out_base.name + ".json")
    with open(tsv, "wb") as raw, gzip.GzipFile(fileobj=raw, mode="wb", mtime=0, filename="") as gz:
        with io.TextIOWrapper(gz, encoding="utf-8", newline="\n") as fh:
            np.savetxt(fh, data, delimiter="\t", fmt="%.10g")
    meta = {
        "SamplingFrequency": float(sampling_frequency),
        "StartTime": float(start_time),
        "Columns": list(channels),
        **(extra_meta or {}),
    }
    sidecar.write_text(json.dumps(meta, indent=2) + "\n", encoding="utf-8")
    return [tsv, sidecar]


def _bad(why: str) -> ValueError:
    return ValueError(f"not a valid EDF file: {why}")


def read_edf(edf_path: Path) -> tuple[dict[str, np.ndarray], dict[str, float], float]:
    """Read EDF/EDF+ -> (physical channels by label, rate by label, StartTime 0.0).

    The `EDF Annotations` signal is skipped. The whole file is validated first.
    """
    raw = Path(edf_path).read_bytes()
    if len(raw) < 256:
        raise _bad("header is truncated")
    if raw[192:197] == b"EDF+D":
        raise _bad("discontinuous EDF+D is not supported")
    try:
        header_bytes = int(raw[184:192])
        n_rec = int(raw[236:244])
        dur = float(raw[244:252])
        ns = int(raw[252:256])
    except ValueError:
        raise _bad("unreadable header fields") from None
    if ns < 1 or dur <= 0 or n_rec < 0 or header_bytes != 256 * (ns + 1) or len(raw) < header_bytes:
        raise _bad("inconsistent header")

    def field(offset: int, width: int, cast=str) -> list:
        base = 256 + offset * ns
        try:
            return [cast(raw[base + i * width : base + (i + 1) * width].decode("ascii").strip()) for i in range(ns)]
        except ValueError:
            raise _bad("unreadable signal header") from None

    labels = field(0, 16)
    pmin, pmax = field(104, 8, float), field(112, 8, float)
    dmin, dmax = field(120, 8, float), field(128, 8, float)
    spr = field(216, 8, int)
    if any(s < 1 for s in spr) or any(a == b for a, b in zip(dmin, dmax)):
        raise _bad("inconsistent signal header")
    rec_len = sum(spr)
    if len(raw) != header_bytes + n_rec * rec_len * 2:
        raise _bad("file length does not match header")

    data = np.frombuffer(raw, dtype="<i2", offset=header_bytes).reshape(n_rec, rec_len)
    channels: dict[str, np.ndarray] = {}
    rates: dict[str, float] = {}
    pos = 0
    for i, label in enumerate(labels):
        block = data[:, pos : pos + spr[i]]
        pos += spr[i]
        if label == "EDF Annotations":
            continue
        if label in channels:
            raise _bad(f"duplicate channel label {label!r}")
        gain = (pmax[i] - pmin[i]) / (dmax[i] - dmin[i])
        channels[label] = (block.reshape(-1).astype(float) - dmin[i]) * gain + pmin[i]
        rates[label] = spr[i] / dur
    if not channels:
        raise _bad("no signal channels")
    return channels, rates, 0.0


def edf_to_bids_physio(edf_path: Path, out_dir: Path, stem_prefix: str, recording_label: str) -> list[Path]:
    """Convert an EDF to BIDS physio files, one per sampling rate."""
    channels, rates, start = read_edf(edf_path)  # validates before any output
    groups: dict[float, dict[str, np.ndarray]] = {}
    for label, values in channels.items():
        groups.setdefault(rates[label], {})[label] = values
    Path(out_dir).mkdir(parents=True, exist_ok=True)
    out: list[Path] = []
    for rate, group in groups.items():
        label = recording_label
        if len(groups) > 1:
            label += re.sub(r"[^0-9a-zA-Z]", "", f"{rate:g}".replace(".", "p")) + "hz"
        out += write_bids_physio(
            group,
            sampling_frequency=rate,
            start_time=start,
            out_base=Path(out_dir) / f"{stem_prefix}_recording-{label}_physio",
        )
    return out
