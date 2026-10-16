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

/** What gets saved: only an explicit choice. A suggestion the user never saw is not
 *  saved (the CLI would not write it either); "none" is saved as '' so a Merge can
 *  clear an existing link. undefined = never linked, write nothing. */
export function savedLink(colData, criteria) {
    const choice = colData ? colData.eligibility_criterion : undefined;
    if (choice === undefined) return undefined;
    return (criteria || []).some((c) => c.id === choice) ? choice : '';
}

export function applyLinkToSchema(schema, column, link) {
    if (!schema[column] || link === undefined) return;
    schema[column].EligibilityCriterion = link;
}

export function unitMismatch(columnUnit, criterionUnit) {
    return Boolean(String(columnUnit || '').trim() && String(criterionUnit || '').trim()
        && !same(columnUnit, criterionUnit));
}

const esc = (text) => String(text ?? '').replace(/[&<>"']/g, (ch) => (
    { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[ch]));

/** <option> list for the panel's select; project.json text is escaped (it can come from a colleague). */
export function criterionOptionsHtml(criteria, linked) {
    return ['<option value="">none</option>'].concat((criteria || []).map((c) => (
        `<option value="${esc(c.id)}"${c.id === linked ? ' selected' : ''}>${esc(c.label || c.id)}${c.unit ? ` (${esc(c.unit)})` : ''}</option>`
    ))).join('');
}
