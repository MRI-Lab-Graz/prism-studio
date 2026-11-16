import { describe, expect, it } from 'vitest';

import { authorFromCandidate, composeAuthor, createOrcidRuns, lookupMissingOrcids, mergeOrcids, orcidId, parseAuthor, pickCandidate } from './author-entry.js';

describe('orcidId', () => {
    it('takes the bare id from an id or a URL, empty when invalid', () => {
        expect(orcidId('https://orcid.org/0000-0001-2345-678X')).toBe('0000-0001-2345-678X');
        expect(orcidId(' 0000-0001-2345-6789 ')).toBe('0000-0001-2345-6789');
        expect(orcidId('12345')).toBe('');
    });
});

describe('composeAuthor', () => {
    it('always writes Family, Given (ORCID)', () => {
        expect(composeAuthor(['Beck', 'Aaron T.', ''])).toBe('Beck, Aaron T.');
        expect(composeAuthor(['Beck', 'Aaron T.', 'https://orcid.org/0000-0001-2345-6789'])).toBe(
            'Beck, Aaron T. (0000-0001-2345-6789)',
        );
    });
    it('is incomplete without both names or with a bad ORCID', () => {
        expect(composeAuthor(['Beck', '', ''])).toBe('');
        expect(composeAuthor(['', 'Aaron', ''])).toBe('');
        expect(composeAuthor(['Beck', 'Aaron', 'nope'])).toBe('');
    });
});

describe('parseAuthor', () => {
    it('splits a stored entry, null when it is not in the fixed format', () => {
        expect(parseAuthor('Beck, Aaron T. (0000-0001-2345-6789)')).toEqual(['Beck', 'Aaron T.', '0000-0001-2345-6789']);
        expect(parseAuthor('Beck, Aaron')).toEqual(['Beck', 'Aaron', '']);
        expect(parseAuthor('Aaron Beck')).toBeNull();
    });
});

describe('pickCandidate', () => {
    const c = (given_names, family_name, orcid_id) => ({ given_names, family_name, orcid_id });
    it('nothing found: no ORCID, the author is added as typed', () => {
        expect(pickCandidate([], 'Beck', 'Aaron')).toBeNull();
    });
    it('one hit, or exactly one exact name match: taken without asking', () => {
        const one = c('Aaron T.', 'Beck', '0000-0001-2345-6789');
        expect(pickCandidate([one], 'Beck', 'Aaron')).toBe(one);
        const exact = c('Aaron', 'Beck', '0000-0001-2345-6789');
        expect(pickCandidate([c('Aaron T.', 'Beck', '0000-0002-0000-0001'), exact], 'beck', 'AARON')).toBe(exact);
    });
    it('several that fit: undefined, the user chooses', () => {
        const list = [c('Aaron', 'Beck', '0000-0001-0000-0001'), c('Aaron', 'Beck', '0000-0001-0000-0002')];
        expect(pickCandidate(list, 'Beck', 'Aaron')).toBeUndefined();
    });
});

describe('authorFromCandidate', () => {
    it('uses the names ORCID has, the typed ones where it has none', () => {
        expect(authorFromCandidate({ given_names: 'Aaron T.', family_name: 'Beck', orcid_id: '0000-0001-2345-6789' }, 'B', 'A'))
            .toBe('Beck, Aaron T. (0000-0001-2345-6789)');
        expect(authorFromCandidate({ orcid_id: '0000-0001-2345-6789' }, 'Beck', 'Aaron')).toBe('Beck, Aaron (0000-0001-2345-6789)');
        expect(authorFromCandidate(null, 'Beck', 'Aaron')).toBe('Beck, Aaron');
    });
});

const ORCID_A = '0000-0002-0000-0001';
const found = (family, given) => `${family}, ${given} (${ORCID_A})`;

describe('lookupMissingOrcids', () => {
    it('asks one author at a time, only those without an ORCID, and reports what it found', async () => {
        const authors = ['Stephan, E.', 'Beck, Aaron (0000-0001-2345-6789)', 'no format', 'Fäth, M.'];
        let running = 0;
        const asked = [];
        const lookup = async (family, given) => {
            expect(++running).toBe(1); // never two at once
            asked.push(`${family}|${given}`);
            await Promise.resolve();
            running--;
            return family === 'Fäth' ? 'Fäth, M.' : found(family, given); // no ORCID found: the plain name comes back
        };
        const progress = [];
        const out = await lookupMissingOrcids(authors, lookup, { onProgress: (done, total, text) => progress.push([done, total, text]) });
        expect(asked).toEqual(['Stephan|E.', 'Fäth|M.']);
        expect([...out.found]).toEqual([['Stephan, E.', found('Stephan', 'E.')]]);
        expect(out.aborted).toBe(false);
        expect(progress).toEqual([[0, 2, 'Stephan, E.'], [1, 2, 'Fäth, M.'], [2, 2, '']]);
    });

    it('stops after the current author when asked to', async () => {
        let stop = false;
        const lookup = async (family, given) => { stop = true; return found(family, given); };
        const out = await lookupMissingOrcids(['A, a', 'B, b'], lookup, { shouldStop: () => stop });
        expect([...out.found.keys()]).toEqual(['A, a']);
        expect(out.aborted).toBe(false);
    });

    it('aborts, and reports nothing, when the run is no longer valid after an await', async () => {
        let valid = true;
        const lookup = async (family, given) => { valid = false; return found(family, given); };
        const out = await lookupMissingOrcids(['A, a', 'B, b'], lookup, { isValid: () => valid });
        expect(out.aborted).toBe(true);
        expect(out.found.size).toBe(0);
    });

    it('does not start when the run is already invalid', async () => {
        const lookup = async () => { throw new Error('must not be asked'); };
        expect((await lookupMissingOrcids(['A, a'], lookup, { isValid: () => false })).aborted).toBe(true);
    });
});

describe('mergeOrcids', () => {
    it('sets the ORCID only on authors that still exist unchanged and still have none', () => {
        const foundMap = new Map([['A, a', found('A', 'a')], ['B, b', found('B', 'b')], ['C, c', found('C', 'c')]]);
        const current = ['A, a', 'B, b (0000-0001-2345-6789)', 'C, c edited', 'D, d'];
        expect(mergeOrcids(current, foundMap)).toEqual([found('A', 'a'), current[1], 'C, c edited', 'D, d']);
    });
});

describe('createOrcidRuns', () => {
    const tpl = {};
    it('allows one run at a time', () => {
        const runs = createOrcidRuns();
        const run = runs.begin(tpl);
        expect(runs.active).toBe(true);
        expect(runs.begin(tpl)).toBeNull();
        run.end();
        expect(runs.active).toBe(false);
        expect(runs.begin(tpl)).not.toBeNull();
    });
    it('is valid only for the same template while connected, and not once aborted or ended', () => {
        const runs = createOrcidRuns();
        const run = runs.begin(tpl);
        expect(run.isValid(tpl, () => true)).toBe(true);
        expect(run.isValid({}, () => true)).toBe(false); // another template was loaded
        expect(run.isValid(tpl, () => false)).toBe(false); // the row was re-rendered away
        run.abort();
        expect(run.isValid(tpl, () => true)).toBe(false);
        run.end();
        expect(runs.begin(tpl).isValid(tpl, () => true)).toBe(true);
    });
    it('abort and stop skip a pending pick-one dialog', () => {
        const runs = createOrcidRuns();
        for (const end of ['abort', 'stop']) {
            const run = runs.begin(tpl);
            let skipped = 0;
            run.cancelPick = () => { skipped++; };
            run[end]();
            expect(skipped).toBe(1);
            run.end();
        }
    });
    it('stop() on the registry stops the current run', () => {
        const runs = createOrcidRuns();
        const run = runs.begin(tpl);
        runs.stop();
        expect(run.stopped).toBe(true);
    });
});
