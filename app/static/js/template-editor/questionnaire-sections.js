/**
 * The "Questionnaire info" card of the template editor: which schema field sits in which section, what a field
 * is called for people, and when a field counts as "not filled in".
 * A field is written "<Section>/<Field>" (Technical, Study, Metadata or I18n); ITEM/ is an item field.
 */
export const QUESTIONNAIRE_SECTIONS = [
    { id: 'identity', label: 'Identity', fields: ['Study/TaskName', 'Study/OriginalName', 'Study/ShortName', 'Study/Category', 'Study/Construct', 'Study/Keywords', 'Study/Description'] },
    { id: 'edition', label: 'Edition and forms', fields: ['Study/Version', 'Study/Versions', 'Study/VariantDefinitions'] },
    { id: 'authors', label: 'Authors and citation', fields: ['Study/Authors', 'Study/Citation', 'Study/DOI'] },
    { id: 'license', label: 'License and access', fields: ['Study/LicenseID', 'Study/LicenseURL', 'Study/CopyrightHolder', 'Study/Access', 'Study/PermissionsNote', 'Study/PermissionsURL'] },
    {
        id: 'administration',
        label: 'Administration',
        fields: [
            'Technical/Respondent', 'Technical/AdministrationMethod', 'Study/Instructions', 'Study/AdministrationTime', 'Study/ScoringTime', 'Study/RecallPeriod',
            'Study/AgeRange', 'Study/ItemCount', 'Technical/Language', 'Technical/SoftwarePlatform', 'Technical/SoftwareVersion',
        ],
    },
    { id: 'quality', label: 'Quality and norms', fields: ['Study/Reliability', 'Study/Validity', 'Study/Norming', 'Study/Subscales'] },
    { id: 'languages', label: 'Languages', fields: ['I18n/Languages', 'I18n/DefaultLanguage', 'I18n/TranslationMethod'] },
    { id: 'record', label: 'Record', fields: ['Metadata/Creator', 'Metadata/CreationDate', 'Metadata/SchemaVersion'] },
    { id: 'advanced', label: 'Advanced', fields: ['Study/TermURL', 'Study/License'] },
];

// Single-value fields the user cannot choose: shown nowhere.
const HIDDEN = new Set(['Technical/StimulusType', 'Technical/FileFormat']);

export const FIELD_LABELS = {
    'Study/TaskName': 'File ID (e.g. phq9)',
    'Study/ShortName': 'Abbreviation (e.g. PHQ-9)',
    'Study/Version': 'Edition (e.g. 3.0)',
    'Study/Versions': 'Forms (e.g. long, short)',
    'Study/VariantDefinitions': 'Response formats',
    'ITEM/ApplicableVersions': 'Used in forms',
};

// A field's help text where the schema's own description is not the right thing to say (the schema is vendored).
export const FIELD_HINTS = {
    'Study/TermURL': 'Link to an external definition of the construct (for example SNOMED or PhenX). Optional. PRISM does not need it: the questionnaire is identified by its PRISM ID, and links to external vocabularies are kept in the specification\'s mappings/ layer.',
};

/** The read-only "PRISM ID: prism:<task>" line (selectable text) shown next to TermURL; '' when there is no ID. */
export function prismIdHtml(id) {
    if (!id) return '';
    const safe = String(id).replace(/[&<>"']/g, (c) => `&#${c.charCodeAt(0)};`);
    return `<span class="text-muted small">PRISM ID: <code class="user-select-all">${safe}</code></span>`;
}

export const LICENSE_FIRST = ['CC-BY-4.0', 'CC0-1.0', 'Proprietary'];

/** Every schema field in exactly one section (a field the map does not know goes to Advanced), in section order. */
export function assignFields(schemaFields) {
    const present = new Set(schemaFields);
    const placed = new Set();
    const map = new Map();
    for (const section of QUESTIONNAIRE_SECTIONS) {
        const fields = section.fields.filter((field) => present.has(field));
        fields.forEach((field) => placed.add(field));
        map.set(section.id, fields);
    }
    for (const field of schemaFields) {
        if (!placed.has(field) && !HIDDEN.has(field)) map.get('advanced').push(field);
    }
    return map;
}

/** How many of a section's `paths` the backend lists as empty required fields (`missing` is a Set of paths). */
export function countMissing(paths, missing) {
    return paths.filter((path) => missing.has(path)).length;
}

/** "Not filled in": absent, null, blank text, an empty list, or a language object whose English text is empty. */
export function isMissing(value) {
    if (value === undefined || value === null) return true;
    if (typeof value === 'string') return value.trim() === '';
    if (Array.isArray(value)) return value.length === 0;
    if (typeof value === 'object') return isMissing(value.en);
    return false;
}
