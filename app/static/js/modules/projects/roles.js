// Standard CRediT Taxonomy v1 (https://credit.niso.org/)
export const CREDIT_ROLES = [
    'Conceptualization',
    'Data curation',
    'Formal analysis',
    'Funding acquisition',
    'Investigation',
    'Methodology',
    'Project administration',
    'Resources',
    'Software',
    'Supervision',
    'Validation',
    'Visualization',
    'Writing - original draft',
    'Writing - review & editing',
];

export function normalizeRoleLabel(value) {
    const text = String(value || '').trim();
    if (!text) return '';
    const matched = CREDIT_ROLES.find(role => role.toLowerCase() === text.toLowerCase());
    return matched || text;
}

// Roles may be separated by commas, semicolons or newlines.
export function parseRolesInput(value) {
    const seen = new Set();
    return String(value || '')
        .split(/[,;\n]/)
        .map(normalizeRoleLabel)
        .filter(role => {
            const key = role.toLowerCase();
            if (!role || seen.has(key)) return false;
            seen.add(key);
            return true;
        });
}
