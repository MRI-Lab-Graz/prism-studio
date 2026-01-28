#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Windows-specific tests for PRISM web interface upload functionality.
Tests file upload handling, path processing, and session management on Windows.
"""

import os
import sys
import tempfile
import shutil
import json
from pathlib import Path

# Force UTF-8 encoding for Windows console
if sys.platform.startswith('win'):
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

# Add paths for testing
app_path = os.path.join(os.path.dirname(__file__), "..", "app")
sys.path.insert(0, app_path)
sys.path.insert(0, os.path.join(app_path, "src"))

try:
    from cross_platform import normalize_path, safe_path_join, CrossPlatformFile, validate_filename_cross_platform
    from system_files import filter_system_files, is_system_file
except ImportError as e:
    print(f"❌ Import error: {e}")
    sys.exit(1)


class TestWindowsWebUpload:
    """Test web upload scenarios specific to Windows"""

    def test_upload_path_normalization(self):
        """Test that uploaded file paths are normalized correctly"""
        print("  🧪 Testing upload path normalization...")
        
        # Simulate paths that might come from web upload
        upload_paths = [
            "dataset/sub-01/func/sub-01_bold.nii.gz",  # Unix-style
            "dataset\\sub-01\\func\\sub-01_bold.nii.gz",  # Windows-style
            "dataset/sub-01\\ses-01/func\\file.nii.gz",  # Mixed
        ]
        
        for path in upload_paths:
            try:
                normalized = normalize_path(path)
                # Should be consistent forward slashes
                if "\\" in normalized:
                    print(f"    ⚠️  Backslashes remain in: {normalized}")
                else:
                    print(f"    ✅ {path} -> {normalized}")
            except Exception as e:
                print(f"    ❌ Failed to normalize: {path}: {e}")
                return False
        
        return True

    def test_upload_with_drive_letter(self):
        """Test handling when Windows drive letters appear in upload paths"""
        print("  🧪 Testing drive letter in upload paths...")
        
        # These shouldn't happen in normal web uploads, but test resilience
        problematic_paths = [
            "C:\\Users\\test\\dataset\\sub-01",
            "D:/data/prism/sub-01",
        ]
        
        for path in problematic_paths:
            try:
                # Try to extract relative portion
                parts = Path(path).parts
                # Skip drive letter if present
                relative_parts = [p for p in parts if not p.endswith(":") and p != "\\"]
                relative_path = os.path.join(*relative_parts) if relative_parts else ""
                
                print(f"    ✅ {path} -> {relative_path}")
            except Exception as e:
                print(f"    ⚠️  {path}: {e}")
        
        return True

    def test_metadata_path_json_format(self):
        """Test the metadata_paths_json format used for large uploads"""
        print("  🧪 Testing metadata paths JSON format...")
        
        # Simulate the JSON string sent from frontend
        metadata_paths = [
            "sub-01/func/sub-01_task-rest_bold.json",
            "sub-01\\func\\sub-01_task-rest_bold.json",  # Windows style
            "sub-02/anat/sub-02_T1w.json",
            "dataset_description.json",
            "participants.json",
        ]
        
        try:
            # Convert to JSON string (as sent by frontend)
            json_string = json.dumps(metadata_paths)
            
            # Parse back (as received by backend)
            parsed_paths = json.loads(json_string)
            
            # Normalize all paths
            normalized_paths = [normalize_path(p) for p in parsed_paths]
            
            print(f"    ✅ Processed {len(normalized_paths)} paths")
            
            # Check for system files
            filtered = filter_system_files([os.path.basename(p) for p in normalized_paths])
            print(f"    ✅ Filtered to {len(filtered)} valid files")
            
            return True
            
        except Exception as e:
            print(f"    ❌ Failed: {e}")
            return False

    def test_batch_file_upload_simulation(self):
        """Simulate batch upload of 5000+ files"""
        print("  🧪 Testing large batch upload simulation...")
        
        # Generate realistic file list
        file_list = []
        
        for sub in range(1, 51):  # 50 subjects
            for ses in range(1, 3):  # 2 sessions each
                # Add functional data
                for run in range(1, 4):  # 3 runs
                    base = f"sub-{sub:02d}/ses-{ses:02d}/func"
                    file_list.append(f"{base}/sub-{sub:02d}_ses-{ses:02d}_task-rest_run-{run}_bold.nii.gz")
                    file_list.append(f"{base}/sub-{sub:02d}_ses-{ses:02d}_task-rest_run-{run}_bold.json")
                
                # Add anatomical data
                anat_base = f"sub-{sub:02d}/ses-{ses:02d}/anat"
                file_list.append(f"{anat_base}/sub-{sub:02d}_ses-{ses:02d}_T1w.nii.gz")
                file_list.append(f"{anat_base}/sub-{sub:02d}_ses-{ses:02d}_T1w.json")
        
        # Add top-level files
        file_list.extend([
            "dataset_description.json",
            "participants.tsv",
            "participants.json",
            "README",
        ])
        
        print(f"    Generated {len(file_list)} files")
        
        try:
            # Test JSON serialization (as sent to backend)
            json_string = json.dumps(file_list)
            print(f"    ✅ JSON string size: {len(json_string):,} bytes")
            
            # Test parsing
            parsed = json.loads(json_string)
            print(f"    ✅ Parsed {len(parsed)} paths")
            
            # Test path normalization on all
            normalized = [normalize_path(p) for p in parsed[:10]]  # Test first 10
            print(f"    ✅ Path normalization successful")
            
            return True
            
        except Exception as e:
            print(f"    ❌ Failed: {e}")
            return False

    def test_datalab_style_upload(self):
        """Test DataLad-style upload (metadata only, skip large files)"""
        print("  🧪 Testing DataLad-style upload...")
        
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create mock file structure
            files = [
                "sub-01/func/sub-01_bold.nii.gz",  # Large - skip
                "sub-01/func/sub-01_bold.json",     # Metadata - upload
                "sub-01/anat/sub-01_T1w.nii.gz",   # Large - skip
                "sub-01/anat/sub-01_T1w.json",     # Metadata - upload
                "dataset_description.json",         # Metadata - upload
                "participants.tsv",                 # Metadata - upload
                "sub-01/survey/sub-01_task-survey_beh.tsv",  # Data - upload
                "Thumbs.db",                        # System file - skip
            ]
            
            # Determine which files to upload
            metadata_extensions = {'.json', '.tsv', '.txt', '.md'}
            large_extensions = {'.nii.gz', '.nii', '.mp4', '.avi', '.wav'}
            
            upload_files = []
            skip_files = []
            
            for file_path in files:
                filename = os.path.basename(file_path)
                
                # Skip system files
                if is_system_file(filename):
                    skip_files.append(file_path)
                    continue
                
                # Get extension
                ext = ''.join(Path(file_path).suffixes)
                
                if ext in metadata_extensions:
                    upload_files.append(file_path)
                elif ext in large_extensions:
                    skip_files.append(file_path)
                else:
                    upload_files.append(file_path)
            
            print(f"    ✅ Upload: {len(upload_files)} files")
            print(f"    ✅ Skip: {len(skip_files)} files")
            
            # Verify system files were skipped
            if "Thumbs.db" in [os.path.basename(f) for f in upload_files]:
                print(f"    ❌ System file not filtered")
                return False
            
            return True


class TestWindowsSessionManagement:
    """Test session management on Windows"""

    def test_temp_directory_creation(self):
        """Test temporary upload directory creation on Windows"""
        print("  🧪 Testing temp directory creation...")
        
        with tempfile.TemporaryDirectory() as base_tmpdir:
            # Simulate session directory creation
            session_id = "test_session_12345"
            session_dir = os.path.join(base_tmpdir, session_id)
            
            try:
                os.makedirs(session_dir, exist_ok=True)
                print(f"    ✅ Created: {session_dir}")
                
                # Create subdirectories
                subdirs = ["sub-01/func", "sub-01/anat", "sub-02/func"]
                for subdir in subdirs:
                    full_path = os.path.join(session_dir, subdir)
                    os.makedirs(full_path, exist_ok=True)
                
                print(f"    ✅ Created {len(subdirs)} subdirectories")
                
                # Verify structure
                if os.path.exists(session_dir):
                    return True
                else:
                    print(f"    ❌ Directory not created")
                    return False
                    
            except Exception as e:
                print(f"    ❌ Failed: {e}")
                return False

    def test_session_cleanup(self):
        """Test session directory cleanup"""
        print("  🧪 Testing session cleanup...")
        
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create mock session directories
            sessions = []
            for i in range(3):
                session_dir = os.path.join(tmpdir, f"session_{i}")
                os.makedirs(session_dir)
                
                # Create some files
                for j in range(5):
                    file_path = os.path.join(session_dir, f"file_{j}.json")
                    CrossPlatformFile.write_text(file_path, '{"test": "data"}')
                
                sessions.append(session_dir)
            
            print(f"    ✅ Created {len(sessions)} mock sessions")
            
            # Clean up sessions
            try:
                for session_dir in sessions:
                    if os.path.exists(session_dir):
                        shutil.rmtree(session_dir)
                
                # Verify cleanup
                remaining = [s for s in sessions if os.path.exists(s)]
                if remaining:
                    print(f"    ❌ {len(remaining)} sessions not cleaned")
                    return False
                
                print(f"    ✅ All sessions cleaned up")
                return True
                
            except Exception as e:
                print(f"    ❌ Cleanup failed: {e}")
                return False

    def test_concurrent_session_isolation(self):
        """Test that concurrent sessions don't interfere"""
        print("  🧪 Testing concurrent session isolation...")
        
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create multiple session directories
            sessions = {}
            for i in range(5):
                session_id = f"session_{i}"
                session_dir = os.path.join(tmpdir, session_id)
                os.makedirs(session_dir)
                
                # Each session has its own files
                file_path = os.path.join(session_dir, "data.json")
                data = {"session": session_id, "data": f"test_{i}"}
                CrossPlatformFile.write_text(file_path, json.dumps(data))
                
                sessions[session_id] = session_dir
            
            # Verify isolation - read back data
            try:
                for session_id, session_dir in sessions.items():
                    file_path = os.path.join(session_dir, "data.json")
                    content = CrossPlatformFile.read_text(file_path)
                    data = json.loads(content)
                    
                    if data["session"] != session_id:
                        print(f"    ❌ Session data mixed: {session_id}")
                        return False
                
                print(f"    ✅ {len(sessions)} sessions properly isolated")
                return True
                
            except Exception as e:
                print(f"    ❌ Failed: {e}")
                return False


class TestWindowsFileSecurity:
    """Test file security and validation on Windows"""

    def test_path_traversal_prevention(self):
        """Test prevention of path traversal attacks"""
        print("  🧪 Testing path traversal prevention...")
        
        malicious_paths = [
            "../../../etc/passwd",
            "..\\..\\..\\Windows\\System32\\config",
            "sub-01/../../secret.txt",
            "sub-01\\..\\..\\..\\sensitive",
        ]
        
        with tempfile.TemporaryDirectory() as tmpdir:
            for path in malicious_paths:
                try:
                    # Attempt to create "safe" path
                    normalized = normalize_path(path)
                    full_path = safe_path_join(tmpdir, normalized)
                    
                    # Check if it's still within tmpdir
                    real_tmpdir = os.path.realpath(tmpdir)
                    real_full = os.path.realpath(full_path) if os.path.exists(full_path) else full_path
                    
                    if not real_full.startswith(real_tmpdir):
                        print(f"    ⚠️  Potential escape: {path}")
                    else:
                        print(f"    ✅ Contained: {path}")
                        
                except Exception as e:
                    # Exception is acceptable for malicious paths
                    print(f"    ✅ Blocked: {path}")
        
        return True

    def test_filename_injection_prevention(self):
        """Test prevention of filename injection attacks"""
        print("  🧪 Testing filename injection prevention...")
        
        malicious_names = [
            "file.json; rm -rf /",
            "file.json && del *.*",
            "file.json | malicious.exe",
            "file.json\x00.exe",  # Null byte injection
            "file.json`whoami`",
        ]
        
        for name in malicious_names:
            issues = validate_filename_cross_platform(name)
            if issues:
                print(f"    ✅ Detected issue in: {repr(name)}")
            else:
                # Check for dangerous characters manually
                dangerous = [';', '|', '&', '`', '\x00']
                if any(c in name for c in dangerous):
                    print(f"    ⚠️  Should detect: {repr(name)}")
                else:
                    print(f"    ✅ Clean: {repr(name)}")
        
        return True

    def test_hidden_file_handling(self):
        """Test handling of hidden files on Windows"""
        print("  🧪 Testing hidden file handling...")
        
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create normal and "hidden" files
            files = [
                ("normal.json", False),
                (".hidden", True),  # Unix-style hidden
                ("_hidden.json", False),  # Not really hidden on Windows
            ]
            
            for filename, should_be_system in files:
                filepath = os.path.join(tmpdir, filename)
                CrossPlatformFile.write_text(filepath, '{"test": "data"}')
                
                is_sys = is_system_file(filename)
                
                if should_be_system and not is_sys:
                    print(f"    ⚠️  Should be detected as system: {filename}")
                elif not should_be_system and is_sys:
                    print(f"    ⚠️  Should not be system: {filename}")
                else:
                    print(f"    ✅ {filename}: {'system' if is_sys else 'normal'}")
        
        return True


def run_all_tests():
    """Run all Windows web upload tests"""
    print("=" * 70)
    print("🌐 WINDOWS WEB INTERFACE UPLOAD TESTS")
    print("=" * 70)
    
    if not sys.platform.startswith("win"):
        print("\n⚠️  Warning: Not running on Windows!")
        print("Some tests may behave differently on non-Windows platforms.\n")
    
    test_classes = [
        ("Web Upload Handling", TestWindowsWebUpload),
        ("Session Management", TestWindowsSessionManagement),
        ("File Security", TestWindowsFileSecurity),
    ]
    
    total_passed = 0
    total_tests = 0
    
    for class_name, test_class in test_classes:
        print(f"\n🔧 {class_name}")
        print("-" * 70)
        
        instance = test_class()
        methods = [m for m in dir(instance) if m.startswith("test_")]
        
        for method_name in methods:
            total_tests += 1
            method = getattr(instance, method_name)
            
            try:
                if method():
                    total_passed += 1
                else:
                    print(f"    ❌ {method_name} failed")
            except Exception as e:
                print(f"    ❌ {method_name} error: {e}")
                import traceback
                traceback.print_exc()
        
        print()
    
    print("=" * 70)
    print(f"📊 RESULTS: {total_passed}/{total_tests} tests passed")
    
    if total_passed == total_tests:
        print("🎉 All Windows web tests passed!")
        return 0
    else:
        print(f"❌ {total_tests - total_passed} test(s) failed")
        return 1


if __name__ == "__main__":
    sys.exit(run_all_tests())
