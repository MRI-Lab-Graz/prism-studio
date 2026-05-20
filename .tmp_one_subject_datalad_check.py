import json
from pathlib import Path

from src.project_manager import ProjectManager

path_str = "/Volumes/Thunder/129_PK01/rawdata"
path = Path(path_str)
pm = ProjectManager()

status_before = pm.get_datalad_status(path_str)
before_next_missing = status_before.get("next_missing_subdataset")

result = pm.enable_datalad_for_project(path, message="Enable DataLad for PRISM project")
datalad_info = result.get("datalad", {}) or {}
created = datalad_info.get("subdatasets_created") or []
failures = datalad_info.get("subdataset_failures") or []
after_next_missing = datalad_info.get("next_missing_subdataset")

subject = created[0] if created else before_next_missing

print("RESULT_JSON_START")
print(
    json.dumps(
        {
            "before_next_missing": before_next_missing,
            "success": result.get("success"),
            "message": result.get("message"),
            "subdatasets_created": created,
            "subdataset_failures": failures,
            "next_missing_after": after_next_missing,
            "subject_checked": subject,
        },
        indent=2,
    )
)
print("RESULT_JSON_END")

if subject:
    print(f"SUBJECT_CHECK::{subject}")
