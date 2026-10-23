"""Counts and device/sequence parameters per recorded modality, read from BIDS sidecars."""

from __future__ import annotations

import json
from pathlib import Path

from src.environment_mri_scan import (
    _discover_sidecar_json_paths,
    _subject_session_from_path,
    resolve_bids_rawdata_root,
)

_MRI = ("RepetitionTime", "EchoTime", "FlipAngle", "MagneticFieldStrength", "Manufacturer", "ManufacturersModelName")
_REC = ("SamplingFrequency", "EEGReference", "Manufacturer", "ManufacturersModelName")
PARAM_FIELDS = {
    "func": _MRI,
    "anat": _MRI,
    "dwi": _MRI,
    "fmap": _MRI,
    "eeg": _REC,
    "physio": _REC,
}


def _ordered(values) -> list:
    try:
        return sorted(values)
    except TypeError:  # mixed types or lists
        return sorted(values, key=str)


def acquisition_summary(project_path: Path) -> dict:
    """``{"modalities": {mod: {"n_subjects", "sessions": {label: n}, "params": {field: [values]}}}}``.

    Session labels are the folder labels exactly as found. Modalities without
    acquisition parameters (survey, biometrics) are left out.
    """
    root = resolve_bids_rawdata_root(Path(project_path))
    subjects: dict[str, set] = {}
    sessions: dict[str, dict[str, set]] = {}
    params: dict[str, dict[str, dict[str, object]]] = {}
    for path in _discover_sidecar_json_paths(root):
        modality = path.parent.name
        if modality not in PARAM_FIELDS:
            continue
        subject, session = _subject_session_from_path(path, root)
        try:
            sidecar = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        subjects.setdefault(modality, set()).add(subject)
        if session:
            sessions.setdefault(modality, {}).setdefault(session[4:], set()).add(subject)
        seen = params.setdefault(modality, {})
        for field in PARAM_FIELDS[modality]:
            if field in sidecar:
                seen.setdefault(field, {})[json.dumps(sidecar[field])] = sidecar[field]
    return {
        "modalities": {
            m: {
                "n_subjects": len(subjects[m]),
                "sessions": {k: len(v) for k, v in sessions.get(m, {}).items()},
                "params": {
                    f: _ordered(vals.values()) for f, vals in params[m].items()
                },
            }
            for m in sorted(subjects)
        }
    }
