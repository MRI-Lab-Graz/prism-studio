import { describe, expect, it } from 'vitest';

import { addChip, normalizeChipText, removeChip } from './chip-list.js';

describe('normalizeChipText', () => {
    it('trims and collapses whitespace', () => {
        expect(normalizeChipText('  stimulus   valence ')).toBe('stimulus valence');
        expect(normalizeChipText(null)).toBe('');
    });
});

describe('addChip', () => {
    it('appends a new entry in order', () => {
        expect(addChip(['age'], ' sex ')).toEqual(['age', 'sex']);
    });
    it('ignores empty text', () => {
        expect(addChip(['age'], '   ')).toEqual(['age']);
    });
    it('ignores a duplicate, whatever its case, and keeps the first spelling', () => {
        expect(addChip(['Age'], 'age')).toEqual(['Age']);
    });
    it('never changes the list it was given', () => {
        const before = ['age'];
        addChip(before, 'sex');
        expect(before).toEqual(['age']);
    });
});

describe('removeChip', () => {
    it('removes exactly that entry', () => {
        expect(removeChip(['age', 'sex'], 'age')).toEqual(['sex']);
    });
    it('leaves the list alone when the entry is not there', () => {
        expect(removeChip(['age'], 'iq')).toEqual(['age']);
    });
});
