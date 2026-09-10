/**
 * Groups official-library template rows (survey or biometrics) under their
 * Study.Category, in a fixed display order (matches the modality's schema
 * Category enum). Pure function - no DOM access - extracted out of
 * survey-generator.js so the grouping logic is unit-testable (same
 * reasoning as projects/global-tier-totals.js).
 */
export function groupTemplatesByCategory(files, categoryOrder) {
    const buckets = new Map(categoryOrder.map((category) => [category, []]));
    const fallback = categoryOrder[categoryOrder.length - 1];

    for (const file of files || []) {
        const category = file?.study?.Category;
        const key = buckets.has(category) ? category : fallback;
        buckets.get(key).push(file);
    }

    return categoryOrder
        .map((category) => ({ category, files: buckets.get(category) }))
        .filter((group) => group.files.length > 0);
}
