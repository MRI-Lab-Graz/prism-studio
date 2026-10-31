import { describe, expect, it } from 'vitest';

import { authorFromCandidate, composeAuthor, orcidId, parseAuthor, pickCandidate } from './author-entry.js';

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
