/** Links a participants column to an eligibility criterion from project.json.
 *
 * Only the criterion id is stored in participants.json (EligibilityCriterion);
 * the limits stay in the project metadata. The user always picks the criterion
 * themselves: even an obvious match (Age) is never pre-selected.
 */

const same = (a, b) => String(a || '').trim().toLowerCase() === String(b || '').trim().toLowerCase();

/** The explicit choice (even "none"); nothing chosen shows "none". Unknown ids are dropped. */
export function effectiveLink(colData, criteria) {
    const choice = colData ? colData.eligibility_criterion : undefined;
    return (criteria || []).some((c) => c.id === choice) ? choice : '';
}

/** What gets saved: only an explicit choice. "none" is saved as '' so a Merge can
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
