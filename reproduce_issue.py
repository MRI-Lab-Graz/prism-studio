import pandas as pd
import io
import os
from pathlib import Path
from app.src.converters.survey import SurveyResponsesConverter, SurveyValueOutOfBoundsError

# Create minimal CSV
csv_content = """participant_id,PSS01
1,5
2,5
3,5
4,5
"""
csv_file = "test_responses.csv"
with open(csv_file, "w") as f:
    f.write(csv_content)

# Create a library directory with a survey-perceived-stress-scale template
lib_dir = Path("test_library")
surveys_dir = lib_dir / "surveys"
os.makedirs(surveys_dir, exist_ok=True)

try:
    from openpyxl import Workbook
    wb = Workbook()
    ws = wb.active
    ws.append(["Variable Name", "Question Text", "Answer Options"])
    ws.append(["PSS01", "In the last month...", "0=Never, 1=Almost Never, 2=Sometimes, 3=Fairly Often, 4=Very Often"])
    template_file = surveys_dir / "perceived-stress-scale.xlsx"
    wb.save(template_file)

    converter = SurveyResponsesConverter()
    try:
        # Use 'survey' parameter instead of 'task_names'
        converter.convert_xlsx(
            input_path=csv_file,
            library_dir=str(lib_dir),
            output_root="test_output",
            survey="perceived-stress-scale"
        )
    except SurveyValueOutOfBoundsError as e:
        print(f"error type name: {type(e).__name__}")
        print(f"suggested_offsets: {e.suggested_offsets}")
        
        evidence = getattr(e, 'evidence', {})
        if evidence:
            print(f"evidence classification: {evidence.get('classification')}")
            print(f"invalid_without_offset: {evidence.get('invalid_without_offset')}")
            print(f"corrected_by_best_offset: {evidence.get('corrected_by_best_offset')}")
            print(f"newly_invalid_with_best_offset: {evidence.get('newly_invalid_with_best_offset')}")
        else:
            print("evidence classification: N/A")
            print("invalid_without_offset: N/A")
            print("corrected_by_best_offset: N/A")
            print("newly_invalid_with_best_offset: N/A")
    except Exception as ex:
        import traceback
        traceback.print_exc()
finally:
    import shutil
    if os.path.exists(csv_file): os.remove(csv_file)
    if os.path.exists("test_library"): shutil.rmtree("test_library")
    if os.path.exists("test_output"): shutil.rmtree("test_output")

