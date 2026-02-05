# NeuroBagel Compliance Guide

## Overview

The PRISM `participants.json` template now follows **NeuroBagel participant metadata standards** for semantic interoperability. This ensures that participant demographic data can be machine-read and integrated with NeuroBagel's federated data discovery platform.

## What Changed

### New Top-Level Fields

#### 1. **@context** (JSON-LD)
Provides semantic meaning through RDF prefix definitions:

```json
"@context": {
  "nb": "http://neurobagel.org/vocab/",
  "ncit": "http://ncicb.nci.nih.gov/xml/owl/EVS/Thesaurus.owl#",
  "snomed": "http://purl.bioontology.org/ontology/SNOMEDCT/",
  "snomedct": "http://snomed.info/id/",
  "iso639": "http://purl.org/iso/iso639#",
  "iso3166": "http://purl.org/iso/iso3166#",
  "cde": "https://cde.nlm.nih.gov/cdeResultsFull.action?CDE_ID=",
  "hed": "https://www.hedtags.org/display_hed.html?version=latest&search="
}
```

**Vocabularies:**
- **SNOMED-CT**: Medical terminology (sex, diagnosis codes)
- **NCIT**: National Cancer Institute thesaurus (study groups, diagnoses)
- **ISO 639/3166**: Language and country codes
- **CDE**: NIH Common Data Elements
- **HED**: Hierarchical Event Descriptors

#### 2. **VariableType** (Per Variable)
Classifies variable semantics:

- `Identifier` - Unique identifiers (participant_id)
- `Continuous` - Numeric ranges (age, height, weight, BMI)
- `Categorical` - Discrete categories with levels (sex, education, group)
- `Collection` - Multi-valued variables (assessments, multiple languages)

#### 3. **Annotations** (Per Variable)
Provides machine-readable semantic tags:

```json
"age": {
  "VariableType": "Continuous",
  "Annotations": {
    "IsAbout": "snomed:397669002",           // SNOMED code for age
    "Label": "Age",                          // Human-readable label
    "DictionarySourceURI": "cde:5057201"     // NIH CDE reference
  }
}
```

#### 4. **Semantic Coding for Categorical Variables**
Categorical levels now include ontology codes:

```json
"sex": {
  "M": {
    "en": "Male",
    "de": "Männlich",
    "SnomedCode": "snomed:248153007",
    "IRI": "http://snomed.info/id/248153007"
  }
}
```

**Benefits:**
- Machine-readable standardization
- Automatic mapping between studies
- Interoperability with clinical databases

## Implementation Details

### Variables with Added Semantic Annotations

| Variable | VariableType | Primary Annotation | Purpose |
|----------|------|-------------------|---------|
| participant_id | Identifier | snomed:14421000 (Person) | Unique participant ID |
| age | Continuous | snomed:397669002 (Age) | Participant age |
| sex | Categorical | snomed:263495000 (Biological sex) | Biological sex at birth |
| gender | Categorical | snomed:14647231000119105 (Gender identity) | Gender identity |
| handedness | Categorical | snomed:20863000 (Handedness) | Hand preference |
| education_level | Categorical | snomed:224530016 (Education) | Education level (ISCED) |
| education_years | Continuous | snomed:224530016 (Education) | Years of formal education |
| group | Categorical | ncit:C41185 (Study group) | Study group assignment |

### SNOMED-CT Codes by Concept

**Sex/Gender:**
- Male: `248153007`
- Female: `248152002`
- Intersex: `34000006`
- Non-binary: `33791000087105`
- Transgender man: `407376001`
- Transgender woman: `407377005`

**Handedness:**
- Right-handed: `9640002`
- Left-handed: `19935008`
- Ambidextrous: `23481009`

**Other:**
- Age: `397669002`
- Education: `224530016`
- Biological sex: `263495000`
- Gender identity: `14647231000119105`

## Validation & Usage

### JSON-LD Validation
Validate with NeuroBagel annotation tool:
https://annotate.neurobagel.org

### Data Dictionary Lookup
Fields reference NIH Common Data Elements (CDE):
- Age: [CDE 5057201](https://cde.nlm.nih.gov/cdeResultsFull.action?CDE_ID=5057201)
- Sex: [CDE 5057211](https://cde.nlm.nih.gov/cdeResultsFull.action?CDE_ID=5057211)
- Education: [CDE 5090887](https://cde.nlm.nih.gov/cdeResultsFull.action?CDE_ID=5090887)

### NeuroBagel Harmonization
The template declares compliance with NeuroBagel standards:

```json
"Study": {
  "NeuroBagelHarmonization": "This template follows NeuroBagel participant metadata standards..."
}
```

## Backward Compatibility

✅ **Fully backward compatible**
- All existing PRISM fields preserved
- Semantic annotations are *additive*, not replacement
- Standard BIDS participants.json still valid
- No changes to data values or structure

## Ontology Resolution

When processing this file, systems can:

1. **Resolve SNOMED codes** to get clinical definitions
2. **Link to CDE** for data element metadata
3. **Harmonize with other datasets** using same codes
4. **Integrate with clinical systems** (HER, HL7)
5. **Enable federated search** across studies

## Example: Sex/Gender Harmonization

**Before (Data Only):**
```json
"sex": "M"
```

**After (With Semantic Annotation):**
```json
"sex": {
  "value": "M",
  "label": "Male",
  "snomed": "http://snomed.info/id/248153007",
  "icd11": "QL41",
  "LOINC": "21840-4"
}
```

This allows:
- Automatic mapping between coding systems
- Integration with clinical databases
- Machine learning models trained on standardized codes

## References

### NeuroBagel Resources
- Documentation: https://github.com/neurobagel/documentation
- Data Models: https://neurobagel.org/data-models/
- Annotation Tool: https://annotate.neurobagel.org/
- BIDS Compliance: https://bids-standard.github.io/

### Ontologies
- SNOMED-CT: https://www.snomed.org/
- NCIT: https://ncit.nci.nih.gov/
- CDE: https://cde.nlm.nih.gov/
- HED: https://www.hedtags.org/

### Standards
- ISCED 2011: https://uis.unesco.org/en/topic/international-standard-classification-education-isced
- ISO 639: https://www.loc.gov/standards/iso639-2/
- ISO 3166: https://www.iso.org/iso-3166-country-codes.html
- JSON-LD: https://json-ld.org/

## Migration Guide

### For Existing Datasets

If you have an older `participants.json`, no action needed! It remains valid. To upgrade:

1. Update your schema to include `@context` block
2. Add `VariableType` to each variable definition
3. Add `Annotations` with SNOMED/NCIT codes for key variables
4. Add SnomedCode/IRI to categorical levels

### For BIDS Validators

BIDS validators treat the `@context` and annotations as custom extensions. Standard BIDS compliance is maintained—these additions enable *enhanced* interoperability.

## Future Enhancements

### Planned Additions
- HED tags for event-related variables
- Value-level annotations for multi-language coding
- Links to standardized assessment tools
- Integration with FAIR data principles

### Community Contributions
The NeuroBagel community welcomes refinements:
- Suggest additional SNOMED codes
- Improve translations
- Add domain-specific extensions
- Report compatibility issues

---

**Version:** 1.2.0  
**Updated:** 2026-01-22  
**Compliant With:** NeuroBagel v1.0, BIDS 1.8+, JSON-LD 1.1
