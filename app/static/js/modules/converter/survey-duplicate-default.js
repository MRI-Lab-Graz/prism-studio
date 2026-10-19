/** LimeSurvey archives hold one row per participant and wave: number them as sessions by date. */
export function defaultDuplicateHandling(filename) {
    return String(filename || '').toLowerCase().endsWith('.lsa') ? 'sessions' : null;
}

/** Re-uploading a LimeSurvey export should only bring in what is not in the project yet. */
export function defaultSkipExisting(filename) {
    return defaultDuplicateHandling(filename) === 'sessions';
}
