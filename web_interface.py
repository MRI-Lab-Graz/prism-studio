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
    # Import modules directly
    import validator
    import reporting
    import stats
    from validator import DatasetValidator
    from reporting import print_dataset_summary
    from stats import DatasetStats
except ImportError as e:
    print(f"Error importing modules: {e}")
    print("Please ensure you're running from the project root and dependencies are installed")
    print(f"Current directory: {os.getcwd()}")
    print(f"Looking for modules in: {src_path}")
    
    # Try alternative import approach
    try:
        # Add current directory to path and try importing src modules
        if os.getcwd() not in sys.path:
            sys.path.insert(0, os.getcwd())
        
        from src.validator import DatasetValidator
        from src.reporting import print_dataset_summary
        from src.stats import DatasetStats
        print("✅ Successfully imported modules using src.* imports")
    except ImportError as e2:
        print(f"Alternative import also failed: {e2}")
        
        # Final fallback - import the main validation function
        try:
            # Import the main validation function from psycho-validator.py
            with open('psycho-validator.py', 'r') as f:
                main_script = f.read()
            
            # Extract just the validation functions
            exec(main_script, globals())
            print("✅ Successfully imported validation functions from main script")
        except Exception as e3:
            print(f"Final fallback failed: {e3}")
            sys.exit(1)

app = Flask(__name__)
app.secret_key = 'psycho-validator-secret-key'  # Change this in production
app.config['MAX_CONTENT_LENGTH'] = 500 * 1024 * 1024  # 500MB max file size

def format_validation_results(issues, dataset_stats, dataset_path):
    """Format validation results in BIDS-validator style with grouped errors"""
    
    # Group issues by error code and type
    error_groups = {}
    warning_groups = {}
    
    valid_files = []
    invalid_files = []
    
    for issue in issues:
        if len(issue) >= 2:
            level, message = issue[0], issue[1]
            file_path = issue[2] if len(issue) > 2 else None
            
            # Extract error code from message if possible
            error_code = 'GENERAL_ERROR'
            if 'Invalid BIDS filename' in message:
                error_code = 'INVALID_BIDS_FILENAME'
            elif 'Missing sidecar' in message:
                error_code = 'MISSING_SIDECAR'
            elif 'schema error' in message:
                error_code = 'SCHEMA_VALIDATION_ERROR'
            elif 'not valid JSON' in message:
                error_code = 'INVALID_JSON'
            elif "doesn't match expected pattern" in message:
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
            else:
                # Valid file
                if file_path:
                    valid_files.append({'path': file_path})
    
    # Calculate summary
    total_errors = sum(group['count'] for group in error_groups.values())
    total_warnings = sum(group['count'] for group in warning_groups.values())
    
    return {
        'valid': total_errors == 0,
        'summary': {
            'total_files': len(valid_files) + len(invalid_files),
            'valid_files': len(valid_files),
            'invalid_files': len(invalid_files),
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
        
        # Validate the dataset
        try:
            # Use the main validation function
            issues, dataset_stats = validate_dataset(dataset_path, verbose=True)
            
            # Convert to structured results format for web display
            results = format_validation_results(issues, dataset_stats, dataset_path)
            
        except NameError:
            # Fallback to class-based validation if function not available
            validator = DatasetValidator()
            issues = []
            dataset_stats = None
            
            # Basic validation fallback
            for root, dirs, files in os.walk(dataset_path):
                for file in files:
                    file_path = os.path.join(root, file)
                    # Basic filename validation
                    filename_issues = validator.validate_filename(file, 'unknown')
                    for level, message in filename_issues:
                        issues.append({
                            'type': level,
                            'code': 'FILENAME_VALIDATION',
                            'message': message,
                            'file': file_path
                        })
            
            results = {
                'valid': len([i for i in issues if i.get('type') != 'ERROR']) == len(issues),
                'errors': [i for i in issues if i.get('type') == 'ERROR'],
                'warnings': [i for i in issues if i.get('type') == 'WARNING'],
                'total_files': len(issues),
                'dataset_path': dataset_path
            }
        
        # Add timestamp
        from datetime import datetime
        results['timestamp'] = datetime.now().isoformat()
        
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
        if os.path.exists(temp_dir):
            shutil.rmtree(temp_dir, ignore_errors=True)
        flash(f'Error processing dataset: {str(e)}', 'error')
        return redirect(url_for('index'))

def process_folder_upload(files, temp_dir):
    """Process uploaded folder files and recreate directory structure"""
    dataset_root = os.path.join(temp_dir, 'dataset')
    os.makedirs(dataset_root, exist_ok=True)
    
    for file in files:
        if file.filename:
            # Get the relative path from the browser
            relative_path = file.filename
            if hasattr(file, 'filename') and '/' in file.filename:
                # Handle webkitRelativePath
                relative_path = file.filename
            
            # Create the full path
            file_path = os.path.join(dataset_root, relative_path)
            
            # Create directories if they don't exist
            os.makedirs(os.path.dirname(file_path), exist_ok=True)
            
            # Save the file
            file.save(file_path)
    
    return dataset_root

def process_zip_upload(file, temp_dir, filename):
    """Process uploaded ZIP file"""
    file_path = os.path.join(temp_dir, filename)
    file.save(file_path)
    
    # Extract ZIP file
    with zipfile.ZipFile(file_path, 'r') as zip_ref:
        zip_ref.extractall(temp_dir)
    
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
        # Validate the dataset
        validator = DatasetValidator()
        results = validator.validate_dataset(folder_path)
        
        # Store results
        result_id = f"result_{len(validation_results)}"
        validation_results[result_id] = {
            'results': results,
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
    
    # Calculate summary statistics
    total_files = len(results.get('valid_files', [])) + len(results.get('invalid_files', []))
    valid_files = len(results.get('valid_files', []))
    invalid_files = len(results.get('invalid_files', []))
    
    # Group errors and warnings by type
    error_groups = {}
    warning_groups = {}
    
    for error in results.get('errors', []):
        error_type = error.get('type', 'General')
        if error_type not in error_groups:
            error_groups[error_type] = []
        error_groups[error_type].append(error)
    
    for warning in results.get('warnings', []):
        warning_type = warning.get('type', 'General')
        if warning_type not in warning_groups:
            warning_groups[warning_type] = []
        warning_groups[warning_type].append(warning)
    
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
                         total_files=total_files,
                         valid_files=valid_files,
                         invalid_files=invalid_files,
                         error_groups=error_groups,
                         warning_groups=warning_groups,
                         dataset_stats=dataset_stats)

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