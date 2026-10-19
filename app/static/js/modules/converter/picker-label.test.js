import { describe, expect, it } from 'vitest';

import { pickedLabel, syncPickedLabel } from './picker-label.js';

describe('pickedLabel', () => {
    it('shows the picked server path first', () => {
        expect(pickedLabel({ path: '/data/a.lsa', files: [{ name: 'b.csv' }] })).toBe('/data/a.lsa');
    });

    it('shows a single file name, or a count for several files', () => {
        expect(pickedLabel({ files: [{ name: 'b.csv' }] })).toBe('b.csv');
        expect(pickedLabel({ files: [{ name: 'a' }, { name: 'b' }] })).toBe('2 files selected');
    });

    it('falls back to the empty text', () => {
        expect(pickedLabel({})).toBe('No file selected');
        expect(pickedLabel({ empty: 'No folder selected' })).toBe('No folder selected');
    });
});

describe('syncPickedLabel', () => {
    it('writes value and tooltip, and tolerates a missing element', () => {
        const el = { value: '', title: '' };
        syncPickedLabel(el, { path: '/x/y.csv' });
        expect(el.value).toBe('/x/y.csv');
        expect(el.title).toBe('/x/y.csv');
        expect(() => syncPickedLabel(null, { path: 'a' })).not.toThrow();
    });
});
