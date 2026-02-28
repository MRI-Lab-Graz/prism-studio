import json
from pathlib import Path

from flask import jsonify, request


def _normalize_author_names(authors_value):
    """Normalize author payload (strings or dicts) to a list of display names."""
    if isinstance(authors_value, (str, dict)):
        authors = [authors_value]
    elif isinstance(authors_value, list):
        authors = authors_value
    else:
        return []

    normalized = []
    for author in authors:
        if isinstance(author, dict):
            given = str(author.get("given-names") or author.get("given") or "").strip()
            family = str(author.get("family-names") or author.get("family") or "").strip()
            name = str(author.get("name") or "").strip()
            if given and family:
                normalized.append(f"{given} {family}")
            elif name:
                normalized.append(name)
            elif family:
                normalized.append(family)
            elif given:
                normalized.append(given)
            continue

        text = str(author or "").strip()
        if text:
            normalized.append(text)

    return normalized


def handle_get_dataset_description(
    get_current_project,
    get_bids_file_path,
    read_citation_cff_fields,
    merge_citation_fields,
    project_manager,
):
    """Get the dataset_description.json for the current project."""
    current = get_current_project()
    if not current.get("path"):
        return jsonify({"success": False, "error": "No project selected"}), 400

    project_path = Path(current["path"])
    desc_path = get_bids_file_path(project_path, "dataset_description.json")

    if not desc_path.exists():
        return (
            jsonify({"success": False, "error": "dataset_description.json not found"}),
            404,
        )

    try:
        with open(desc_path, "r", encoding="utf-8") as f:
            description = json.load(f)

        citation_fields = read_citation_cff_fields(project_path / "CITATION.cff")
        if citation_fields:
            desc_authors = _normalize_author_names(description.get("Authors"))
            citation_authors = _normalize_author_names(citation_fields.get("Authors"))
            if citation_authors and (
                not desc_authors or len(citation_authors) > len(desc_authors)
            ):
                description["Authors"] = citation_fields["Authors"]
            if not description.get("License") and citation_fields.get("License"):
                description["License"] = citation_fields["License"]
            if not description.get("HowToAcknowledge") and citation_fields.get(
                "HowToAcknowledge"
            ):
                description["HowToAcknowledge"] = citation_fields["HowToAcknowledge"]
            if not description.get("ReferencesAndLinks") and citation_fields.get(
                "ReferencesAndLinks"
            ):
                description["ReferencesAndLinks"] = citation_fields[
                    "ReferencesAndLinks"
                ]

        validation_description = merge_citation_fields(description, citation_fields)
        issues = project_manager.validate_dataset_description(validation_description)

        return jsonify({"success": True, "description": description, "issues": issues})
    except Exception as e:
        return (
            jsonify(
                {
                    "success": False,
                    "error": f"Failed to read dataset_description.json: {str(e)}",
                }
            ),
            500,
        )


def handle_save_dataset_description(
    get_current_project,
    get_bids_file_path,
    read_citation_cff_fields,
    merge_citation_fields,
    project_manager,
    set_current_project,
    save_last_project,
):
    """Save the dataset_description.json for the current project."""
    current = get_current_project()
    if not current.get("path"):
        return jsonify({"success": False, "error": "No project selected"}), 400

    data = request.get_json()
    if not data or "description" not in data:
        return jsonify({"success": False, "error": "No description data provided"}), 400

    description = data["description"]
    citation_fields_payload = data.get("citation_fields") or {}
    if not isinstance(citation_fields_payload, dict):
        citation_fields_payload = {}
    project_path = Path(current["path"])
    desc_path = get_bids_file_path(project_path, "dataset_description.json")

    try:
        if "Name" not in description and "name" in description:
            description["Name"] = description.pop("name")

        if "Name" not in description:
            return (
                jsonify({"success": False, "error": "Dataset 'Name' is required"}),
                400,
            )
        if "BIDSVersion" not in description:
            description["BIDSVersion"] = "1.10.1"

        citation_cff_path = project_path / "CITATION.cff"
        existing_citation_fields = read_citation_cff_fields(citation_cff_path)
        submitted_citation_fields = {
            "Authors": citation_fields_payload.get("Authors", description.get("Authors")),
            "HowToAcknowledge": citation_fields_payload.get("HowToAcknowledge", description.get("HowToAcknowledge")),
            "License": citation_fields_payload.get("License", description.get("License")),
            "ReferencesAndLinks": citation_fields_payload.get("ReferencesAndLinks", description.get("ReferencesAndLinks")),
        }

        synced_authors = _normalize_author_names(submitted_citation_fields.get("Authors"))
        if synced_authors:
            description["Authors"] = synced_authors

        citation_fields = dict(existing_citation_fields)
        for key, value in submitted_citation_fields.items():
            if value not in (None, "", [], {}):
                citation_fields[key] = value
        if not citation_cff_path.exists():
            if "License" not in description:
                description["License"] = "CC0"

        if "DatasetType" not in description:
            description["DatasetType"] = "raw"
        if "HEDVersion" not in description:
            description.pop("HEDVersion", None)

        validation_description = merge_citation_fields(description, citation_fields)
        issues = project_manager.validate_dataset_description(validation_description)

        with open(desc_path, "w", encoding="utf-8") as f:
            json.dump(description, f, indent=2, ensure_ascii=False)

        try:
            citation_payload = dict(description)
            for key, value in citation_fields.items():
                if value not in (None, "", [], {}):
                    citation_payload[key] = value
            project_manager.update_citation_cff(project_path, citation_payload)
        except Exception as e:
            print(f"Warning: could not update CITATION.cff: {e}")

        if "Name" in description:
            set_current_project(str(project_path), description["Name"])
            save_last_project(str(project_path), description["Name"])

        return jsonify(
            {
                "success": True,
                "message": "dataset_description.json saved successfully",
                "issues": issues,
            }
        )
    except Exception as e:
        return (
            jsonify(
                {
                    "success": False,
                    "error": f"Failed to save dataset_description.json: {str(e)}",
                }
            ),
            500,
        )


def handle_validate_dataset_description_draft(merge_citation_fields, project_manager):
    """Validate a draft dataset_description payload (without saving)."""
    try:
        data = request.get_json()
        if not data or "description" not in data:
            return (
                jsonify({"success": False, "error": "No description data provided"}),
                400,
            )

        description = data.get("description") or {}
        if not isinstance(description, dict):
            return (
                jsonify(
                    {
                        "success": False,
                        "error": "Description must be an object",
                    }
                ),
                400,
            )

        citation_fields = data.get("citation_fields") or {}
        if not isinstance(citation_fields, dict):
            citation_fields = {}

        validation_description = merge_citation_fields(description, citation_fields)
        issues = project_manager.validate_dataset_description(validation_description)

        return jsonify({"success": True, "issues": issues})
    except Exception as e:
        return (
            jsonify(
                {
                    "success": False,
                    "error": f"Failed to validate description draft: {str(e)}",
                }
            ),
            500,
        )
