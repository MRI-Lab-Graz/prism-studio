/** LimeSurvey archives hold one row per participant and wave: number them as sessions by date. */
export function defaultDuplicateHandling(filename) {
    return String(filename || '').toLowerCase().endsWith('.lsa') ? 'sessions' : null;
}

/** Re-uploading a LimeSurvey export should only bring in what is not in the project yet. */
export function defaultSkipExisting(filename) {
    return defaultDuplicateHandling(filename) === 'sessions';
}

/** Set the default and fire `change`: a plain `.value =` would leave Session ID active and green. */
export function applyDuplicateDefault(filename, select) {
    const value = defaultDuplicateHandling(filename);
    if (!value || !select) return;
    select.value = value;
    select.dispatchEvent(new Event('change'));
}
