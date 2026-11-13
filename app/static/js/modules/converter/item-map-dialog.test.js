import { describe, expect, it, vi } from 'vitest';

import { choicesToSend, columnsFor, createItemMapDialog, unmappedItems, unusedColumns } from './item-map-dialog.js';

describe('item map dialog rules', () => {
    const rows = [
        { item: 'ADS01', column: 'A01', why: 'number' },
        { item: 'ADS02', column: null, why: 'none' },
    ];
    const columns = ['id', 'A01', 'A02'];

    it('offers an item its own column plus every column no other row uses', () => {
        expect(columnsFor('ADS02', rows, columns)).toEqual(['id', 'A02']);
        expect(columnsFor('ADS01', rows, columns)).toEqual(['id', 'A01', 'A02']);
    });

    it('lists unused columns, the choices to send and the unmapped items', () => {
        expect(unusedColumns(rows, columns)).toEqual(['id', 'A02']);
        expect(choicesToSend(rows)).toEqual({ ADS01: 'A01', ADS02: '' });
        expect(unmappedItems(rows)).toEqual(['ADS02']);
    });
});

describe('item map dialog open', () => {
    it('a second open() while the dialog is open does nothing and keeps the first one pending', async () => {
        const stub = () => ({
            addEventListener() {}, replaceChildren() {}, append() {}, closest: () => null,
            classList: { toggle() {} }, setAttribute() {},
        });
        const root = { querySelector: stub, addEventListener() {} };
        const show = vi.fn();
        vi.stubGlobal('window', { bootstrap: { Modal: { getOrCreateInstance: () => ({ show, hide() {} }) } } });
        vi.stubGlobal('Option', class { constructor(text, value) { this.text = text; this.value = value; } });
        const post = vi.fn(async (url, data) => (data.get('task')
            ? { task: 'ads', rows: [], columns: [] }
            : { tasks: ['ads'] }));
        const dialog = createItemMapDialog({ root, post });
        const first = dialog.open('file', '/p');
        await vi.waitFor(() => expect(show).toHaveBeenCalledTimes(1));
        expect(await dialog.open('file', '/p')).toBeNull();
        expect(show).toHaveBeenCalledTimes(1);
        expect(post).toHaveBeenCalledTimes(2);
        void first;
        vi.unstubAllGlobals();
    });
});
