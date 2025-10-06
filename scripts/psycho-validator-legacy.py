import os
import re
import json
import shutil
import subprocess
from jsonschema import validate, ValidationError

"""
Optional: official BIDS schema tools (Python)
Support both legacy 'bidsschematools' and newer 'bids_schema' style modules.
"""
try:
    import bidsschematools as _bst
except Exception:
    _bst = None
try:
    import bids_schema as _bsc  # hypothetical/newer name used in some environments
except Exception:
    _bsc = None

def _load_bids_schema_via_python():
    """Try to load the official BIDS schema via installed Python packages.
    Tries bidsschematools and bids_schema. Returns (schema_obj, error_message or None).
    """
    last_err = None
    # Try bidsschematools first
    if _bst is not None:
        try:
            if hasattr(_bst, 'load_schema'):
                return _bst.load_schema(), None
            if hasattr(_bst, 'schema') and hasattr(_bst.schema, 'load_schema'):
                return _bst.schema.load_schema(), None
            if hasattr(_bst, 'Schema'):
                try:
                    return _bst.Schema(), None
                except Exception as e:
                    last_err = f"bidsschematools.Schema failed: {e}"
            else:
                last_err = "Unsupported bidsschematools version/API"
        except Exception as e:
            last_err = f"bidsschematools error: {e}"
    else:
        last_err = "bidsschematools not installed"

    # Try bids_schema (alternative/newer module name)
    if _bsc is not None:
        try:
            # common guesses across versions
            if hasattr(_bsc, 'load_schema'):
                return _bsc.load_schema(), None
            if hasattr(_bsc, 'get_schema'):
                return _bsc.get_schema(), None
            if hasattr(_bsc, 'Schema'):
                try:
                    return _bsc.Schema(), None
                except Exception as e:
                    last_err = f"bids_schema.Schema failed: {e}"
            # Some distros expose module attributes for components
            if hasattr(_bsc, 'schema') and hasattr(_bsc.schema, 'load_schema'):
                return _bsc.schema.load_schema(), None
            last_err = "Unsupported bids_schema version/API"
        except Exception as e:
            last_err = f"bids_schema error: {e}"
    else:
        # keep last_err from previous attempts
        pass

    return None, last_err or "No supported BIDS schema Python package found"

def _load_bids_schema_from_path(path):
    """Load a BIDS schema-like JSON from a local path, returning (obj, err).
    Expects a JSON file that includes top-level keys like 'entities', 'datatypes',
    or an 'objects' dict containing them. If YAML is provided, we do not parse it.
    """
    try:
        if not os.path.isfile(path):
            return None, f"Path is not a file: {path}"
        with open(path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        return data, None
    except Exception as e:
        return None, str(e)

def _get_pkg_version_safe(pkg):
    try:
        return getattr(pkg, '__version__', None) or getattr(pkg, 'VERSION', None)
    except Exception:
        return None

def _print_bids_schema_summary(local_path=None):
    schema = None
    err = None
    used = None
    if local_path:
        schema, err = _load_bids_schema_from_path(local_path)
        used = f"local JSON @ {local_path}"
    if not schema:
        schema, err = _load_bids_schema_via_python()
        if schema:
            if used is None and _bst is not None:
                used = f"bidsschematools {_get_pkg_version_safe(_bst) or ''}".strip()
            elif used is None and _bsc is not None:
                used = f"bids_schema {_get_pkg_version_safe(_bsc) or ''}".strip()
    if not schema:
        print(f"⚠️  Could not load BIDS schema: {err}")
        print("💡 Install one of: pip install bidsschematools | pip install bids-schema (if available)")
        print("📖 Docs: https://bidsschematools.readthedocs.io/")
        print("📖 Spec: https://bids-specification.readthedocs.io/")
        return
    # Try to extract entities, datatypes, suffixes (best-effort across versions)
    entities = None
    datatypes = None
    suffixes = None
    if isinstance(schema, dict):
        entities = schema.get('entities') or schema.get('objects', {}).get('entities')
        datatypes = schema.get('datatypes') or schema.get('objects', {}).get('datatypes')
        suffixes = schema.get('suffixes') or schema.get('objects', {}).get('suffixes')
    else:
        entities = getattr(schema, 'entities', None)
        datatypes = getattr(schema, 'datatypes', None)
        suffixes = getattr(schema, 'suffixes', None)

    print("\n="*30)
    print("📚 BIDS SCHEMA SUMMARY")
    print("="*60)
    if used:
        print(f"Source: {used}")
    if entities:
        names = list(entities.keys()) if isinstance(entities, dict) else list(map(str, entities))
        print(f"🔹 Entities ({len(names)}): {', '.join(sorted(names)[:20])}{'...' if len(names)>20 else ''}")
    if datatypes:
        names = list(datatypes.keys()) if isinstance(datatypes, dict) else list(map(str, datatypes))
        print(f"🔹 Datatypes ({len(names)}): {', '.join(sorted(names))}")
    if suffixes:
        names = list(suffixes.keys()) if isinstance(suffixes, dict) else list(map(str, suffixes))
        # Show common MRI suffixes if present
        show = [n for n in names if n in ("T1w","T2w","bold","dwi","phasediff","fieldmap","epi")]
        show = show or names[:10]
        print(f"🔹 Suffixes (sample): {', '.join(show)}")
    print()

# ----------------------------
# Utility: filename handling
# ----------------------------
COMPOUND_EXTS = (".nii.gz", ".tsv.gz", ".edf.gz")

def split_compound_ext(filename):
    """Return (stem, ext) and handle compound extensions like .nii.gz.
    stem excludes the full extension chain; ext is the full extension (e.g., .nii.gz)
    """
    if any(filename.endswith(ext) for ext in COMPOUND_EXTS):
        for ext in COMPOUND_EXTS:
            if filename.endswith(ext):
                stem = filename[: -len(ext)]
                return stem, ext
    base, ext = os.path.splitext(filename)
    return base, ext

def derive_sidecar_path(file_path):
    """Derive the JSON sidecar path for a data file, respecting compound extensions."""
    dirname = os.path.dirname(file_path)
    fname = os.path.basename(file_path)
    stem, _ext = split_compound_ext(fname)
    return os.path.join(dirname, f"{stem}.json")

# ----------------------------
# Regex for BIDS-style filenames
# ----------------------------
# Standard BIDS-like for behavioral/stim modalities (task-based)
BIDS_REGEX = re.compile(
    r"^sub-[a-zA-Z0-9]+"
    r"(_ses-[a-zA-Z0-9]+)?"
    r"(_task-[a-zA-Z0-9]+)?"  # task optional for MRI
    r"(_run-[0-9]+)?"
)

# MRI filename pattern (e.g., sub-01[_ses-01][_task-..][_run-..]_T1w|_bold|_dwi etc.)
MRI_SUFFIX_REGEX = re.compile(r"_(T1w|T2w|T2star|FLAIR|PD|PDw|T1map|T2map|bold|dwi|magnitude1|magnitude2|phasediff|fieldmap|epi)$")

# ----------------------------
# Modality definitions
# ----------------------------
MODALITY_PATTERNS = {
    "movie": r".+\.mp4$",
    "image": r".+\.(png|jpg|jpeg|tiff)$",
    "eyetracking": r".+\.(tsv|edf)$",
    "eeg": r".+\.(edf|bdf|eeg)$",
    "audio": r".+\.(wav|mp3)$",
    "behavior": r".+\.tsv$",
    "physiological": r".+\.(edf|bdf|txt|csv)$",
    # MRI submodalities (nested under 'mri' folder)
    "anat": r".+_(T1w|T2w|T2star|FLAIR|PD|PDw|T1map|T2map)\.nii(\.gz)?$",
    "func": r".+_bold\.nii(\.gz)?$",
    "fmap": r".+_(magnitude1|magnitude2|phasediff|fieldmap|epi)\.nii(\.gz)?$",
    "dwi":  r".+_dwi\.nii(\.gz)?$"
}

# ----------------------------
# Schema Versioning System
# ----------------------------
def parse_version(version_string):
    """Parse semantic version string to tuple of integers"""
    try:
        return tuple(map(int, version_string.split('.')))
    except:
        return (0, 0, 0)

def is_compatible_version(required_version, provided_version):
    """Check if provided version is compatible with required version"""
    req_major, req_minor, req_patch = parse_version(required_version)
    prov_major, prov_minor, prov_patch = parse_version(provided_version)
    
    # Same major version is required for compatibility
    if req_major != prov_major:
        return False
    
    # Minor version can be higher (backward compatible)
    if prov_minor < req_minor:
        return False
        
    # Patch version can be different
    return True

def load_schema(name):
    """Load schema with version information"""
    schema_path = os.path.join("schemas", f"{name}.schema.json")
    if os.path.exists(schema_path):
        try:
            with open(schema_path) as f:
                schema = json.load(f)
            
            # Add schema metadata for versioning
            schema_version = schema.get('version', '1.0.0')
            schema['_validator_info'] = {
                'schema_version': schema_version,
                'modality': name,
                'loaded_at': json.dumps({"timestamp": "runtime"})
            }
            return schema
        except (json.JSONDecodeError, IOError) as e:
            print(f"Warning: Could not load schema {schema_path}: {e}")
    return None

def validate_schema_version(metadata, schema):
    """Validate that metadata schema version is compatible with loaded schema"""
    issues = []
    
    if not schema or '_validator_info' not in schema:
        return issues
    
    schema_version = schema['_validator_info']['schema_version']
    
    # Check if metadata specifies a schema version
    metadata_version = None
    if 'Metadata' in metadata and 'SchemaVersion' in metadata['Metadata']:
        metadata_version = metadata['Metadata']['SchemaVersion']
    
    if metadata_version:
        if not is_compatible_version(schema_version, metadata_version):
            issues.append(("WARNING", 
                f"Schema version mismatch: metadata uses v{metadata_version}, "
                f"validator expects v{schema_version}. Consider upgrading metadata."))
    else:
        issues.append(("INFO", 
            f"No schema version specified in metadata. Using validator default v{schema_version}"))
    
    return issues

SCHEMAS = {m: load_schema(m) for m in MODALITY_PATTERNS}
# MRI nested schemas
SCHEMAS['anat'] = load_schema(os.path.join('mri', 'anat'))
SCHEMAS['func'] = load_schema(os.path.join('mri', 'func'))
SCHEMAS['fmap'] = load_schema(os.path.join('mri', 'fmap'))
SCHEMAS['dwi']  = load_schema(os.path.join('mri', 'dwi'))
SCHEMAS['dataset_description'] = load_schema('dataset_description')

# ----------------------------
# Inherited Metadata System
# ----------------------------
def collect_inherited_metadata(file_path, root_dir):
    """Collect metadata that should be inherited from parent directories"""
    inherited_data = {}
    
    # Get relative path from root
    rel_path = os.path.relpath(file_path, root_dir)
    path_parts = rel_path.split(os.sep)
    
    # Build list of potential inheritance paths
    inheritance_paths = []
    current_path = root_dir
    
    # Add dataset-level inheritance
    inheritance_paths.append(os.path.join(root_dir, "task-*_stim.json"))
    
    # Walk up the directory tree
    for i, part in enumerate(path_parts[:-1]):  # exclude filename
        current_path = os.path.join(current_path, part)
        
        # Look for generic inheritance files
        inheritance_patterns = [
            os.path.join(current_path, "*_stim.json"),
            os.path.join(current_path, "stim.json")
        ]
        
        # Add subject-specific inheritance
        if part.startswith("sub-"):
            inheritance_patterns.append(os.path.join(current_path, f"{part}_stim.json"))
        
        inheritance_paths.extend(inheritance_patterns)
    
    # Collect metadata from inheritance files (most general to most specific)
    for pattern in inheritance_paths:
        if "*" in pattern:
            import glob
            matching_files = glob.glob(pattern)
        else:
            matching_files = [pattern] if os.path.exists(pattern) else []
        
        for inheritance_file in matching_files:
            if os.path.exists(inheritance_file):
                try:
                    with open(inheritance_file) as f:
                        inheritance_data = json.load(f)
                    # Merge with existing inherited data (later files override earlier ones)
                    inherited_data.update(inheritance_data)
                except (json.JSONDecodeError, IOError):
                    continue
    
    return inherited_data

def merge_metadata(inherited_data, sidecar_data):
    """Merge inherited metadata with sidecar metadata (sidecar takes precedence)"""
    merged = inherited_data.copy()
    
    def deep_merge(base_dict, override_dict):
        """Recursively merge dictionaries"""
        for key, value in override_dict.items():
            if key in base_dict and isinstance(base_dict[key], dict) and isinstance(value, dict):
                deep_merge(base_dict[key], value)
            else:
                base_dict[key] = value
    
    deep_merge(merged, sidecar_data)
    return merged

# ----------------------------
# Participants.tsv Integration
# ----------------------------
def load_participants_info(root_dir):
    """Load and parse participants.tsv file"""
    participants_path = os.path.join(root_dir, "participants.tsv")
    participants_info = {}
    
    if not os.path.exists(participants_path):
        return participants_info, ["Missing participants.tsv file"]
    
    issues = []
    try:
        with open(participants_path, 'r') as f:
            lines = f.readlines()
        
        if not lines:
            issues.append("participants.tsv is empty")
            return participants_info, issues
        
        # Parse header
        header = lines[0].strip().split('\t')
        if 'participant_id' not in header:
            issues.append("participants.tsv missing required 'participant_id' column")
            return participants_info, issues
        
        participant_id_idx = header.index('participant_id')
        
        # Parse data rows
        for line_num, line in enumerate(lines[1:], 2):
            if line.strip():  # Skip empty lines
                values = line.strip().split('\t')
                if len(values) > participant_id_idx:
                    participant_id = values[participant_id_idx]
                    
                    # Create participant info dict
                    participant_data = {}
                    for i, value in enumerate(values):
                        if i < len(header):
                            participant_data[header[i]] = value
                    
                    participants_info[participant_id] = participant_data
                else:
                    issues.append(f"participants.tsv line {line_num}: insufficient columns")
    
    except Exception as e:
        issues.append(f"Error reading participants.tsv: {e}")
    
    return participants_info, issues

def validate_participants_consistency(stats, participants_info):
    """Validate consistency between found subjects and participants.tsv"""
    issues = []
    
    if not participants_info:
        return issues  # Already handled in load_participants_info
    
    # Convert subject IDs to participant_id format (sub-001 -> sub-001)
    found_subjects = set(stats.subjects)
    listed_participants = set(participants_info.keys())
    
    # Check for subjects in data but not in participants.tsv
    missing_in_participants = found_subjects - listed_participants
    for subject in missing_in_participants:
        issues.append(("WARNING", f"Subject {subject} found in data but not listed in participants.tsv"))
    
    # Check for participants listed but not found in data
    missing_in_data = listed_participants - found_subjects
    for participant in missing_in_data:
        issues.append(("WARNING", f"Participant {participant} listed in participants.tsv but no data found"))
    
    return issues

# ----------------------------
# Helper: validate sidecar JSON (enhanced with inheritance)
# ----------------------------
def validate_sidecar(file_path, schema, root_dir):
    sidecar = derive_sidecar_path(file_path)
    issues = []
    
    if not os.path.exists(sidecar):
        issues.append(("ERROR", f"Missing sidecar for {file_path}"))
        return issues
    
    try:
        # Load sidecar data
        with open(sidecar) as f:
            sidecar_data = json.load(f)
        
        # Collect inherited metadata
        inherited_data = collect_inherited_metadata(file_path, root_dir)
        
        # Merge inherited and sidecar metadata
        complete_metadata = merge_metadata(inherited_data, sidecar_data)
        
        # Validate schema version compatibility
        if schema:
            version_issues = validate_schema_version(complete_metadata, schema)
            issues.extend(version_issues)
            
            # Validate against schema
            validate(instance=complete_metadata, schema=schema)
            
        # Store complete metadata for potential future use
        # (could be used for database export, cross-file validation, etc.)
        
    except ValidationError as e:
        issues.append(("ERROR", f"{sidecar} schema error: {e.message}"))
    except json.JSONDecodeError:
        issues.append(("ERROR", f"{sidecar} is not valid JSON"))
    except Exception as e:
        issues.append(("ERROR", f"Error processing {sidecar}: {e}"))
    
    return issues

# ----------------------------
# Dataset Statistics Class
# ----------------------------
class DatasetStats:
    def __init__(self):
        self.subjects = set()
        self.sessions = set()
        self.modalities = {}  # modality -> file count
        self.tasks = set()
        self.total_files = 0
        self.sidecar_files = 0
        # For consistency checking
        self.subject_data = {}  # subject_id -> {sessions: {}, modalities: set(), tasks: set()}
        
    def add_file(self, subject_id, session_id, modality, task, filename):
        self.subjects.add(subject_id)
        if session_id:
            self.sessions.add(f"{subject_id}/{session_id}")
        if modality not in self.modalities:
            self.modalities[modality] = 0
        self.modalities[modality] += 1
        if task:
            self.tasks.add(task)
        self.total_files += 1
        
        # Check for sidecar
        if filename.endswith('.json'):
            self.sidecar_files += 1
        
        # Track per-subject data for consistency checking
        if subject_id not in self.subject_data:
            self.subject_data[subject_id] = {
                'sessions': set(),
                'modalities': set(),
                'tasks': set(),
                'session_data': {}  # session_id -> {modalities: set(), tasks: set()}
            }
        
        subject_info = self.subject_data[subject_id]
        subject_info['modalities'].add(modality)
        if task:
            subject_info['tasks'].add(task)
        
        if session_id:
            subject_info['sessions'].add(session_id)
            if session_id not in subject_info['session_data']:
                subject_info['session_data'][session_id] = {
                    'modalities': set(),
                    'tasks': set()
                }
            subject_info['session_data'][session_id]['modalities'].add(modality)
            if task:
                subject_info['session_data'][session_id]['tasks'].add(task)

    def check_consistency(self):
        """Check for consistency across subjects and return warnings"""
        warnings = []
        
        if len(self.subjects) < 2:
            return warnings  # Can't check consistency with less than 2 subjects
        
        # Separate subjects with and without sessions
        subjects_with_sessions = {}
        subjects_without_sessions = {}
        
        for subject_id, data in self.subject_data.items():
            if data['sessions']:
                subjects_with_sessions[subject_id] = data
            else:
                subjects_without_sessions[subject_id] = data
        
        # Check consistency within session-based subjects
        if len(subjects_with_sessions) > 1:
            warnings.extend(self._check_session_consistency(subjects_with_sessions))
        
        # Check consistency within non-session subjects
        if len(subjects_without_sessions) > 1:
            warnings.extend(self._check_non_session_consistency(subjects_without_sessions))
        
        # Warn if mixing session and non-session structures
        if subjects_with_sessions and subjects_without_sessions:
            warnings.append(("WARNING", f"Mixed session structure: {len(subjects_with_sessions)} subjects have sessions, {len(subjects_without_sessions)} don't"))
        
        return warnings
    
    def _check_session_consistency(self, subjects_with_sessions):
        """Check consistency among subjects with sessions"""
        warnings = []
        
        # Find all unique sessions across subjects
        all_sessions = set()
        for data in subjects_with_sessions.values():
            all_sessions.update(data['sessions'])
        
        # Check if all subjects have all sessions
        for subject_id, data in subjects_with_sessions.items():
            missing_sessions = all_sessions - data['sessions']
            if missing_sessions:
                for session in missing_sessions:
                    warnings.append(("WARNING", f"Subject {subject_id} missing session {session}"))
        
        # For each session, check modality/task consistency
        for session in all_sessions:
            session_modalities = set()
            session_tasks = set()
            subjects_with_this_session = []
            
            # Collect all modalities and tasks for this session
            for subject_id, data in subjects_with_sessions.items():
                if session in data['sessions'] and session in data['session_data']:
                    session_data = data['session_data'][session]
                    session_modalities.update(session_data['modalities'])
                    session_tasks.update(session_data['tasks'])
                    subjects_with_this_session.append(subject_id)
            
            # Check each subject has all modalities/tasks for this session
            for subject_id in subjects_with_this_session:
                if session in subjects_with_sessions[subject_id]['session_data']:
                    subject_session_data = subjects_with_sessions[subject_id]['session_data'][session]
                    
                    missing_modalities = session_modalities - subject_session_data['modalities']
                    missing_tasks = session_tasks - subject_session_data['tasks']
                    
                    for modality in missing_modalities:
                        warnings.append(("WARNING", f"Subject {subject_id} session {session} missing {modality} data"))
                    
                    for task in missing_tasks:
                        warnings.append(("WARNING", f"Subject {subject_id} session {session} missing task {task}"))
        
        return warnings
    
    def _check_non_session_consistency(self, subjects_without_sessions):
        """Check consistency among subjects without sessions"""
        warnings = []
        
        # Find all modalities and tasks across subjects
        all_modalities = set()
        all_tasks = set()
        for data in subjects_without_sessions.values():
            all_modalities.update(data['modalities'])
            all_tasks.update(data['tasks'])
        
        # Check each subject has all modalities and tasks
        for subject_id, data in subjects_without_sessions.items():
            missing_modalities = all_modalities - data['modalities']
            missing_tasks = all_tasks - data['tasks']
            
            for modality in missing_modalities:
                warnings.append(("WARNING", f"Subject {subject_id} missing {modality} data"))
            
            for task in missing_tasks:
                warnings.append(("WARNING", f"Subject {subject_id} missing task {task}"))
        
        return warnings

# ----------------------------
# Main validator
# ----------------------------
def run_bids_validator_cli(root_dir):
    """Run official Node 'bids-validator' if available and return (issues, summary_info)."""
    issues = []
    summary_info = {}
    exe = shutil.which('bids-validator')
    if not exe:
        return None, None  # Not available
    try:
        # --no-color for clean output, --json for machine parseable
        result = subprocess.run(
            [exe, '--json', '--no-color', root_dir],
            capture_output=True, text=True, check=False
        )
        output = result.stdout.strip()
        if not output:
            return issues, summary_info
        data = json.loads(output)
        # Extract issues (errors/warnings may be under data['issues'])
        if isinstance(data, dict):
            # Summary if present
            summary_info = data.get('summary') or {}
            # Newer versions: data['issues'] = {'errors':[], 'warnings':[]}
            issues_block = data.get('issues') or {}
            def _fmt_msg(level_item):
                msg = level_item.get('reason') or level_item.get('code') or ''
                paths = []
                # Try multiple shapes used by bids-validator
                if isinstance(level_item.get('files'), list):
                    for fi in level_item['files']:
                        # shapes: {'file': {'path': str}} or {'path': str}
                        if isinstance(fi, dict):
                            if isinstance(fi.get('file'), dict) and fi['file'].get('path'):
                                paths.append(fi['file']['path'])
                            elif fi.get('path'):
                                paths.append(fi['path'])
                if isinstance(level_item.get('file'), dict) and level_item['file'].get('path'):
                    paths.append(level_item['file']['path'])
                if paths:
                    # De-duplicate and shorten output
                    uniq = []
                    for p in paths:
                        if p not in uniq:
                            uniq.append(p)
                    if len(uniq) == 1:
                        return f"{msg} [at {uniq[0]}]"
                    else:
                        return f"{msg} [e.g., {uniq[0]} and {len(uniq)-1} more]"
                return msg or json.dumps(level_item)
            for err in issues_block.get('errors', []) or []:
                issues.append(("ERROR", f"BIDS: {_fmt_msg(err)}"))
            for warn in issues_block.get('warnings', []) or []:
                issues.append(("WARNING", f"BIDS: {_fmt_msg(warn)}"))
            # Older format: flat list under data['errors'] / data['warnings']
            for err in data.get('errors', []) or []:
                issues.append(("ERROR", f"BIDS: {_fmt_msg(err)}"))
            for warn in data.get('warnings', []) or []:
                issues.append(("WARNING", f"BIDS: {_fmt_msg(warn)}"))
        return issues, summary_info
    except Exception as e:
        # Treat as not available on error
        return None, None

def validate_dataset(root_dir, bids_mode='auto'):
    issues = []
    stats = DatasetStats()

    # 0. Optionally run official BIDS validator
    skip_core_bids_checks = False
    bids_issues = []
    bids_summary = None
    # Helpers to make the official bids-validator ignore our custom modalities
    def _detect_custom_modalities(base_dir):
        custom_dirs = []
        for entry in os.listdir(base_dir):
            sub_path = os.path.join(base_dir, entry)
            if entry.startswith("sub-") and os.path.isdir(sub_path):
                # subject-level custom modality containers
                for name in ("behavior", "eyetracking", "physiological", "movie", "image", "audio", "mri"):
                    p = os.path.join(sub_path, name)
                    if os.path.isdir(p):
                        custom_dirs.append(os.path.relpath(p, base_dir))
                # session-level variants
                for ses in os.listdir(sub_path):
                    ses_path = os.path.join(sub_path, ses)
                    if os.path.isdir(ses_path) and ses.startswith("ses-"):
                        for name in ("behavior", "eyetracking", "physiological", "movie", "image", "audio", "mri"):
                            p = os.path.join(ses_path, name)
                            if os.path.isdir(p):
                                custom_dirs.append(os.path.relpath(p, base_dir))
        return custom_dirs

    def _ensure_bidsignore(base_dir):
        bidsignore_path = os.path.join(base_dir, ".bidsignore")
        if os.path.exists(bidsignore_path):
            return False
        lines = [
            "# Ignore custom non-core BIDS modality folders (psycho-validator still checks them)",
            "sub-*/behavior/",
            "sub-*/eyetracking/",
            "sub-*/physiological/",
            "sub-*/movie/",
            "sub-*/image/",
            "sub-*/audio/",
            "sub-*/mri/",
            "sub-*/ses-*/behavior/",
            "sub-*/ses-*/eyetracking/",
            "sub-*/ses-*/physiological/",
            "sub-*/ses-*/movie/",
            "sub-*/ses-*/image/",
            "sub-*/ses-*/audio/",
            "sub-*/ses-*/mri/",
            "",
            "# Common caches",
            "**/__pycache__/",
            "**/.ipynb_checkpoints/",
            "**/.DS_Store",
        ]
        try:
            with open(bidsignore_path, "w") as f:
                f.write("\n".join(lines) + "\n")
            issues.append(("INFO", "Created .bidsignore so bids-validator ignores custom modalities"))
            return True
        except Exception as e:
            issues.append(("WARNING", f"Failed to write .bidsignore: {e}"))
            return False
    if bids_mode != 'off':
        # If custom modalities are present, ensure the official validator ignores them
        if _detect_custom_modalities(root_dir):
            _ensure_bidsignore(root_dir)
        bi, bs = run_bids_validator_cli(root_dir)
        if bi is not None:
            # Found bids-validator and ran it
            bids_issues = bi
            bids_summary = bs or {}
            # Respect BIDS as source of truth for core modalities; we skip our MRI checks
            skip_core_bids_checks = True
            # Add an info line
            issues.append(("INFO", "Using official BIDS validator for core BIDS checks"))
        elif bids_mode == 'auto':
            issues.append(("INFO", "bids-validator not found; falling back to internal checks"))

    # 1. Dataset-level checks
    dataset_desc_path = os.path.join(root_dir, "dataset_description.json")
    if not os.path.exists(dataset_desc_path):
        issues.append(("ERROR", "Missing dataset_description.json"))
    
    # 2. Load and validate participants.tsv
    participants_info, participant_issues = load_participants_info(root_dir)
    for issue in participant_issues:
        issues.append(("WARNING", issue))

    # 3. Walk through subject directories
    for item in os.listdir(root_dir):
        item_path = os.path.join(root_dir, item)
        if os.path.isdir(item_path) and item.startswith("sub-"):
            # This is a subject directory
            subject_issues = validate_subject(item_path, item, stats, root_dir, skip_core_bids_checks)
            issues += subject_issues

    # 4. Check cross-subject consistency (skip when using official BIDS validator)
    if not skip_core_bids_checks:
        consistency_warnings = stats.check_consistency()
        issues += consistency_warnings
    
    # 5. Validate participants.tsv consistency
    participant_consistency_issues = validate_participants_consistency(stats, participants_info)
    issues += participant_consistency_issues

    # Merge in BIDS validator issues last (so INFO lines appear earlier)
    issues += bids_issues

    return issues, stats

def validate_subject(subject_dir, subject_id, stats, root_dir, skip_core_bids_checks=False):
    """Validate a single subject directory"""
    issues = []
    
    def _record_stats_for_dir(modality_dir, modality):
        for fname in os.listdir(modality_dir):
            file_path = os.path.join(modality_dir, fname)
            if os.path.isfile(file_path):
                task = None
                if "_task-" in fname:
                    m = re.search(r'_task-([A-Za-z0-9]+)(?:_|$)', fname)
                    if m:
                        task = m.group(1)
                stats.add_file(subject_id, None, modality, task, fname)
    
    for item in os.listdir(subject_dir):
        item_path = os.path.join(subject_dir, item)
        if os.path.isdir(item_path):
            if item.startswith("ses-"):
                # Session directory
                issues += validate_session(item_path, subject_id, item, stats, root_dir, skip_core_bids_checks)
            elif item == "mri":
                # MRI container without sessions
                if not skip_core_bids_checks:
                    issues += validate_mri_container(item_path, subject_id, None, stats, root_dir)
                else:
                    # Stats-only scan of MRI container
                    for sub in os.listdir(item_path):
                        sub_path = os.path.join(item_path, sub)
                        if os.path.isdir(sub_path) and sub in ("anat", "func", "fmap", "dwi"):
                            _record_stats_for_dir(sub_path, sub)
            elif item in MODALITY_PATTERNS:
                # Direct modality directory (no sessions)
                if skip_core_bids_checks and item in ("anat", "func", "fmap", "dwi"):
                    # Skip internal MRI checks when official BIDS validator is used but still collect stats
                    _record_stats_for_dir(item_path, item)
                else:
                    issues += validate_modality_dir(item_path, subject_id, None, item, stats, root_dir)
    
    return issues

def validate_session(session_dir, subject_id, session_id, stats, root_dir, skip_core_bids_checks=False):
    """Validate a single session directory"""
    issues = []
    
    def _record_stats_for_dir(modality_dir, modality):
        for fname in os.listdir(modality_dir):
            file_path = os.path.join(modality_dir, fname)
            if os.path.isfile(file_path):
                task = None
                if "_task-" in fname:
                    m = re.search(r'_task-([A-Za-z0-9]+)(?:_|$)', fname)
                    if m:
                        task = m.group(1)
                stats.add_file(subject_id, session_id, modality, task, fname)
    
    for item in os.listdir(session_dir):
        item_path = os.path.join(session_dir, item)
        if os.path.isdir(item_path):
            if item == "mri":
                if not skip_core_bids_checks:
                    issues += validate_mri_container(item_path, subject_id, session_id, stats, root_dir)
                else:
                    # Stats-only scan of MRI container
                    for sub in os.listdir(item_path):
                        sub_path = os.path.join(item_path, sub)
                        if os.path.isdir(sub_path) and sub in ("anat", "func", "fmap", "dwi"):
                            _record_stats_for_dir(sub_path, sub)
            elif item in MODALITY_PATTERNS:
                if skip_core_bids_checks and item in ("anat", "func", "fmap", "dwi"):
                    # Skip internal MRI checks when official BIDS validator is used but still collect stats
                    _record_stats_for_dir(item_path, item)
                else:
                    issues += validate_modality_dir(item_path, subject_id, session_id, item, stats, root_dir)

    return issues

def validate_mri_container(mri_dir, subject_id, session_id, stats, root_dir):
    """Validate nested MRI submodalities under an 'mri' folder (anat/func/fmap/dwi)."""
    issues = []
    for sub in os.listdir(mri_dir):
        sub_path = os.path.join(mri_dir, sub)
        if os.path.isdir(sub_path) and sub in ("anat", "func", "fmap", "dwi"):
            issues += validate_modality_dir(sub_path, subject_id, session_id, sub, stats, root_dir)
    
    return issues

def validate_modality_dir(modality_dir, subject_id, session_id, modality, stats, root_dir):
    """Validate files in a modality directory"""
    issues = []
    pattern = re.compile(MODALITY_PATTERNS[modality])
    schema = SCHEMAS.get(modality)
    expected_suffix = {
        'eeg': 'eeg',
        'behavior': 'beh',
        'physiological': 'physio',
        'eyetracking': 'eyetrack',
        'anat': None, 'func': None, 'fmap': None, 'dwi': None,
        'image': None, 'audio': None, 'movie': None,
    }
    
    for fname in os.listdir(modality_dir):
        file_path = os.path.join(modality_dir, fname)
        if os.path.isfile(file_path):
            # Extract task from filename if possible
            task = None
            if "_task-" in fname:
                # Capture task label up to next '_' (entity boundary) or end of string
                task_match = re.search(r'_task-([A-Za-z0-9]+)(?:_|$)', fname)
                if task_match:
                    task = task_match.group(1)
                    # Enforce BIDS task label rule: alphanumeric only
                    if re.search(r"[^A-Za-z0-9]", task):
                        suggestion = re.sub(r"[^A-Za-z0-9]", "", task)
                        issues.append(("ERROR", f"{file_path}: invalid task label '{task}'. Use only letters/digits. Suggested: '{suggestion}'"))
            
            # Add to stats for all files in modality directory
            stats.add_file(subject_id, session_id, modality, task, fname)
            
            # Non-BIDS _stim suffix hints
            if re.search(r"_stim\.", fname):
                hint = expected_suffix.get(modality)
                if hint:
                    issues.append(("ERROR", f"{file_path}: non-BIDS suffix '_stim'. Use '_{hint}' instead and provide a matching sidecar JSON."))
                else:
                    issues.append(("ERROR", f"{file_path}: non-BIDS suffix '_stim'. Replace with a BIDS-appropriate suffix for this modality."))

            # Check naming convention (MRI vs others)
            base, ext = split_compound_ext(fname)
            is_nifti = ext in (".nii", ".nii.gz")
            is_tsv = ext in (".tsv", ".tsv.gz")
            if modality in ("anat", "func", "fmap", "dwi"):
                if is_nifti:
                    if not BIDS_REGEX.match(base) or not MRI_SUFFIX_REGEX.search(base):
                        issues.append(("ERROR", f"Invalid MRI filename: {fname} in {modality_dir}"))
                else:
                    # For non-NIfTI files in MRI folders (e.g., events.tsv, .json, .bval/.bvec), use general BIDS base check only
                    if not BIDS_REGEX.match(base):
                        issues.append(("ERROR", f"Invalid filename: {fname} in {modality_dir}"))
            else:
                if not BIDS_REGEX.match(base):
                    issues.append(("ERROR", f"Invalid filename: {fname} in {modality_dir}"))

            # Pattern conformity and modality-specific hints
            allowed_extra = False
            if modality == 'func':
                # Accept events.tsv and corresponding JSON in func folder
                if re.match(r".+_events\.tsv(\.gz)?$", fname) or fname.endswith('_events.json'):
                    allowed_extra = True
            if modality == 'dwi':
                # Accept diffusion gradient files
                if fname.endswith('.bval') or fname.endswith('.bvec'):
                    allowed_extra = True
            # JSON sidecars are metadata; don't warn about pattern mismatch
            if ext == '.json':
                pass
            elif not pattern.match(fname) and not allowed_extra:
                if modality == 'physiological' and fname.endswith('.csv'):
                    issues.append(("ERROR", f"{file_path}: .csv not valid for BIDS physio. Use .tsv(.gz) with '_physio' suffix and a JSON data dictionary."))
                else:
                    issues.append(("WARNING", f"{file_path}: does not match expected pattern for modality '{modality}'"))

            # Validate expected subject/session presence in filename
            if subject_id not in fname:
                issues.append(("ERROR", f"Filename {fname} doesn't contain subject ID {subject_id}"))
            if session_id and session_id not in fname:
                issues.append(("ERROR", f"Filename {fname} doesn't contain session ID {session_id}"))

            # Sidecar presence and validation
            sidecar = derive_sidecar_path(file_path)
            require_sidecar = False
            warn_sidecar = False
            # Require sidecars for imaging and EEG
            if modality in ("anat", "func", "fmap", "dwi") and is_nifti:
                require_sidecar = True
            if modality == 'eeg' and re.search(r"\.(edf|bdf|eeg)$", fname):
                require_sidecar = True
            # Events data dictionary is recommended but not required
            if modality == 'func' and is_tsv and fname.endswith('_events.tsv'):
                warn_sidecar = True
            # Generic recommendation for behavioral and eyetracking TSVs
            if modality in ('behavior', 'eyetracking') and is_tsv:
                warn_sidecar = True

            if require_sidecar:
                if not os.path.exists(sidecar):
                    issues.append(("ERROR", f"Missing sidecar JSON: {sidecar}"))
                else:
                    issues += validate_sidecar(file_path, schema, root_dir)
            else:
                if os.path.exists(sidecar):
                    issues += validate_sidecar(file_path, schema, root_dir)
                elif warn_sidecar:
                    issues.append(("WARNING", f"Missing recommended data dictionary: {sidecar}"))
    
    return issues

# ----------------------------
# Summary Display Functions
# ----------------------------
def print_dataset_summary(dataset_path, stats):
    """Print a comprehensive dataset summary like BIDS validator"""
    print("\n" + "="*60)
    print("🗂️  DATASET SUMMARY")
    print("="*60)
    
    # Dataset info
    dataset_name = os.path.basename(os.path.abspath(dataset_path))
    print(f"📁 Dataset: {dataset_name}")
    
    # Subject and session counts
    num_subjects = len(stats.subjects)
    num_sessions = len(stats.sessions)
    has_sessions = num_sessions > 0
    
    print(f"👥 Subjects: {num_subjects}")
    if has_sessions:
        print(f"📋 Sessions: {num_sessions}")
        # Calculate sessions per subject
        sessions_per_subject = {}
        for session in stats.sessions:
            subj = session.split('/')[0]
            sessions_per_subject[subj] = sessions_per_subject.get(subj, 0) + 1
        avg_sessions = sum(sessions_per_subject.values()) / len(sessions_per_subject) if sessions_per_subject else 0
        print(f"📊 Sessions per subject: {avg_sessions:.1f} (avg)")
    else:
        print("📋 Sessions: No session structure detected")
    
    # Modality breakdown
    print(f"\n🎯 MODALITIES ({len(stats.modalities)} found):")
    if stats.modalities:
        for modality, count in sorted(stats.modalities.items()):
            schema_status = "✅" if SCHEMAS.get(modality) else "❌"
            print(f"  {schema_status} {modality}: {count} files")
    else:
        print("  No modality data found")
    
    # Task breakdown
    print(f"\n📝 TASKS ({len(stats.tasks)} found):")
    if stats.tasks:
        for task in sorted(stats.tasks):
            print(f"  • {task}")
    else:
        print("  No tasks detected")
    
    # File statistics
    data_files = stats.total_files - stats.sidecar_files
    print(f"\n📄 FILES:")
    print(f"  • Data files: {data_files}")
    print(f"  • Sidecar files: {stats.sidecar_files}")
    print(f"  • Total files: {stats.total_files}")

def print_validation_results(problems):
    """Print validation results with proper categorization"""
    if not problems:
        print("\n" + "="*60)
        print("✅ VALIDATION RESULTS")
        print("="*60)
        print("🎉 No issues found! Dataset is valid.")
        return
    
    # Categorize problems
    errors = [msg for level, msg in problems if level == "ERROR"]
    warnings = [msg for level, msg in problems if level == "WARNING"]
    infos = [msg for level, msg in problems if level == "INFO"]
    
    print("\n" + "="*60)
    print("🔍 VALIDATION RESULTS")
    print("="*60)
    
    if errors:
        print(f"\n🔴 ERRORS ({len(errors)}):")
        for i, error in enumerate(errors, 1):
            print(f"  {i:2d}. {error}")
    
    if warnings:
        print(f"\n🟡 WARNINGS ({len(warnings)}):")
        for i, warning in enumerate(warnings, 1):
            print(f"  {i:2d}. {warning}")
    
    if infos:
        print(f"\n🔵 INFO ({len(infos)}):")
        for i, info in enumerate(infos, 1):
            print(f"  {i:2d}. {info}")
    
    # Summary line
    print(f"\n📊 SUMMARY: {len(errors)} errors, {len(warnings)} warnings, {len(infos)} info")
    
    if errors:
        print("❌ Dataset validation failed due to errors.")
    else:
        print("⚠️  Dataset has warnings but no critical errors.")

def print_schema_info(modality):
    """Prints a user-friendly description of a schema."""
    schema = SCHEMAS.get(modality)
    if not schema:
        print(f"❌ Schema for modality '{modality}' not found.")
        return

    print("\n" + "="*60)
    print(f"📄 SCHEMA DETAILS FOR: {modality.upper()}")
    print("="*60)
    
    # Schema metadata
    if "title" in schema:
        print(f"  Title: {schema['title']}")
    if "description" in schema:
        print(f"  Description: {schema['description']}")
    
    # Version information
    version = schema.get('version', 'unknown')
    schema_id = schema.get('$id', 'unknown')
    print(f"  Version: {version}")
    print(f"  Schema ID: {schema_id}")
    
    print("\nFIELDS:")
    
    required_fields = schema.get("required", [])
    
    def print_properties(properties, required_list, indent_level=0):
        """Recursively print properties with proper indentation"""
        indent = "  " * (indent_level + 1)
        
        for prop, details in properties.items():
            is_required = "REQUIRED" if prop in required_list else "OPTIONAL"
            prop_type = details.get('type', 'N/A')
            
            print(f"\n{indent}- {prop} ({prop_type}) - [{is_required}]")
            
            if "description" in details:
                print(f"{indent}  {details['description']}")
            
            if "enum" in details:
                enum_values = details['enum']
                if len(enum_values) <= 5:
                    print(f"{indent}  Options: {', '.join(map(str, enum_values))}")
                else:
                    print(f"{indent}  Options: {', '.join(map(str, enum_values[:3]))}... ({len(enum_values)} total)")
            
            if "minimum" in details:
                print(f"{indent}  Minimum: {details['minimum']}")
            if "maximum" in details:
                print(f"{indent}  Maximum: {details['maximum']}")
            if "default" in details:
                print(f"{indent}  Default: {details['default']}")
            
            # Handle nested objects
            if prop_type == "object" and "properties" in details:
                nested_required = details.get("required", [])
                print_properties(details["properties"], nested_required, indent_level + 1)
    
    print_properties(schema.get("properties", {}), required_fields)

def list_schema_versions():
    """List all available schema versions"""
    print("\n" + "="*60)
    print("📚 AVAILABLE SCHEMA VERSIONS")
    print("="*60)
    
    for modality, schema in SCHEMAS.items():
        if schema:
            version = schema.get('version', 'unknown')
            schema_id = schema.get('$id', 'N/A')
            print(f"  {modality:12} v{version:8} ({schema_id})")
        else:
            print(f"  {modality:12} {'ERROR':8} (Schema not found)")
    
    print(f"\n📋 Schema versioning follows semantic versioning (MAJOR.MINOR.PATCH)")
    print(f"   • MAJOR: Breaking changes (incompatible)")
    print(f"   • MINOR: New features (backward compatible)")  
    print(f"   • PATCH: Bug fixes (backward compatible)")

def validate_dataset_fair(dataset_root):
    """Validate dataset-level FAIR compliance"""
    print(f"🔍 Validating FAIR compliance for dataset: {dataset_root}")
    
    # Check for dataset_description.json
    dataset_desc_path = os.path.join(dataset_root, "dataset_description.json")
    if not os.path.exists(dataset_desc_path):
        print("❌ dataset_description.json not found!")
        print("💡 Use --create-fair-template to generate a FAIR-compliant template")
        return
    
    # Load and validate dataset description
    try:
        with open(dataset_desc_path, 'r') as f:
            dataset_desc = json.load(f)
    except Exception as e:
        print(f"❌ Error reading dataset_description.json: {e}")
        return
    
    # Validate against schema
    dataset_schema = SCHEMAS.get('dataset_description')
    if dataset_schema:
        try:
            validate(dataset_desc, dataset_schema)
            print("✅ Dataset description schema validation passed")
        except ValidationError as e:
            print(f"⚠️  Schema validation warnings:")
            error_path = " -> ".join(str(p) for p in e.absolute_path) if e.absolute_path else "root"
            print(f"   Path: {error_path}")
            print(f"   Issue: {e.message}")
    else:
        print("⚠️  Dataset description schema not available for validation")
    
    # Run FAIR compliance check
    from fair_checker import FAIRComplianceChecker
    checker = FAIRComplianceChecker()
    results = checker.evaluate_dataset(dataset_desc_path)
    
    if 'error' in results:
        print(f"❌ {results['error']}")
        return
    
    # Display results
    print(f"\n🔍 Dataset FAIR Compliance Report")
    print("=" * 60)
    
    # Overall grade
    print(f"🎯 Overall Grade: {results['grade']}")
    print(f"📊 Total Score: {results['total_percentage']:.1f}%\n")
    
    # Individual scores
    print("📈 Category Scores:")
    for category, percentage in results['percentages'].items():
        bar_length = int(percentage / 5)  # Scale to 20 chars max
        bar = "█" * bar_length + "░" * (20 - bar_length)
        print(f"  {category.upper():13} [{bar}] {percentage:5.1f}%")
    
    # Recommendations
    if results['recommendations']:
        print(f"\n💡 Recommendations for FAIR improvement:")
        for i, rec in enumerate(results['recommendations'], 1):
            print(f"  {i:2d}. {rec}")
    
    # Export FAIR metadata if score is good
    if results['total_percentage'] >= 50:
        print(f"\n🚀 Exporting FAIR metadata...")
        from fair_export import export_fair_metadata
        export_results = export_fair_metadata(dataset_desc_path)
        
        for format_type, result in export_results.items():
            if result:
                print(f"  ✅ {format_type}: {result}")
            else:
                print(f"  ❌ {format_type}: Export failed")

def create_fair_template(output_file):
    """Create a FAIR-compliant dataset_description.json template"""
    template = {
        "Name": "Your Dataset Name",
        "BIDSVersion": "1.9.0",
        "DatasetType": "raw",
        "License": "CC-BY-4.0",
        "Authors": [
            {
                "name": "Your Name",
                "orcid": "0000-0000-0000-0000",
                "affiliation": "Your Institution",
                "ror": "https://ror.org/your-institution-id"
            }
        ],
        "Funding": [
            {
                "agency": "Funding Agency Name",
                "grant_number": "Grant Number",
                "funder_id": "https://doi.org/10.13039/funder-id"
            }
        ],
        "EthicsApprovals": [
            {
                "committee": "Ethics Committee Name",
                "approval_number": "Approval Number",
                "date": "YYYY-MM-DD"
            }
        ],
        "DatasetDOI": "10.PLACEHOLDER/dataset-doi",
        "Description": "Detailed description of your psychological research dataset including methods, participants, and data collection procedures.",
        "Keywords": [
            "psychology",
            "neuroscience",
            "behavioral data",
            "experimental psychology"
        ],
        "ResearchDomains": [
            "cognitive psychology",
            "experimental psychology"
        ],
        "Acknowledgements": "Acknowledge participants, funding sources, and collaborators.",
        "ReferencesAndLinks": [
            "https://github.com/your-repository",
            "https://your-project-website.com"
        ],
        "DataCollection": {
            "start_date": "YYYY-MM-DD",
            "end_date": "YYYY-MM-DD",
            "location": "Data collection location"
        },
        "Publications": [
            {
                "title": "Related Publication Title",
                "doi": "10.PLACEHOLDER/publication-doi",
                "year": "YYYY"
            }
        ],
        "Contact": {
            "name": "Contact Person Name",
            "email": "contact@institution.edu",
            "orcid": "0000-0000-0000-0000"
        },
        "GeneratedBy": [
            {
                "Name": "psycho-validator",
                "Version": "1.3.0",
                "CodeURL": "https://github.com/MRI-Lab-Graz/psycho-validator"
            }
        ]
    }
    
    try:
        with open(output_file, 'w') as f:
            json.dump(template, f, indent=2)
        
        print(f"✅ FAIR-compliant template created: {output_file}")
        print("\n📝 Next steps:")
        print("  1. Edit the template with your actual dataset information")
        print("  2. Ensure all ORCID IDs and DOIs are valid")
        print("  3. Run --dataset-fair to check compliance")
        print("  4. Use --fair-export to generate XML metadata")
        
    except Exception as e:
        print(f"❌ Error creating template: {e}")

def generate_full_fair_report(dataset_root):
    """Generate comprehensive FAIR report for entire dataset"""
    print(f"🔍 Generating comprehensive FAIR report for: {dataset_root}")
    print("=" * 80)
    
    # Check dataset description first
    dataset_desc_path = os.path.join(dataset_root, "dataset_description.json")
    dataset_score = None
    
    if os.path.exists(dataset_desc_path):
        print("\n📋 DATASET-LEVEL FAIR COMPLIANCE")
        print("-" * 40)
        
        from fair_checker import FAIRComplianceChecker
        checker = FAIRComplianceChecker()
        results = checker.evaluate_dataset(dataset_desc_path)
        
        if 'error' not in results:
            dataset_score = results['total_percentage']
            print(f"📊 Overall Score: {dataset_score:.1f}%")
            print(f"🎯 Grade: {results['grade']}")
            
            # Quick category overview
            for category, percentage in results['percentages'].items():
                status = "✅" if percentage >= 70 else "⚠️" if percentage >= 50 else "❌"
                print(f"  {status} {category.upper()}: {percentage:.1f}%")
    else:
        print("❌ No dataset_description.json found - create one for better FAIR compliance")
    
    # Scan for all metadata files
    print(f"\n📁 STIMULUS-LEVEL METADATA ANALYSIS")
    print("-" * 40)
    
    metadata_files = []
    for root, dirs, files in os.walk(dataset_root):
        for file in files:
            if file.endswith('.json') and 'stim' in file:
                metadata_files.append(os.path.join(root, file))
    
    if not metadata_files:
        print("ℹ️  No stimulus metadata files found")
        return
    
    print(f"Found {len(metadata_files)} stimulus metadata files")
    
    # Analyze each metadata file
    fair_scores = []
    modality_summary = {}
    
    from fair_checker import FAIRComplianceChecker
    checker = FAIRComplianceChecker()
    
    for metadata_file in metadata_files[:10]:  # Limit to first 10 for performance
        try:
            results = checker.evaluate_dataset(metadata_file)
            if 'error' not in results:
                score = results['total_percentage']
                fair_scores.append(score)
                
                # Determine modality
                modality = detect_modality_from_path(metadata_file)
                if modality not in modality_summary:
                    modality_summary[modality] = []
                modality_summary[modality].append(score)
                
                # Show brief result
                status = "✅" if score >= 70 else "⚠️" if score >= 50 else "❌"
                rel_path = os.path.relpath(metadata_file, dataset_root)
                print(f"  {status} {rel_path}: {score:.1f}%")
                
        except Exception as e:
            rel_path = os.path.relpath(metadata_file, dataset_root)
            print(f"  ❌ {rel_path}: Error - {e}")
    
    # Summary statistics
    if fair_scores:
        print(f"\n📊 STIMULUS METADATA SUMMARY")
        print("-" * 40)
        avg_score = sum(fair_scores) / len(fair_scores)
        min_score = min(fair_scores)
        max_score = max(fair_scores)
        
        print(f"📈 Average FAIR Score: {avg_score:.1f}%")
        print(f"📉 Range: {min_score:.1f}% - {max_score:.1f}%")
        
        # Modality breakdown
        print(f"\n🎯 MODALITY BREAKDOWN:")
        for modality, scores in modality_summary.items():
            if scores:
                avg_mod = sum(scores) / len(scores)
                print(f"  {modality}: {avg_mod:.1f}% avg ({len(scores)} files)")
        
        # Overall assessment
        print(f"\n🏆 OVERALL DATASET ASSESSMENT")
        print("-" * 40)
        
        overall_score = dataset_score if dataset_score else avg_score
        if overall_score >= 80:
            print("🥇 EXCELLENT - Dataset meets high FAIR standards")
        elif overall_score >= 60:
            print("🥈 GOOD - Dataset is FAIR-compliant with room for improvement")
        elif overall_score >= 40:
            print("🥉 FAIR - Basic compliance achieved, significant improvements needed")
        else:
            print("📋 NEEDS WORK - Major FAIR improvements required")
            
        print(f"Combined Score: {overall_score:.1f}%")

def generate_fair_summary(dataset_root):
    """Generate quick FAIR compliance summary"""
    print(f"🔍 FAIR Compliance Summary: {os.path.basename(dataset_root)}")
    print("=" * 60)
    
    # Quick dataset check
    dataset_desc_path = os.path.join(dataset_root, "dataset_description.json")
    if os.path.exists(dataset_desc_path):
        print("✅ Dataset description found")
        
        # Quick validation
        try:
            with open(dataset_desc_path, 'r') as f:
                dataset_desc = json.load(f)
            
            # Check key FAIR indicators
            indicators = {
                'DOI': dataset_desc.get('DatasetDOI', '').startswith('10.'),
                'Authors': len(dataset_desc.get('Authors', [])) > 0,
                'License': dataset_desc.get('License') not in [None, '', 'All rights reserved'],
                'Keywords': len(dataset_desc.get('Keywords', [])) >= 3,
                'Description': len(dataset_desc.get('Description', '')) > 50,
                'Contact': dataset_desc.get('Contact', {}).get('email') is not None
            }
            
            passed = sum(indicators.values())
            total = len(indicators)
            
            print(f"📊 Quick FAIR Check: {passed}/{total} indicators passed")
            for indicator, status in indicators.items():
                status_icon = "✅" if status else "❌"
                print(f"  {status_icon} {indicator}")
                
        except Exception as e:
            print(f"⚠️  Error reading dataset description: {e}")
    else:
        print("❌ No dataset_description.json found")
        print("💡 Run: python psycho-validator.py --create-fair-template dataset_description.json")
    
    # Count metadata files
    metadata_count = 0
    for root, dirs, files in os.walk(dataset_root):
        metadata_count += sum(1 for f in files if f.endswith('.json') and 'stim' in f)
    
    print(f"\n📁 Found {metadata_count} stimulus metadata files")
    
    if metadata_count > 0:
        print("💡 Run full analysis: python psycho-validator.py --full-fair-report .")

def detect_modality_from_path(file_path):
    """Detect modality from file path"""
    path_lower = file_path.lower()
    for modality in MODALITY_PATTERNS.keys():
        if modality in path_lower:
            return modality
    return 'unknown'

# ----------------------------
# CLI entry point
# ----------------------------
if __name__ == "__main__":
    import argparse
    import sys

    parser = argparse.ArgumentParser(description="Psycho-Validator (BIDS-inspired)")
    parser.add_argument("dataset", nargs='?', default=None, help="Path to dataset root")
    parser.add_argument("-v", "--verbose", action="store_true", 
                       help="Show detailed validation information")
    parser.add_argument("--bids-mode", choices=["auto", "off", "require"], default="auto",
                        help="Use official bids-validator for core BIDS checks: auto=use if installed, off=disable, require=fail if not available")
    parser.add_argument("--schema-info", metavar="MODALITY",
                       help="Display schema details for a specific modality")
    parser.add_argument("--list-versions", action="store_true",
                       help="List all available schema versions")
    parser.add_argument("--bids-schema", action="store_true",
                       help="Show summary of the BIDS schema (via Python package or local JSON)")
    parser.add_argument("--bids-schema-path", type=str, default=None,
                       help="Optional: path to a local BIDS schema JSON file to inspect")
    parser.add_argument("--check-bids-cli", action="store_true",
                       help="Check availability of Node 'bids-validator' and print version")
    parser.add_argument("--check-compatibility", nargs=2, metavar=('SCHEMA_VERSION', 'REQUIRED_VERSION'),
                       help="Check if a schema version is compatible with a required version")
    parser.add_argument("--fair-export", metavar="METADATA_FILE",
                       help="Export metadata in FAIR-compliant formats (Dublin Core, DataCite)")
    parser.add_argument("--fair-check", metavar="METADATA_FILE",
                       help="Evaluate FAIR principles compliance of metadata")
    parser.add_argument("--dataset-fair", metavar="DATASET_ROOT",
                       help="Validate dataset-level FAIR compliance (checks dataset_description.json)")
    parser.add_argument("--create-fair-template", metavar="OUTPUT_FILE",
                       help="Create FAIR-compliant dataset_description.json template")
    parser.add_argument("--full-fair-report", metavar="DATASET_ROOT",
                       help="Generate comprehensive FAIR report for entire dataset")
    parser.add_argument("--fair-summary", metavar="DATASET_ROOT",
                       help="Generate FAIR compliance summary for all metadata files")
    parser.add_argument("--init-bidsignore", action="store_true",
                       help="Create a recommended .bidsignore in the dataset to exclude non-BIDS folders (audio/image/movie/mri, scripts, etc.) from the official validator")
    parser.add_argument("--force-bidsignore", action="store_true",
                       help="Overwrite existing .bidsignore when used with --init-bidsignore")
    args = parser.parse_args()

    if args.schema_info:
        print_schema_info(args.schema_info)
        sys.exit(0)
    
    if args.list_versions:
        list_schema_versions()
        sys.exit(0)

    if args.check_bids_cli:
        exe = shutil.which('bids-validator')
        if exe:
            try:
                out = subprocess.run([exe, '--version'], capture_output=True, text=True)
                print(f"✅ bids-validator available: {out.stdout.strip() or exe}")
            except Exception:
                print("✅ bids-validator found (version check failed)")
        else:
            print("❌ bids-validator not found. Install: npm install -g bids-validator")
        sys.exit(0)

    if args.bids_schema:
        _print_bids_schema_summary(args.bids_schema_path)
        sys.exit(0)
    
    if args.check_compatibility:
        schema_version, required_version = args.check_compatibility
        is_compat = is_compatible_version(schema_version, required_version)
        print(f"Schema version {schema_version} {'IS' if is_compat else 'IS NOT'} compatible with required version {required_version}")
        sys.exit(0 if is_compat else 1)
    
    if args.fair_export:
        from fair_export import export_fair_metadata
        if not os.path.exists(args.fair_export):
            print(f"❌ Metadata file not found: {args.fair_export}")
            sys.exit(1)
        
        print(f"🔄 Exporting FAIR metadata for: {args.fair_export}")
        results = export_fair_metadata(args.fair_export)
        
        success_count = sum(1 for result in results.values() if result)
        total_count = len(results)
        
        if success_count == total_count:
            print(f"✅ All {total_count} FAIR exports completed successfully!")
            sys.exit(0)
        else:
            print(f"⚠️  {success_count}/{total_count} FAIR exports completed")
            sys.exit(1)
    
    if args.fair_check:
        from fair_checker import FAIRComplianceChecker
        if not os.path.exists(args.fair_check):
            print(f"❌ Metadata file not found: {args.fair_check}")
            sys.exit(1)
        
        checker = FAIRComplianceChecker()
        results = checker.evaluate_dataset(args.fair_check)
        
        if 'error' in results:
            print(f"❌ {results['error']}")
            sys.exit(1)
        
        # Display results
        print(f"\n🔍 FAIR Compliance Report: {os.path.basename(args.fair_check)}")
        print("=" * 60)
        
        # Overall grade
        print(f"🎯 Overall Grade: {results['grade']}")
        print(f"📊 Total Score: {results['total_percentage']:.1f}%\n")
        
        # Individual scores
        print("📈 Category Scores:")
        for category, percentage in results['percentages'].items():
            bar_length = int(percentage / 5)  # Scale to 20 chars max
            bar = "█" * bar_length + "░" * (20 - bar_length)
            print(f"  {category.upper():13} [{bar}] {percentage:5.1f}%")
        
        # Recommendations
        print(f"\n💡 Recommendations ({len(results['recommendations'])} items):")
        for i, rec in enumerate(results['recommendations'], 1):
            print(f"  {i:2d}. {rec}")
        
        # Exit with appropriate code
        sys.exit(0 if results['total_percentage'] >= 70 else 1)
    
    if args.dataset_fair:
        validate_dataset_fair(args.dataset_fair)
        sys.exit(0)
    
    if args.create_fair_template:
        create_fair_template(args.create_fair_template)
        sys.exit(0)
    
    if args.full_fair_report:
        generate_full_fair_report(args.full_fair_report)
        sys.exit(0)
        
    if args.fair_summary:
        generate_fair_summary(args.fair_summary)
        sys.exit(0)

    if args.init_bidsignore and not args.dataset:
        parser.error("--init-bidsignore requires: dataset")

    if not args.dataset:
        parser.error("the following arguments are required: dataset")

    if not os.path.exists(args.dataset):
        print(f"❌ Dataset directory not found: {args.dataset}")
        sys.exit(1)

    # Handle .bidsignore initialization
    if args.init_bidsignore:
        bidsignore_path = os.path.join(args.dataset, ".bidsignore")
        if os.path.exists(bidsignore_path) and not args.force_bidsignore:
            print(f"⚠️  .bidsignore already exists at {bidsignore_path} (use --force-bidsignore to overwrite)")
            sys.exit(0)

        lines = [
            "# Ignore non-BIDS custom modalities and helper scripts",
            "scripts/",
            "code/",
            "**/.DS_Store",
            "",
            "# Custom modality folders (kept for psycho-validator)",
            "sub-*/ses-*/audio/",
            "sub-*/ses-*/image/",
            "sub-*/movie/",
            "",
            "# Optional extra MRI container not in BIDS",
            "sub-*/ses-*/mri/",
            "",
            "# Common caches",
            "**/__pycache__/",
            "**/.ipynb_checkpoints/",
        ]
        try:
            with open(bidsignore_path, "w") as f:
                f.write("\n".join(lines) + "\n")
            print(f"✅ Wrote .bidsignore to {bidsignore_path}")
            print("💡 The official bids-validator will now ignore these paths; psycho-validator still checks them.")
        except Exception as e:
            print(f"❌ Failed to write .bidsignore: {e}")
            sys.exit(1)
        sys.exit(0)

    print(f"🔍 Validating dataset: {args.dataset}")
    if args.verbose:
        print(f"📁 Scanning for modalities: {list(MODALITY_PATTERNS.keys())}")
        print(f"📋 Available schemas: {[k for k, v in SCHEMAS.items() if v is not None]}")
    
    # Handle require mode: fail early if not available
    if args.bids_mode == 'require' and shutil.which('bids-validator') is None:
        print("❌ bids-validator not found but --bids-mode=require specified")
        print("💡 Install with: npm install -g bids-validator")
        sys.exit(2)

    problems, stats = validate_dataset(args.dataset, bids_mode=args.bids_mode)

    # Print comprehensive summary
    print_dataset_summary(args.dataset, stats)
    
    # Print validation results
    print_validation_results(problems)
    
    # Exit with appropriate code
    error_count = sum(1 for level, _ in problems if level == "ERROR")
    if error_count > 0:
        sys.exit(1)