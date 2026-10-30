"""Running a Varioport conversion: one place for ``convert physio`` and Studio's Physio converter."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Callable


def run_varioport_conversion(
    convert_varioport: Callable[..., Any],
    raw_file: Path,
    out_edf: Path,
    out_json: Path,
    *,
    task: str,
    sampling_rate: float | None,
    bids_base: Path | None = None,
    log_fn: Callable[[str], Any] = print,
) -> None:
    """Convert ``raw_file`` to EDF+ and a sidecar; a Type-7 RAW (unsupported header) is retried once with the
    experimental multiplexed decoder, which needs a QC by the user."""
    extra = {"bids_base": bids_base} if bids_base else {}
    arguments = (str(raw_file), str(out_edf), str(out_json))
    try:
        convert_varioport(*arguments, task_name=task, base_freq=sampling_rate, **extra)
    except ValueError as error:
        if "Unsupported Varioport header type" not in str(error):
            raise
        log_fn("⚠️ Type-7 RAW detected. Retrying with experimental multiplexed decoder (QC required).")
        convert_varioport(*arguments, task_name=task, base_freq=sampling_rate, allow_raw_multiplexed=True, **extra)
