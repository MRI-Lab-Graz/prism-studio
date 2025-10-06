"""
Core validation logic for psycho-validator
"""

import os
import re
import json
from jsonschema import validate, ValidationError

# Modality patterns
MODALITY_PATTERNS = {
    "movie": r".+\.mp4$",
    "image": r".+\.(png|jpg|jpeg|tiff)$",
    "eyetracking": r".+\.(tsv|edf)$",
    "eeg": r".+\.(edf|bdf|eeg)$",
    "audio": r".+\.(wav|mp3)$",
    "behavior": r".+\.tsv$",
    "physiological": r".+\.(edf|bdf|txt|csv)$",
    # MRI submodalities
    "anat": r".+_(T1w|T2w|T2star|FLAIR|PD|PDw|T1map|T2map)\.nii(\.gz)?$",
    "func": r".+_bold\.nii(\.gz)?$",
    "fmap": r".+_(magnitude1|magnitude2|phasediff|fieldmap|epi)\.nii(\.gz)?$",
    "dwi":  r".+_dwi\.nii(\.gz)?$"
}

# BIDS naming patterns
BIDS_REGEX = re.compile(
    r"^sub-[a-zA-Z0-9]+"
    r"(_ses-[a-zA-Z0-9]+)?"
    r"(_task-[a-zA-Z0-9]+)?"
    r"(_run-[0-9]+)?"
)

MRI_SUFFIX_REGEX = re.compile(
    r"_(T1w|T2w|T2star|FLAIR|PD|PDw|T1map|T2map|bold|dwi|magnitude1|magnitude2|phasediff|fieldmap|epi)$"
)

# File extensions that need special handling
COMPOUND_EXTS = (".nii.gz", ".tsv.gz", ".edf.gz")


def split_compound_ext(filename):
    """Return (stem, ext) and handle compound extensions like .nii.gz."""
    if any(filename.endswith(ext) for ext in COMPOUND_EXTS):
        for ext in COMPOUND_EXTS:
            if filename.endswith(ext):
                stem = filename[: -len(ext)]
                return stem, ext
    base, ext = os.path.splitext(filename)
    return base, ext


def derive_sidecar_path(file_path):
    """Derive the JSON sidecar path for a data file."""
    dirname = os.path.dirname(file_path)
    fname = os.path.basename(file_path)
    stem, _ext = split_compound_ext(fname)
    return os.path.join(dirname, f"{stem}.json")


class DatasetValidator:
    """Main dataset validation class"""
    
    def __init__(self, schemas=None):
        self.schemas = schemas or {}
        
    def validate_filename(self, filename, modality):
        """Validate filename against BIDS conventions and modality patterns"""
        issues = []
        
        base, ext = split_compound_ext(filename)
        pattern = re.compile(MODALITY_PATTERNS.get(modality, r".*"))
        
        # Check BIDS naming
        if not BIDS_REGEX.match(base):
            issues.append(("ERROR", f"Invalid BIDS filename format: {filename}"))
            
        # Check modality pattern
        if not pattern.match(filename):
            issues.append(("WARNING", f"Filename doesn't match expected pattern for {modality}: {filename}"))
            
        # Check MRI-specific patterns
        if modality in ("anat", "func", "fmap", "dwi"):
            if ext in (".nii", ".nii.gz") and not MRI_SUFFIX_REGEX.search(base):
                issues.append(("ERROR", f"Invalid MRI suffix for {modality}: {filename}"))
                
        return issues
    
    def validate_sidecar(self, file_path, modality, root_dir):
        """Validate JSON sidecar against schema"""
        sidecar_path = derive_sidecar_path(file_path)
        issues = []
        
        if not os.path.exists(sidecar_path):
            return [("ERROR", f"Missing sidecar for {file_path}")]
            
        try:
            with open(sidecar_path) as f:
                sidecar_data = json.load(f)
                
            # Validate against schema if available
            schema = self.schemas.get(modality)
            if schema:
                validate(instance=sidecar_data, schema=schema)
                
        except ValidationError as e:
            issues.append(("ERROR", f"{sidecar_path} schema error: {e.message}"))
        except json.JSONDecodeError:
            issues.append(("ERROR", f"{sidecar_path} is not valid JSON"))
        except Exception as e:
            issues.append(("ERROR", f"Error processing {sidecar_path}: {e}"))
            
        return issues