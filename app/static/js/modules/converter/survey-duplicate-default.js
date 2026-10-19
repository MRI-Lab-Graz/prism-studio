/** LimeSurvey archives hold one row per participant and wave: number them as sessions by date. */
export function defaultDuplicateHandling(filename) {
    return String(filename || '').toLowerCase().endsWith('.lsa') ? 'sessions' : null;
}
