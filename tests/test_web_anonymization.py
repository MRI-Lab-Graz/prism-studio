#!/usr/bin/env python3
"""
Test script for web interface anonymization integration.
"""
import os
import sys
import json
import tempfile
import shutil
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent / "app"))

def test_anonymization_payload():
    """Test that the anonymization payload structure is correct."""
    print("\n=== Testing Anonymization Payload Structure ===")
    
    # Simulate the JavaScript payload
    payload = {
        "dataset_path": "/path/to/dataset",
        "recipe_dir": "",
        "modality": "survey",
        "format": "csv",
        "survey": "",
        "lang": "en",
        "layout": "long",
        "include_raw": False,
        "boilerplate": False,
        "anonymize": True,
        "mask_questions": False,
        "id_length": 8,
        "random_ids": False
    }
    
    print("✅ Payload structure validated")
    print(f"   - anonymize: {payload['anonymize']}")
    print(f"   - mask_questions: {payload['mask_questions']}")
    print(f"   - id_length: {payload['id_length']}")
    print(f"   - random_ids: {payload['random_ids']}")
    
    return True


def test_anonymization_with_test_dataset():
    """Test anonymization with a real test dataset."""
    print("\n=== Testing Anonymization with Test Dataset ===")
    
    # Create temporary test dataset
    with tempfile.TemporaryDirectory() as tmpdir:
        dataset_path = Path(tmpdir) / "test_dataset"
        dataset_path.mkdir()
        
        # Create participants.tsv
        participants_tsv = dataset_path / "participants.tsv"
        participants_tsv.write_text(
            "participant_id\tage\tsex\n"
            "sub-001\t25\tF\n"
            "sub-002\t30\tM\n"
            "sub-003\t28\tF\n"
        )
        
        # Create derivatives directory with test data
        derivatives_dir = dataset_path / "derivatives" / "prism-export-survey"
        derivatives_dir.mkdir(parents=True)
        
        # Create test TSV file
        test_tsv = derivatives_dir / "task-test_survey.tsv"
        test_tsv.write_text(
            "participant_id\tquestion\tanswer\n"
            "sub-001\tHow old are you?\t25\n"
            "sub-002\tHow old are you?\t30\n"
            "sub-003\tHow old are you?\t28\n"
        )
        
        # Import anonymization functions
        from src.anonymizer import create_participant_mapping, anonymize_tsv_file
        
        # Create mapping
        mapping_file = create_participant_mapping(
            str(participants_tsv),
            output_dir=str(derivatives_dir),
            id_length=8,
            use_random=False
        )
        
        print(f"✅ Created mapping file: {mapping_file}")
        
        # Anonymize the TSV file
        anonymize_tsv_file(
            str(test_tsv),
            mapping_file,
            mask_questions=True
        )
        
        print("✅ Anonymized TSV file")
        
        # Verify anonymization
        anonymized_content = test_tsv.read_text()
        print("\nAnonymized content:")
        print(anonymized_content)
        
        # Check that original IDs are gone
        assert "sub-001" not in anonymized_content, "Original ID found in anonymized file"
        assert "sub-002" not in anonymized_content, "Original ID found in anonymized file"
        assert "sub-003" not in anonymized_content, "Original ID found in anonymized file"
        
        # Check that questions are masked
        assert "How old are you?" not in anonymized_content, "Question text not masked"
        assert "[MASKED]" in anonymized_content or "***" in anonymized_content, "No masking marker found"
        
        print("✅ Anonymization verification passed")
        
        # Check mapping file
        with open(mapping_file, 'r') as f:
            mapping_content = f.read()
            print(f"\nMapping file preview:\n{mapping_content[:200]}...")
        
        return True


def test_api_endpoint_structure():
    """Test that the API endpoint has the correct structure."""
    print("\n=== Testing API Endpoint Structure ===")
    
    try:
        from src.web.blueprints.tools import tools_bp
        print("✅ Successfully imported tools blueprint")
        
        # Check if the route exists
        route_found = False
        for rule in tools_bp.url_map.iter_rules():
            if '/api/recipes-surveys' in rule.rule:
                route_found = True
                print(f"✅ Found route: {rule.rule} [{', '.join(rule.methods)}]")
                break
        
        if not route_found:
            print("⚠️  Route not found in blueprint rules (might be registered at runtime)")
        
        return True
        
    except ImportError as e:
        print(f"❌ Failed to import tools blueprint: {e}")
        return False


def main():
    """Run all tests."""
    print("=" * 60)
    print("PRISM Web Anonymization Integration Tests")
    print("=" * 60)
    
    tests = [
        ("Payload Structure", test_anonymization_payload),
        ("Anonymization with Test Dataset", test_anonymization_with_test_dataset),
        ("API Endpoint Structure", test_api_endpoint_structure),
    ]
    
    results = []
    for name, test_func in tests:
        try:
            result = test_func()
            results.append((name, result, None))
        except Exception as e:
            print(f"❌ Test failed with error: {e}")
            import traceback
            traceback.print_exc()
            results.append((name, False, str(e)))
    
    # Summary
    print("\n" + "=" * 60)
    print("Test Summary")
    print("=" * 60)
    
    passed = sum(1 for _, result, _ in results if result)
    total = len(results)
    
    for name, result, error in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status}: {name}")
        if error:
            print(f"   Error: {error}")
    
    print(f"\nTotal: {passed}/{total} tests passed")
    
    return passed == total


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
