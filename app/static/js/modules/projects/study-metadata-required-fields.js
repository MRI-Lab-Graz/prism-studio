/**
 * CORE-tier field schema for the Study Metadata form's "Core X/Y" readiness
 * badges. Backend (projects_metadata_helpers.REQUIRED_FIELDS_SCHEMA) is the
 * source of truth, served via GET /api/config -> studyMetadataRequiredFields.
 * This default is only the offline/pre-fetch fallback and must be kept in
 * sync with the backend value.
 */
export const DEFAULT_REQUIRED_FIELDS_SCHEMA = {
    Basics: new Set(['EthicsApprovals', 'Keywords', 'Funding']),
    Overview: new Set(),
    StudyDesign: new Set(['Type']),
    Recruitment: new Set(['Method']),
    Eligibility: new Set(['InclusionCriteria']),
    Procedure: new Set(['Overview']),
};

export function normalizeRequiredFieldsSchema(raw) {
    if (!raw || typeof raw !== 'object') return DEFAULT_REQUIRED_FIELDS_SCHEMA;

    const result = {};
    for (const section of Object.keys(DEFAULT_REQUIRED_FIELDS_SCHEMA)) {
        const fields = raw[section];
        result[section] = Array.isArray(fields)
            ? new Set(fields)
            : DEFAULT_REQUIRED_FIELDS_SCHEMA[section];
    }
    return result;
}
