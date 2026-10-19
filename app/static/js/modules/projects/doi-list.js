/** Pure helpers for the DOI rows (Background Literature). */

export function normalizeDoi(value) {
    return String(value || '').trim()
        .replace(/^https?:\/\/(dx\.)?doi\.org\//i, '')
        .replace(/^doi:\s*/i, '')
        .trim();
}

/** Indexes of entries repeating an earlier DOI (DOIs are case-insensitive). */
export function duplicateIndexes(values) {
    const seen = new Set();
    const dupes = new Set();
    values.forEach((value, i) => {
        const key = normalizeDoi(value).toLowerCase();
        if (!key) return;
        if (seen.has(key)) dupes.add(i);
        seen.add(key);
    });
    return dupes;
}

/** Button shown at the end of a looked-up row: search until checked, then delete. */
export function rowAction({ value, checked }) {
    if (!String(value || '').trim()) return 'none';
    return checked ? 'remove' : 'search';
}
