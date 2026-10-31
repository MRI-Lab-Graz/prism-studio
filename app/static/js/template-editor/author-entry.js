/** One author is stored as one string, always "Family, Given (ORCID)" (the template schema has no structure). */
const ORCID = /\d{4}-\d{4}-\d{4}-\d{3}[\dX]/;

/** The bare ORCID iD from an iD or URL; '' when there is none. */
export const orcidId = (text) => (String(text ?? '').match(ORCID) || [''])[0];

const clean = (text) => String(text ?? '').replace(/\s+/g, ' ').trim();

/** [family, given, orcid] -> stored string; '' = incomplete (a name missing, or an ORCID that is not one). */
export function composeAuthor([family, given, orcid]) {
    const name = [clean(family), clean(given)];
    if (!name[0] || !name[1]) return '';
    const id = orcidId(orcid);
    if (clean(orcid) && !id) return '';
    return `${name.join(', ')}${id ? ` (${id})` : ''}`;
}

/** Stored string -> [family, given, orcid]; null when it is not in the fixed format. */
export function parseAuthor(text) {
    const match = String(text ?? '').match(/^([^,()]+),\s*([^()]+?)\s*(?:\((\d{4}-\d{4}-\d{4}-\d{3}[\dX])\))?$/);
    return match ? [clean(match[1]), clean(match[2]), match[3] || ''] : null;
}

const same = (a, b) => clean(a).toLowerCase() === clean(b).toLowerCase();

/** The ORCID hit to use without asking: null = none found, undefined = several fit, the user chooses. */
export function pickCandidate(candidates, family, given) {
    if (!candidates.length) return null;
    if (candidates.length === 1) return candidates[0];
    const exact = candidates.filter((c) => same(c.family_name, family) && same(c.given_names, given));
    return exact.length === 1 ? exact[0] : undefined;
}

/** The stored string for a chosen hit (null = no ORCID); ORCID's spelling of the names wins. */
export const authorFromCandidate = (candidate, family, given) => composeAuthor([
    candidate?.family_name || family, candidate?.given_names || given, candidate?.orcid_id || '',
]);
