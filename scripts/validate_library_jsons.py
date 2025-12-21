import json
import os
import sys
from pathlib import Path
from jsonschema import validate, ValidationError

# Add src to path
project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root / "src"))

from library_i18n import compile_survey_template
from schema_manager import load_schema

def validate_library():
    library_dir = project_root / "library" / "survey"
    schema = load_schema("survey", version="stable")
    
    if not schema:
        print("❌ Error: Could not load survey schema.")
        sys.exit(1)

    files = sorted(list(library_dir.glob("survey-*.json")))
    print(f"Validating {len(files)} library files...")

    errors_found = 0
    for f in files:
        try:
            with open(f, "r", encoding="utf-8") as f_in:
                data = json.load(f_in)
            
            # Compile to 'de' (since most of our legacy data is German)
            compiled = compile_survey_template(data, lang="de")
            
            # Validate against schema
            validate(instance=compiled, schema=schema)
            print(f"✅ {f.name}: Valid")
            
        except ValidationError as e:
            print(f"❌ {f.name}: Schema Validation Error")
            print(f"   Path: {'.'.join(map(str, e.path))}")
            print(f"   Message: {e.message}")
            errors_found += 1
        except Exception as e:
            print(f"❌ {f.name}: Error")
            print(f"   {e}")
            errors_found += 1

    if errors_found == 0:
        print("\n🎉 All library files are valid!")
    else:
        print(f"\nFound {errors_found} errors.")
        sys.exit(1)

if __name__ == "__main__":
    validate_library()
