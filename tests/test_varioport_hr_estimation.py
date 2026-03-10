import sys
from pathlib import Path

import numpy as np

project_root = Path(__file__).resolve().parents[1]
app_path = project_root / "app"
if str(app_path) not in sys.path:
    sys.path.insert(0, str(app_path))

from helpers.physio.convert_varioport import _estimate_average_heart_rate_bpm


def _synthetic_ecg(duration_s: int, sampling_rate: int, bpm: float) -> np.ndarray:
    total = duration_s * sampling_rate
    rng = np.random.default_rng(42)
    signal = rng.normal(0.0, 0.03, total)

    step = int(round((60.0 / bpm) * sampling_rate))
    qrs = np.array([0.0, 0.5, 1.6, 0.9, 0.2, 0.0, -0.1, 0.0], dtype=float)

    idx = step
    while idx < total - len(qrs):
        signal[idx : idx + len(qrs)] += qrs
        jitter = int(rng.integers(-int(0.04 * step), int(0.04 * step) + 1))
        idx += max(step + jitter, int(0.6 * step))

    return signal


def test_hr_estimation_rest_task_tracks_plausible_rate():
    signal = _synthetic_ecg(duration_s=120, sampling_rate=256, bpm=72.0)

    bpm = _estimate_average_heart_rate_bpm(signal, 256, task_name="rest")

    assert bpm is not None
    assert 60.0 <= bpm <= 85.0


def test_hr_estimation_rejects_unrealistic_resting_artifact_rate():
    sr = 256
    duration = 120
    total = sr * duration
    artifact = np.zeros(total, dtype=float)

    # 200 bpm-like periodic artifact (should be rejected for rest tasks)
    step = int(round((60.0 / 200.0) * sr))
    pulse = np.array([0.0, 1.0, 0.2, 0.0], dtype=float)
    for idx in range(step, total - len(pulse), step):
        artifact[idx : idx + len(pulse)] += pulse

    bpm = _estimate_average_heart_rate_bpm(artifact, sr, task_name="rest")

    assert bpm is None


def test_hr_estimation_quality_gate_is_task_label_independent_for_good_signal():
    signal = _synthetic_ecg(duration_s=120, sampling_rate=256, bpm=72.0)

    bpm_rest, details_rest = _estimate_average_heart_rate_bpm(
        signal,
        256,
        task_name="rest",
        return_details=True,
    )

    bpm_other, details_other = _estimate_average_heart_rate_bpm(
        signal,
        256,
        task_name="stress",
        return_details=True,
    )

    assert bpm_rest is not None
    assert bpm_other is not None
    assert details_rest.get("status") == "estimated"
    assert details_other.get("status") == "estimated"
