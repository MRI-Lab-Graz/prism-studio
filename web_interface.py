"""
Web interface for psycho-validator
A simple Flask web app that provides a user-friendly interface for dataset validation
"""

import os
import sys
import json
import tempfile
import shutil
from pathlib import Path
from flask import Flask, render_template, request, jsonify, send_file, flash, redirect, url_for
from werkzeug.utils import secure_filename
import zipfile
import io

# Add src to path
src_path = os.path.join(os.path.dirname(__file__), 'src')
if src_path not in sys.path:
    sys.path.insert(0, src_path)
try:
    from src.validator import DatasetValidator
    from src.reporting import print_dataset_summary
    from src.stats import DatasetStats
    # Import the canonical validate_dataset from src.runner
    from src.runner import validate_dataset
except ImportError as e:
    print(f"Error importing core modules: {e}")
    print("Ensure you're running from the project root and that .venv is activated")
    sys.exit(1)

app = Flask(__name__)
app.secret_key = 'psycho-validator-secret-key'  # Change this in production
app.config['MAX_CONTENT_LENGTH'] = 100 * 1024 * 1024  # 100MB max file size (metadata only)

# File extensions to process (metadata and small data files only)
# We skip large neuroimaging data files - we only validate their JSON sidecars
METADATA_EXTENSIONS = {
    '.json',      # Sidecar metadata
    '.tsv',       # Behavioral/events data
    '.csv',       # Alternative tabular format
    '.txt',       # Text data/logs
    '.edf',       # EEG/eye-tracking (relatively small)
    '.bdf',       # BioSemi EEG format
}

# Extensions to SKIP (large data files we don't need)
SKIP_EXTENSIONS = {
    '.nii', '.nii.gz',      # NIfTI neuroimaging (can be GB)
    '.mp4', '.avi', '.mov',  # Video files
    '.png', '.jpg', '.jpeg', '.tiff',  # Large images
    '.eeg', '.dat', '.fif',  # Large electrophysiology raw data
    '.mat',                  # MATLAB files (can be large)
}

def format_validation_results(issues, dataset_stats, dataset_path):
    """Format validation results in BIDS-validator style with grouped errors"""
    # Group issues by error code and type
    error_groups = {}
    warning_groups = {}

    valid_files = []
    invalid_files = []
    file_paths = set()

    def extract_path_from_message(msg):
        """Try to heuristically extract a file path or filename from a validator message."""
        if not msg:
            return None
        # If message explicitly contains an absolute path
        import re
        abs_path_match = re.search(r"(/[^\s:,]+\.[A-Za-z0-9]+(?:\.gz)?)", msg)
        if abs_path_match:
            return abs_path_match.group(1)
        # dataset_description.json special case
        if 'dataset_description.json' in msg:
            return os.path.join(dataset_path or '', 'dataset_description.json')
        # Look for sub-... filenames like sub-01_task-foo_blah.ext
        name_match = re.search(r"(sub-[A-Za-z0-9._-]+\.[A-Za-z0-9]+(?:\.gz)?)", msg)
        if name_match:
            return os.path.join(dataset_path or '', name_match.group(1))
        # Generic filename with extension (e.g., task-recognition_stim.json)
        generic_match = re.search(r"([A-Za-z0-9._\-]+\.(?:json|tsv|edf|nii|nii\.gz|txt|csv|mp4|png|jpg|jpeg))", msg)
        if generic_match:
            return os.path.join(dataset_path or '', generic_match.group(1))
        return None

    for issue in issues:
        # Support tuples like (level, message) or (level, message, path)
        if isinstance(issue, dict):
            level = issue.get('type') or issue.get('level') or issue.get('severity') or 'ERROR'
            message = issue.get('message', '')
            file_path = issue.get('file')
        elif isinstance(issue, (list, tuple)):
            if len(issue) >= 2:
                level, message = issue[0], issue[1]
                file_path = issue[2] if len(issue) > 2 else None
            else:
                continue
        else:
            # Unknown shape: stringify
            level = 'ERROR'
            message = str(issue)
            file_path = None

        if not file_path:
            file_path = extract_path_from_message(message)

        if file_path:
            file_paths.add(file_path)

        # Extract error code from message if possible
        error_code = 'GENERAL_ERROR'
        if 'Invalid BIDS filename' in message or 'Invalid BIDS filename format' in message:
            error_code = 'INVALID_BIDS_FILENAME'
        elif 'Missing sidecar' in message or 'Missing sidecar for' in message:
            error_code = 'MISSING_SIDECAR'
        elif 'schema error' in message:
            error_code = 'SCHEMA_VALIDATION_ERROR'
        elif 'not valid JSON' in message or 'is not valid JSON' in message:
            error_code = 'INVALID_JSON'
        elif "doesn't match expected pattern" in message or 'doesn\'t match expected pattern' in message:
            error_code = 'FILENAME_PATTERN_MISMATCH'

        formatted_issue = {
            'code': error_code,
            'message': message,
            'file': file_path,
            'level': level
        }

        if level == 'ERROR':
            if error_code not in error_groups:
                error_groups[error_code] = {
                    'code': error_code,
                    'description': get_error_description(error_code),
                    'files': [],
                    'count': 0
                }
            error_groups[error_code]['files'].append(formatted_issue)
            error_groups[error_code]['count'] += 1

            if file_path:
                invalid_files.append({'path': file_path, 'errors': [message]})

        elif level == 'WARNING':
            if error_code not in warning_groups:
                warning_groups[error_code] = {
                    'code': error_code,
                    'description': get_error_description(error_code),
                    'files': [],
                    'count': 0
                }
            warning_groups[error_code]['files'].append(formatted_issue)
            warning_groups[error_code]['count'] += 1

            if file_path:
                valid_files.append({'path': file_path})  # Warnings don't make files invalid
        else:
            # Treat other levels as info/valid
            if file_path:
                valid_files.append({'path': file_path})
    
    # If we don't have file paths from issues, prefer dataset_stats total
    try:
        stats_total = getattr(dataset_stats, 'total_files', 0)
    except Exception:
        stats_total = 0

    # Prefer authoritative dataset_stats.total_files when available so counts align
    if stats_total:
        total_files = stats_total
    else:
        total_files = len(file_paths) if file_paths else len(valid_files) + len(invalid_files)

    # Calculate summary
    total_errors = sum(group['count'] for group in error_groups.values())
    total_warnings = sum(group['count'] for group in warning_groups.values())

    # Count valid vs invalid files
    invalid_file_paths = {f['path'] for f in invalid_files if f.get('path')}
    invalid_count = len(invalid_file_paths)
    # If we have dataset total, infer valid_count
    if stats_total:
        valid_count = max(0, stats_total - invalid_count)
    else:
        valid_count = total_files - invalid_count
    
    return {
        'valid': total_errors == 0,
        'summary': {
            'total_files': total_files,
            'valid_files': valid_count,
            'invalid_files': invalid_count,
            'total_errors': total_errors,
            'total_warnings': total_warnings
        },
        'error_groups': error_groups,
        'warning_groups': warning_groups,
        'valid_files': valid_files,
        'invalid_files': invalid_files,
        'errors': [item for group in error_groups.values() for item in group['files']],
        'warnings': [item for group in warning_groups.values() for item in group['files']],
        'dataset_path': dataset_path,
        'dataset_stats': dataset_stats
    }

def get_error_description(error_code):
    """Get user-friendly descriptions for error codes"""
    descriptions = {
        'INVALID_BIDS_FILENAME': 'Filenames must follow BIDS naming convention (sub-<label>_[ses-<label>_]...)',
        'MISSING_SIDECAR': 'Required JSON sidecar files are missing for data files',
        'SCHEMA_VALIDATION_ERROR': 'JSON sidecar content does not match required schema',
        'INVALID_JSON': 'JSON files contain syntax errors or are not valid JSON',
        'FILENAME_PATTERN_MISMATCH': 'Filenames do not match expected patterns for their modality',
        'GENERAL_ERROR': 'General validation error'
    }
    return descriptions.get(error_code, 'Validation error')

def get_error_documentation_url(error_code):
    """Get documentation URL for an error code"""
    # Map error codes to documentation anchors
    base_url = "https://github.com/MRI-Lab-Graz/psycho-validator/blob/main/docs/ERROR_CODES.md"
    
    doc_anchors = {
        'INVALID_BIDS_FILENAME': f"{base_url}#invalid_bids_filename",
        'MISSING_SIDECAR': f"{base_url}#missing_sidecar",
        'SCHEMA_VALIDATION_ERROR': f"{base_url}#schema_validation_error",
        'INVALID_JSON': f"{base_url}#invalid_json",
        'FILENAME_PATTERN_MISMATCH': f"{base_url}#filename_pattern_mismatch",
        'GENERAL_ERROR': base_url
    }
    return doc_anchors.get(error_code, base_url)

def shorten_path(file_path, max_parts=3):
    """Shorten a file path to show only the last N parts with ellipsis"""
    if not file_path:
        return 'General'
    
    parts = file_path.replace('\\', '/').split('/')
    if len(parts) <= max_parts:
        return '/'.join(parts)
    
    return '.../' + '/'.join(parts[-max_parts:])

def get_filename_from_path(file_path):
    """Extract just the filename from a path"""
    if not file_path:
        return 'General'
    return os.path.basename(file_path)

# Global storage for validation results
validation_results = {}

@app.route('/')
def index():
    """Main page with upload form"""
    return render_template('index.html')

@app.route('/upload', methods=['POST'])
def upload_dataset():
    """Handle dataset upload and validation"""
    if 'dataset' not in request.files:
        flash('No dataset uploaded', 'error')
        return redirect(url_for('index'))
    
    files = request.files.getlist('dataset')
    if not files or (len(files) == 1 and files[0].filename == ''):
        flash('No files selected', 'error')
        return redirect(url_for('index'))
    
    # Create temporary directory for processing
    temp_dir = tempfile.mkdtemp(prefix='psycho_validator_')
    
    try:
        # Check if this is a folder upload (multiple files) or ZIP upload (single file)
        if len(files) > 1 or (len(files) == 1 and not files[0].filename.lower().endswith('.zip')):
            # Handle folder upload
            dataset_path = process_folder_upload(files, temp_dir)
            filename = f"folder_upload_{len(files)}_files"
        else:
            # Handle ZIP upload
            file = files[0]
            filename = secure_filename(file.filename)
            if not filename.lower().endswith('.zip'):
                flash('Please upload a ZIP file or select a folder', 'error')
                shutil.rmtree(temp_dir, ignore_errors=True)
                return redirect(url_for('index'))
            
            dataset_path = process_zip_upload(file, temp_dir, filename)
        
        # DEBUG: Print dataset_path and sample files
        print(f"📁 [UPLOAD] Validating dataset at: {dataset_path}")
        for root, dirs, files in os.walk(dataset_path):
            for file in files[:10]:
                print(f"   {os.path.relpath(os.path.join(root, file), dataset_path)}")
            break
        # Validate the dataset
        validate_fn = globals().get('validate_dataset')
        if callable(validate_fn):
            issues, dataset_stats = validate_fn(dataset_path, verbose=True)
            results = format_validation_results(issues, dataset_stats, dataset_path)
        else:
            # Fallback to class-based scanning using DatasetValidator and DatasetStats
            validator = DatasetValidator()
            ds = DatasetStats()
            issues = []

            for root, dirs, files in os.walk(dataset_path):
                for file in files:
                    if file.startswith('.'):
                        continue
                    file_path = os.path.join(root, file)
                    # try to infer modality from parent dir name
                    modality = os.path.basename(os.path.dirname(file_path)) or 'unknown'
                    filename_issues = validator.validate_filename(file, modality)
                    for level, message in filename_issues:
                        # normalize to tuple form (level, message, file_path)
                        issues.append((level, message, file_path))
                    # sidecar validation for non-json files
                    if not file.endswith('.json'):
                        sidecar_issues = validator.validate_sidecar(file_path, modality, dataset_path)
                        for level, message in sidecar_issues:
                            issues.append((level, message, file_path))
                    # update stats
                    # try to derive subject/session/task from filename pattern like sub-XX
                    subject_id = None
                    session_id = None
                    task = None
                    try:
                        # naive extraction
                        import re
                        m = re.search(r'sub-[A-Za-z0-9]+' , file)
                        if m:
                            subject_id = m.group(0)
                        s = re.search(r'ses-[A-Za-z0-9]+', file)
                        if s:
                            session_id = s.group(0)
                        t = re.search(r'task-[A-Za-z0-9]+', file)
                        if t:
                            task = t.group(0)
                    except:
                        pass
                    ds.add_file(subject_id or 'unknown', session_id, modality, task, file)

            dataset_stats = ds
            results = format_validation_results(issues, dataset_stats, dataset_path)
        
        # Add timestamp
        from datetime import datetime
        results['timestamp'] = datetime.now().isoformat()
        
        # DEBUG: Print summary to console
        print(f"📊 Validation complete:")
        print(f"   Total files: {results['summary']['total_files']}")
        print(f"   Valid files: {results['summary']['valid_files']}")
        print(f"   Invalid files: {results['summary']['invalid_files']}")
        print(f"   Total errors: {results['summary']['total_errors']}")
        
        # Store results globally (in production, use a database)
        result_id = f"result_{len(validation_results)}"
        validation_results[result_id] = {
            'results': results,
            'dataset_path': dataset_path,
            'temp_dir': temp_dir,
            'filename': filename
        }
        
        return redirect(url_for('show_results', result_id=result_id))
        
    except Exception as e:
        # Clean up on error
        print(f"❌ [UPLOAD ERROR] {type(e).__name__}: {str(e)}")
        import traceback
        traceback.print_exc()
        if os.path.exists(temp_dir):
            shutil.rmtree(temp_dir, ignore_errors=True)
        flash(f'Error processing dataset: {str(e)}', 'error')
        return redirect(url_for('index'))

def process_folder_upload(files, temp_dir):
    """Process uploaded folder files and recreate directory structure
    
    Only processes metadata files (JSON, TSV, etc.) to reduce upload size.
    Creates placeholders for skipped large data files based on all_files list.
    """
    dataset_root = os.path.join(temp_dir, 'dataset')
    os.makedirs(dataset_root, exist_ok=True)
    
    processed_count = 0
    skipped_count = 0
    
    # Get the list of all files (including skipped ones) from form data
    all_files_json = request.form.get('all_files')
    all_files_list = json.loads(all_files_json) if all_files_json else []
    
    # Create a set of uploaded file paths for quick lookup
    uploaded_paths = set()
    
    for file in files:
        if file.filename:
            relative_path = file.filename
            
            # Strip the dataset name prefix if present (e.g., "107/" -> "")
            # Browser uploads may include the folder name as a prefix
            path_parts = relative_path.split('/')
            if path_parts and not path_parts[0].startswith('sub-'):
                # First part is not a subject dir, so it's likely the dataset name - skip it
                relative_path = '/'.join(path_parts[1:])
            
            # Skip if the path is empty or just a directory (no filename)
            if not relative_path or relative_path.endswith('/'):
                continue
            
            uploaded_paths.add(relative_path)
            
            # Save the metadata file
            file_path = os.path.join(dataset_root, relative_path)
            os.makedirs(os.path.dirname(file_path), exist_ok=True)
            file.save(file_path)
            processed_count += 1
    
    # Create placeholders for all files that weren't uploaded
    for relative_path in all_files_list:
        # Strip the dataset name prefix if present
        path_parts = relative_path.split('/')
        if path_parts and not path_parts[0].startswith('sub-'):
            relative_path = '/'.join(path_parts[1:])
        
        if relative_path not in uploaded_paths:
            file_path = os.path.join(dataset_root, relative_path)
            os.makedirs(os.path.dirname(file_path), exist_ok=True)
            # Create empty placeholder
            with open(file_path, 'w') as f:
                f.write('')
            skipped_count += 1
    
    print(f"📁 Processed {processed_count} metadata files, created {skipped_count} placeholders for data files")
    # DEBUG: Print the full file tree
    print(f"📁 [UPLOAD] File tree in temp_dir after upload:")
    for root, dirs, files in os.walk(dataset_root):
        for file in files:
            rel_path = os.path.relpath(os.path.join(root, file), dataset_root)
            print(f"   {rel_path}")
    return dataset_root

def process_zip_upload(file, temp_dir, filename):
    """Process uploaded ZIP file
    
    Extracts only metadata files from ZIP to reduce processing time and storage.
    """
    file_path = os.path.join(temp_dir, filename)
    file.save(file_path)
    
    processed_count = 0
    skipped_count = 0
    
    # Extract ZIP file selectively
    with zipfile.ZipFile(file_path, 'r') as zip_ref:
        for zip_info in zip_ref.namelist():
            # Skip directories
            if zip_info.endswith('/'):
                continue
            
            # Check file extension
            _, ext = os.path.splitext(zip_info.lower())
            if ext == '.gz' and zip_info.lower().endswith('.nii.gz'):
                ext = '.nii.gz'
            
            # Extract metadata files, skip large data files
            if ext in METADATA_EXTENSIONS or ext == '':
                zip_ref.extract(zip_info, temp_dir)
                processed_count += 1
            elif ext in SKIP_EXTENSIONS:
                # Create empty placeholder
                extract_path = os.path.join(temp_dir, zip_info)
                os.makedirs(os.path.dirname(extract_path), exist_ok=True)
                with open(extract_path, 'w') as f:
                    f.write('')
                skipped_count += 1
    
    print(f"📦 Extracted {processed_count} metadata files, skipped {skipped_count} data files from ZIP")
    
    # Find the actual dataset directory (might be nested)
    return find_dataset_root(temp_dir)

@app.route('/validate_folder', methods=['POST'])
def validate_folder():
    """Handle local folder validation"""
    folder_path = request.form.get('folder_path', '').strip()
    
    if not folder_path:
        flash('Please provide a folder path', 'error')
        return redirect(url_for('index'))
    
    if not os.path.exists(folder_path):
        flash('Folder does not exist', 'error')
        return redirect(url_for('index'))
    
    if not os.path.isdir(folder_path):
        flash('Path is not a directory', 'error')
        return redirect(url_for('index'))
    
    try:
        # Validate the dataset using canonical runner
        issues, stats = validate_dataset(folder_path, verbose=False)
        
        # Format results for web display
        formatted_results = format_validation_results(issues, stats, folder_path)
        
        # Store results
        result_id = f"result_{len(validation_results)}"
        validation_results[result_id] = {
            'results': formatted_results,
            'dataset_path': folder_path,
            'temp_dir': None,  # No temp dir for local folders
            'filename': os.path.basename(folder_path)
        }
        
        return redirect(url_for('show_results', result_id=result_id))
        
    except Exception as e:
        flash(f'Error validating dataset: {str(e)}', 'error')
        return redirect(url_for('index'))

@app.route('/results/<result_id>')
def show_results(result_id):
    """Display validation results"""
    if result_id not in validation_results:
        flash('Results not found', 'error')
        return redirect(url_for('index'))
    
    data = validation_results[result_id]
    results = data['results']
    
    # Get dataset stats if available
    dataset_stats = None
    if results.get('dataset_description'):
        try:
            stats = DatasetStats(data['dataset_path'])
            dataset_stats = {
                'total_subjects': len(stats.subjects),
                'total_sessions': len(stats.sessions),
                'modalities': stats.modality_counts,
                'tasks': list(stats.tasks)
            }
        except:
            pass
    
    return render_template('results.html', 
                         results=results,
                         result_id=result_id,
                         filename=data['filename'],
                         dataset_stats=dataset_stats,
                         shorten_path=shorten_path,
                         get_filename_from_path=get_filename_from_path,
                         get_error_documentation_url=get_error_documentation_url)

@app.route('/download_report/<result_id>')
def download_report(result_id):
    """Download validation report as JSON"""
    if result_id not in validation_results:
        flash('Results not found', 'error')
        return redirect(url_for('index'))
    
    data = validation_results[result_id]
    results = data['results']
    
    # Create JSON report
    report = {
        'dataset': data['filename'],
        'validation_timestamp': results.get('timestamp', ''),
        'summary': {
            'total_files': len(results.get('valid_files', [])) + len(results.get('invalid_files', [])),
            'valid_files': len(results.get('valid_files', [])),
            'invalid_files': len(results.get('invalid_files', [])),
            'total_errors': len(results.get('errors', [])),
            'total_warnings': len(results.get('warnings', []))
        },
        'results': results
    }
    
    # Create in-memory file
    output = io.BytesIO()
    output.write(json.dumps(report, indent=2).encode('utf-8'))
    output.seek(0)
    
    return send_file(
        output,
        mimetype='application/json',
        as_attachment=True,
        download_name=f'validation_report_{data["filename"]}.json'
    )

@app.route('/cleanup/<result_id>')
def cleanup(result_id):
    """Clean up temporary files"""
    if result_id in validation_results:
        data = validation_results[result_id]
        if data['temp_dir'] and os.path.exists(data['temp_dir']):
            shutil.rmtree(data['temp_dir'], ignore_errors=True)
        del validation_results[result_id]
    
    flash('Results cleaned up', 'success')
    return redirect(url_for('index'))

@app.route('/api/validate', methods=['POST'])
def api_validate():
    """API endpoint for validation (for programmatic access)"""
    try:
        data = request.get_json()
        if not data or 'dataset_path' not in data:
            return jsonify({'error': 'Missing dataset_path parameter'}), 400
        
        dataset_path = data['dataset_path']
        if not os.path.exists(dataset_path):
            return jsonify({'error': 'Dataset path does not exist'}), 400
        
        validator = DatasetValidator()
        results = validator.validate_dataset(dataset_path)
        
        return jsonify(results)
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

def find_dataset_root(extract_dir):
    """Find the actual dataset root directory after extraction"""
    # Look for dataset_description.json or typical BIDS structure
    for root, dirs, files in os.walk(extract_dir):
        if 'dataset_description.json' in files:
            return root
        # Look for subject directories
        if any(d.startswith('sub-') for d in dirs):
            return root
    
    # If no clear dataset structure, return the extraction directory
    return extract_dir

def main():
    """Run the web application"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Psycho-Validator Web Interface')
    parser.add_argument('--host', default='127.0.0.1', help='Host to bind to (default: 127.0.0.1)')
    parser.add_argument('--port', type=int, default=5000, help='Port to bind to (default: 5000)')
    parser.add_argument('--debug', action='store_true', help='Run in debug mode')
    parser.add_argument('--public', action='store_true', help='Allow external connections (sets host to 0.0.0.0)')
    
    args = parser.parse_args()
    
    host = '0.0.0.0' if args.public else args.host
    
    print("🌐 Starting Psycho-Validator Web Interface")
    print(f"🔗 Open your browser to: http://{host}:{args.port}")
    if args.public:
        print("⚠️  Warning: Running in public mode - accessible from other computers")
    print("💡 Press Ctrl+C to stop the server")
    print()
    
    app.run(host=host, port=args.port, debug=args.debug)

if __name__ == '__main__':
    main()