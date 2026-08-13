/**
 * Sums CORE/FAIR/Required(creation-blocking) field counts across every
 * section, for the compact reminder badges on the "Project Loaded" panel
 * (open-project.js). Pure function of computeLocalCompleteness()'s sections
 * map (metadata.js) - no DOM access, so it stays unit-testable without a
 * browser/jsdom (same reasoning as study-metadata-required-fields.js).
 */
export function computeGlobalTierTotals(sections) {
    const totals = {
        blockingTotal: 0, blockingFilled: 0,
        coreTotal: 0, coreFilled: 0,
        fairTotal: 0, fairFilled: 0
    };
    for (const sec of Object.values(sections || {})) {
        totals.coreTotal += sec.required_total || 0;
        totals.coreFilled += sec.required_filled || 0;
        totals.fairTotal += sec.optional_total || 0;
        totals.fairFilled += sec.optional_filled || 0;
        for (const f of sec.fields || []) {
            if (f.blocksCreation) {
                totals.blockingTotal += 1;
                if (f.filled) totals.blockingFilled += 1;
            }
        }
    }
    return totals;
}
