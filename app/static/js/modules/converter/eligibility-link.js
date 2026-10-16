/** Links a participants column to an eligibility criterion from project.json.
 *
 * Only the criterion id is stored in participants.json (EligibilityCriterion);
 * the limits stay in the project metadata. Pre-selecting a criterion by
 * NeuroBagel term is GUI state: the user confirms or changes it.
 */

const same = (a, b) => String(a || '').trim().toLowerCase() === String(b || '').trim().toLowerCase();

export function suggestCriterion(colData, criteria) {
    if (!colData || !colData.term_url) return '';
    const hit = (criteria || []).find((c) => c.term && same(c.term, colData.term_url));
    return hit ? hit.id : '';
}

/** The explicit choice (even "none") wins; otherwise the suggestion. Unknown ids are dropped. */
export function effectiveLink(colData, criteria) {
    const choice = colData ? colData.eligibility_criterion : undefined;
    if (choice === undefined) return suggestCriterion(colData, criteria);
    return (criteria || []).some((c) => c.id === choice) ? choice : '';
}

export function applyLinkToSchema(schema, column, criterionId) {
    if (!schema[column]) return;
    if (criterionId) schema[column].EligibilityCriterion = criterionId;
    else delete schema[column].EligibilityCriterion;
}

export function unitMismatch(columnUnit, criterionUnit) {
    return Boolean(String(columnUnit || '').trim() && String(criterionUnit || '').trim()
        && !same(columnUnit, criterionUnit));
}
