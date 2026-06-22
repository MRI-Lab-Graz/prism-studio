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
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

from src.datalad_execution import (
    DATALAD_DOCS_URL,
    DATALAD_INSTALL_HINT,
    is_datalad_dataset,
    parse_json_from_output,
    resolve_datalad_executable,
    run_datalad_get_paths,
    run_datalad_run,
)

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
    "Manufacturer",
    "ManufacturersModelName",
    "SoftwareVersions",
    "SoftwareVersion",
    "ApplicationName",
    "ApplicationVersion",
    "ImplementationVersionName",
    "SourceApplicationEntityTitle",
    "BidsGuess",
    # Operator / personnel
    "OperatorsName",
    "ReferringPhysicianName",
    "PerformingPhysicianName",
    "PerformingPhysiciansName",
    "RequestingPhysician",
    "PhysiciansOfRecord",
    "NameOfPhysiciansReadingStudy",
    # Dates / times (can link back to a specific session)
    "AcquisitionDateTime",
    "AcquisitionDate",
    "AcquisitionTime",
    "StudyTime",
    "SeriesDate",
    "SeriesTime",
    "StudyDate",
    "ContentDate",
    "ContentTime",
    "PatientBirthDate",
    # Study / procedure identifiers
    "StudyInstanceUID",
    "SeriesInstanceUID",
    "StudyID",
    "SeriesNumber",
    "AccessionNumber",
    "RequestedProcedureID",
    "ScheduledProcedureStepID",
    "PerformedProcedureStepID",
    "SOPInstanceUID",
    "MediaStorageSOPInstanceUID",
    "FrameOfReferenceUID",
    "SynchronizationFrameOfReferenceUID",
    # Protocol comments can reveal scanner/site specifics
    "ProtocolName",
    "ProcedureStepDescription",
    "SeriesDescription",
    "RequestAttributesSequence",
    "PerformedProcedureStepDescription",
    "ImageComments",
    "AcquisitionComments",
    "StudyComments",
}

#: Additional fields scrubbed for anatomical modalities (anat/).
ANAT_EXTRA_SCRUB: Set[str] = {
    "ImageOrientationPatientDICOM",
    "ImagePositionPatientDICOM",
    # Patient info sometimes encoded in anat sidecars
    "PatientName",
    "PatientID",
    "PatientSex",
    "PatientAge",
    "PatientWeight",
    "PatientPosition",
    "BodyPartExamined",
    "PatientOrientation",
    "SliceLocation",
    "TablePosition",
    "MagneticFieldStrength",
    "ReceiveCoilName",
    "TransmitCoilName",
    "GradientSetType",
    "MRTransmitCoilSequence",
}

#: Fields to scrub for functional (func/) and diffusion (dwi/) sidecars.
FUNC_DWI_EXTRA_SCRUB: Set[str] = {
    "ImageOrientationPatientDICOM",
    "ImagePositionPatientDICOM",
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
    "T1w",
    "T2w",
    "FLAIR",
    "T1rho",
    "T2star",
    "UNIT1",
    "angio",
    "PDw",
    "PDT2",
    "T1map",
    "T2map",
}

# Pattern-based key matching inspired by publicBIDS scrubber.
_PREFIX_SCRUB_PATTERNS: Tuple[str, ...] = (
    "private_",
    "userdefined_",
    "userdefined",
    "px_",
)
_WORD_FRAGMENT_SCRUB_PATTERNS: Tuple[str, ...] = (
    "patient",
    "subject",
    "physician",
    "operator",
)

# JSON fields that may indicate a scan is already defaced.
_DEFACING_METADATA_HINT_KEYS: Tuple[str, ...] = (
    "deidentificationmethod",
    "deidentificationmethoddescription",
    "imagecomments",
    "description",
)
_DEFACING_METADATA_HINT_VALUES: Tuple[str, ...] = (
    "deface",
    "defaced",
    "skullstrip",
    "skull-stripped",
    "face removed",
)

# Grouped scrub controls for UI/API selection mode.
SCRUB_TAG_GROUP_FIELDS: Dict[str, Set[str]] = {
    "scanner_site": {
        "DeviceSerialNumber",
        "StationName",
        "InstitutionName",
        "InstitutionAddress",
        "InstitutionalDepartmentName",
        "Manufacturer",
        "ManufacturersModelName",
        "SoftwareVersions",
        "SoftwareVersion",
        "ApplicationName",
        "ApplicationVersion",
        "ImplementationVersionName",
        "SourceApplicationEntityTitle",
        "BidsGuess",
        "MagneticFieldStrength",
        "ReceiveCoilName",
        "TransmitCoilName",
        "GradientSetType",
        "MRTransmitCoilSequence",
    },
    "timestamps": {
        "AcquisitionDateTime",
        "AcquisitionDate",
        "AcquisitionTime",
        "StudyTime",
        "SeriesDate",
        "SeriesTime",
        "StudyDate",
        "ContentDate",
        "ContentTime",
    },
    "personnel": {
        "OperatorsName",
        "ReferringPhysicianName",
        "PerformingPhysicianName",
        "PerformingPhysiciansName",
        "RequestingPhysician",
        "PhysiciansOfRecord",
        "NameOfPhysiciansReadingStudy",
    },
    "patient_subject": {
        "PatientBirthDate",
        "PatientName",
        "PatientID",
        "PatientSex",
        "PatientAge",
        "PatientWeight",
        "PatientPosition",
        "BodyPartExamined",
        "PatientOrientation",
    },
    "uids_identifiers": {
        "StudyInstanceUID",
        "SeriesInstanceUID",
        "StudyID",
        "SeriesNumber",
        "AccessionNumber",
        "RequestedProcedureID",
        "ScheduledProcedureStepID",
        "PerformedProcedureStepID",
        "SOPInstanceUID",
        "MediaStorageSOPInstanceUID",
        "FrameOfReferenceUID",
        "SynchronizationFrameOfReferenceUID",
    },
    "protocol_comments": {
        "ProtocolName",
        "ProcedureStepDescription",
        "SeriesDescription",
        "RequestAttributesSequence",
        "PerformedProcedureStepDescription",
        "ImageComments",
        "AcquisitionComments",
        "StudyComments",
    },
    "geometry": {
        "ImageOrientationPatientDICOM",
        "ImagePositionPatientDICOM",
        "SliceLocation",
        "TablePosition",
    },
    # Enables wildcard-like privacy sweep patterns (Private_*, Patient*, ...).
    "private_patterns": set(),
}

_GROUP_PREFIX_PATTERN_TRIGGERS: Set[str] = {"private_patterns"}
_GROUP_WORD_PATTERN_TRIGGERS: Set[str] = {
    "private_patterns",
    "patient_subject",
    "personnel",
}


# ---------------------------------------------------------------------------
# Core scrubbing function
# ---------------------------------------------------------------------------


def scrub_sensitive_json_fields(
    data: Dict[str, Any],
    modality: Optional[str] = None,
    extra_fields: Optional[Set[str]] = None,
    selected_groups: Optional[Set[str]] = None,
) -> Tuple[Dict[str, Any], List[str]]:
    """Remove privacy-sensitive fields from a BIDS JSON sidecar.

    Args:
        data: Parsed JSON sidecar as a dict.
        modality: BIDS modality folder name ('anat', 'func', 'dwi', 'fmap').
                  If None, only ALWAYS_SCRUB fields are removed.
        extra_fields: Any additional field names to remove on top of the
                  standard sets.
        selected_groups: Optional set of scrub tag group IDs. When provided,
                 only those groups are used (instead of full scrub-all).

    Returns:
        Tuple of (scrubbed_data, removed_fields) where removed_fields is the
        list of field names that were actually present and removed.
    """
    normalized_modality = str(modality or "").strip().lower()
    normalized_groups = {
        str(group or "").strip().lower()
        for group in (selected_groups or set())
        if str(group or "").strip()
    }

    if normalized_groups:
        to_remove: Set[str] = set()
        for group_id in normalized_groups:
            to_remove |= SCRUB_TAG_GROUP_FIELDS.get(group_id, set())
        apply_pattern_sweep = (
            (not normalized_modality or normalized_modality in MRI_MODALITIES)
            and bool(normalized_groups & _GROUP_PREFIX_PATTERN_TRIGGERS)
        )
        apply_word_pattern_sweep = (
            (not normalized_modality or normalized_modality in MRI_MODALITIES)
            and bool(normalized_groups & _GROUP_WORD_PATTERN_TRIGGERS)
        )
    else:
        to_remove = set(ALWAYS_SCRUB)
        if modality and modality in _MODALITY_EXTRA:
            to_remove |= _MODALITY_EXTRA[modality]
        apply_pattern_sweep = (
            not normalized_modality or normalized_modality in MRI_MODALITIES
        )
        apply_word_pattern_sweep = apply_pattern_sweep

    if extra_fields:
        to_remove |= extra_fields

    removed: List[str] = []
    scrubbed = dict(data)

    def _mark_removed(key: str) -> None:
        if key not in removed:
            removed.append(key)

    # Exact-key (case-insensitive) removals.
    exact_remove_lower = {field.lower() for field in to_remove}

    for key in list(scrubbed.keys()):
        key_lower = key.lower()
        should_remove = key_lower in exact_remove_lower

        # Pattern removals keep parity with publicBIDS-style privacy sweeps.
        if (
            not should_remove
            and apply_pattern_sweep
            and key_lower.startswith(_PREFIX_SCRUB_PATTERNS)
        ):
            should_remove = True
        if (
            not should_remove
            and apply_word_pattern_sweep
            and any(word in key_lower for word in _WORD_FRAGMENT_SCRUB_PATTERNS)
        ):
            should_remove = True

        if should_remove:
            del scrubbed[key]
            _mark_removed(key)

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
    return scrub_sensitive_json_fields(
        data, modality=modality, extra_fields=extra_fields
    )


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
_ACQ_ENTITY_RE = re.compile(r"_acq-([A-Za-z0-9]+)", re.IGNORECASE)


def _extract_terminal_suffix_label(filename: str) -> Optional[str]:
    """Return the terminal BIDS suffix token from a filename, or None."""
    name = str(filename or "").strip()
    if not name:
        return None

    lower_name = name.lower()
    for compound_ext in (".nii.gz", ".tsv.gz"):
        if lower_name.endswith(compound_ext):
            name = name[: -len(compound_ext)]
            break
    else:
        if "." in name:
            name = name.rsplit(".", 1)[0]

    if not name:
        return None

    suffix = name.rsplit("_", 1)[-1]
    if not suffix or "-" in suffix:
        return None
    return suffix


def _extract_acq_label(filename: str) -> Optional[str]:
    """Return the BIDS acq- label token from a filename, or None."""
    match = _ACQ_ENTITY_RE.search(str(filename or ""))
    if not match:
        return None
    value = str(match.group(1) or "").strip()
    return value or None


def _build_defacing_variant_metadata(filename: str) -> Dict[str, str]:
    """Build normalized variant metadata used for defacing selection filters."""
    suffix = _extract_terminal_suffix_label(filename)
    acq = _extract_acq_label(filename)
    suffix_norm = str(suffix or "").strip().lower()
    acq_norm = str(acq or "").strip().lower()

    key_parts: list[str] = []
    if acq_norm:
        key_parts.append(f"acq:{acq_norm}")
    if suffix_norm:
        key_parts.append(f"suffix:{suffix_norm}")
    key = "|".join(key_parts)

    if acq and suffix:
        label = f"acq-{acq} {suffix}"
    elif suffix:
        label = suffix
    elif acq:
        label = f"acq-{acq}"
    else:
        label = "unlabeled anatomical"

    return {
        "key": key,
        "label": label,
        "suffix": str(suffix or ""),
        "acq": str(acq or ""),
    }


def _normalize_selected_defacing_variants(
    selected_variants: Optional[Set[str]],
) -> Optional[Set[str]]:
    if selected_variants is None:
        return None
    return {
        str(value).strip().lower()
        for value in selected_variants
        if str(value).strip()
    }


def _matches_selected_defacing_variants(
    filename: str,
    selected_variants: Optional[Set[str]],
) -> bool:
    normalized_selected = _normalize_selected_defacing_variants(selected_variants)
    if normalized_selected is None:
        return True

    variant_key = _build_defacing_variant_metadata(filename).get("key", "").strip().lower()
    if not variant_key:
        return False
    return variant_key in normalized_selected


def collect_defacing_scan_variants(project_path: Path) -> List[Dict[str, Any]]:
    """Return available anatomical scan variants (acq/suffix combinations)."""
    variants: Dict[str, Dict[str, Any]] = {}

    for nifti_file in _iter_anatomical_nifti_files(project_path):
        metadata = _build_defacing_variant_metadata(nifti_file.name)
        key = str(metadata.get("key") or "").strip().lower()
        if not key:
            continue

        if key not in variants:
            variants[key] = {
                "key": key,
                "label": str(metadata.get("label") or ""),
                "suffix": str(metadata.get("suffix") or ""),
                "acq": str(metadata.get("acq") or ""),
                "count": 0,
            }
        variants[key]["count"] = int(variants[key].get("count", 0)) + 1

    return sorted(
        variants.values(),
        key=lambda item: (
            str(item.get("suffix") or "").lower(),
            str(item.get("acq") or "").lower(),
            str(item.get("label") or "").lower(),
        ),
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


def _json_metadata_defacing_heuristic(json_sidecar: Path) -> Optional[bool]:
    """Check JSON metadata for explicit defacing hints.

    Returns:
        True when metadata strongly suggests a defaced image, else None.
    """
    try:
        with open(json_sidecar, "r", encoding="utf-8") as fh:
            payload = json.load(fh)
    except Exception:
        return None

    if not isinstance(payload, dict):
        return None

    for key, value in payload.items():
        key_text = str(key or "").strip().lower()
        if key_text not in _DEFACING_METADATA_HINT_KEYS:
            continue
        value_text = str(value or "").strip().lower()
        if any(hint in value_text for hint in _DEFACING_METADATA_HINT_VALUES):
            return True
    return None


def _has_defacing_sidecar_artifact(nifti_path: Path) -> bool:
    """Return True when nearby files indicate defacing artifacts or outputs."""
    parent = nifti_path.parent
    name_lower = nifti_path.name.lower()
    base_name = name_lower
    if base_name.endswith(".nii.gz"):
        base_name = base_name[: -len(".nii.gz")]
    elif base_name.endswith(".nii"):
        base_name = base_name[: -len(".nii")]

    # Keep matching narrow to avoid unrelated derivatives in the same folder.
    subject_prefix = base_name.rsplit("_", 1)[0] if "_" in base_name else base_name
    for sibling in parent.iterdir():
        sibling_name = sibling.name.lower()
        if subject_prefix and not sibling_name.startswith(subject_prefix):
            continue
        if "deface" in sibling_name or "skullstrip" in sibling_name:
            return True
    return False


def _iter_anatomical_nifti_files(
    project_path: Path,
    selected_variants: Optional[Set[str]] = None,
    excluded_subjects: Optional[Set[str]] = None,
    excluded_sessions: Optional[Set[str]] = None,
) -> List[Path]:
    """Return anatomical NIfTI files under sub-*/anat/ that match known suffixes."""
    normalized_excluded_subjects = {
        str(label).strip()
        for label in (excluded_subjects or set())
        if str(label).strip()
    }
    normalized_excluded_sessions = {
        str(label).strip()
        for label in (excluded_sessions or set())
        if str(label).strip()
    }

    results: List[Path] = []
    for sub_dir in project_path.iterdir():
        if not (sub_dir.is_dir() and sub_dir.name.startswith("sub-")):
            continue
        if sub_dir.name in normalized_excluded_subjects:
            continue
        for nifti_file in sub_dir.rglob("*.nii*"):
            relative_parts = nifti_file.relative_to(project_path).parts
            if normalized_excluded_sessions and any(
                part.startswith("ses-") and part in normalized_excluded_sessions
                for part in relative_parts
            ):
                continue
            if detect_modality_from_path(nifti_file) != "anat":
                continue
            filename = nifti_file.name
            if not any(
                f"_{suffix}.nii" in filename or f"_{suffix}.nii.gz" in filename
                for suffix in ANAT_SUFFIXES
            ):
                continue
            if not _matches_selected_defacing_variants(filename, selected_variants):
                continue
            results.append(nifti_file)
    return sorted(set(results))


def has_anatomical_data(project_path: Path) -> bool:
    """Return True when the dataset has at least one anatomical NIfTI candidate."""
    return bool(_iter_anatomical_nifti_files(project_path))


def get_defacing_preflight(project_path: Path) -> Dict[str, Any]:
    """Return defacing prerequisites and dataset readiness for UI/backend checks."""
    pydeface_executable = shutil.which("pydeface") or ""
    fsl_executable = shutil.which("fsl") or ""
    bet_executable = shutil.which("bet") or ""
    fsl_available = bool(fsl_executable or bet_executable)
    has_anat = has_anatomical_data(project_path)

    can_run = bool(pydeface_executable) and fsl_available and has_anat
    missing: List[str] = []
    if not pydeface_executable:
        missing.append("pydeface")
    if not fsl_available:
        missing.append("FSL (fsl or bet)")
    if not has_anat:
        missing.append("anatomical scans")

    if can_run:
        message = "Defacing is available for this dataset."
    elif not has_anat:
        message = "No anatomical scans found in this dataset. Defacing options are hidden."
    elif not pydeface_executable:
        message = "pydeface is not available in this environment. Install pydeface and FSL before running defacing."
    else:
        message = "FSL is not available in this environment. Install/configure FSL before running defacing."

    return {
        "has_anatomical_data": has_anat,
        "available_scan_variants": collect_defacing_scan_variants(project_path),
        "pydeface_available": bool(pydeface_executable),
        "pydeface_executable": pydeface_executable,
        "fsl_available": fsl_available,
        "fsl_executable": fsl_executable or bet_executable,
        "can_run_defacing": can_run,
        "missing_requirements": missing,
        "message": message,
    }


def prepare_defacing_export_copy(
    project_path: Path,
    output_root: Path,
    *,
    selected_variants: Optional[Set[str]] = None,
    excluded_subjects: Optional[Set[str]] = None,
    excluded_sessions: Optional[Set[str]] = None,
    preserve_datalad_metadata: bool = False,
    datalad_executable: str = "",
) -> Dict[str, Any]:
    """Copy anatomical scans into an export target folder without mutating source.

    The copied layout preserves each file's project-relative path (e.g.
    ``sub-001/ses-1/anat/...``), so downstream defacing operates on a structural
    mirror of the selected anatomical scope.
    """
    source_root = Path(project_path)
    destination_root = Path(output_root)
    destination_root.mkdir(parents=True, exist_ok=True)

    target_name = f"{source_root.name}_defacing_export"
    target_path = destination_root / target_name
    suffix = 2
    while target_path.exists():
        target_path = destination_root / f"{target_name}_{suffix}"
        suffix += 1

    if preserve_datalad_metadata:
        if not is_datalad_dataset(source_root):
            return {
                "success": False,
                "error": (
                    "DataLad-preserving defacing copy requested, but source project "
                    "is not a DataLad dataset."
                ),
                "target_path": str(target_path),
                "copied_nifti_files": 0,
                "copied_sidecars": 0,
            }

        resolved_datalad = str(datalad_executable or resolve_datalad_executable()).strip()
        if not resolved_datalad:
            return {
                "success": False,
                "error": (
                    "DataLad-preserving defacing copy requires datalad. "
                    f"{DATALAD_INSTALL_HINT}. Learn more: {DATALAD_DOCS_URL}"
                ),
                "target_path": str(target_path),
                "copied_nifti_files": 0,
                "copied_sidecars": 0,
            }

        clone_command = [resolved_datalad, "clone", str(source_root), str(target_path)]
        try:
            clone_process = subprocess.run(
                clone_command,
                capture_output=True,
                text=True,
                timeout=900,
                check=False,
            )
        except subprocess.TimeoutExpired:
            return {
                "success": False,
                "error": "DataLad clone timed out while preparing export defacing copy.",
                "target_path": str(target_path),
                "copied_nifti_files": 0,
                "copied_sidecars": 0,
                "datalad_clone": {
                    "command": " ".join(clone_command),
                },
            }
        except Exception as exc:
            return {
                "success": False,
                "error": f"DataLad clone failed while preparing export defacing copy: {exc}",
                "target_path": str(target_path),
                "copied_nifti_files": 0,
                "copied_sidecars": 0,
                "datalad_clone": {
                    "command": " ".join(clone_command),
                },
            }

        if clone_process.returncode != 0:
            detail = (clone_process.stderr or clone_process.stdout or "").strip()
            try:
                shutil.rmtree(target_path, ignore_errors=True)
            except Exception:
                pass
            return {
                "success": False,
                "error": (
                    "DataLad clone failed while preparing export defacing copy: "
                    f"{detail or 'Unknown DataLad error.'}"
                ),
                "target_path": str(target_path),
                "copied_nifti_files": 0,
                "copied_sidecars": 0,
                "datalad_clone": {
                    "command": " ".join(clone_command),
                },
            }

        selected_nifti_files = _iter_anatomical_nifti_files(
            target_path,
            selected_variants=selected_variants,
            excluded_subjects=excluded_subjects,
            excluded_sessions=excluded_sessions,
        )
        if not selected_nifti_files:
            try:
                shutil.rmtree(target_path, ignore_errors=True)
            except Exception:
                pass
            return {
                "success": False,
                "error": "No anatomical scans matched the selected export defacing scope.",
                "target_path": str(target_path),
                "copied_nifti_files": 0,
                "copied_sidecars": 0,
                "datalad_clone": {
                    "command": " ".join(clone_command),
                },
            }

        copied_sidecars = 0
        for nifti_file in selected_nifti_files:
            sidecar_path: Optional[Path] = None
            if nifti_file.name.endswith(".nii.gz"):
                candidate = nifti_file.with_name(nifti_file.name[: -len(".nii.gz")] + ".json")
                if candidate.exists():
                    sidecar_path = candidate
            elif nifti_file.suffix.lower() == ".nii":
                candidate = nifti_file.with_suffix(".json")
                if candidate.exists():
                    sidecar_path = candidate
            if sidecar_path is not None:
                copied_sidecars += 1

        return {
            "success": True,
            "target_path": str(target_path),
            "copied_nifti_files": len(selected_nifti_files),
            "copied_sidecars": copied_sidecars,
            "datalad_clone": {
                "command": " ".join(clone_command),
                "success": True,
            },
        }

    selected_nifti_files = _iter_anatomical_nifti_files(
        source_root,
        selected_variants=selected_variants,
        excluded_subjects=excluded_subjects,
        excluded_sessions=excluded_sessions,
    )
    if not selected_nifti_files:
        return {
            "success": False,
            "error": "No anatomical scans matched the selected export defacing scope.",
            "target_path": str(target_path),
            "copied_nifti_files": 0,
            "copied_sidecars": 0,
        }

    copied_nifti_files = 0
    copied_sidecars = 0
    seen_sidecars: Set[str] = set()

    for nifti_file in selected_nifti_files:
        try:
            rel_nifti = nifti_file.relative_to(source_root)
        except ValueError:
            continue

        destination_nifti = target_path / rel_nifti
        destination_nifti.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(nifti_file, destination_nifti)
        copied_nifti_files += 1

        sidecar_path = None
        if nifti_file.name.endswith(".nii.gz"):
            candidate = nifti_file.with_name(nifti_file.name[: -len(".nii.gz")] + ".json")
            if candidate.exists():
                sidecar_path = candidate
        elif nifti_file.suffix.lower() == ".nii":
            candidate = nifti_file.with_suffix(".json")
            if candidate.exists():
                sidecar_path = candidate

        if sidecar_path is None:
            continue

        try:
            rel_sidecar = sidecar_path.relative_to(source_root)
        except ValueError:
            continue

        rel_sidecar_text = rel_sidecar.as_posix()
        if rel_sidecar_text in seen_sidecars:
            continue

        seen_sidecars.add(rel_sidecar_text)
        destination_sidecar = target_path / rel_sidecar
        destination_sidecar.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(sidecar_path, destination_sidecar)
        copied_sidecars += 1

    if copied_nifti_files == 0:
        try:
            shutil.rmtree(target_path, ignore_errors=True)
        except Exception:
            pass
        return {
            "success": False,
            "error": "No anatomical scans could be copied to export target.",
            "target_path": str(target_path),
            "copied_nifti_files": 0,
            "copied_sidecars": 0,
        }

    return {
        "success": True,
        "target_path": str(target_path),
        "copied_nifti_files": copied_nifti_files,
        "copied_sidecars": copied_sidecars,
    }


def deface_anatomical_scans(
    project_path: Path,
    *,
    force: bool = False,
    timeout_seconds: int = 300,
    selected_variants: Optional[Set[str]] = None,
    excluded_subjects: Optional[Set[str]] = None,
    excluded_sessions: Optional[Set[str]] = None,
) -> Dict[str, Any]:
    """Run pydeface in-place on anatomical scans and return an operation summary."""
    project_root = Path(project_path)
    datalad_tracked = is_datalad_dataset(project_root)
    datalad_executable = resolve_datalad_executable() if datalad_tracked else ""
    datalad_info: Dict[str, Any] = {
        "tracked": datalad_tracked,
        "available": bool(datalad_executable),
        "used_run": False,
        "run_count": 0,
        "run_failures": 0,
        "get": None,
        "groups": [],
        "message": "",
    }

    anatomical_files = _iter_anatomical_nifti_files(
        project_path,
        selected_variants=selected_variants,
        excluded_subjects=excluded_subjects,
        excluded_sessions=excluded_sessions,
    )
    if not anatomical_files:
        if selected_variants is None:
            empty_message = "No anatomical scans found to deface."
        else:
            empty_message = (
                "No anatomical scans matched the selected defacing filters."
            )
        return {
            "success": True,
            "message": empty_message,
            "counts": {
                "total": 0,
                "already_defaced": 0,
                "defaced": 0,
                "failed": 0,
                "skipped": 0,
            },
            "items": [],
            "datalad": datalad_info,
        }

    preflight = get_defacing_preflight(project_path)
    pydeface_executable = str(preflight.get("pydeface_executable") or "")
    if not preflight.get("pydeface_available"):
        return {
            "success": False,
            "error": str(preflight.get("message") or "pydeface is unavailable."),
            "counts": {
                "total": 0,
                "already_defaced": 0,
                "defaced": 0,
                "failed": 0,
                "skipped": 0,
            },
            "items": [],
            "datalad": datalad_info,
        }

    if not preflight.get("fsl_available"):
        return {
            "success": False,
            "error": str(
                preflight.get("message")
                or "FSL is not available in this environment."
            ),
            "counts": {
                "total": 0,
                "already_defaced": 0,
                "defaced": 0,
                "failed": 0,
                "skipped": 0,
            },
            "items": [],
            "datalad": datalad_info,
        }

    if datalad_tracked and not datalad_executable:
        datalad_info["message"] = (
            "Project is tracked by DataLad, but datalad is not available. "
            f"{DATALAD_INSTALL_HINT}. Learn more: {DATALAD_DOCS_URL}"
        )
        return {
            "success": False,
            "error": str(datalad_info["message"]),
            "counts": {
                "total": 0,
                "already_defaced": 0,
                "defaced": 0,
                "failed": 0,
                "skipped": 0,
            },
            "items": [],
            "datalad": datalad_info,
        }
    elif datalad_tracked and datalad_executable:
        datalad_info["message"] = (
            "DataLad run mode is enabled for defacing with one run commit per subject."
        )

    counts = {
        "total": len(anatomical_files),
        "already_defaced": 0,
        "defaced": 0,
        "failed": 0,
        "skipped": 0,
    }
    items: List[Dict[str, Any]] = []

    files_to_process: list[Path] = []
    for nifti_file in anatomical_files:
        relative_nifti = nifti_file.relative_to(project_root).as_posix()
        sidecar_json = None
        if nifti_file.name.endswith(".nii.gz"):
            sidecar_candidate = nifti_file.with_name(
                nifti_file.name[: -len(".nii.gz")] + ".json"
            )
            if sidecar_candidate.exists():
                sidecar_json = sidecar_candidate
        elif nifti_file.suffix.lower() == ".nii":
            sidecar_candidate = nifti_file.with_suffix(".json")
            if sidecar_candidate.exists():
                sidecar_json = sidecar_candidate

        if sidecar_json is not None and not force:
            defacing_state = is_anatomical_defaced(sidecar_json, check_nibabel=True)
            if defacing_state.get("status") == "defaced":
                counts["already_defaced"] += 1
                items.append(
                    {
                        "file": relative_nifti,
                        "status": "already_defaced",
                        "message": str(defacing_state.get("reason") or ""),
                    }
                )
                continue
        files_to_process.append(nifti_file)

    if datalad_tracked and datalad_executable:
        grouped: Dict[str, list[Path]] = {}
        for nifti_file in files_to_process:
            rel_path = nifti_file.relative_to(project_root).as_posix()
            subject_label = "dataset-root"
            for part in Path(rel_path).parts:
                if part.startswith("sub-"):
                    subject_label = part
                    break
            grouped.setdefault(subject_label, []).append(nifti_file)

        for subject_label, subject_files in sorted(grouped.items(), key=lambda item: item[0]):
            rel_targets = sorted(
                [path.relative_to(project_root).as_posix() for path in subject_files]
            )
            get_result = run_datalad_get_paths(
                project_root,
                paths=rel_targets,
                datalad_executable=datalad_executable,
                timeout_seconds=max(1, int(timeout_seconds)) * 2,
                recursive=False,
                no_data=False,
            )
            group_info: Dict[str, Any] = {
                "subject": subject_label,
                "get": {
                    "attempted": bool(get_result.get("attempted")),
                    "success": bool(get_result.get("success")),
                    "message": str(get_result.get("message") or ""),
                    "command": str(get_result.get("command") or ""),
                },
                "run": None,
            }
            datalad_info["groups"].append(group_info)

            if not get_result.get("success"):
                datalad_info["run_failures"] = int(datalad_info.get("run_failures") or 0) + 1
                counts["failed"] += len(rel_targets)
                for rel_target in rel_targets:
                    items.append(
                        {
                            "file": rel_target,
                            "status": "failed",
                            "message": str(
                                get_result.get("message")
                                or "DataLad get failed before defacing run."
                            ),
                        }
                    )
                continue

            manifest = {"files": rel_targets}
            fd, manifest_path = tempfile.mkstemp(
                prefix="prism_deface_manifest_", suffix=".json"
            )
            script_fd, script_path = tempfile.mkstemp(
                prefix="prism_deface_runner_", suffix=".py"
            )
            try:
                with open(fd, "w", encoding="utf-8", closefd=True) as handle:
                    json.dump(manifest, handle)
                script_content = """import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

manifest = json.loads(Path(sys.argv[1]).read_text(encoding=\"utf-8\"))
project_root = Path(sys.argv[2])
pydeface_exe = sys.argv[3]
timeout = max(1, int(sys.argv[4]))

counts = {\"defaced\": 0, \"failed\": 0}
items = []

for rel in manifest.get(\"files\", []):
    file_path = project_root / rel
    backup = None
    try:
        with tempfile.NamedTemporaryFile(prefix=\"prism_deface_\", suffix=file_path.suffix, delete=False) as tmp:
            backup = Path(tmp.name)
        shutil.copy2(file_path, backup)
        proc = subprocess.run(
            [pydeface_exe, rel, \"--outfile\", rel, \"--force\"],
            cwd=str(project_root),
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
        if proc.returncode == 0:
            counts[\"defaced\"] += 1
            items.append({\"file\": rel, \"status\": \"defaced\", \"message\": \"Defacing completed\"})
        else:
            counts[\"failed\"] += 1
            try:
                shutil.copy2(backup, file_path)
            except Exception:
                pass
            msg = (proc.stderr or proc.stdout or \"pydeface failed\").strip()
            items.append({\"file\": rel, \"status\": \"failed\", \"message\": msg})
    except subprocess.TimeoutExpired:
        counts[\"failed\"] += 1
        try:
            if backup is not None:
                shutil.copy2(backup, file_path)
        except Exception:
            pass
        items.append({\"file\": rel, \"status\": \"failed\", \"message\": \"Defacing timed out\"})
    except Exception as exc:
        counts[\"failed\"] += 1
        try:
            if backup is not None:
                shutil.copy2(backup, file_path)
        except Exception:
            pass
        items.append({\"file\": rel, \"status\": \"failed\", \"message\": str(exc)})
    finally:
        if backup is not None:
            try:
                backup.unlink(missing_ok=True)
            except Exception:
                pass

print(json.dumps({\"counts\": counts, \"items\": items}, ensure_ascii=False))
"""
                with open(script_fd, "w", encoding="utf-8", closefd=True) as handle:
                    handle.write(script_content)

                run_message = (
                    f"PRISM: Deface anatomical scans for {subject_label}"
                    if subject_label != "dataset-root"
                    else "PRISM: Deface anatomical scans"
                )
                datalad_run_result = run_datalad_run(
                    project_root,
                    message=run_message,
                    command=[
                        sys.executable,
                        script_path,
                        manifest_path,
                        str(project_root),
                        pydeface_executable,
                        str(max(1, int(timeout_seconds))),
                    ],
                    datalad_executable=datalad_executable,
                    timeout_seconds=max(1, int(timeout_seconds)) * 4,
                )
            finally:
                Path(manifest_path).unlink(missing_ok=True)
                Path(script_path).unlink(missing_ok=True)

            datalad_info["used_run"] = True
            datalad_info["run_count"] = int(datalad_info.get("run_count") or 0) + 1
            group_info["run"] = {
                "attempted": bool(datalad_run_result.get("attempted")),
                "success": bool(datalad_run_result.get("success")),
                "message": str(datalad_run_result.get("message") or ""),
                "command": str(datalad_run_result.get("command") or ""),
            }

            if not datalad_run_result.get("success"):
                datalad_info["run_failures"] = int(datalad_info.get("run_failures") or 0) + 1
                counts["failed"] += len(rel_targets)
                error_message = str(datalad_run_result.get("message") or "pydeface failed")
                for rel_target in rel_targets:
                    items.append(
                        {
                            "file": rel_target,
                            "status": "failed",
                            "message": error_message,
                        }
                    )
                continue

            parsed = parse_json_from_output(str(datalad_run_result.get("stdout") or ""))
            if not isinstance(parsed, dict):
                counts["failed"] += len(rel_targets)
                for rel_target in rel_targets:
                    items.append(
                        {
                            "file": rel_target,
                            "status": "failed",
                            "message": "Defacing run output could not be parsed.",
                        }
                    )
                continue

            counts_obj = parsed.get("counts")
            parsed_counts = counts_obj if isinstance(counts_obj, dict) else {}
            counts["defaced"] += int(parsed_counts.get("defaced") or 0)
            counts["failed"] += int(parsed_counts.get("failed") or 0)
            items_obj = parsed.get("items")
            parsed_items = items_obj if isinstance(items_obj, list) else []
            for entry in parsed_items:
                if not isinstance(entry, dict):
                    continue
                items.append(
                    {
                        "file": str(entry.get("file") or ""),
                        "status": str(entry.get("status") or "failed"),
                        "message": str(entry.get("message") or ""),
                    }
                )
    else:
        for nifti_file in files_to_process:
            relative_nifti = nifti_file.relative_to(project_root).as_posix()
            item_result: Dict[str, Any] = {
                "file": relative_nifti,
                "status": "",
                "message": "",
            }

            backup_file: Optional[Path] = None
            try:
                with tempfile.NamedTemporaryFile(
                    prefix="prism_deface_",
                    suffix=nifti_file.suffix,
                    delete=False,
                ) as temp_file:
                    backup_file = Path(temp_file.name)
                shutil.copy2(nifti_file, backup_file)
            except Exception as exc:
                counts["failed"] += 1
                item_result["status"] = "failed"
                item_result["message"] = f"Could not create backup: {exc}"
                items.append(item_result)
                continue

            try:
                pydeface_command = [
                    pydeface_executable,
                    str(nifti_file),
                    "--outfile",
                    str(nifti_file),
                    "--force",
                ]

                process = subprocess.run(
                    pydeface_command,
                    capture_output=True,
                    text=True,
                    timeout=max(1, int(timeout_seconds)),
                    check=False,
                )
                run_success = process.returncode == 0
                run_error_message = (
                    (process.stderr or process.stdout or "pydeface failed").strip()
                    if not run_success
                    else ""
                )

                if run_success:
                    counts["defaced"] += 1
                    item_result["status"] = "defaced"
                    item_result["message"] = "Defacing completed"
                else:
                    counts["failed"] += 1
                    item_result["status"] = "failed"
                    item_result["message"] = run_error_message or "pydeface failed"
                    try:
                        if backup_file is not None:
                            shutil.copy2(backup_file, nifti_file)
                    except Exception:
                        pass
            except subprocess.TimeoutExpired:
                counts["failed"] += 1
                item_result["status"] = "failed"
                item_result["message"] = "Defacing timed out"
                try:
                    if backup_file is not None:
                        shutil.copy2(backup_file, nifti_file)
                except Exception:
                    pass
            except Exception as exc:
                counts["failed"] += 1
                item_result["status"] = "failed"
                item_result["message"] = str(exc)
                try:
                    if backup_file is not None:
                        shutil.copy2(backup_file, nifti_file)
                except Exception:
                    pass
            finally:
                if backup_file is not None:
                    try:
                        backup_file.unlink(missing_ok=True)
                    except Exception:
                        pass

            items.append(item_result)

    success = counts["failed"] == 0
    message = (
        "Defacing completed successfully."
        if success
        else "Defacing finished with errors. Review failed files."
    )

    return {
        "success": success,
        "message": message,
        "counts": counts,
        "items": items,
        "datalad": datalad_info,
    }


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

    # 2. JSON metadata hints (for tools that preserve BIDS names but annotate JSON).
    metadata_hint = _json_metadata_defacing_heuristic(json_sidecar)
    if metadata_hint is True:
        return {
            "status": "defaced",
            "reason": "JSON metadata indicates defacing/skull-stripping",
            "nifti_found": True,
        }

    # 3. Nearby defacing artifacts (mask or helper outputs).
    if _has_defacing_sidecar_artifact(nifti):
        return {
            "status": "defaced",
            "reason": "Found nearby defacing artifact/output in same folder",
            "nifti_found": True,
        }

    # 4. nibabel header heuristic
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


def build_defacing_report(
    project_path: Path,
    selected_variants: Optional[Set[str]] = None,
    excluded_subjects: Optional[Set[str]] = None,
    excluded_sessions: Optional[Set[str]] = None,
) -> List[Dict[str, Any]]:
    """
    Scan all anatomical JSON sidecars in *project_path* and report defacing status.

    Returns a list of dicts, one per anat JSON, with keys:
      ``file``    — path relative to project_path
      ``status``  — "defaced" / "not_defaced" / "unknown"
      ``reason``  — human-readable detail
    """
    report: List[Dict[str, Any]] = []
    normalized_excluded_subjects = {
        str(label).strip()
        for label in (excluded_subjects or set())
        if str(label).strip()
    }
    normalized_excluded_sessions = {
        str(label).strip()
        for label in (excluded_sessions or set())
        if str(label).strip()
    }

    for sub_dir in project_path.iterdir():
        if not (sub_dir.is_dir() and sub_dir.name.startswith("sub-")):
            continue
        if sub_dir.name in normalized_excluded_subjects:
            continue
        for json_file in sub_dir.rglob("*.json"):
            relative_parts = json_file.relative_to(project_path).parts
            if normalized_excluded_sessions and any(
                part.startswith("ses-") and part in normalized_excluded_sessions
                for part in relative_parts
            ):
                continue
            if detect_modality_from_path(json_file) != "anat":
                continue
            # Only check files whose stem suggests an anatomical suffix
            stem_upper = json_file.stem.upper()
            if not any(suf.upper() in stem_upper for suf in ANAT_SUFFIXES):
                continue
            if not _matches_selected_defacing_variants(
                json_file.name,
                selected_variants,
            ):
                continue
            result = is_anatomical_defaced(json_file)
            result["file"] = json_file.relative_to(project_path).as_posix()
            report.append(result)
    return report
