/** Rules for a new item ID: it becomes a data column name, so letters, digits, "_" and "-" only,
 *  and two IDs that differ only in case count as the same. Returns '' when the ID is fine. */
export function itemIdProblem(id, existingIds) {
    if (id === '__proto__' || !/^[A-Za-z0-9_-]+$/.test(id)) return 'Use only letters, digits, "_" and "-" in an item ID (it becomes a data column name).';
    const clash = existingIds.find((other) => other.toLowerCase() === id.toLowerCase());
    return clash ? `An item "${clash}" already exists (IDs differing only in case count as the same).` : '';
}
