import { describe, expect, it } from 'vitest';

import { duplicateIndexes, normalizeDoi, rowAction } from './doi-list.js';

describe('normalizeDoi', () => {
    it('strips the resolver prefix and doi: label', () => {
        expect(normalizeDoi(' https://doi.org/10.1/abc ')).toBe('10.1/abc');
        expect(normalizeDoi('doi: 10.1/abc')).toBe('10.1/abc');
    });
});

describe('duplicateIndexes', () => {
    it('flags later repeats, ignoring prefix, case and blanks', () => {
        const dupes = duplicateIndexes(['10.1/ABC', '', 'https://doi.org/10.1/abc', '10.2/x', '10.1/abc']);
        expect([...dupes]).toEqual([2, 4]);
    });

    it('is empty when all DOIs differ', () => {
        expect(duplicateIndexes(['10.1/a', '10.1/b']).size).toBe(0);
    });
});

describe('rowAction', () => {
    it('offers search for an unchecked value, delete once checked, nothing for an empty row', () => {
        expect(rowAction({ value: '10.1/a', checked: false })).toBe('search');
        expect(rowAction({ value: '10.1/a', checked: true })).toBe('remove');
        expect(rowAction({ value: '  ', checked: false })).toBe('none');
    });
});
