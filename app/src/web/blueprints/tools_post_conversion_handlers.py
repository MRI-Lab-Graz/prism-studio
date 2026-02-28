import csv
import json
from pathlib import Path

from flask import jsonify


def handle_limesurvey_save_to_project(project_path: str | None, data: dict | None):
    from src.cross_platform import CrossPlatformFile
    from werkzeug.utils import secure_filename

    if not project_path:
        return jsonify({"success": False, "error": "No project selected"}), 400

    resolved_project_path = Path(project_path)
    if not resolved_project_path.exists():
        return jsonify({"success": False, "error": "Project path does not exist"}), 400

    if not data:
        return jsonify({"success": False, "error": "No data provided"}), 400

    templates = data.get("templates", [])
    if not templates:
        return jsonify({"success": False, "error": "No templates provided"}), 400

    library_survey_path = resolved_project_path / "code" / "library" / "survey"
    library_survey_path.mkdir(parents=True, exist_ok=True)

    saved_files = []
    errors = []

    for template in templates:
        filename = template.get("filename")
        content = template.get("content")

        if not filename or content is None:
            errors.append("Invalid template entry: missing filename or content")
            continue

        safe_filename = secure_filename(filename)
        if not safe_filename:
            errors.append(f"Invalid filename: {filename}")
            continue

        if not safe_filename.endswith(".json"):
            safe_filename += ".json"

        file_path = library_survey_path / safe_filename

        try:
            json_content = json.dumps(content, indent=2, ensure_ascii=False)
            CrossPlatformFile.write_text(str(file_path), json_content)
            saved_files.append({"filename": safe_filename, "path": str(file_path)})
        except Exception as e:
            errors.append(f"Failed to save {safe_filename}: {str(e)}")

    return jsonify(
        {
            "success": len(saved_files) > 0,
            "saved_files": saved_files,
            "saved_count": len(saved_files),
            "library_path": str(library_survey_path),
            "errors": errors if errors else None,
        }
    )


def handle_fix_participants_bids(data: dict | None):
    import pandas as pd

    if not data:
        return jsonify({"success": False, "error": "No data provided"}), 400

    file_path = data.get("file_path")
    sex_mapping = data.get(
        "sex_mapping", {1: "M", 2: "F", 3: "O", "1": "M", "2": "F", "3": "O"}
    )
    dry_run = data.get("dry_run", False)

    if not file_path:
        return jsonify({"success": False, "error": "No file path provided"}), 400

    resolved_file_path = Path(file_path).expanduser().resolve()
    if not resolved_file_path.exists():
        return jsonify({"success": False, "error": f"File not found: {resolved_file_path}"}), 404

    try:
        df = pd.read_csv(resolved_file_path, sep="\t", dtype=str)
        changes = []

        numeric_columns = ["age", "height", "weight", "years_of_education"]
        for col in df.columns:
            col_lower = col.lower()
            if col_lower in numeric_columns:
                try:
                    numeric_values = pd.to_numeric(df[col], errors="coerce")
                    numeric_count = numeric_values.notna().sum()

                    if numeric_count > 0:
                        original_sample = df[col].dropna().head(3).tolist()
                        df[col] = numeric_values
                        new_sample = df[col].dropna().head(3).tolist()

                        if str(original_sample) != str(new_sample):
                            changes.append(
                                {
                                    "column": col,
                                    "type": "numeric_conversion",
                                    "before": original_sample,
                                    "after": new_sample,
                                    "count": int(numeric_count),
                                }
                            )
                except Exception:
                    pass

        sex_col = None
        for col in df.columns:
            if col.lower() in ["sex", "gender"]:
                sex_col = col
                break

        if sex_col:
            is_numeric_coded = all(
                str(v).strip() in ["1", "2", "3", "0"] or pd.isna(v)
                for v in df[sex_col]
            )

            if is_numeric_coded:
                original_values = df[sex_col].copy()

                def convert_sex_code(x):
                    if pd.isna(x):
                        return x
                    str_key = str(x).strip()
                    if str_key in sex_mapping:
                        return sex_mapping[str_key]
                    try:
                        int_key = int(x)
                        if int_key in sex_mapping:
                            return sex_mapping[int_key]
                    except (ValueError, TypeError):
                        pass
                    return x

                df[sex_col] = df[sex_col].map(convert_sex_code)

                before_counts = original_values.value_counts().to_dict()
                after_counts = df[sex_col].value_counts().to_dict()

                changes.append(
                    {
                        "column": sex_col,
                        "type": "sex_code_conversion",
                        "mapping": sex_mapping,
                        "before": before_counts,
                        "after": after_counts,
                    }
                )

        if not changes:
            return jsonify(
                {
                    "success": True,
                    "message": "No changes needed - file is already BIDS compliant",
                    "changes": [],
                }
            )

        if dry_run:
            return jsonify(
                {
                    "success": True,
                    "message": f"Would fix {len(changes)} issues",
                    "changes": changes,
                    "dry_run": True,
                }
            )

        df.to_csv(
            resolved_file_path,
            sep="\t",
            index=False,
            na_rep="n/a",
            quoting=csv.QUOTE_NONE,
            escapechar="\\",
        )

        return jsonify(
            {
                "success": True,
                "message": f"Fixed {len(changes)} issues in {resolved_file_path.name}",
                "changes": changes,
                "file_path": str(resolved_file_path),
            }
        )

    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500