#!/usr/bin/env python3
"""
FAIR Data Export Module for Psycho-Validator
Implements Dublin Core and DataCite metadata export for FAIR compliance
"""

import json
import xml.etree.ElementTree as ET
from datetime import datetime
import os

def export_dublin_core(metadata_file, output_file=None):
    """
    Export metadata to Dublin Core format for FAIR findability
    Supports both dataset-level (dataset_description.json) and stimulus-level metadata
    """
    with open(metadata_file, 'r') as f:
        metadata = json.load(f)
    
    # Create Dublin Core XML structure
    root = ET.Element("metadata")
    root.set("xmlns:dc", "http://purl.org/dc/elements/1.1/")
    root.set("xmlns:dcterms", "http://purl.org/dc/terms/")
    
    # Detect if this is a dataset description (BIDS-style) or stimulus metadata
    is_dataset_description = "Name" in metadata and "BIDSVersion" in metadata
    
    if is_dataset_description:
        # Dataset-level Dublin Core mapping
        dc_mapping = {
            "dc:title": metadata.get("Name", "Unknown Dataset"),
            "dc:creator": format_creators(metadata.get("Authors", [])),
            "dc:subject": "; ".join(metadata.get("Keywords", ["Psychology"])),
            "dc:description": metadata.get("Description", "Psychological research dataset"),
            "dc:date": get_nested_value(metadata, "DataCollection.start_date", datetime.now().strftime("%Y-%m-%d")),
            "dc:type": "Dataset",
            "dc:identifier": metadata.get("DatasetDOI", f"local:{os.path.basename(metadata_file)}"),
            "dc:language": "en",
            "dc:rights": metadata.get("License", "All rights reserved")
        }
    else:
        # Stimulus-level Dublin Core mapping (backwards compatibility)
        dc_mapping = {
            "dc:title": get_nested_value(metadata, "Study.TaskName", "Unknown Task"),
            "dc:creator": get_nested_value(metadata, "Metadata.Creator", "Unknown Creator"),
            "dc:subject": get_nested_value(metadata, "Categories.PrimaryCategory", "Psychology"),
            "dc:description": get_nested_value(metadata, "Metadata.Description", "Psychological stimulus data"),
            "dc:date": get_nested_value(metadata, "Metadata.CreationDate", datetime.now().strftime("%Y-%m-%d")),
            "dc:type": get_nested_value(metadata, "Technical.StimulusType", "Dataset"),
            "dc:format": get_nested_value(metadata, "Technical.FileFormat", "Unknown"),
            "dc:identifier": get_nested_value(metadata, "Metadata.DatasetDOI", f"local:{os.path.basename(metadata_file)}"),
            "dc:language": "en",
            "dc:rights": get_nested_value(metadata, "Metadata.License", "All rights reserved")
        }
    
    # Add optional elements if available
    keywords = get_nested_value(metadata, "Metadata.Keywords", [])
    if keywords:
        for keyword in keywords:
            dc_mapping[f"dc:subject_{len(dc_mapping)}"] = keyword
    
    # Add ORCID if available
    orcid = get_nested_value(metadata, "Metadata.CreatorORCID")
    if orcid:
        dc_mapping["dcterms:creator"] = f"https://orcid.org/{orcid}"
    
    # Add institutional affiliation
    institution = get_nested_value(metadata, "Metadata.Institution")
    if institution:
        dc_mapping["dcterms:publisher"] = institution
    
    # Add ROR if available
    ror = get_nested_value(metadata, "Metadata.InstitutionROR")
    if ror:
        dc_mapping["dcterms:publisher_id"] = ror
    
    # Create XML elements
    for key, value in dc_mapping.items():
        if value:
            elem = ET.SubElement(root, key.split('_')[0])  # Remove suffix for duplicates
            elem.text = str(value)
    
    # Write to file
    if output_file is None:
        output_file = metadata_file.replace('.json', '_dublin_core.xml')
    
    tree = ET.ElementTree(root)
    ET.indent(tree, space="  ", level=0)  # Pretty print
    tree.write(output_file, encoding='utf-8', xml_declaration=True)
    
    return output_file

def export_datacite(metadata_file, output_file=None):
    """
    Export metadata to DataCite format for DOI registration
    """
    with open(metadata_file, 'r') as f:
        metadata = json.load(f)
    
    # Create DataCite XML structure
    root = ET.Element("resource")
    root.set("xmlns", "http://datacite.org/schema/kernel-4")
    root.set("xmlns:xsi", "http://www.w3.org/2001/XMLSchema-instance")
    root.set("xsi:schemaLocation", "http://datacite.org/schema/kernel-4 http://schema.datacite.org/meta/kernel-4/metadata.xsd")
    
    # Detect if this is a dataset description or stimulus metadata
    is_dataset_description = "Name" in metadata and "BIDSVersion" in metadata
    
    # Identifier (DOI)
    identifier = ET.SubElement(root, "identifier")
    identifier.set("identifierType", "DOI")
    if is_dataset_description:
        doi = metadata.get("DatasetDOI")
    else:
        doi = get_nested_value(metadata, "Metadata.DatasetDOI")
    identifier.text = doi if doi else "10.PLACEHOLDER/DATASET"
    
    # Creators
    creators = ET.SubElement(root, "creators")
    
    if is_dataset_description:
        # Handle BIDS-style authors array
        authors = metadata.get("Authors", [])
        for author in authors:
            creator = ET.SubElement(creators, "creator")
            creator_name = ET.SubElement(creator, "creatorName")
            
            if isinstance(author, dict):
                creator_name.text = author.get("name", "Unknown Creator")
                # Add ORCID if available
                orcid = author.get("orcid")
                if orcid:
                    name_identifier = ET.SubElement(creator, "nameIdentifier")
                    name_identifier.set("nameIdentifierScheme", "ORCID")
                    name_identifier.set("schemeURI", "https://orcid.org")
                    name_identifier.text = f"https://orcid.org/{orcid}"
                # Add affiliation
                affiliation = author.get("affiliation")
                if affiliation:
                    aff_elem = ET.SubElement(creator, "affiliation")
                    aff_elem.text = affiliation
            else:
                creator_name.text = str(author)
    else:
        # Handle stimulus-level metadata (backwards compatibility)
        creator = ET.SubElement(creators, "creator")
        creator_name = ET.SubElement(creator, "creatorName")
        creator_name.text = get_nested_value(metadata, "Metadata.Creator", "Unknown Creator")
        
        # Add ORCID if available
        orcid = get_nested_value(metadata, "Metadata.CreatorORCID")
        if orcid:
            name_identifier = ET.SubElement(creator, "nameIdentifier")
            name_identifier.set("nameIdentifierScheme", "ORCID")
            name_identifier.set("schemeURI", "https://orcid.org")
            name_identifier.text = f"https://orcid.org/{orcid}"
    
    # Titles
    titles = ET.SubElement(root, "titles")
    title = ET.SubElement(titles, "title")
    title.text = get_nested_value(metadata, "Study.TaskName", "Psychological Stimulus Dataset")
    
    # Publisher
    publisher = ET.SubElement(root, "publisher")
    publisher.text = get_nested_value(metadata, "Metadata.Institution", "Unknown Institution")
    
    # Publication Year
    pub_year = ET.SubElement(root, "publicationYear")
    creation_date = get_nested_value(metadata, "Metadata.CreationDate", datetime.now().strftime("%Y-%m-%d"))
    pub_year.text = creation_date.split('-')[0]  # Extract year
    
    # Resource Type
    resource_type = ET.SubElement(root, "resourceType")
    resource_type.set("resourceTypeGeneral", "Dataset")
    resource_type.text = f"Psychology {get_nested_value(metadata, 'Technical.StimulusType', 'Data')}"
    
    # Subjects/Keywords
    subjects = ET.SubElement(root, "subjects")
    
    # Add primary category
    primary_cat = get_nested_value(metadata, "Categories.PrimaryCategory")
    if primary_cat:
        subject = ET.SubElement(subjects, "subject")
        subject.text = primary_cat
    
    # Add keywords
    keywords = get_nested_value(metadata, "Metadata.Keywords", [])
    for keyword in keywords:
        subject = ET.SubElement(subjects, "subject")
        subject.text = keyword
    
    # Dates
    dates = ET.SubElement(root, "dates")
    date_created = ET.SubElement(dates, "date")
    date_created.set("dateType", "Created")
    date_created.text = get_nested_value(metadata, "Metadata.CreationDate", datetime.now().strftime("%Y-%m-%d"))
    
    # Rights
    rights_list = ET.SubElement(root, "rightsList")
    rights = ET.SubElement(rights_list, "rights")
    license_info = get_nested_value(metadata, "Metadata.License", "All rights reserved")
    rights.text = license_info
    
    if license_info.startswith("CC"):
        rights.set("rightsURI", f"https://creativecommons.org/licenses/{license_info.lower().replace('cc-', '')}/4.0/")
    
    # Descriptions
    descriptions = ET.SubElement(root, "descriptions")
    description = ET.SubElement(descriptions, "description")
    description.set("descriptionType", "Abstract")
    
    desc_text = get_nested_value(metadata, "Metadata.Description")
    if not desc_text:
        # Generate description from available metadata
        task_name = get_nested_value(metadata, "Study.TaskName", "unknown task")
        stimulus_type = get_nested_value(metadata, "Technical.StimulusType", "stimulus")
        desc_text = f"Psychological {stimulus_type.lower()} data from {task_name} experiment"
    
    description.text = desc_text
    
    # Write to file
    if output_file is None:
        output_file = metadata_file.replace('.json', '_datacite.xml')
    
    tree = ET.ElementTree(root)
    ET.indent(tree, space="  ", level=0)
    tree.write(output_file, encoding='utf-8', xml_declaration=True)
    
    return output_file

def get_nested_value(dictionary, key_path, default=None):
    """
    Get nested dictionary value using dot notation (e.g., 'Study.TaskName')
    """
    keys = key_path.split('.')
    value = dictionary
    
    try:
        for key in keys:
            value = value[key]
        return value
    except (KeyError, TypeError):
        return default

def format_creators(authors):
    """
    Format authors list for Dublin Core creator field
    """
    if not authors:
        return "Unknown Creator"
    
    creator_names = []
    for author in authors:
        if isinstance(author, dict):
            name = author.get("name", "Unknown")
            orcid = author.get("orcid")
            if orcid:
                creator_names.append(f"{name} (ORCID: {orcid})")
            else:
                creator_names.append(name)
        else:
            creator_names.append(str(author))
    
    return "; ".join(creator_names)

def export_fair_metadata(metadata_file):
    """
    Export metadata in multiple FAIR-compliant formats
    """
    results = {}
    
    try:
        # Dublin Core export
        dc_file = export_dublin_core(metadata_file)
        results['dublin_core'] = dc_file
        print(f"✅ Dublin Core exported: {dc_file}")
    except Exception as e:
        print(f"❌ Dublin Core export failed: {e}")
        results['dublin_core'] = None
    
    try:
        # DataCite export
        datacite_file = export_datacite(metadata_file)
        results['datacite'] = datacite_file
        print(f"✅ DataCite exported: {datacite_file}")
    except Exception as e:
        print(f"❌ DataCite export failed: {e}")
        results['datacite'] = None
    
    return results

def main():
    """
    Command line interface for FAIR metadata export
    """
    import sys
    
    if len(sys.argv) != 2:
        print("Usage: python fair_export.py <metadata_file.json>")
        sys.exit(1)
    
    metadata_file = sys.argv[1]
    
    if not os.path.exists(metadata_file):
        print(f"Error: File {metadata_file} not found")
        sys.exit(1)
    
    print(f"🔄 Exporting FAIR metadata for: {metadata_file}")
    results = export_fair_metadata(metadata_file)
    
    print("\n📊 Export Summary:")
    for format_name, output_file in results.items():
        status = "✅ Success" if output_file else "❌ Failed"
        print(f"  {format_name}: {status}")
        if output_file:
            print(f"    Output: {output_file}")

if __name__ == "__main__":
    main()
