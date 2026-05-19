import json
import shutil
import os
import sys
from pathlib import Path

# Add paths to sys.path
sys.path.insert(0, os.path.join(os.getcwd(), 'app'))
sys.path.insert(0, os.path.join(os.getcwd(), 'app/src'))

from project_manager import ProjectManager

project_path = '/Volumes/Thunder/129_PK01/rawdata'
project = Path(project_path)
subject = project / 'sub-001'
pm = ProjectManager()

datalad_path = shutil.which('datalad')
print(f"datalad_executable: {datalad_path}")

try:
    status = pm.get_datalad_status(project_path)
    print("datalad_status:")
    print(json.dumps(status, indent=2))
except Exception as e:
    print(f"Error getting status: {e}")

try:
    print("Starting _create_nested_subdatasets...")
    result = pm._create_nested_subdatasets(project, datalad_path or '')
    print("nested_result:")
    print(json.dumps(result, indent=2))
except Exception as e:
    print(f"Error creating nested subdatasets: {e}")

has_git = (subject / '.git').exists()
has_datalad = (subject / '.datalad').exists()
print(f"sub-001_has_git: {has_git}")
print(f"sub-001_has_datalad: {has_datalad}")
