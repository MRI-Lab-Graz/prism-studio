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

/** Look the ORCID up for each author that has none, one at a time (the ORCID API is shared: no parallel bursts).
 *  `lookup(family, given)` gives the stored string (it may ask the user). Returns { found, aborted }: `found` maps an
 *  author's original string to the string with its ORCID (only real hits); `aborted` = the run became invalid
 *  (`isValid()` false: another template, re-rendered row, ...), then nothing may be written. `shouldStop()` ends the run
 *  after the current author, keeping what was found. `onProgress(done, total, current)` runs before each author and at the end. */
export async function lookupMissingOrcids(authors, lookup, { isValid = () => true, shouldStop = () => false, onProgress = () => {} } = {}) {
    const todo = authors.map((a) => [a, parseAuthor(a)]).filter(([, p]) => p && !p[2]);
    const hits = new Map();
    for (const [n, [original, [family, given]]] of todo.entries()) {
        if (!isValid()) return { found: new Map(), aborted: true };
        if (shouldStop()) break;
        onProgress(n, todo.length, original);
        const result = await lookup(family, given);
        if (!isValid()) return { found: new Map(), aborted: true };
        if (parseAuthor(result)?.[2]) hits.set(original, result);
    }
    onProgress(todo.length, todo.length, '');
    return { found: hits, aborted: false };
}

/** Apply found ORCIDs to the CURRENT author list: only authors that still exist unchanged and still have no ORCID. */
export function mergeOrcids(current, found) {
    return current.map((a) => (found.has(a) && !parseAuthor(a)?.[2] ? found.get(a) : a));
}

/** The one ORCID run of the editor: a second begin() while one is active gives null. */
export function createOrcidRuns() {
    let current = null;
    return {
        get active() { return current !== null; },
        stop() { current?.stop(); },
        begin(template) {
            if (current) return null;
            const run = {
                template, stopped: false, aborted: false, cancelPick: null,
                stop() { run.stopped = true; run.cancelPick?.(); },
                abort() { run.aborted = true; run.cancelPick?.(); },
                isValid: (liveTemplate, connected) => current === run && !run.aborted && liveTemplate === run.template && connected(),
                end() { if (current === run) current = null; },
            };
            current = run;
            return run;
        },
    };
}
