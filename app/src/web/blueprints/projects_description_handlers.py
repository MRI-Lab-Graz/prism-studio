import json
from pathlib import Path

from flask import jsonify, request

from .projects_helpers import _resolve_requested_or_current_project_root


def _normalize_dataset_type(dataset_type):
    value = str(dataset_type or "").strip().lower()
    if value in {"raw", "derivative"}:
        return value
    return "raw"


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
            family = str(
                author.get("family-names") or author.get("family") or ""
            ).strip()
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


def _normalize_roles(roles_value):
    """Normalize contributor roles payload to a de-duplicated list of strings."""
    if isinstance(roles_value, list):
        raw_roles = roles_value
    elif isinstance(roles_value, str):
        raw_roles = [item.strip() for item in roles_value.split(",")]
    else:
        raw_roles = []

    normalized = []
    seen = set()
    for role in raw_roles:
        value = str(role or "").strip()
        if not value:
            continue
        key = value.lower()
        if key in seen:
            continue
        seen.add(key)
        normalized.append(value)
    return normalized


def _author_display_names(author):
    """Build possible contributor display-name variants for author matching."""
    names = []
    if isinstance(author, dict):
        given = str(author.get("given-names") or author.get("given") or "").strip()
        family = str(author.get("family-names") or author.get("family") or "").strip()
        explicit_name = str(author.get("name") or "").strip()
        if family and given:
            names.extend([f"{family}, {given}", f"{given} {family}"])
        if family:
            names.append(family)
        if explicit_name:
            names.append(explicit_name)
        if given:
            names.append(given)
    else:
        text = str(author or "").strip()
        if text:
            names.append(text)

    unique = []
    seen = set()
    for name in names:
        normalized = str(name or "").strip()
        if not normalized:
            continue
        key = normalized.lower()
        if key in seen:
            continue
        seen.add(key)
        unique.append(normalized)
    return unique


def _load_contributor_roles(project_path: Path):
    """Read project.json governance.contacts and build a lookup from author name to roles."""
    project_json = project_path / "project.json"
    if not project_json.exists():
        return {}

    try:
        with open(project_json, "r", encoding="utf-8") as f:
            payload = json.load(f)
    except Exception:
        return {}

    governance = payload.get("governance") if isinstance(payload, dict) else None
    contacts = governance.get("contacts") if isinstance(governance, dict) else None
    if not isinstance(contacts, list):
        return {}

    lookup = {}
    for item in contacts:
        if not isinstance(item, dict):
            continue
        name = str(item.get("name") or "").strip()
        roles = _normalize_roles(item.get("roles"))
        if name and roles:
            lookup[name.lower()] = roles
    return lookup


def _load_corresponding_author(project_path: Path):
    """Read project.json governance.contacts and find the corresponding author name."""
    project_json = project_path / "project.json"
    if not project_json.exists():
        return ""

    try:
        with open(project_json, "r", encoding="utf-8") as f:
            payload = json.load(f)
    except Exception:
        return ""

    governance = payload.get("governance") if isinstance(payload, dict) else None
    contacts = governance.get("contacts") if isinstance(governance, dict) else None
    if not isinstance(contacts, list):
        return ""

    for item in contacts:
        if not isinstance(item, dict):
            continue
        if item.get("corresponding"):
            return str(item.get("name") or "").strip()
    return ""


def _sync_authors_to_project_json(project_path: Path, authors_value) -> None:
    """Persist rich author data (roles, corresponding, orcid…) to project.json governance.contacts."""
    if isinstance(authors_value, (str, dict)):
        authors = [authors_value]
    elif isinstance(authors_value, list):
        authors = authors_value
    else:
        return

    contacts = []
    for author in authors:
        contributor = _author_to_contributor(author)
        if contributor:
            contacts.append(contributor)

    if not contacts:
        return

    project_json = project_path / "project.json"
    existing: dict = {}
    if project_json.exists():
        try:
            with open(project_json, "r", encoding="utf-8") as f:
                loaded = json.load(f)
                if isinstance(loaded, dict):
                    existing = loaded
        except Exception:
            existing = {}

    # Preserve existing roles not supplied in the new contacts
    governance = existing.get("governance") if isinstance(existing, dict) else None
    existing_contacts = governance.get("contacts") if isinstance(governance, dict) else []
    existing_roles_by_name: dict = {}
    if isinstance(existing_contacts, list):
        for item in existing_contacts:
            if not isinstance(item, dict):
                continue
            n = str(item.get("name") or "").strip()
            roles = item.get("roles")
            if n and isinstance(roles, list) and roles:
                existing_roles_by_name[n] = roles

    for contact in contacts:
        if not contact.get("roles") and contact.get("name") in existing_roles_by_name:
            contact["roles"] = existing_roles_by_name[contact["name"]]

    if "governance" not in existing or not isinstance(existing.get("governance"), dict):
        existing["governance"] = {}
    existing["governance"]["contacts"] = contacts

    try:
        with open(project_json, "w", encoding="utf-8") as f:
            json.dump(existing, f, indent=2, ensure_ascii=False)
    except Exception:
        pass  # best-effort; don't fail the main save


def _remove_legacy_contributor_files(project_path: Path) -> None:
    """Delete legacy contributor files once project.json becomes canonical."""
    for legacy_name in ("contributors.json", "contributor.json"):
        legacy_path = project_path / legacy_name
        try:
            legacy_path.unlink(missing_ok=True)
        except Exception:
            # Best-effort cleanup only; do not fail save flow on stale files.
            pass


def _enrich_authors_with_roles(project_path: Path, authors_value):
    """Attach contributor roles to author dictionaries for frontend editing."""
    if not isinstance(authors_value, list):
        return authors_value

    role_lookup = _load_contributor_roles(project_path)
    corresponding_name = _load_corresponding_author(project_path)
    if not role_lookup and not corresponding_name:
        return authors_value

    enriched = []
    for author in authors_value:
        if not isinstance(author, dict):
            enriched.append(author)
            continue

        author_roles = _normalize_roles(author.get("roles"))
        is_corresponding = bool(author.get("corresponding"))

        if not author_roles:
            for candidate in _author_display_names(author):
                matched = role_lookup.get(candidate.lower())
                if matched:
                    author_roles = matched
                    break

        if not is_corresponding and corresponding_name:
            for candidate in _author_display_names(author):
                if candidate.lower() == corresponding_name.lower():
                    is_corresponding = True
                    break

        updated_author = dict(author)
        if author_roles:
            updated_author["roles"] = author_roles
        if is_corresponding:
            updated_author["corresponding"] = True
        enriched.append(updated_author)

    return enriched


def _author_to_contributor(author):
    """Normalize an author entry to a contributors.json contributor object."""
    given = ""
    family = ""
    name = ""
    orcid = ""
    email = ""
    roles = []
    corresponding = False

    if isinstance(author, dict):
        given = str(author.get("given-names") or author.get("given") or "").strip()
        family = str(author.get("family-names") or author.get("family") or "").strip()
        name = str(author.get("name") or "").strip()
        orcid = str(author.get("orcid") or author.get("ORCID") or "").strip()
        email = str(author.get("email") or "").strip()
        roles = _normalize_roles(author.get("roles"))
        corresponding = bool(author.get("corresponding"))
    else:
        text = str(author or "").strip()
        if not text:
            return None
        if "," in text:
            left, right = text.split(",", 1)
            family = left.strip()
            given = right.strip()
        else:
            name = text

    if family and given:
        display_name = f"{family}, {given}"
    elif family:
        display_name = family
    elif name:
        display_name = name
    elif given:
        display_name = given
    else:
        return None

    return {
        "name": display_name,
        "roles": roles,
        "orcid": orcid,
        "email": email,
        "corresponding": corresponding,
    }


def handle_get_dataset_description(
    get_current_project,
    get_bids_file_path,
    read_citation_cff_fields,
    merge_citation_fields,
    project_manager,
):
    """Get the dataset_description.json for the current project."""
    project_path, error_message, status_code = (
        _resolve_requested_or_current_project_root(
            get_current_project,
            request.args.get("project_path"),
        )
    )
    if project_path is None:
        return jsonify({"success": False, "error": error_message}), status_code

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
            citation_authors = citation_fields.get("Authors")
            if citation_authors:
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

        description["Authors"] = _enrich_authors_with_roles(
            project_path, description.get("Authors")
        )

        validation_citation_fields = dict(citation_fields or {})
        if validation_citation_fields.get("Authors"):
            validation_citation_fields["Authors"] = _normalize_author_names(
                validation_citation_fields.get("Authors")
            )

        validation_description = merge_citation_fields(
            description, validation_citation_fields
        )
        if validation_description.get("Authors"):
            validation_description["Authors"] = _normalize_author_names(
                validation_description.get("Authors")
            )
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
    data = request.get_json()
    if not data or "description" not in data:
        return jsonify({"success": False, "error": "No description data provided"}), 400

    project_path, error_message, status_code = (
        _resolve_requested_or_current_project_root(
            get_current_project,
            data.get("project_path"),
        )
    )
    if project_path is None:
        return jsonify({"success": False, "error": error_message}), status_code

    description = data["description"]
    citation_fields_payload = data.get("citation_fields") or {}
    if not isinstance(citation_fields_payload, dict):
        citation_fields_payload = {}
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
            "Authors": citation_fields_payload.get(
                "Authors", description.get("Authors")
            ),
            "HowToAcknowledge": citation_fields_payload.get(
                "HowToAcknowledge", description.get("HowToAcknowledge")
            ),
            "License": citation_fields_payload.get(
                "License", description.get("License")
            ),
            "ReferencesAndLinks": citation_fields_payload.get(
                "ReferencesAndLinks", description.get("ReferencesAndLinks")
            ),
        }

        synced_authors = _normalize_author_names(
            submitted_citation_fields.get("Authors")
        )
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
        else:
            description["DatasetType"] = _normalize_dataset_type(
                description.get("DatasetType")
            )
        if not description.get("HEDVersion"):
            description.pop("HEDVersion", None)

        validation_description = merge_citation_fields(description, citation_fields)
        issues = project_manager.validate_dataset_description(validation_description)

        citation_payload = dict(description)
        for key, value in citation_fields.items():
            if value not in (None, "", [], {}):
                citation_payload[key] = value

        citation_updated = False
        try:
            project_manager.update_citation_cff(project_path, citation_payload)
            _sync_authors_to_project_json(
                project_path, submitted_citation_fields.get("Authors")
            )
            _remove_legacy_contributor_files(project_path)
            citation_updated = True
        except Exception as e:
            print(f"Warning: could not update CITATION.cff: {e}")

        description_to_store = dict(description)
        if citation_updated:
            # Keep citation-rich metadata in CITATION.cff and avoid redundant fields
            # in dataset_description.json (BIDS recommends Name/DatasetDOI as the
            # compatibility fallback fields in dataset_description.json).
            for citation_owned_key in (
                "Authors",
                "HowToAcknowledge",
                "License",
                "ReferencesAndLinks",
            ):
                description_to_store.pop(citation_owned_key, None)

        with open(desc_path, "w", encoding="utf-8") as f:
            json.dump(description_to_store, f, indent=2, ensure_ascii=False)

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

        if "DatasetType" in description:
            description["DatasetType"] = _normalize_dataset_type(
                description.get("DatasetType")
            )

        validation_citation_fields = dict(citation_fields)
        if validation_citation_fields.get("Authors"):
            validation_citation_fields["Authors"] = _normalize_author_names(
                validation_citation_fields.get("Authors")
            )

        validation_description = merge_citation_fields(
            description, validation_citation_fields
        )
        if validation_description.get("Authors"):
            validation_description["Authors"] = _normalize_author_names(
                validation_description.get("Authors")
            )
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


def handle_get_citation_status(get_current_project, project_manager):
    """Return CITATION.cff status for the current project."""
    project_path, error_message, status_code = (
        _resolve_requested_or_current_project_root(
            get_current_project,
            request.args.get("project_path"),
        )
    )
    if project_path is None:
        return jsonify({"success": False, "error": error_message}), status_code

    try:
        status = project_manager.get_citation_cff_status(project_path)
        return jsonify({"success": True, **status})
    except Exception as e:
        return (
            jsonify(
                {
                    "success": False,
                    "error": f"Failed to read citation status: {str(e)}",
                }
            ),
            500,
        )


def handle_regenerate_citation(
    get_current_project, get_bids_file_path, project_manager
):
    """Regenerate CITATION.cff from dataset_description.json for current project."""
    payload = request.get_json(silent=True) or {}
    project_path, error_message, status_code = (
        _resolve_requested_or_current_project_root(
            get_current_project,
            payload.get("project_path"),
        )
    )
    if project_path is None:
        return jsonify({"success": False, "error": error_message}), status_code

    desc_path = get_bids_file_path(project_path, "dataset_description.json")
    if not desc_path.exists():
        return (
            jsonify(
                {
                    "success": False,
                    "error": "dataset_description.json not found",
                }
            ),
            404,
        )

    try:
        with open(desc_path, "r", encoding="utf-8") as f:
            description = json.load(f)

        if not isinstance(description, dict):
            return (
                jsonify(
                    {
                        "success": False,
                        "error": "dataset_description.json has invalid structure",
                    }
                ),
                400,
            )

        project_manager.update_citation_cff(project_path, description)
        _remove_legacy_contributor_files(project_path)
        status = project_manager.get_citation_cff_status(project_path)

        return jsonify(
            {
                "success": True,
                "message": "CITATION.cff regenerated successfully",
                **status,
            }
        )
    except Exception as e:
        return (
            jsonify(
                {
                    "success": False,
                    "error": f"Failed to regenerate citation: {str(e)}",
                }
            ),
            500,
        )
