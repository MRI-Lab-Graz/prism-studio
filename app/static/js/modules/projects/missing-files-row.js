// Missing Files table (Study Metadata > Missing Data & Known Issues): each
// row is Subject | Session | Modality | Reason | Detail, serialized as a
// single " | "-joined line so it keeps fitting the existing MissingData.MissingFiles
// string field (project.json) with no backend changes.

export const MISSING_FILE_REASON_OPTIONS = [
    { value: '', label: 'Select a reason...' },
    { value: 'motion_artifact', label: 'Motion artifact' },
    { value: 'scanner_defect', label: 'MRI scanner defect' },
    { value: 'task_not_understood', label: 'Task not understood' },
    { value: 'equipment_failure', label: 'Equipment failure' },
    { value: 'participant_withdrew', label: 'Participant withdrew' },
    { value: 'other', label: 'Other' },
];

const FIELD_ORDER = ['subject', 'session', 'modality', 'reason', 'detail'];

// ponytail: legacy 2-column rows ("SubjectID | what's missing") parse into
// subject/session rather than their old meaning, since there's no reliable
// way to tell old and new shapes apart. Upgrade path: bump a schema version
// into project.json if this ever needs a real migration.
export function parseMissingFilesValue(rawValue) {
    const text = String(rawValue || '').trim();
    if (!text) return [];
    return text
        .split('\n')
        .map(line => line.trim())
        .filter(Boolean)
        .map(line => {
            const parts = line.split('|').map(p => p.trim());
            while (parts.length < FIELD_ORDER.length) parts.push('');
            const row = {};
            FIELD_ORDER.forEach((key, i) => {
                row[key] = parts[i];
            });
            return row;
        });
}

export function combineMissingFilesRow(fields = {}) {
    const values = FIELD_ORDER.map(key => String(fields[key] || '').trim());
    if (!values.some(Boolean)) return '';
    while (values.length > 1 && !values[values.length - 1]) values.pop();
    return values.join(' | ');
}
