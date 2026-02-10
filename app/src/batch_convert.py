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
import re
import shutil
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

# ANSI color codes for terminal output
class Colors:
    """ANSI color codes for terminal output."""
    RESET = '\033[0m'
    RED = '\033[91m'        # Error (bright red)
    YELLOW = '\033[93m'      # Warning (bright yellow)
    GREEN = '\033[92m'       # Success (bright green)
    BLUE = '\033[94m'        # Info (bright blue)
    CYAN = '\033[96m'        # Data preview (bright cyan)
    
    @staticmethod
    def colorize(message: str, level: str) -> str:
        """Add color codes to a message based on log level."""
        if level == "error":
            return f"{Colors.RED}{message}{Colors.RESET}"
        elif level == "warning":
            return f"{Colors.YELLOW}{message}{Colors.RESET}"
        elif level == "success":
            return f"{Colors.GREEN}{message}{Colors.RESET}"
        elif level == "info":
            return f"{Colors.BLUE}{message}{Colors.RESET}"
        elif level == "preview":
            return f"{Colors.CYAN}{message}{Colors.RESET}"
        return message

# Pattern for BIDS-like filenames: sub-XXX_ses-YYY_task-ZZZ[_extra].<ext>
BIDS_FILENAME_PATTERN = re.compile(
    r"^(?P<sub>sub-[a-zA-Z0-9]+)"
    r"(?:_(?P<ses>ses-[a-zA-Z0-9]+))?"
    r"_(?P<task>task-[a-zA-Z0-9]+)"
    r"(?P<extra>(?:_[a-zA-Z0-9]+(?:-[a-zA-Z0-9]+)?)*)"
    r"\.(?P<ext>[a-zA-Z0-9]+(?:\.gz)?)$",
    re.IGNORECASE,
)

# Modality-specific patterns with required suffixes
EYETRACKING_FILENAME_PATTERN = re.compile(
    r"^(?P<sub>sub-[a-zA-Z0-9]+)"
    r"(?:_(?P<ses>ses-[a-zA-Z0-9]+))?"
    r"_(?P<task>task-[a-zA-Z0-9]+)"
    r"(?P<extra>(?:_[a-zA-Z0-9]+(?:-[a-zA-Z0-9]+)?)*)"
    r"_(?P<suffix>eyetrack|eyetracking|events)"
    r"\.(?P<ext>[a-zA-Z0-9]+(?:\.gz)?)$",
    re.IGNORECASE,
)

PHYSIO_FILENAME_PATTERN = re.compile(
    r"^(?P<sub>sub-[a-zA-Z0-9]+)"
    r"(?:_(?P<ses>ses-[a-zA-Z0-9]+))?"
    r"_(?P<task>task-[a-zA-Z0-9]+)"
    r"(?P<extra>(?:_[a-zA-Z0-9]+(?:-[a-zA-Z0-9]+)?)*)"
    r"_physio"
    r"\.(?P<ext>[a-zA-Z0-9]+(?:\.gz)?)$",
    re.IGNORECASE,
)

# Modality detection by extension
PHYSIO_EXTENSIONS = {".raw", ".vpd", ".edf"}
EYETRACKING_EXTENSIONS = {".edf", ".tsv", ".tsv.gz", ".asc"}
GENERIC_EXTENSIONS = {
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
            "time": {"Description": "Time in seconds", "Unit": "s"},
        },
    }

    if "Channels" in extra_meta:
        for ch in extra_meta["Channels"]:
            sidecar["Columns"][ch] = {"Description": f"Channel {ch}"}

    with open(output_json, "w", encoding="utf-8") as f:
        json.dump(sidecar, f, indent=2, ensure_ascii=False)


def _parse_tsv_columns(source_path: Path) -> dict:
    """Parse TSV file to extract column information.
    
    Returns a dict with:
        - 'columns': list of column names
        - 'column_count': number of columns
        - 'row_count': number of data rows (excluding header)
    """
    try:
        with open(source_path, 'r', encoding='utf-8', errors='ignore') as f:
            header_line = f.readline().strip()
            columns = header_line.split('\t')
            
            # Count rows
            row_count = sum(1 for _ in f)
        
        return {
            'columns': columns,
            'column_count': len(columns),
            'row_count': row_count,
        }
    except Exception:
        return {'columns': [], 'column_count': 0, 'row_count': 0}


def _extract_eyetracking_metadata_from_tsv(tsv_path: Path) -> dict:
    """Extract metadata from TSV file, particularly from SAMPLE_MESSAGE column.
    
    For SR Research EyeLink exports, metadata is embedded in the SAMPLE_MESSAGE column.
    Example: 'RECCFG CR 1000 2 1 2 1 R;ELCLCFG BTABLER;GAZE_COORDS 0.00 0.00 1919.00 1079.00...'
    """
    metadata = {}
    
    try:
        with open(tsv_path, 'r', encoding='utf-8', errors='ignore') as f:
            header_line = f.readline().strip()
            columns = header_line.split('\t')
            
            # Try to find SAMPLE_MESSAGE column
            if 'SAMPLE_MESSAGE' not in columns:
                return metadata
            
            msg_idx = columns.index('SAMPLE_MESSAGE')
            
            # Read first few lines to extract config
            for line_num, line in enumerate(f):
                if line_num > 10:  # Check first few lines only
                    break
                
                parts = line.strip().split('\t')
                if msg_idx < len(parts):
                    msg = parts[msg_idx]
                    
                    # Skip empty messages
                    if not msg or msg == '.':
                        continue
                    
                    # Extract sampling rate: "RECCFG CR 1000 2..." → 1000 Hz
                    if 'RECCFG CR' in msg and 'SamplingFrequency' not in metadata:
                        try:
                            match = re.search(r'RECCFG CR (\d+)', msg)
                            if match:
                                metadata['SamplingFrequency'] = int(match.group(1))
                        except Exception:
                            pass
                    
                    # Extract screen coords: "GAZE_COORDS 0.00 0.00 1919.00 1079.00" → [1920, 1080]
                    if 'GAZE_COORDS' in msg and 'ScreenResolution' not in metadata:
                        try:
                            match = re.search(r'GAZE_COORDS [\d.]+ [\d.]+ ([\d.]+) ([\d.]+)', msg)
                            if match:
                                width = int(float(match.group(1)) + 1)
                                height = int(float(match.group(2)) + 1)
                                metadata['ScreenResolution'] = [width, height]
                        except Exception:
                            pass
                    
                    # Extract camera lens focal length
                    if 'CAMERA_LENS_FOCAL_LENGTH' in msg and 'CameraLensFocalLength' not in metadata:
                        try:
                            match = re.search(r'CAMERA_LENS_FOCAL_LENGTH ([\d.]+)', msg)
                            if match:
                                metadata['CameraLensFocalLength'] = float(match.group(1))
                        except Exception:
                            pass
                    
                    # Extract pupil fit method: "ELCL_PROC CENTROID" → "centroid"
                    if 'ELCL_PROC' in msg and 'PupilFitMethod' not in metadata:
                        try:
                            match = re.search(r'ELCL_PROC (\w+)', msg)
                            if match:
                                method = match.group(1).lower()
                                if method == 'centroid':
                                    metadata['PupilFitMethod'] = 'centroid'
                                elif method == 'ellipse':
                                    metadata['PupilFitMethod'] = 'ellipse'
                        except Exception:
                            pass
                    
                    # Extract pupil data type: "PUPIL_DATA_TYPE RAW_AUTOSLIP"
                    if 'PUPIL_DATA_TYPE' in msg and 'PupilDataType' not in metadata:
                        try:
                            match = re.search(r'PUPIL_DATA_TYPE (\S+)', msg)
                            if match:
                                metadata['PupilDataType'] = match.group(1)
                        except Exception:
                            pass
                    
                    # Extract tracking mode: "RECCFG CR" → "pupil-cr"
                    if 'RECCFG' in msg and 'TrackingMode' not in metadata:
                        try:
                            if 'RECCFG CR' in msg:
                                metadata['TrackingMode'] = 'pupil-cr'
                            elif 'RECCFG PL' in msg:
                                metadata['TrackingMode'] = 'pupil-only'
                        except Exception:
                            pass
    except Exception:
        pass
    
    return metadata


def _get_tsv_preview(file_path: Path, max_rows: int = 8) -> str:
    """Get first N rows of a TSV file as formatted string."""
    import csv
    
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            reader = csv.reader(f, delimiter='\t')
            rows = []
            for i, row in enumerate(reader):
                if i >= max_rows:
                    break
                rows.append(row)
            
            if not rows:
                return "(empty file)"
            
            # Format as aligned columns
            if len(rows) == 1:
                return ' | '.join(rows[0][:5]) + ('...' if len(rows[0]) > 5 else '')
            
            # Calculate column widths
            col_widths = []
            for col_idx in range(len(rows[0])):
                max_width = max(len(str(rows[row_idx][col_idx] if col_idx < len(rows[row_idx]) else ''))
                               for row_idx in range(len(rows)))
                col_widths.append(min(max_width, 15))  # Cap width at 15 chars
            
            # Format header
            header = ' | '.join(rows[0][col_idx].ljust(col_widths[col_idx])
                              for col_idx in range(min(len(rows[0]), 5)))
            if len(rows[0]) > 5:
                header += ' | ...'
            
            # Format data rows
            data_lines = []
            for row_idx in range(1, len(rows)):
                line = ' | '.join(str(rows[row_idx][col_idx] if col_idx < len(rows[row_idx]) else '')[:col_widths[col_idx]].ljust(col_widths[col_idx])
                                 for col_idx in range(min(len(rows[row_idx]), 5)))
                if len(rows[row_idx]) > 5:
                    line += ' | ...'
                data_lines.append(line)
            
            return header + '\n' + '\n'.join(data_lines)
    except Exception as e:
        return f"(could not read preview: {str(e)[:50]})"


def _process_eyetracking_tsv(source_path: Path, output_path: Path) -> dict:
    """Process eyetracking TSV file: normalize to PRISM format.
    
    Operations:
    1. Drops RECORDING_SESSION_LABEL (redundant in filename)
    2. Converts dots (.) to empty strings (BIDS standard for missing values)
    3. Renames EyeLink columns to BEP020-standard names:
       - AVERAGE_GAZE_X → x_coordinate
       - AVERAGE_GAZE_Y → y_coordinate
       - AVERAGE_PUPIL_SIZE → pupil_size
       - TIMESTAMP → timestamp
    4. Orders core columns first: timestamp, x_coordinate, y_coordinate, pupil_size, then others
    5. Preserves all other columns
    
    Returns info about the processing including dropped columns and row count.
    """
    import csv
    
    # Columns to drop (redundant with PRISM structure)
    columns_to_drop = {'RECORDING_SESSION_LABEL'}
    
    # Column mapping: EyeLink name → BEP020 standard name
    column_mapping = {
        'AVERAGE_GAZE_X': 'x_coordinate',
        'AVERAGE_GAZE_Y': 'y_coordinate',
        'AVERAGE_PUPIL_SIZE': 'pupil_size',
        'TIMESTAMP': 'timestamp',
    }
    
    # Core columns that should appear first in this order
    core_columns_order = ['timestamp', 'x_coordinate', 'y_coordinate', 'pupil_size']
    
    try:
        # Detect if gzipped
        if source_path.suffix.lower() == '.gz':
            import gzip
            open_func = gzip.open
            mode = 'rt'
        else:
            open_func = open
            mode = 'r'
        
        # Read input
        with open_func(source_path, mode, encoding='utf-8', errors='ignore') as infile:
            reader = csv.DictReader(infile, delimiter='\t')
            rows = list(reader)
        
        if not rows:
            return {'status': 'error', 'message': 'No data rows found'}
        
        # Get original columns and clean BOM if present
        original_columns = [col.lstrip('\ufeff') for col in rows[0].keys()]
        
        # Build new column names:
        # 1. Filter out columns to drop
        # 2. Rename mapped columns
        # 3. Arrange core columns first, then others
        renamed_columns = []
        for col in original_columns:
            if col in columns_to_drop:
                continue  # Skip this column
            elif col in column_mapping:
                renamed_columns.append(column_mapping[col])
            else:
                renamed_columns.append(col)
        
        # Sort columns: core columns first (in order), then others
        new_columns = []
        for core_col in core_columns_order:
            if core_col in renamed_columns:
                new_columns.append(core_col)
                renamed_columns.remove(core_col)
        
        # Add remaining columns
        new_columns.extend(renamed_columns)
        
        # Open output file
        if output_path.suffix.lower() == '.gz':
            import gzip
            outfile = gzip.open(output_path, 'wt', encoding='utf-8')
        else:
            outfile = open(output_path, 'w', encoding='utf-8', newline='')
        
        with outfile as out:
            writer = csv.DictWriter(out, fieldnames=new_columns, delimiter='\t')
            writer.writeheader()
            
            # Write rows with renamed columns and normalized missing values
            for row in rows:
                new_row = {}
                for old_col_raw, value in row.items():
                    # Clean BOM from column name if present
                    old_col = old_col_raw.lstrip('\ufeff')
                    
                    # Skip dropped columns
                    if old_col in columns_to_drop:
                        continue
                    
                    # Get new column name
                    new_col = column_mapping.get(old_col, old_col)
                    
                    # Convert dots to empty strings (BIDS standard for missing values)
                    # Keep empty strings as-is
                    normalized_value = '' if value == '.' else value
                    
                    new_row[new_col] = normalized_value
                writer.writerow(new_row)
        
        # Calculate which columns were actually dropped from original
        dropped_cols = [col for col in original_columns if col in columns_to_drop]
        
        return {
            'status': 'success',
            'original_columns': list(original_columns),
            'new_columns': new_columns,
            'row_count': len(rows),
            'renamed_columns': {v: k for k, v in column_mapping.items() if k in original_columns},
            'dropped_columns': dropped_cols,
            'normalized_missing_values': True,
            'missing_value_indicator': 'dots (.) converted to empty strings'
        }
    
    except Exception as e:
        return {'status': 'error', 'message': str(e)}


def _process_eyetracking_events_tsv(source_path: Path, output_path: Path) -> dict:
    """Process eyetracking events TSV file (fixations/saccades).
    
    Renames key columns to BIDS-standard names:
    - First column (timestamp) → onset
    - Second column (duration) → duration
    - Third column (event type) → trial_type
    - Other columns preserved
    
    Returns info about the processing.
    """
    import csv
    
    try:
        # Detect if gzipped
        if source_path.suffix.lower() == '.gz':
            import gzip
            open_func = gzip.open
            mode = 'rt'
        else:
            open_func = open
            mode = 'r'
        
        # Read input
        with open_func(source_path, mode, encoding='utf-8', errors='ignore') as infile:
            reader = csv.DictReader(infile, delimiter='\t')
            rows = list(reader)
        
        if not rows:
            return {'status': 'error', 'message': 'No data rows found'}
        
        # Get original columns
        original_columns = list(rows[0].keys())
        
        # Map first 3 columns to BIDS standard (onset, duration, trial_type)
        # Rest stay as-is
        new_columns = []
        column_mapping = {}
        
        for i, col in enumerate(original_columns):
            if i == 0:  # First column → onset
                new_columns.append('onset')
                column_mapping[col] = 'onset'
            elif i == 1:  # Second column → duration
                new_columns.append('duration')
                column_mapping[col] = 'duration'
            elif i == 2:  # Third column → trial_type
                new_columns.append('trial_type')
                column_mapping[col] = 'trial_type'
            else:
                new_columns.append(col)
        
        # Open output file
        if output_path.suffix.lower() == '.gz':
            import gzip
            outfile = gzip.open(output_path, 'wt', encoding='utf-8')
        else:
            outfile = open(output_path, 'w', encoding='utf-8', newline='')
        
        with outfile as out:
            writer = csv.DictWriter(out, fieldnames=new_columns, delimiter='\t')
            writer.writeheader()
            
            # Write rows with renamed columns
            for row in rows:
                new_row = {}
                for old_col, value in row.items():
                    new_col = column_mapping.get(old_col, old_col)
                    new_row[new_col] = value
                writer.writerow(new_row)
        
        return {
            'status': 'success',
            'original_columns': original_columns,
            'new_columns': new_columns,
            'row_count': len(rows),
            'renamed_columns': column_mapping
        }
    
    except Exception as e:
        return {'status': 'error', 'message': str(e)}


def _create_events_sidecar(
    output_json: Path,
    *,
    task_name: str,
    extra_meta: dict | None = None,
) -> None:
    """Create a BIDS-style JSON sidecar for eyetracking events.
    
    Events files contain fixations, saccades, and messages detected from the raw data.
    Following BIDS BEP020 specification.
    """
    from datetime import datetime
    
    extra_meta = extra_meta or {}
    
    # Build events-specific sidecar
    sidecar = {
        "Columns": ["onset", "duration", "trial_type", "blink", "message"],
        "Description": "Eye-tracking events (fixations, saccades, messages)",
        "OnsetSource": "timestamp",
        "TaskName": task_name.replace("task-", ""),
        "SchemaVersion": "1.1.0",
        "CreationDate": datetime.now().strftime("%Y-%m-%d"),
    }
    
    # Column descriptions
    sidecar["onset"] = {
        "Description": "Event onset time",
        "Units": "ms",
        "Origin": "Device timestamp"
    }
    
    sidecar["duration"] = {
        "Description": "Event duration",
        "Units": "ms"
    }
    
    sidecar["trial_type"] = {
        "Description": "Type of event detected",
        "Levels": {
            "fixation": "Indicates a fixation event",
            "saccade": "Indicates a saccadic movement",
            "blink": "Indicates an eye blink",
            "message": "System message or marker"
        }
    }
    
    sidecar["blink"] = {
        "Description": "Blink status of the eye",
        "Levels": {
            "0": "Eye open",
            "1": "Eye closed/blinking",
            "n/a": "Not applicable"
        }
    }
    
    sidecar["message"] = {
        "Description": "Message text logged by the eye-tracker or system"
    }
    
    # Add device info if available
    if "Manufacturer" in extra_meta:
        sidecar["Manufacturer"] = extra_meta["Manufacturer"]
    
    if "SamplingFrequency" in extra_meta:
        sidecar["SamplingFrequency"] = extra_meta["SamplingFrequency"]
    
    with open(output_json, "w", encoding="utf-8") as f:
        json.dump(sidecar, f, indent=2, ensure_ascii=False)


def _create_eyetracking_sidecar(
    source_path: Path,
    output_json: Path,
    *,
    task_name: str,
    extra_meta: dict | None = None,
) -> None:
    """Create a BIDS-style JSON sidecar for eyetracking data.
    
    Uses flat, top-level key structure following BIDS BEP020 specification.
    Supports both EDF and TSV formats. For TSV files, extracts metadata
    from the file itself (e.g., SAMPLE_MESSAGE column).
    """
    from datetime import datetime
    
    extra_meta = extra_meta or {}
    file_ext = source_path.suffix.lower()
    
    # For TSV files, extract metadata
    if file_ext in (".tsv", ".tsv.gz"):
        tsv_meta = _extract_eyetracking_metadata_from_tsv(source_path)
        extra_meta.update(tsv_meta)
    
    # Build BIDS-style flat sidecar
    sidecar = {
        # Required fields
        "Manufacturer": extra_meta.get("Manufacturer", "SR Research"),
        "SamplingFrequency": extra_meta.get("SamplingFrequency", "unknown"),
        "RecordedEye": extra_meta.get("RecordedEye", "both"),
        "ScreenResolution": extra_meta.get("ScreenResolution", [1920, 1080]),
        "ScreenDistance": extra_meta.get("ScreenDistance", "unknown"),
        "TaskName": task_name.replace("task-", ""),
        "SchemaVersion": "1.1.0",
        "CreationDate": datetime.now().strftime("%Y-%m-%d"),
    }
    
    # Add optional manufacturer/model fields if available
    if "ManufacturerModelName" in extra_meta:
        sidecar["ManufacturersModelName"] = extra_meta["ManufacturerModelName"]
    
    if "SoftwareVersion" in extra_meta:
        sidecar["SoftwareVersion"] = extra_meta["SoftwareVersion"]
    
    # Eye tracking method (P-CR, P-only, CR-only)
    if "TrackingMode" in extra_meta:
        tracking = extra_meta["TrackingMode"]
        if tracking == "pupil-cr":
            sidecar["EyeTrackingMethod"] = "P-CR"
        elif tracking == "pupil-only":
            sidecar["EyeTrackingMethod"] = "P-only"
    
    # Pupil fitting method
    if "PupilFitMethod" in extra_meta:
        sidecar["PupilFitMethod"] = extra_meta["PupilFitMethod"]
    
    # Screen parameters
    if "ScreenSize" in extra_meta:
        sidecar["ScreenSize"] = extra_meta["ScreenSize"]
    
    if "ScreenRefreshRate" in extra_meta:
        sidecar["ScreenRefreshRate"] = extra_meta["ScreenRefreshRate"]
    
    sidecar["SampleCoordinateSystem"] = "gaze-on-screen"
    
    # Calibration information
    if "CalibrationPositions" in extra_meta:
        sidecar["CalibrationCount"] = extra_meta["CalibrationPositions"]
    
    if "CalibrationAccuracy" in extra_meta:
        sidecar["AverageCalibrationError"] = extra_meta["CalibrationAccuracy"]
    
    # File format
    if file_ext == ".edf":
        sidecar["FileFormat"] = "edf"
    elif file_ext in (".tsv", ".tsv.gz"):
        sidecar["FileFormat"] = file_ext
    elif file_ext == ".asc":
        sidecar["FileFormat"] = "asc"
    
    # Processing level
    if file_ext in (".tsv", ".tsv.gz"):
        sidecar["ProcessingLevel"] = "parsed"
    else:
        sidecar["ProcessingLevel"] = "raw"
    
    # Column definitions for TSV files
    if file_ext in (".tsv", ".tsv.gz"):
        tsv_info = _parse_tsv_columns(source_path)
        
        # Mapping of EyeLink column names to BIDS-style descriptions
        column_descriptions = {
            "RECORDING_SESSION_LABEL": {
                "Description": "Session label for this recording",
                "Units": "string"
            },
            "TRIAL_INDEX": {
                "Description": "Trial number",
                "Units": "index"
            },
            "AVERAGE_GAZE_X": {
                "Description": "Average gaze X position",
                "Units": "pixels"
            },
            "AVERAGE_GAZE_Y": {
                "Description": "Average gaze Y position",
                "Units": "pixels"
            },
            "AVERAGE_PUPIL_SIZE": {
                "Description": "Average pupil diameter",
                "Units": "arbitrary"
            },
            "AVERAGE_VELOCITY_X": {
                "Description": "Average gaze velocity X",
                "Units": "pixels/s"
            },
            "AVERAGE_VELOCITY_Y": {
                "Description": "Average gaze velocity Y",
                "Units": "pixels/s"
            },
            "AVERAGE_ACCELERATION_X": {
                "Description": "Average gaze acceleration X",
                "Units": "pixels/s²"
            },
            "AVERAGE_ACCELERATION_Y": {
                "Description": "Average gaze acceleration Y",
                "Units": "pixels/s²"
            },
            "AVERAGE_IN_BLINK": {
                "Description": "Proportion of trial time during blink",
                "Units": "0-1"
            },
            "AVERAGE_IN_SACCADE": {
                "Description": "Proportion of trial time during saccade",
                "Units": "0-1"
            },
            "IP_START_TIME": {
                "Description": "Interval start timestamp",
                "Units": "arbitrary"
            },
            "TIMESTAMP": {
                "Description": "Sample timestamp",
                "Units": "milliseconds"
            },
            "SAMPLE_MESSAGE": {
                "Description": "EyeLink recorder messages and metadata",
                "Units": "string"
            },
        }
        
        columns = {}
        for col_name in tsv_info.get('columns', []):
            if col_name in column_descriptions:
                columns[col_name] = column_descriptions[col_name]
            else:
                # For unknown columns, create a generic description
                columns[col_name] = {
                    "Description": f"{col_name.replace('_', ' ').lower()}",
                    "Units": "unknown"
                }
        
        sidecar["Columns"] = columns
    
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

    output_files = []

    try:
        # Try to use the Varioport converter for .raw/.vpd
        # Note: ext doesn't include the dot (e.g., "raw" not ".raw")
        if ext in ("raw", "vpd"):
            conversion_failed = False
            conversion_error_msg = None
            
            if log_callback:
                log_callback(
                    f"  🔬 Attempting RAW → EDF conversion...",
                    "info",
                )
            
            try:
                from helpers.physio.convert_varioport import convert_varioport

                # Build EDF output filename (no recording label needed for converted files)
                parts_edf = [sub]
                if ses:
                    parts_edf.append(ses)
                parts_edf.append(task)
                parts_edf.append("physio")
                base_name_edf = "_".join(parts_edf)
                
                out_edf = out_folder / f"{base_name_edf}.edf"
                # Write sidecar to root for BIDS inheritance
                out_root_json = (
                    output_dir / f"task-{task.replace('task-', '')}_physio.json"
                )

                if log_callback:
                    log_callback(
                        f"  🔄 Converting Varioport {ext.upper()} → EDF format...",
                        "info",
                    )
                    log_callback(
                        "  📊 Reading binary data, extracting channels, resampling...",
                        "info",
                    )

                convert_varioport(
                    str(source_path),
                    str(out_edf),
                    str(out_root_json),
                    task_name=task.replace("task-", ""),
                    base_freq=base_freq,
                )

                if out_edf.exists():
                    output_files.append(out_edf)
                    if log_callback:
                        edf_size = out_edf.stat().st_size / (1024 * 1024)  # MB
                        log_callback(
                            f"  ✅ Converted to EDF: {out_edf.name} ({edf_size:.2f} MB)",
                            "success",
                        )
                else:
                    conversion_failed = True
                    conversion_error_msg = "EDF file was not created after conversion"

            except ImportError as e:
                conversion_failed = True
                conversion_error_msg = f"Varioport converter not available: {e}"
            except Exception as e:
                conversion_failed = True
                conversion_error_msg = f"Conversion failed: {e}"
            
            # Fallback if conversion failed for any reason
            if conversion_failed:
                if log_callback:
                    log_callback(
                        f"  ⚠️  CONVERSION FAILED: {conversion_error_msg}",
                        "error",
                    )
                    log_callback(
                        f"  ⚠️  Fallback: Copying {ext.upper()} file without conversion",
                        "error",
                    )
                    log_callback(
                        "  💡 Note: RAW files should be converted to EDF format. Please check logs.",
                        "warning",
                    )
                
                # Use 'unconverted' label to make it clear this wasn't processed
                rec_label = "unconverted"
                parts_fallback = [sub]
                if ses:
                    parts_fallback.append(ses)
                parts_fallback.append(task)
                parts_fallback.append(f"recording-{rec_label}")
                parts_fallback.append("physio")
                base_name_fallback = "_".join(parts_fallback)
                
                out_data = out_folder / f"{base_name_fallback}.{ext}"
                out_root_json = (
                    output_dir / f"task-{task.replace('task-', '')}_physio.json"
                )

                shutil.copy2(source_path, out_data)

                if not out_root_json.exists():
                    _create_physio_sidecar(
                        source_path,
                        out_root_json,
                        task_name=task,
                        sampling_rate=base_freq,
                        recording_label="unconverted",
                    )

                output_files.extend([out_data])
        else:
            # For .edf or other formats already in physio-compatible format
            # Build filename without recording label
            parts_clean = [sub]
            if ses:
                parts_clean.append(ses)
            parts_clean.append(task)
            parts_clean.append("physio")
            base_name_clean = "_".join(parts_clean)
            
            out_data = out_folder / f"{base_name_clean}.{ext}"
            out_root_json = output_dir / f"task-{task.replace('task-', '')}_physio.json"

            shutil.copy2(source_path, out_data)

            # Extract metadata if it's an EDF file and root sidecar doesn't exist
            if not out_root_json.exists():
                edf_meta = {}
                if ext == "edf":
                    edf_meta = _extract_edf_metadata(source_path)

                _create_physio_sidecar(
                    source_path,
                    out_root_json,
                    task_name=task,
                    sampling_rate=base_freq,
                    extra_meta=edf_meta,
                )

            output_files.extend([out_data])

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
    log_callback: Callable[[str, str], None] | None = None,
) -> ConvertedFile:
    """Convert a single eyetracking file to PRISM format.
    
    Supports multiple formats:
    - EDF (EyeLink binary format)
    - TSV / TSV.GZ (Tab-separated values, e.g., EyeLink Data Viewer export)
    - ASC (EyeLink ASCII format)
    
    Files are copied to output and a JSON sidecar with metadata is created.
    """
    sub = parsed["sub"]
    ses = parsed["ses"]
    task = parsed["task"]
    suffix = parsed.get("suffix", "eyetrack").lower()  # "eyetrack" or "events"
    ext = parsed["ext"].lower()
    
    # Normalize extension
    if ext.startswith("."):
        ext = ext[1:]
    if ext == "gz":
        # Handle .tsv.gz → base name should still be "tsv.gz" but saved as "eyetrack.tsv.gz"
        ext = "tsv.gz"
    elif ext == "tsv.gz":
        pass
    else:
        ext = ext.lstrip(".")

    # Log file details
    if log_callback:
        log_callback(f"📍 File: {source_path.name}", "info")
        log_callback(f"   Subject: {sub}, Task: {task.replace('task-', '')}, Format: .{ext.upper()}", "info")

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
    parts.append("eyetracking")
    base_name = "_".join(parts)

    # Determine output filename based on source extension
    if ext == "edf":
        out_data = out_folder / f"{base_name}.edf"
    elif ext == "tsv" or ext == "tsv.gz":
        out_data = out_folder / f"{base_name}.{ext}"
    elif ext == "asc":
        out_data = out_folder / f"{base_name}.asc"
    else:
        out_data = out_folder / f"{base_name}.{ext}"

    # Root-level JSON for shared metadata
    out_root_json = output_dir / f"task-{task.replace('task-', '')}_eyetracking.json"
    # Subject-level JSON for file-specific metadata
    out_json = out_folder / f"{base_name}.json"

    output_files = []

    try:
        # Copy the data file
        if log_callback:
            log_callback(f"  🔄 Copying data file to {out_folder.relative_to(output_dir.parent)}...", "info")
        
        # Handle TSV processing differently - rename BIDS columns
        if ext in ("tsv", "tsv.gz"):
            if suffix == "events":
                # Events file: onset, duration, trial_type columns
                if log_callback:
                    log_callback(f"     Processing Events TSV: renaming to BIDS format (onset, duration, trial_type)...", "info")
                
                process_result = _process_eyetracking_events_tsv(source_path, out_data)
            else:
                # Samples file: x, y, pupil_size, timestamp columns
                if log_callback:
                    log_callback(f"     Processing Samples TSV: renaming BIDS columns (x_coordinate, y_coordinate, pupil_size, timestamp)...", "info")
                
                process_result = _process_eyetracking_tsv(source_path, out_data)
            
            if process_result['status'] == 'error':
                if log_callback:
                    log_callback(f"     ❌ TSV processing error: {process_result['message']}", "error")
                raise Exception(f"TSV processing failed: {process_result['message']}")
            
            renamed = process_result.get('renamed_columns', {})
            if renamed and log_callback:
                log_callback(f"     ✓ Renamed columns: {', '.join([f'{v}→{k}' for k, v in renamed.items()])}", "success")
            
            # Show first 8 rows of output as preview
            if log_callback and suffix in ("eyetrack", "eyetracking"):
                preview = _get_tsv_preview(out_data, max_rows=8)
                log_callback(f"     📋 Output preview (first 8 rows):", "preview")
                for line in preview.split('\n'):
                    log_callback(f"        {line}", "preview")
        else:
            # For EDF/ASC, just copy
            shutil.copy2(source_path, out_data)
        
        output_files.append(out_data)
        
        if log_callback:
            file_size = out_data.stat().st_size
            size_str = f"{file_size / (1024 * 1024):.2f} MB" if file_size > 1024 * 1024 else f"{file_size / 1024:.2f} KB"
            log_callback(f"  ✅ Copied: {out_data.name} ({size_str})", "success")

        # Extract metadata based on file type
        if log_callback:
            log_callback(f"  🔄 Extracting metadata and creating JSON sidecar...", "info")
        
        extra_meta = {}
        
        if ext == "edf":
            if log_callback:
                log_callback(f"     Reading EDF header...", "info")
            extra_meta = _extract_edf_metadata(source_path)
        elif ext in ("tsv", "tsv.gz") and suffix in ("eyetrack", "eyetracking"):
            if log_callback:
                log_callback(f"     Parsing TSV structure and columns...", "info")
            extra_meta = _extract_eyetracking_metadata_from_tsv(source_path)
        
        # Create appropriate sidecar based on file type
        if suffix == "events":
            _create_events_sidecar(
                out_json, task_name=task, extra_meta=extra_meta
            )
        else:
            # Create full subject-level sidecar for samples/EDF
            _create_eyetracking_sidecar(
                source_path, out_json, task_name=task, extra_meta=extra_meta
            )

        # Try to enrich with EDF header info if it's an EDF file and pyedflib is available
        if ext == "edf":
            try:
                import pyedflib

                with pyedflib.EdfReader(str(source_path)) as f:
                    with open(out_json, "r", encoding="utf-8") as jf:
                        sidecar = json.load(jf)

                    # Extract sampling rate (from first signal)
                    if f.signals_in_file > 0:
                        freq = f.getSampleFrequency(0)
                        sidecar["SamplingFrequency"] = freq
                        if log_callback:
                            log_callback(f"     SamplingFrequency: {freq} Hz", "info")

                    # Extract duration
                    duration = f.getFileDuration()
                    if log_callback:
                        log_callback(f"     Duration: {duration:.2f} seconds", "info")

                    with open(out_json, "w", encoding="utf-8") as jf:
                        json.dump(sidecar, jf, indent=2)
            except (ImportError, Exception):
                pass
        
        # Load subject sidecar to check if root-level one is needed
        with open(out_json, "r", encoding="utf-8") as jf:
            subject_sidecar = json.load(jf)
        
        # Create/update root-level JSON with shared fields only
        # (if it doesn't exist or if we need to update it)
        root_sidecar = {}
        if out_root_json.exists():
            with open(out_root_json, "r", encoding="utf-8") as jf:
                root_sidecar = json.load(jf)
        
        # Build root sidecar with only shared/common fields
        root_sidecar_new = {
            "Manufacturer": subject_sidecar.get("Manufacturer", "SR Research"),
            "TaskName": subject_sidecar.get("TaskName"),
            "FileFormat": subject_sidecar.get("FileFormat", "tsv" if ext in ("tsv", "tsv.gz") else ext),
            "SchemaVersion": subject_sidecar.get("SchemaVersion", "1.1.0"),
        }
        
        # Write root sidecar if different or doesn't exist
        if root_sidecar != root_sidecar_new:
            with open(out_root_json, "w", encoding="utf-8") as jf:
                json.dump(root_sidecar_new, jf, indent=2)
            if log_callback and not out_root_json.exists():
                log_callback(f"  ✅ Root sidecar created: {out_root_json.name}", "success")
        
        # Check if subject sidecar differs from root - keep it if different
        subject_differs = any(
            subject_sidecar.get(k) != root_sidecar_new.get(k)
            for k in ["SamplingFrequency", "ScreenResolution", "ScreenDistance", 
                      "RecordedEye", "EyeTrackingMethod", "PupilFitMethod"]
        )
        
        if subject_differs:
            output_files.append(out_json)
            if log_callback:
                log_callback(f"  ✅ Subject sidecar created: {out_json.name} (subject-specific)", "success")
        else:
            # Subject sidecar is identical to root, remove it
            if out_json.exists():
                out_json.unlink()
            if log_callback:
                log_callback(f"  ℹ️  Using root sidecar (identical across subjects)", "info")

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
        if log_callback:
            log_callback(f"  ❌ Error: {str(e)}", "error")
        
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

        # Create a minimal root sidecar if it's a data file (not already a json)
        output_files = [out_data]
        if ext != "json":
            out_root_json = (
                output_dir / f"task-{task.replace('task-', '')}_{suffix}.json"
            )
            if not out_root_json.exists():
                sidecar = {
                    "Metadata": {
                        "SourceFile": source_path.name,
                        "OrganizedBy": "prism batch organizer",
                    }
                }
                with open(out_root_json, "w", encoding="utf-8") as f:
                    json.dump(sidecar, f, indent=2)

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
    modality_filter: str = "all",
    log_callback: Callable | None = None,
    dry_run: bool = False,
) -> BatchConvertResult:
    """Batch convert all supported files from a flat folder structure.

    Args:
        source_folder: Path to folder containing raw data files
        output_folder: Path to output PRISM dataset folder
        physio_sampling_rate: Optional sampling rate override for physio files
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

        # Detect modality first
        modality = detect_modality(ext)

        # Override modality if filter is specific and not 'all'
        if modality_filter not in ("all", "physio", "eyetracking"):
            modality = "generic"
            target_modality = modality_filter
        else:
            target_modality = modality

        # Parse filename with modality-specific validation
        if target_modality == "physio":
            parsed = PHYSIO_FILENAME_PATTERN.match(file_path.name)
            if parsed:
                parsed = {
                    "sub": parsed.group("sub"),
                    "ses": parsed.group("ses"),
                    "task": parsed.group("task"),
                    "extra": parsed.group("extra") or "",
                    "ext": parsed.group("ext").lower(),
                }
            expected_suffix = "_physio"
        elif target_modality == "eyetracking":
            parsed = EYETRACKING_FILENAME_PATTERN.match(file_path.name)
            if parsed:
                parsed = {
                    "sub": parsed.group("sub"),
                    "ses": parsed.group("ses"),
                    "task": parsed.group("task"),
                    "extra": parsed.group("extra") or "",
                    "suffix": parsed.group("suffix").lower(),  # "eyetrack" or "events"
                    "ext": parsed.group("ext").lower(),
                }
            expected_suffix = "_eyetracking"
        else:
            parsed = parse_bids_filename(file_path.name)
            expected_suffix = ""

        if not parsed:
            msg = f"Invalid filename pattern. Expected: sub-XXX_ses-YYY_task-ZZZ{expected_suffix}.{ext}"
            result.skipped.append((file_path, msg))
            log(
                f"⏭️  [{idx}/{len(files_to_process)}] Skipped: {file_path.name} - {msg}",
                "warning",
            )
            continue

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
                log_callback=log,
            )
        elif target_modality == "eyetracking":
            converted = convert_eyetracking_file(
                file_path,
                output_folder,
                parsed=parsed,
                log_callback=log,
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
                    f"✅ [{idx}/{len(files_to_process)}] Success: {file_path.name} → {converted.modality}/ [{', '.join([f.name for f in converted.output_files])}]",
                    "success",
                )
        else:
            log(
                f"❌ [{idx}/{len(files_to_process)}] Error: {file_path.name} - {converted.error}",
                "error",
            )

    # Check if any files have 'unconverted' in their name (fallback was triggered)
    unconverted_count = sum(
        1 for conv in result.converted 
        if conv.success and any('unconverted' in str(f) for f in conv.output_files)
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
    
    # Alert user if any conversions failed and files were copied as fallback
    if unconverted_count > 0:
        log("", "info")
        log(f"⚠️  WARNING: {unconverted_count} file(s) were copied without conversion!", "error")
        log("   RAW/VPD files should be converted to EDF format.", "warning")
        log("   Files are labeled 'recording-unconverted' - check logs above for details.", "warning")
    
    if dry_run:
        log("💡 Run 'Copy to Project' when you're ready to execute.", "info")

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
        "Authors": ["PRISM Batch Converter"],
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
