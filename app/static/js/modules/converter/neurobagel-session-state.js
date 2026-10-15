/**
 * The NeuroBagel widget rebuilds its column state from server defaults plus the
 * last *saved* participants.json. Copy the in-session (unsaved) edits over the
 * rebuilt state so editing never requires "Save Draft" first.
 */

const SCALAR_EDITS = ['description', 'unit', 'data_type', 'standardized_variable', 'term_url', 'label'];

export function carryForwardColumnEdits(prevColumns, nextColumns) {
    for (const [name, next] of Object.entries(nextColumns || {})) {
        const prev = prevColumns?.[name];
        if (!prev || !next) continue;

        SCALAR_EDITS.forEach(key => {
            if (prev[key] !== undefined && prev[key] !== null && prev[key] !== '') next[key] = prev[key];
        });
        if (prev.level_key_mappings) next.level_key_mappings = { ...prev.level_key_mappings };

        // The set of levels follows the data; only their annotations carry over.
        for (const [code, level] of Object.entries(next.levels || {})) {
            if (prev.levels?.[code]) next.levels[code] = { ...level, ...prev.levels[code] };
        }
    }
    return nextColumns;
}
