import json
import re
from pathlib import Path

from flask import jsonify, request
from src.orcid_lookup import OrcidLookupError, search_orcid_candidates

from .projects_helpers import _resolve_requested_or_current_project_root


_PLACEHOLDER_AUTHOR_SNIPPETS = (
    "prism",
    "dataset",
    "optional",
    "required",
    "recommended",
    "list of",
    "individuals who contributed",
)
_PLACEHOLDER_DATASET_NAMES = {
    "prism survey dataset",
    "prism biometrics dataset",
    "untitled dataset",
    "prism dataset",
}
_PLACEHOLDER_KEYWORDS = {"psychology", "survey", "prism", "experiment"}
_PLACEHOLDER_ACKNOWLEDGEMENTS_SNIPPETS = (
    "created using the prism framework",
    "prism framework",
)
_PLACEHOLDER_DESCRIPTION_SNIPPETS = (
    "prism-compatible dataset for psychological research",
)


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


def _canonical_author_name(author) -> str:
    """Return a comparison-friendly author identity string."""
    if isinstance(author, dict):
        given = str(author.get("given-names") or author.get("given") or "").strip()
        family = str(author.get("family-names") or author.get("family") or "").strip()
        name = str(author.get("name") or "").strip()
        if given and family:
            raw = f"{given} {family}"
        elif name:
            raw = name
        else:
            raw = family or given
    else:
        raw = str(author or "").strip()

    if not raw:
        return ""

    text = raw
    if "," in text:
        family, given = text.split(",", 1)
        text = f"{given.strip()} {family.strip()}".strip()

    text = re.sub(r"[^a-z0-9\s]", " ", text.lower())
    return re.sub(r"\s+", " ", text).strip()


def _canonical_author_name_set(authors_value) -> set[str]:
    """Build canonical author identity set from mixed author payloads."""
    if isinstance(authors_value, (str, dict)):
        authors = [authors_value]
    elif isinstance(authors_value, list):
        authors = authors_value
    else:
        return set()

    names = set()
    for author in authors:
        canonical = _canonical_author_name(author)
        if canonical:
            names.add(canonical)
    return names


def _clean_text_list(value) -> list[str]:
    if isinstance(value, list):
        values = value
    elif value in (None, "", {}, []):
        values = []
    else:
        values = [value]

    cleaned = []
    for item in values:
        text = str(item or "").strip()
        if text:
            cleaned.append(text)
    return cleaned


def _looks_placeholder_author_set(author_names: set[str]) -> bool:
    if not author_names:
        return False
    return all(
        any(snippet in name for snippet in _PLACEHOLDER_AUTHOR_SNIPPETS)
        for name in author_names
    )


def _looks_placeholder_dataset_name(value) -> bool:
    normalized = re.sub(r"\s+", " ", str(value or "").strip().lower())
    if not normalized:
        return True
    if normalized in _PLACEHOLDER_DATASET_NAMES:
        return True
    return normalized.startswith("prism ") and normalized.endswith(" dataset")


def _looks_placeholder_keyword_set(value) -> bool:
    keywords = [k.lower() for k in _clean_text_list(value)]
    if not keywords:
        return True
    keyword_set = set(keywords)
    return "prism" in keyword_set and keyword_set.issubset(_PLACEHOLDER_KEYWORDS)


def _looks_placeholder_acknowledgements(value) -> bool:
    normalized = re.sub(r"\s+", " ", str(value or "").strip().lower())
    if not normalized:
        return True
    return any(snippet in normalized for snippet in _PLACEHOLDER_ACKNOWLEDGEMENTS_SNIPPETS)


def _looks_placeholder_description(value) -> bool:
    normalized = re.sub(r"\s+", " ", str(value or "").strip().lower())
    if not normalized:
        return True
    return any(snippet in normalized for snippet in _PLACEHOLDER_DESCRIPTION_SNIPPETS)


def _apply_citation_precedence_for_display(description: dict, citation_fields: dict) -> dict:
    merged = dict(description)
    if not citation_fields:
        return merged

    citation_authors = citation_fields.get("Authors")
    if citation_authors:
        citation_names = _canonical_author_name_set(citation_authors)
        if citation_names and not _looks_placeholder_author_set(citation_names):
            merged["Authors"] = citation_authors

    for key in ("License", "HowToAcknowledge", "ReferencesAndLinks"):
        value = citation_fields.get(key)
        if value not in (None, "", [], {}):
            merged[key] = value

    citation_title = str(citation_fields.get("Title") or "").strip()
    if citation_title and _looks_placeholder_dataset_name(merged.get("Name")):
        merged["Name"] = citation_title

    citation_keywords = citation_fields.get("Keywords")
    if citation_keywords and _looks_placeholder_keyword_set(merged.get("Keywords")):
        merged["Keywords"] = citation_keywords

    citation_description = str(citation_fields.get("Description") or "").strip()
    if citation_description and _looks_placeholder_description(merged.get("Description")):
        merged["Description"] = citation_description

    if _looks_placeholder_acknowledgements(merged.get("Acknowledgements")):
        merged["Acknowledgements"] = str(citation_fields.get("HowToAcknowledge") or "").strip()

    return merged


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


def handle_search_orcid_by_name(search_candidates=search_orcid_candidates):
    """Search ORCID candidates by given/family name using backend lookup service."""
    given_names = str(request.args.get("given_names") or "").strip()
    family_name = str(request.args.get("family_name") or "").strip()
    current_orcid = str(request.args.get("current_orcid") or "").strip()
    limit_raw = str(request.args.get("limit") or "").strip()

    if not given_names and not family_name:
        return (
            jsonify(
                {
                    "success": False,
                    "error": "Provide given_names and/or family_name for ORCID search.",
                }
            ),
            400,
        )

    limit = 5
    if limit_raw:
        try:
            limit = int(limit_raw)
        except ValueError:
            limit = 5

    try:
        candidates = search_candidates(
            given_names,
            family_name,
            limit=limit,
            preferred_orcid=current_orcid,
        )
    except OrcidLookupError:
        return (
            jsonify(
                {
                    "success": False,
                    "error": "ORCID lookup is currently unavailable.",
                    "candidates": [],
                }
            ),
            502,
        )

    return jsonify(
        {
            "success": True,
            "candidates": candidates,
        }
    )


def handle_get_metadata_status(get_current_project, project_manager):
    """Return metadata-file consistency status for the current project."""
    project_path, error_message, status_code = (
        _resolve_requested_or_current_project_root(
            get_current_project,
            request.args.get("project_path"),
        )
    )
    if project_path is None:
        return jsonify({"success": False, "error": error_message}), status_code

    try:
        status = project_manager.get_metadata_sync_status(project_path)
        return jsonify({"success": True, **status})
    except Exception as exc:
        return (
            jsonify(
                {
                    "success": False,
                    "error": f"Could not read metadata consistency status: {exc}",
                }
            ),
            500,
        )


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
    """Normalize an author entry to a project.json governance contact object."""
    given = ""
    family = ""
    name = ""
    website = ""
    orcid = ""
    email = ""
    affiliation = ""
    roles = []
    corresponding = False

    if isinstance(author, dict):
        given = str(author.get("given-names") or author.get("given") or "").strip()
        family = str(author.get("family-names") or author.get("family") or "").strip()
        name = str(author.get("name") or "").strip()
        website = str(author.get("website") or "").strip()
        orcid = str(author.get("orcid") or author.get("ORCID") or "").strip()
        email = str(author.get("email") or "").strip()
        affiliation = str(author.get("affiliation") or "").strip()
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

    contributor = {
        "name": display_name,
        "roles": roles,
        "orcid": orcid,
        "email": email,
        "corresponding": corresponding,
    }

    if given:
        contributor["given-names"] = given
    if family:
        contributor["family-names"] = family
    if website:
        contributor["website"] = website
    if affiliation:
        contributor["affiliation"] = affiliation

    return contributor


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
            description = _apply_citation_precedence_for_display(
                description,
                citation_fields,
            )

        description = project_manager.apply_project_metadata_precedence(
            description,
            project_path=project_path,
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
            # Only skip None (field not submitted at all).
            # Explicitly submitted empty values ([], "") must overwrite the
            # existing CITATION.cff value so the user can clear a field.
            if value is None:
                continue
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

        project_metadata_payload = dict(description)
        for key, value in submitted_citation_fields.items():
            if value is None:
                continue
            project_metadata_payload[key] = value

        citation_updated = False
        try:
            project_manager.sync_dataset_metadata_to_project_json(
                project_path, project_metadata_payload
            )
            _sync_authors_to_project_json(
                project_path, submitted_citation_fields.get("Authors")
            )
            project_manager.update_citation_cff(project_path, project_metadata_payload)
            _remove_legacy_contributor_files(project_path)
            citation_updated = True
        except Exception as e:
            print(f"Warning: could not update CITATION.cff: {e}")

        description_to_store = dict(description)
        if citation_updated or citation_cff_path.exists():
            # Keep citation-owned metadata in CITATION.cff and avoid redundant
            # fields in dataset_description.json to stay BIDS-compliant.
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
    """Regenerate CITATION.cff from canonical project metadata for current project."""
    payload = request.get_json(silent=True) or {}
    project_path, error_message, status_code = (
        _resolve_requested_or_current_project_root(
            get_current_project,
            payload.get("project_path"),
        )
    )
    if project_path is None:
        return jsonify({"success": False, "error": error_message}), status_code

    try:
        project_manager.regenerate_citation_cff(project_path)
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
