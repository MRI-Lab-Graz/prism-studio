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

/**
 * Section-level badge elements are rendered with id `sm<Key>Badge` (e.g.
 * smBasicsBadge -> "Basics"), matching the keys in computeLocalCompleteness()'s
 * `sections` map (metadata.js). Used to derive which sections belong to a
 * collapsed section-group header (Core study setup / Recruitment and
 * execution / Reporting and follow-up) from the DOM itself, instead of a
 * second hardcoded section list the template's actual grouping could drift
 * from if a section is ever moved between groups.
 */
export function sectionKeyFromBadgeId(id) {
    return String(id || '').replace(/^sm/, '').replace(/Badge$/, '');
}

/**
 * Required/Core/FAIR totals for just the given subset of section keys (e.g.
 * the sections inside one collapsed group), reusing computeGlobalTierTotals's
 * summation over that subset.
 */
export function computeGroupTierTotals(sections, sectionKeys) {
    const subset = {};
    for (const key of sectionKeys || []) {
        if (sections && sections[key]) subset[key] = sections[key];
    }
    return computeGlobalTierTotals(subset);
}
