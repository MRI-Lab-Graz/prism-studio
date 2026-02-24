#!/usr/bin/env python3
"""Test that all 13 mandatory metadata fields persist correctly to project.json"""

import json
import requests
import sys
from pathlib import Path

# Test payload with all 13 mandatory fields filled
test_payload = {
    "path": "/tmp/test_metadata_project",
    "name": "TestMetadataProject",
    # BIDS mandatory fields (3)
    "authors": ["Test Author"],
    "license": "CC0",
    # Study metadata sections (10 mandatory fields across 5 sections)
    "Overview": {
        "Main": "This is a test overview of the study"
    },
    "StudyDesign": {
        "Type": "Experimental"
    },
    "Recruitment": {
        "Method": ["Online advertising"],
        "Location": ["University campus"],
        "Period": {
            "Start": "2024-01",
            "End": "2024-12"
        },
        "Compensation": "20 EUR"
    },
    "Eligibility": {
        "InclusionCriteria": ["Age 18+", "Fluent in English"],
        "ExclusionCriteria": ["History of neurological conditions"]
    },
    "Procedure": {
        "Overview": "Participants complete online survey"
    }
}

def test_metadata_persistence():
    """Send create request and verify project.json contains all fields"""
    
    # Clean up any existing test project
    test_path = Path("/tmp/test_metadata_project")
    if test_path.exists():
        import shutil
        shutil.rmtree(test_path)
    
    # Send create request
    try:
        response = requests.post(
            "http://localhost:5001/api/projects/create",
            json=test_payload,
            timeout=10
        )
        
        if response.status_code != 200:
            print(f"❌ API request failed: {response.status_code}")
            print(response.text)
            return False
            
        result = response.json()
        if not result.get("success"):
            print(f"❌ Project creation failed: {result.get('error')}")
            return False
            
        print(f"✓ Project created successfully")
        
        # Read project.json
        project_json_path = test_path / "project.json"
        if not project_json_path.exists():
            print(f"❌ project.json not found at {project_json_path}")
            return False
            
        with open(project_json_path) as f:
            project_data = json.load(f)
        
        # Verify all sections are present
        missing_sections = []
        for section in ["Overview", "StudyDesign", "Recruitment", "Eligibility", "Procedure"]:
            if section not in project_data:
                missing_sections.append(section)
        
        if missing_sections:
            print(f"❌ Missing sections in project.json: {', '.join(missing_sections)}")
            return False
        
        print(f"✓ All 5 study metadata sections present")
        
        # Verify specific mandatory fields
        checks = [
            ("Overview.Main", lambda d: d.get("Overview", {}).get("Main")),
            ("StudyDesign.Type", lambda d: d.get("StudyDesign", {}).get("Type")),
            ("Recruitment.Method", lambda d: d.get("Recruitment", {}).get("Method")),
            ("Recruitment.Location", lambda d: d.get("Recruitment", {}).get("Location")),
            ("Recruitment.Period.Start", lambda d: d.get("Recruitment", {}).get("Period", {}).get("Start")),
            ("Recruitment.Period.End", lambda d: d.get("Recruitment", {}).get("Period", {}).get("End")),
            ("Recruitment.Compensation", lambda d: d.get("Recruitment", {}).get("Compensation")),
            ("Eligibility.InclusionCriteria", lambda d: d.get("Eligibility", {}).get("InclusionCriteria")),
            ("Eligibility.ExclusionCriteria", lambda d: d.get("Eligibility", {}).get("ExclusionCriteria")),
            ("Procedure.Overview", lambda d: d.get("Procedure", {}).get("Overview")),
        ]
        
        missing_fields = []
        for field_name, getter in checks:
            value = getter(project_data)
            if not value:
                missing_fields.append(field_name)
            else:
                print(f"  ✓ {field_name}: {value}")
        
        if missing_fields:
            print(f"\n❌ Missing field values: {', '.join(missing_fields)}")
            print("\nproject.json content:")
            print(json.dumps(project_data, indent=2))
            return False
        
        print(f"\n✅ SUCCESS: All 13 mandatory fields persisted correctly!")
        return True
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_metadata_persistence()
    sys.exit(0 if success else 1)
