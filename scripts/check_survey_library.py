import os
import sys
import json
from pathlib import Path

# Add project root to path to import from src
project_root = Path(__file__).resolve().parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

try:
    from src.library_validator import LibraryValidator
    from src.schema_manager import load_schema
    from src.library_i18n import compile_survey_template
    from jsonschema import validate, ValidationError
except ImportError:
    # Fallback for different execution contexts
    sys.path.append(os.path.join(os.getcwd(), "src"))
    from library_validator import LibraryValidator
    from schema_manager import load_schema
    from library_i18n import compile_survey_template
    from jsonschema import validate, ValidationError


def check_uniqueness(library_path):
    print(f"Validating library at {library_path}...")

    if not os.path.exists(library_path):
        print(f"Error: Library path {library_path} does not exist.")
        return False

    library_path_obj = Path(library_path)
    validator = LibraryValidator(library_path)
    
    # 1. Check Uniqueness
    print("Checking variable uniqueness...")
    var_map = validator.get_all_library_variables()
    duplicates = {k: v for k, v in var_map.items() if len(v) > 1}

    if not duplicates:
        print("✅ SUCCESS: All variable names are unique across the library.")
    else:
        print(f"⚠️  WARNING: Found {len(duplicates)} variable names appearing in multiple files:")
        for var, file_list in duplicates.items():
            print(f"  - '{var}' appears in: {', '.join(file_list)}")

    # 2. Check Schema
    print("\nChecking schema compliance...")
    survey_schema = load_schema("survey", version="stable")
    biometrics_schema = load_schema("biometrics", version="stable")
    
    errors_found = 0
    files = sorted(list(library_path_obj.glob("*.json")))
    
    for f in files:
        if not (f.name.startswith("survey-") or f.name.startswith("biometrics-")):
            continue
            
        try:
            with open(f, "r", encoding="utf-8") as f_in:
                data = json.load(f_in)
            
            schema = survey_schema if f.name.startswith("survey-") else biometrics_schema
            
            if not schema:
                print(f"⚠️  Skipping {f.name}: Schema not found.")
                continue

            # For surveys, we might need to compile i18n
            if f.name.startswith("survey-"):
                # Try to compile to 'de' or 'en' to check structure
                try:
                    compiled = compile_survey_template(data, lang="de")
                    validate(instance=compiled, schema=schema)
                except Exception:
                    # If compilation fails or validation fails, try raw validation if it's not i18n
                    validate(instance=data, schema=schema)
            else:
                validate(instance=data, schema=schema)
                
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

    return len(duplicates) == 0 and errors_found == 0


if __name__ == "__main__":
    library_dir = "survey_library"
    if len(sys.argv) > 1:
        library_dir = sys.argv[1]

    success = check_uniqueness(library_dir)
    sys.exit(0 if success else 1)
