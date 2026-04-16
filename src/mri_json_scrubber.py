"""
MRI JSON sidecar scrubber — remove privacy-sensitive fields from BIDS sidecars.

Based on the approach used by publicBIDS (MRI-Lab-Graz) with additions for
defacing detection. This module belongs to the canonical backend (src/).

Sensitive fields are those that can identify a scanner, site, or subject:
  - Device identifiers (SerialNumber, StationName, DeviceSerialNumber)
  - Acquisition timestamps / dates
  - Operator / clinician names
  - Raw k-space / acquisition parameters that can fingerprint a site
  - BodyPart* fields that may reveal clinical information

Defacing detection for anatomical (T1w/T2w/FLAIR…) NIfTI files checks whether
a *_T1w.json sidecar (or equivalent) lives next to a NIfTI whose filename
suggests it has already been defaced (common suffixes: _defaced, _desc-defaced).
Because actual pixel-level analysis is out-of-scope (and slow), we only do a
*filename heuristic* plus an optional NIfTI header check via nibabel when
available.
"""

from __future__ import annotations

import json
import logging
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Sensitive field lists
# Fields are matched case-insensitively against the top-level JSON keys.
# ---------------------------------------------------------------------------

#: Fields that are *always* scrubbed regardless of modality.
ALWAYS_SCRUB: Set[str] = {
    # Scanner / site identifiers
    "DeviceSerialNumber",
    "StationName",
    "InstitutionName",
    "InstitutionAddress",
    "InstitutionalDepartmentName",
    "ManufacturersModelName",
    # Operator / personnel
    "OperatorsName",
    "ReferringPhysicianName",
    "PerformingPhysiciansName",
    # Dates / times (can link back to a specific session)
    "AcquisitionDateTime",
    "AcquisitionDate",
    "AcquisitionTime",
    "SeriesDate",
    "StudyDate",
    "ContentDate",
    "PatientBirthDate",
}

#: Additional fields scrubbed for anatomical modalities (anat/).
ANAT_EXTRA_SCRUB: Set[str] = {
    "ImageOrientationPatientDICOM",
    # Patient info sometimes encoded in anat sidecars
    "PatientName",
    "PatientID",
    "PatientSex",
    "PatientAge",
    "PatientWeight",
}

#: Fields to scrub for functional (func/) and diffusion (dwi/) sidecars.
FUNC_DWI_EXTRA_SCRUB: Set[str] = {
    "ImageOrientationPatientDICOM",
}

#: Fieldmap (fmap/) — same as func/dwi.
FMAP_EXTRA_SCRUB = FUNC_DWI_EXTRA_SCRUB

# modality folder → extra scrub set
_MODALITY_EXTRA: Dict[str, Set[str]] = {
    "anat": ANAT_EXTRA_SCRUB,
    "func": FUNC_DWI_EXTRA_SCRUB,
    "dwi": FUNC_DWI_EXTRA_SCRUB,
    "fmap": FMAP_EXTRA_SCRUB,
}

# Modality folders we consider "MRI BIDS" for scrubbing purposes.
MRI_MODALITIES: Set[str] = {"anat", "func", "dwi", "fmap"}

# Anatomical suffixes used for defacing detection
ANAT_SUFFIXES: Set[str] = {
    "T1w", "T2w", "FLAIR", "T1rho", "T2star",
    "UNIT1", "angio", "PDw", "PDT2", "T1map", "T2map",
}


# ---------------------------------------------------------------------------
# Core scrubbing function
# ---------------------------------------------------------------------------

def scrub_sensitive_json_fields(
    data: Dict[str, Any],
    modality: Optional[str] = None,
    extra_fields: Optional[Set[str]] = None,
) -> Tuple[Dict[str, Any], List[str]]:
    """Remove privacy-sensitive fields from a BIDS JSON sidecar.

    Args:
        data: Parsed JSON sidecar as a dict.
        modality: BIDS modality folder name ('anat', 'func', 'dwi', 'fmap').
                  If None, only ALWAYS_SCRUB fields are removed.
        extra_fields: Any additional field names to remove on top of the
                      standard sets.

    Returns:
        Tuple of (scrubbed_data, removed_fields) where removed_fields is the
        list of field names that were actually present and removed.
    """
    to_remove: Set[str] = set(ALWAYS_SCRUB)
    if modality and modality in _MODALITY_EXTRA:
        to_remove |= _MODALITY_EXTRA[modality]
    if extra_fields:
        to_remove |= extra_fields

    # Build case-insensitive lookup so we match regardless of capitalisation
    key_map: Dict[str, str] = {k.lower(): k for k in data.keys()}
    removed: List[str] = []

    scrubbed = dict(data)
    for field in to_remove:
        actual_key = key_map.get(field.lower())
        if actual_key is not None and actual_key in scrubbed:
            del scrubbed[actual_key]
            removed.append(actual_key)

    if removed:
        logger.debug("Scrubbed %d field(s): %s", len(removed), removed)

    return scrubbed, removed


def scrub_json_file(
    json_path: Path,
    modality: Optional[str] = None,
    extra_fields: Optional[Set[str]] = None,
) -> Tuple[Dict[str, Any], List[str]]:
    """Load a JSON sidecar from disk, scrub it, and return the result.

    Does NOT write the result — the caller decides where to save it.

    Returns:
        Tuple of (scrubbed_data, removed_fields).
    """
    with open(json_path, "r", encoding="utf-8") as fh:
        data = json.load(fh)
    return scrub_sensitive_json_fields(data, modality=modality, extra_fields=extra_fields)


# ---------------------------------------------------------------------------
# Modality detection from path
# ---------------------------------------------------------------------------

def detect_modality_from_path(path: Path) -> Optional[str]:
    """Infer BIDS modality folder from a file path.

    Walks the path components looking for a known modality folder.
    Returns the modality string ('anat', 'func', 'dwi', 'fmap') or None.
    """
    for part in path.parts:
        if part in MRI_MODALITIES:
            return part
    return None


def is_mri_json_sidecar(path: Path) -> bool:
    """Return True when *path* is a JSON sidecar inside an MRI modality folder."""
    if path.suffix.lower() != ".json":
        return False
    return detect_modality_from_path(path) in MRI_MODALITIES


# ---------------------------------------------------------------------------
# Defacing detection (filename heuristic + optional nibabel header check)
# ---------------------------------------------------------------------------

_DEFACED_FILENAME_RE = re.compile(
    r"(_desc-defaced|_defaced|_skullstripped|_brain)(?=_|\.)",
    re.IGNORECASE,
)


def _has_defaced_filename(nifti_path: Path) -> bool:
    """Return True when the NIfTI filename contains a common defacing marker."""
    return bool(_DEFACED_FILENAME_RE.search(nifti_path.stem))


def _nibabel_defacing_heuristic(nifti_path: Path) -> Optional[bool]:
    """
    Use nibabel to check whether the NIfTI header suggests defacing.

    This is a *very coarse* heuristic: defaced images typically have a
    high proportion of zero-valued voxels in the frontal region.  We check
    whether the 'descrip' field in the header contains the word 'defaced'
    or 'skull' as set by tools like pydeface / fsl_deface.

    Returns:
        True   — header carries a defacing marker
        False  — header present but no marker found
        None   — nibabel not available or file unreadable
    """
    try:
        import nibabel as nib  # type: ignore
        img = nib.load(str(nifti_path))
        descrip = ""
        try:
            descrip_bytes = img.header["descrip"]  # type: ignore[index]
            if isinstance(descrip_bytes, (bytes, bytearray)):
                descrip = descrip_bytes.decode("utf-8", errors="ignore")
            else:
                descrip = str(descrip_bytes)
        except Exception:
            pass
        lower_desc = descrip.lower()
        return "deface" in lower_desc or "skull" in lower_desc or "brain" in lower_desc
    except Exception:
        return None


def is_anatomical_defaced(
    json_sidecar: Path,
    check_nibabel: bool = True,
) -> Dict[str, Any]:
    """Determine whether an anatomical scan appears to be defaced.

    Checks (in order):
      1. Whether a sibling NIfTI file (.nii or .nii.gz) has a defacing
         marker in its filename.
      2. If nibabel is available, inspects the NIfTI header description.

    Returns a dict with:
      ``status`` — one of: ``"defaced"``, ``"not_defaced"``, ``"unknown"``
      ``reason`` — human-readable explanation
      ``nifti_found`` — whether a sibling NIfTI was located
    """
    # Find a sibling NIfTI file (same stem, ignoring the .json extension)
    stem = json_sidecar.stem  # e.g. "sub-01_T1w"
    parent = json_sidecar.parent
    nifti: Optional[Path] = None
    for candidate in [parent / f"{stem}.nii.gz", parent / f"{stem}.nii"]:
        if candidate.exists():
            nifti = candidate
            break

    if nifti is None:
        return {
            "status": "unknown",
            "reason": "No sibling NIfTI file found",
            "nifti_found": False,
        }

    # 1. Filename heuristic
    if _has_defaced_filename(nifti):
        return {
            "status": "defaced",
            "reason": f"Defacing marker in filename: {nifti.name}",
            "nifti_found": True,
        }

    # 2. nibabel header heuristic
    if check_nibabel:
        header_result = _nibabel_defacing_heuristic(nifti)
        if header_result is True:
            return {
                "status": "defaced",
                "reason": "NIfTI header describes defaced / skull-stripped image",
                "nifti_found": True,
            }
        if header_result is False:
            return {
                "status": "not_defaced",
                "reason": "No defacing marker found in filename or NIfTI header",
                "nifti_found": True,
            }

    return {
        "status": "unknown",
        "reason": "Cannot determine defacing status (nibabel unavailable or unreadable)",
        "nifti_found": True,
    }


# ---------------------------------------------------------------------------
# Batch helpers used by the export pipeline
# ---------------------------------------------------------------------------

def scan_mri_jsons(project_path: Path) -> List[Path]:
    """Return all MRI sidecar JSON paths under *project_path*."""
    results: List[Path] = []
    for sub_dir in project_path.iterdir():
        if not (sub_dir.is_dir() and sub_dir.name.startswith("sub-")):
            continue
        for json_file in sub_dir.rglob("*.json"):
            if is_mri_json_sidecar(json_file):
                results.append(json_file)
    return results


def build_defacing_report(project_path: Path) -> List[Dict[str, Any]]:
    """
    Scan all anatomical JSON sidecars in *project_path* and report defacing status.

    Returns a list of dicts, one per anat JSON, with keys:
      ``file``    — path relative to project_path
      ``status``  — "defaced" / "not_defaced" / "unknown"
      ``reason``  — human-readable detail
    """
    report: List[Dict[str, Any]] = []
    for sub_dir in project_path.iterdir():
        if not (sub_dir.is_dir() and sub_dir.name.startswith("sub-")):
            continue
        for json_file in sub_dir.rglob("*.json"):
            if detect_modality_from_path(json_file) != "anat":
                continue
            # Only check files whose stem suggests an anatomical suffix
            stem_upper = json_file.stem.upper()
            if not any(suf.upper() in stem_upper for suf in ANAT_SUFFIXES):
                continue
            result = is_anatomical_defaced(json_file)
            result["file"] = str(json_file.relative_to(project_path))
            report.append(result)
    return report
